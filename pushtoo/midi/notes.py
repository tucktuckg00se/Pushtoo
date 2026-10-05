"""Tracks sounding notes by the pitch actually sent, so releases and Panic never strand notes.

A pad's note-off must go to the pitch and channel its note-on used, even if the layout,
octave or key changed while it was held. Pure logic: methods return raw MIDI messages
for the router to send.
"""

from collections import defaultdict
from collections.abc import Hashable

NOTE_ON, NOTE_OFF, CONTROL_CHANGE = 0x90, 0x80, 0xB0
CC_RESET_ALL_CONTROLLERS, CC_ALL_NOTES_OFF = 121, 123

Message = list[int]


class SoundingNotes:
    def __init__(self) -> None:
        self._by_source: dict[Hashable, list[tuple[int, int]]] = {}
        # Several sources can share a (channel, note); send note-off only when the last releases.
        self._counts: dict[tuple[int, int], int] = defaultdict(int)

    def press(self, source: Hashable, channel: int, note: int, velocity: int) -> list[Message]:
        messages = self.release(source)  # a source plays at most one note
        self._by_source[source] = [(channel, note)]
        self._counts[(channel, note)] += 1
        messages.append([NOTE_ON | channel, note, velocity])
        return messages

    def release(self, source: Hashable) -> list[Message]:
        messages = []
        for channel, note in self._by_source.pop(source, []):
            self._counts[(channel, note)] -= 1
            if self._counts[(channel, note)] == 0:
                del self._counts[(channel, note)]
                messages.append([NOTE_OFF | channel, note, 0])
        return messages

    def note_for(self, source: Hashable) -> tuple[int, int] | None:
        """The (channel, note) a source is holding, if any."""
        held = self._by_source.get(source)
        return held[0] if held else None

    def is_sounding(self, channel: int, note: int) -> bool:
        return (channel, note) in self._counts

    def sounding_notes(self) -> set[int]:
        return {note for _, note in self._counts}

    def release_all(self) -> list[Message]:
        messages = [[NOTE_OFF | channel, note, 0] for channel, note in sorted(self._counts)]
        self._by_source.clear()
        self._counts.clear()
        return messages


def panic_messages(sounding: SoundingNotes) -> list[Message]:
    """Explicit note-offs for everything tracked, then All Notes Off and Reset on all channels."""
    messages = sounding.release_all()
    for channel in range(16):
        messages.append([CONTROL_CHANGE | channel, CC_ALL_NOTES_OFF, 0])
        messages.append([CONTROL_CHANGE | channel, CC_RESET_ALL_CONTROLLERS, 0])
    return messages
