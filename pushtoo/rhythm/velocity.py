"""Velocity for each note of a chord (PRD: Chord layout, Velocity page). Pure logic.

Hitting harder still plays louder: the pad's velocity sets a center, scaled into the
Min..Max range. With Random on, each note lands somewhere within Spread of that center,
and Top nudges the highest note so a melody can stand out. Accent means "as loud as
the range allows": the center moves to Max, so Random spreads accented chords down
from Max, loud but alive.
"""

import random as random_module
from dataclasses import dataclass, field

MAX_SPREAD = 127
MAX_TOP = 32


@dataclass
class VelocitySpread:
    random: bool = False
    min: int = 1
    max: int = 127
    spread: int = 24
    top: int = 0  # added to the highest note, -MAX_TOP..MAX_TOP
    rng: random_module.Random = field(default_factory=random_module.Random, repr=False)

    def center(self, velocity: int, accent: bool) -> int:
        if accent:
            return self.max
        return round(self.min + (self.max - self.min) * (max(1, velocity) - 1) / 126)

    def velocities(self, notes: list[int], velocity: int, accent: bool) -> list[int]:
        """One velocity per note, in the notes' order."""
        highest = max(notes, default=None)
        return [self.one(note == highest, velocity, accent) for note in notes]

    def one(self, is_top: bool, velocity: int, accent: bool) -> int:
        """A single note's velocity: for strummed and arpeggiated notes, which play
        one at a time but still know whether they're the chord's top note."""
        center = self.center(velocity, accent)
        if not self.random:
            return center
        value = center + self.rng.randint(-self.spread, self.spread)
        if is_top:
            value += self.top
        return max(self.min, min(self.max, value))

    def set_min(self, value: int) -> None:
        self.min = min(value, self.max)

    def set_max(self, value: int) -> None:
        self.max = max(value, self.min)

    def snapshot(self) -> dict:
        return {
            "random": self.random,
            "min": self.min,
            "max": self.max,
            "spread": self.spread,
            "top": self.top,
        }

    def restore(self, saved: object) -> None:
        if not isinstance(saved, dict):
            return
        if isinstance(saved.get("random"), bool):
            self.random = saved["random"]
        if saved.get("max") in range(1, 128):
            self.max = saved["max"]
        if saved.get("min") in range(1, self.max + 1):
            self.min = saved["min"]
        if saved.get("spread") in range(0, MAX_SPREAD + 1):
            self.spread = saved["spread"]
        if saved.get("top") in range(-MAX_TOP, MAX_TOP + 1):
            self.top = saved["top"]
