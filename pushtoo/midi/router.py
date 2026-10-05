"""Virtual MIDI ports and note routing (PRD F1)."""

import threading

import rtmidi

from pushtoo.midi.notes import Message, SoundingNotes, panic_messages

CLIENT_NAME = "Pushtoo"
OUT_PORT = "Pushtoo Out"
IN_PORT = "Pushtoo In"
POLY_AFTERTOUCH = 0xA0


class MidiRouter:
    """Owns "Pushtoo Out" and "Pushtoo In" and tracks every note it sends.

    Pad callbacks arrive on rtmidi's input thread; the lock keeps note tracking
    consistent if anything else (Panic from another thread, a clock) sends too.
    """

    def __init__(self, output: rtmidi.MidiOut | None = None) -> None:
        if output is None:
            output = rtmidi.MidiOut(rtmidi.API_LINUX_ALSA, name=CLIENT_NAME)
            output.open_virtual_port(OUT_PORT)
            self.feedback = rtmidi.MidiIn(rtmidi.API_LINUX_ALSA, name=CLIENT_NAME)
            self.feedback.open_virtual_port(IN_PORT)
        self.output = output
        self.notes = SoundingNotes()
        self._lock = threading.Lock()

    def _send(self, messages: list[Message]) -> None:
        for message in messages:
            self.output.send_message(message)

    def note_on(self, source, channel: int, note: int, velocity: int) -> None:
        with self._lock:
            self._send(self.notes.press(source, channel, note, velocity))

    def note_off(self, source) -> None:
        with self._lock:
            self._send(self.notes.release(source))

    def poly_aftertouch(self, source, pressure: int) -> None:
        with self._lock:
            target = self.notes.note_for(source)
            if target is not None:
                channel, note = target
                self._send([[POLY_AFTERTOUCH | channel, note, pressure]])

    def panic(self) -> None:
        with self._lock:
            self._send(panic_messages(self.notes))

    def sounding_notes(self) -> set[int]:
        with self._lock:
            return self.notes.sounding_notes()

    def close(self) -> None:
        self.panic()
        self.output.close_port()
