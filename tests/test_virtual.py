"""Pushtoo's own ports on a real ALSA sequencer; skipped where there is none (CI)."""

import os

import pytest
from alsa_midi import NoteOnEvent, PortCaps, SequencerClient

from pushtoo.midi.virtual import PORT_TYPE, VirtualPorts

pytestmark = pytest.mark.skipif(
    not os.access("/dev/snd/seq", os.R_OK | os.W_OK), reason="no ALSA sequencer"
)


def test_ports_are_typed_so_pipewire_marks_them_physical():
    ports = VirtualPorts("Pushtoo Test", "Pushtoo Test Out", "Pushtoo Test In")
    try:
        info = ports.client.get_port_info(ports.out_port)
        assert info.type == PORT_TYPE
    finally:
        ports.close_port()


def test_notes_reach_a_subscriber():
    ports = VirtualPorts("Pushtoo Test", "Pushtoo Test Out", "Pushtoo Test In")
    listener = SequencerClient("Pushtoo Test Listener")
    try:
        inbox = listener.create_port("inbox", PortCaps.WRITE | PortCaps.SUBS_WRITE)
        inbox.connect_from(ports.out_port)
        ports.send_message([0x91, 60, 100])
        # PipeWire subscribes to new ports too; skip its announcements.
        event = listener.event_input(timeout=1)
        while event is not None and not isinstance(event, NoteOnEvent):
            event = listener.event_input(timeout=1)
        assert event is not None
        assert (event.channel, event.note, event.velocity) == (1, 60, 100)
    finally:
        listener.close()
        ports.close_port()
