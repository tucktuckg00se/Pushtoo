"""Pushtoo's ALSA client on a real sequencer; skipped where there is none (CI)."""

import os
import time

import pytest
from alsa_midi import NoteOffEvent, NoteOnEvent, PortCaps, SequencerClient

from pushtoo.midi.virtual import PORT_TYPE, Sequencer

pytestmark = pytest.mark.skipif(
    not os.access("/dev/snd/seq", os.R_OK | os.W_OK), reason="no ALSA sequencer"
)


@pytest.fixture
def wired():
    """A Sequencer output and a listener subscribed to it."""
    sequencer = Sequencer("Pushtoo Test")
    output = sequencer.create_output("Pushtoo Test Out")
    listener = SequencerClient("Pushtoo Test Listener")
    inbox = listener.create_port("inbox", PortCaps.WRITE | PortCaps.SUBS_WRITE)
    inbox.connect_from(output.port)

    def received(timeout=0.3):
        """Note events until the line goes quiet, as (seconds, kind, note)."""
        start, events = time.monotonic(), []
        while (event := listener.event_input(timeout=timeout)) is not None:
            if isinstance(event, NoteOnEvent | NoteOffEvent):  # PipeWire announces too
                kind = "on" if isinstance(event, NoteOnEvent) else "off"
                events.append((time.monotonic() - start, kind, event.note))
        return events

    yield sequencer, output, received
    listener.close()
    sequencer.close()


def test_ports_are_typed_so_pipewire_marks_them_physical(wired):
    sequencer, output, _ = wired
    assert sequencer.client.get_port_info(output.port).type == PORT_TYPE


def test_notes_reach_a_subscriber(wired):
    _, output, received = wired
    output.send_message([0x91, 60, 100])
    assert [(kind, note) for _, kind, note in received()] == [("on", 60)]


def test_scheduled_notes_arrive_on_time_and_tags_take_them_back(wired):
    _, output, received = wired
    now = time.monotonic()
    output.send_at([0x90, 61, 100], now + 0.1, tag=5)
    output.send_at([0x80, 61, 0], now + 0.15)
    output.send_at([0x90, 62, 100], now + 0.2, tag=6)
    output.send_at([0x80, 62, 0], now + 0.25)
    output.cancel(6)  # the note-on goes; its note-off stays, so nothing hangs
    events = received(0.4)
    assert [(kind, note) for _, kind, note in events] == [("on", 61), ("off", 61), ("off", 62)]
    assert 0.08 < events[0][0] < 0.13
