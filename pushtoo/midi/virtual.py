"""Pushtoo's own MIDI ports, "Pushtoo Out" and "Pushtoo In", on one ALSA sequencer client.

rtmidi's virtual ports are typed as application ports, and PipeWire only marks ALSA
ports physical when their type says they lead to other devices (HARDWARE, PORT or
SPECIFIC). DAWs on JACK or PipeWire, REAPER among them, list only physical MIDI ports,
so an rtmidi port never shows up in their settings. Pushtoo relays a hardware
controller, so its ports are typed PORT ("may connect to other devices") as well.
"""

from alsa_midi import MidiBytesEvent, PortCaps, PortType, SequencerClient

from pushtoo.midi.notes import Message

PORT_TYPE = PortType.MIDI_GENERIC | PortType.APPLICATION | PortType.PORT


class VirtualPorts:
    """Satisfies the router's Output protocol for "Pushtoo Out"."""

    def __init__(self, client_name: str, out_name: str, in_name: str) -> None:
        self.client = SequencerClient(client_name)
        self.out_port = self.client.create_port(
            out_name, PortCaps.READ | PortCaps.SUBS_READ, PORT_TYPE
        )
        # For DAW feedback (F7); DAWs see it as an output to send to.
        self.in_port = self.client.create_port(
            in_name, PortCaps.WRITE | PortCaps.SUBS_WRITE, PORT_TYPE
        )

    def send_message(self, message: Message) -> None:
        # Drain at once: alsa-midi buffers even "direct" output until drained.
        self.client.event_output(MidiBytesEvent(message), port=self.out_port)
        self.client.drain_output()

    def close_port(self) -> None:
        self.client.close()
