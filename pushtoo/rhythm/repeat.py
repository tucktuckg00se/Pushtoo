"""Note repeat and arpeggiator (PRD: Rhythm). Pure logic: held pads in, timed notes out.

A held pad sounds the moment it's pressed; after that it plays on the clock's grid.
Every note-on carries its pad's tag and every note-off carries none, so releasing a
pad can take back what it had queued without ever leaving a note hanging.
"""

import random
from collections.abc import Callable, Hashable
from dataclasses import dataclass

from pushtoo.midi.notes import NOTE_OFF, NOTE_ON, Message
from pushtoo.rhythm.arp import PATTERNS, sequence
from pushtoo.rhythm.clock import Clock

# Side buttons top to bottom, as printed on them, and each rate in beats.
RATES = {
    "1/32t": 1 / 12,
    "1/32": 1 / 8,
    "1/16t": 1 / 6,
    "1/16": 1 / 4,
    "1/8t": 1 / 3,
    "1/8": 1 / 2,
    "1/4t": 2 / 3,
    "1/4": 1.0,
}
RATE_NAMES = tuple(RATES)
MODES = ("Repeat", "Arp")
REPEAT_GATE = 50  # percent of a step
FIRST_STEP_GAP = 0.3  # grid steps this soon after a press (in steps) are skipped
CLOCK_TAG = 255  # MIDI clock ticks; pads use 1-254

Scheduled = tuple[float, str, Message, int]  # (time, destination, message, tag)


@dataclass
class Held:
    destination: str
    channel: int
    notes: list[int]
    velocity: int
    pressed_at: float
    order: int
    tag: int
    # Per-note velocities for a hit, from the velocity the pad holds (chord Random).
    vary: Callable[[list[int], int], list[int]] | None = None


class Rhythm:
    def __init__(self) -> None:
        self.on = False
        self.mode = "Repeat"
        self.rate = "1/16"
        self.pattern = PATTERNS[0]
        self.octaves = 1
        self.gate = REPEAT_GATE  # the arp's gate; repeats always use REPEAT_GATE
        self.allow_arp = True  # Drums only repeat
        self.held: dict[Hashable, Held] = {}
        self._order = 0
        self._tag = 0
        self._arp_index = 0
        self._random = random.Random(0)

    @property
    def arp(self) -> bool:
        return self.mode == "Arp" and self.allow_arp

    def _next_tag(self) -> int:
        self._tag = self._tag % (CLOCK_TAG - 1) + 1  # 1..254; 0 means "never take back"
        return self._tag

    def _step_seconds(self, clock: Clock) -> float:
        return RATES[self.rate] * clock.beat_seconds

    # Pads

    def press(
        self,
        key: Hashable,
        destination: str,
        channel: int,
        notes: list[int],
        velocity: int,
        clock: Clock,
        now: float,
        vary: Callable[[list[int], int], list[int]] | None = None,
    ) -> list[Scheduled]:
        """Hold a pad (or a chord); returns its first hit, to send at once."""
        if not self.held:
            self._arp_index = 0
        self._order += 1
        held = Held(
            destination, channel, list(notes), velocity, now, self._order, self._next_tag(), vary
        )
        self.held[key] = held
        if self.arp:
            return self._arp_step(now, clock)
        return self._hit(held, now, self._step_seconds(clock) * REPEAT_GATE / 100)

    def release(self, key: Hashable) -> int | None:
        """Let go of a pad; returns its tag, so the caller can take back its queued
        notes."""
        held = self.held.pop(key, None)
        return held.tag if held else None

    def release_all(self) -> list[int]:
        tags = [h.tag for h in self.held.values()]
        self.held.clear()
        return tags

    def pressure(self, key: Hashable, value: int) -> None:
        """Pad pressure sets the velocity of the repeats that follow."""
        held = self.held.get(key)
        if held is not None and value > 0:
            held.velocity = value

    # The grid

    def events(self, clock: Clock, start: float, end: float) -> list[Scheduled]:
        """Every note for grid steps in [start, end)."""
        if not self.held:
            return []
        step = self._step_seconds(clock)
        found: list[Scheduled] = []
        for _, at in clock.steps(RATES[self.rate], start, end):
            if self.arp:
                if any(at - h.pressed_at >= FIRST_STEP_GAP * step for h in self.held.values()):
                    found += self._arp_step(at, clock)
                continue
            for held in self.held.values():
                if at - held.pressed_at >= FIRST_STEP_GAP * step:
                    found += self._hit(held, at, step * REPEAT_GATE / 100)
        return found

    @staticmethod
    def _hit(held: Held, at: float, length: float) -> list[Scheduled]:
        if held.vary is not None:
            velocities = held.vary(held.notes, held.velocity)
        else:
            velocities = [held.velocity] * len(held.notes)
        on = [
            (at, held.destination, [NOTE_ON | held.channel, n, v], held.tag)
            for n, v in zip(held.notes, velocities, strict=True)
        ]
        off = [
            (at + length, held.destination, [NOTE_OFF | held.channel, n, 0], 0) for n in held.notes
        ]
        return on + off

    def _arp_step(self, at: float, clock: Clock) -> list[Scheduled]:
        by_order = sorted(self.held.values(), key=lambda h: h.order)
        played = [n for h in by_order for n in h.notes]
        notes = sequence(played, self.pattern, self.octaves)
        if not notes:
            return []
        if self.pattern == "Random":
            note = self._random.choice(notes)
        else:
            note = notes[self._arp_index % len(notes)]
        self._arp_index += 1
        # The note belongs to the pad that holds its pitch class (octave copies too).
        owner = next(h for h in reversed(by_order) if any((note - n) % 12 == 0 for n in h.notes))
        length = self._step_seconds(clock) * self.gate / 100
        return self._hit(
            Held(
                owner.destination,
                owner.channel,
                [note],
                owner.velocity,
                at,
                0,
                owner.tag,
                owner.vary,
            ),
            at,
            length,
        )
