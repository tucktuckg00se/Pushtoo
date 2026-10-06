"""Pushtoo's ALSA sequencer client: its own ports, hardware destinations, and timing.

Ports. rtmidi's virtual ports are typed as application ports, and PipeWire only marks
ALSA ports physical when their type says they lead to other devices (HARDWARE, PORT or
SPECIFIC). DAWs on JACK or PipeWire, REAPER among them, list only physical MIDI ports,
so an rtmidi port never shows up in their settings. Pushtoo relays a hardware
controller, so "Pushtoo Out" and "Pushtoo In" are typed PORT ("may connect to other
devices") as well.

Timing. Every output can send now, or at a moment ahead of time on an ALSA queue,
which the kernel delivers on time whatever Python is doing (tools/clock/jitter.py:
p99 0.42 ms under load, where sleeping until each deadline reached 23 ms). Queued
events carry a tag so a stopped rhythm can take back what it scheduled.

alsa-lib handles aren't thread-safe, so output shares one locked client and input
(clock from a DAW) reads on a second client of its own.
"""

import threading
import time
from collections.abc import Callable

from alsa_midi import (
    ALSAError,
    ClockEvent,
    ContinueEvent,
    MidiBytesEvent,
    PortCaps,
    PortType,
    RealTime,
    RemoveCondition,
    SequencerClient,
    StartEvent,
    StopEvent,
)

from pushtoo.midi.notes import Message

PORT_TYPE = PortType.MIDI_GENERIC | PortType.APPLICATION | PortType.PORT
NO_TAG = 0  # events that are never taken back, like note-offs


class Sequencer:
    def __init__(self, client_name: str) -> None:
        self.client_name = client_name
        self.client = SequencerClient(client_name)
        self.queue = self.client.create_queue(client_name)
        self.queue.start()
        self.client.drain_output()
        self._t0 = time.monotonic()  # monotonic time at queue time zero
        self._lock = threading.Lock()
        self._reader: SequencerClient | None = None
        self._reading = threading.Event()

    def create_output(self, name: str) -> "SequencerOutput":
        port = self.client.create_port(name, PortCaps.READ | PortCaps.SUBS_READ, PORT_TYPE)
        return SequencerOutput(self, port)

    # Hardware destinations

    def destinations(self) -> list[str]:
        """Every MIDI output on the system as "client:port", the same names rtmidi uses."""
        with self._lock:
            ports = self.client.list_ports(output=True)
        return [f"{p.client_name}:{p.name}" for p in ports]

    def open_destination(self, display_name: str) -> "SequencerOutput | None":
        with self._lock:
            match = next(
                (
                    p
                    for p in self.client.list_ports(output=True)
                    if f"{p.client_name}:{p.name}" == display_name
                ),
                None,
            )
            if match is None:
                return None
            # An ordinary application port, so it doesn't show up in DAWs as a device.
            port = self.client.create_port(
                f"{self.client_name} to {display_name}"[:63], PortCaps.READ
            )
            port.connect_to(match)
        return SequencerOutput(self, port, owned=True)

    # Sending

    def send(self, port, message: Message, at: float | None = None, tag: int = NO_TAG) -> None:
        """Send now, or at monotonic time `at` (past times go out at once)."""
        with self._lock:
            if at is None:
                self.client.event_output(MidiBytesEvent(message), port=port)
            else:
                stamp = RealTime(max(0.0, at - self._t0))
                event = MidiBytesEvent(message, time=stamp, tag=tag)
                self.client.event_output(event, queue=self.queue, port=port)
            # Drain at once: alsa-midi buffers even "direct" output until drained.
            self.client.drain_output()

    def cancel(self, tag: int | None = None) -> None:
        """Take back queued events: those with `tag`, or every tagged one if None.
        Untagged events (note-offs) always stay, so nothing is left hanging."""
        with self._lock:
            if tag is None:
                self.client.remove_events(RemoveCondition.OUTPUT | RemoveCondition.IGNORE_OFF)
            else:
                self.client.remove_events(
                    RemoveCondition.OUTPUT | RemoveCondition.TAG_MATCH, tag=tag
                )

    # Input

    def read_input(self, name: str, on_message: Callable[[str, float], None]) -> None:
        """Open the input port on a client of its own, and call on_message(kind, now)
        on a reader thread for each "clock", "start", "continue" or "stop" that
        arrives, the messages a leader's MIDI clock is made of."""
        reader = SequencerClient(self.client_name)
        reader.create_port(name, PortCaps.WRITE | PortCaps.SUBS_WRITE, PORT_TYPE)
        self._reader = reader
        kinds = {
            ClockEvent: "clock",
            StartEvent: "start",
            ContinueEvent: "continue",
            StopEvent: "stop",
        }

        def run() -> None:
            while not self._reading.is_set():
                try:
                    event = reader.event_input(timeout=0.2)
                except ALSAError:
                    continue
                kind = kinds.get(type(event))
                if kind is not None:
                    on_message(kind, time.monotonic())

        threading.Thread(target=run, name="pushtoo-midi-in", daemon=True).start()

    def close(self) -> None:
        self._reading.set()
        with self._lock:
            self.client.close()


class SequencerOutput:
    """One output port; satisfies the router's Output protocol."""

    def __init__(self, sequencer: Sequencer, port, owned: bool = False) -> None:
        self.sequencer = sequencer
        self.port = port
        self._owned = owned  # a hardware destination's port, closed with it

    def send_message(self, message: Message) -> None:
        self.sequencer.send(self.port, message)

    def send_at(self, message: Message, at: float, tag: int = NO_TAG) -> None:
        self.sequencer.send(self.port, message, at, tag)

    def cancel(self, tag: int | None = None) -> None:
        self.sequencer.cancel(tag)

    def close_port(self) -> None:
        if self._owned:
            with self.sequencer._lock:
                self.port.close()
