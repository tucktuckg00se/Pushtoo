"""Tracks sounding notes by the pitch actually sent, so releases and Panic never strand notes.

A pad's note-off must go to the destination, channel and pitch its note-on used,
even if the layout, octave, key or output changed while it was held. Pure logic:
methods return (destination, raw MIDI message) pairs for the router to send.
"""

from collections import defaultdict
from collections.abc import Hashable, Iterable

NOTE_ON, NOTE_OFF, CONTROL_CHANGE = 0x90, 0x80, 0xB0
CC_RESET_ALL_CONTROLLERS, CC_ALL_NOTES_OFF = 121, 123

Message = list[int]
Routed = tuple[str, Message]
NoteKey = tuple[str, int, int]  # destination, channel, note


class SoundingNotes:
    def __init__(self) -> None:
        self._by_source: dict[Hashable, NoteKey] = {}
        # Several sources can share a key; send note-off only when the last releases.
        self._counts: dict[NoteKey, int] = defaultdict(int)

    def press(
        self, source: Hashable, destination: str, channel: int, note: int, velocity: int
    ) -> list[Routed]:
        messages = self.release(source)  # a source plays at most one note
        key = (destination, channel, note)
        self._by_source[source] = key
        self._counts[key] += 1
        messages.append((destination, [NOTE_ON | channel, note, velocity]))
        return messages

    def release(self, source: Hashable) -> list[Routed]:
        key = self._by_source.pop(source, None)
        if key is None:
            return []
        self._counts[key] -= 1
        if self._counts[key]:
            return []
        del self._counts[key]
        destination, channel, note = key
        return [(destination, [NOTE_OFF | channel, note, 0])]

    def held_by(self, source: Hashable) -> NoteKey | None:
        return self._by_source.get(source)

    def notes_on(self, destination: str, channel: int) -> set[int]:
        return {n for d, c, n in self._counts if d == destination and c == channel}

    def release_all(self) -> list[Routed]:
        messages = [(d, [NOTE_OFF | c, n, 0]) for d, c, n in sorted(self._counts)]
        self._by_source.clear()
        self._counts.clear()
        return messages


def panic_messages(sounding: SoundingNotes, destinations: Iterable[str]) -> list[Routed]:
    """Explicit note-offs for everything tracked, then All Notes Off and Reset on
    every channel of every destination."""
    messages = sounding.release_all()
    for destination in destinations:
        for channel in range(16):
            messages.append((destination, [CONTROL_CHANGE | channel, CC_ALL_NOTES_OFF, 0]))
            messages.append((destination, [CONTROL_CHANGE | channel, CC_RESET_ALL_CONTROLLERS, 0]))
    return messages
