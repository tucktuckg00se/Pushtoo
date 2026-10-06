"""MIDI output routing (PRD F1, F17).

"Pushtoo Out" is a virtual port that any DAW can read (see virtual.py). Any layout can
instead send straight to a hardware MIDI port, so a USB-MIDI rig works without a DAW in
between.
"""

import logging
import re
import threading
from collections.abc import Callable
from typing import Protocol

from pushtoo.midi.notes import NOTE_ON, Message, Routed, SoundingNotes, panic_messages
from pushtoo.midi.virtual import NO_TAG, Sequencer

CLIENT_NAME = "Pushtoo"
OUT_PORT = "Pushtoo Out"
IN_PORT = "Pushtoo In"
POLY_AFTERTOUCH, CONTROL_CHANGE, CHANNEL_PRESSURE, PITCH_BEND = 0xA0, 0xB0, 0xD0, 0xE0

# Ports that are never useful destinations: our own, the Push itself, system plumbing,
# and unnamed rtmidi clients (push2-python's own connection to the Push shows up as one).
_HIDDEN_PORT_PREFIXES = (
    "Pushtoo",
    "pushtoo",
    "Ableton Push",
    "Midi Through",
    "PipeWire",
    "RtMidiIn Client",
    "RtMidiOut Client",
)
_ALSA_ADDRESS = re.compile(r"\s+\d+:\d+$")

log = logging.getLogger(__name__)


class Output(Protocol):
    def send_message(self, message: Message) -> None: ...
    def send_at(self, message: Message, at: float, tag: int = NO_TAG) -> None: ...
    def cancel(self, tag: int | None = None) -> None: ...
    def close_port(self) -> None: ...


def port_display_name(alsa_name: str) -> str:
    """'USB MIDI:USB MIDI MIDI 1 24:0' -> 'USB MIDI:USB MIDI MIDI 1'.

    ALSA client numbers change when a device is replugged, so destinations are
    identified without them.
    """
    return _ALSA_ADDRESS.sub("", alsa_name)


def short_port_name(destination: str) -> str:
    """'USB MIDI:USB MIDI MIDI 1' -> 'USB MIDI MIDI 1' for display; ALSA port names
    usually repeat their client name."""
    _, _, port = destination.partition(":")
    return port or destination


class MidiRouter:
    """Sends notes and controller messages to named destinations, tracking every note.

    Pad callbacks arrive on rtmidi's input thread; the lock keeps note tracking
    consistent with Panic and port changes from other threads.
    """

    def __init__(
        self,
        virtual_out: Output | None = None,
        list_ports: Callable[[], list[str]] | None = None,
        open_port: Callable[[str], Output | None] | None = None,
    ) -> None:
        self.sequencer: Sequencer | None = None
        if virtual_out is None:
            # One ALSA client for our ports and every hardware destination, so all of
            # them get queue timing (see virtual.py).
            self.sequencer = Sequencer(CLIENT_NAME)
            virtual_out = self.sequencer.create_output(OUT_PORT)
            list_ports = list_ports or self.sequencer.destinations
            open_port = open_port or self.sequencer.open_destination
        self._outputs: dict[str, Output] = {OUT_PORT: virtual_out}
        self._list_ports = list_ports or (lambda: [])
        self._open_port = open_port or (lambda name: None)
        self._destinations = [OUT_PORT]
        self._missing_logged: set[str] = set()
        self.notes = SoundingNotes()
        self._lock = threading.Lock()

    # Destinations

    def destinations(self) -> list[str]:
        """'Pushtoo Out' first, then hardware ports as of the last refresh.

        Cached because screens read it on every refresh; call refresh_destinations()
        when the user is about to pick one.
        """
        return self._destinations

    def refresh_destinations(self) -> list[str]:
        names = [port_display_name(p) for p in self._list_ports()]
        hardware = sorted({n for n in names if not n.startswith(_HIDDEN_PORT_PREFIXES)})
        self._destinations = [OUT_PORT, *hardware]
        self._forget_missing(self._destinations)
        return self._destinations

    def _output(self, destination: str) -> Output | None:
        output = self._outputs.get(destination)
        if output is None:
            output = self._open_port(destination)
            if output is None:
                if destination not in self._missing_logged:
                    log.warning("MIDI destination %r is not available", destination)
                    self._missing_logged.add(destination)
                return None
            self._outputs[destination] = output
            self._missing_logged.discard(destination)
        return output

    def _send(self, messages: list[Routed]) -> None:
        for destination, message in messages:
            output = self._output(destination)
            if output is not None:
                output.send_message(message)

    def _forget_missing(self, present: list[str]) -> None:
        """Close hardware ports that have disappeared so they reopen cleanly later."""
        with self._lock:
            for name in [n for n in self._outputs if n != OUT_PORT and n not in present]:
                self._outputs.pop(name).close_port()

    # Messages

    def note_on(
        self,
        source,
        destination: str,
        channel: int,
        note: int,
        velocity: int,
        retrigger: bool = True,
    ) -> None:
        with self._lock:
            self._send(self.notes.press(source, destination, channel, note, velocity, retrigger))

    def note_on_at(
        self,
        source,
        destination: str,
        channel: int,
        note: int,
        velocity: int,
        at: float,
        tag: int,
        retrigger: bool = True,
    ) -> None:
        """A tracked note that starts at `at`: released like any other, and if it's
        released before it starts, cancel(tag) takes the note-on back first."""
        with self._lock:
            messages = self.notes.press(source, destination, channel, note, velocity, retrigger)
            starts = [m for m in messages if m[1][0] & 0xF0 == NOTE_ON]
            self._send([m for m in messages if m not in starts])  # endings go at once
            output = self._output(destination)
            if output is not None:
                for _, note_on in starts:  # none if the note was already sounding
                    output.send_at(note_on, at, tag)

    def note_off(self, source) -> None:
        with self._lock:
            self._send(self.notes.release(source))

    def poly_aftertouch(self, source, pressure: int) -> None:
        with self._lock:
            held = self.notes.held_by(source)
            if held is not None:
                destination, channel, note = held
                self._send([(destination, [POLY_AFTERTOUCH | channel, note, pressure])])

    def channel_pressure(self, destination: str, channel: int, pressure: int) -> None:
        with self._lock:
            self._send([(destination, [CHANNEL_PRESSURE | channel, pressure])])

    def control_change(self, destination: str, channel: int, control: int, value: int) -> None:
        with self._lock:
            self._send([(destination, [CONTROL_CHANGE | channel, control, value])])

    def pitch_bend(self, destination: str, channel: int, value: int) -> None:
        """value is -8192..8191, as push2-python reports the touch strip."""
        raw = max(0, min(16383, value + 8192))
        with self._lock:
            self._send([(destination, [PITCH_BEND | channel, raw & 0x7F, raw >> 7])])

    def schedule(self, destination: str, message: Message, at: float, tag: int = NO_TAG) -> None:
        """Send at monotonic time `at` (rhythm). Not note-tracked: the caller pairs every
        note-on with a note-off, and Panic takes back what's still queued."""
        with self._lock:
            output = self._output(destination)
            if output is not None:
                output.send_at(message, at, tag)

    def cancel(self, tag: int | None = None) -> None:
        """Take back queued events with `tag`, or all tagged ones."""
        with self._lock:
            for output in self._outputs.values():
                output.cancel(tag)

    def panic(self) -> None:
        self.cancel()  # nothing queued may play after Panic
        with self._lock:
            self._send(panic_messages(self.notes, list(self._outputs)))

    def notes_on(self, destination: str, channel: int) -> set[int]:
        with self._lock:
            return self.notes.notes_on(destination, channel)

    def sounding(self) -> bool:
        """Is any note Pushtoo played still held on?"""
        with self._lock:
            return self.notes.sounding()

    def close(self) -> None:
        self.panic()
        with self._lock:
            for output in self._outputs.values():
                output.close_port()
        if self.sequencer is not None:
            self.sequencer.close()
