"""When each note of a chord starts (PRD: Chord layout, Timing page). Pure logic.

Together, every note starts at once. Spread out, the notes roll in one after another,
Roll milliseconds apart, like a strum or a harp; Loose adds a little random lateness
to each, like hands that aren't quite together. Notes only ever come later, never
early, and the bass stays on time as the anchor.
"""

import random as random_module
from dataclasses import dataclass, field

DIRECTIONS = ("Up", "Down", "Alternate", "Random")
MAX_ROLL = 100  # ms between notes
MAX_LOOSE = 50  # ms of random lateness


@dataclass
class TimingSpread:
    spread: bool = False
    roll: int = 20
    direction: str = "Up"
    loose: int = 0
    rng: random_module.Random = field(default_factory=random_module.Random, repr=False)
    _down_next: bool = field(default=False, repr=False)  # Alternate's next direction

    def offsets(self, notes: list[int]) -> list[float]:
        """Seconds after the trigger that each note starts, in the notes' order."""
        if not self.spread or not notes:
            return [0.0] * len(notes)
        order = sorted(range(len(notes)), key=lambda i: notes[i])  # low to high
        if self.direction == "Down":
            order.reverse()
        elif self.direction == "Alternate":
            if self._down_next:
                order.reverse()
            self._down_next = not self._down_next
        elif self.direction == "Random":
            self.rng.shuffle(order)
        offsets = [0.0] * len(notes)
        for rank, i in enumerate(order):
            offsets[i] = (rank * self.roll + self.rng.uniform(0, self.loose)) / 1000
        return offsets

    def snapshot(self) -> dict:
        return {
            "spread": self.spread,
            "roll": self.roll,
            "direction": self.direction,
            "loose": self.loose,
        }

    def restore(self, saved: object) -> None:
        if not isinstance(saved, dict):
            return
        if isinstance(saved.get("spread"), bool):
            self.spread = saved["spread"]
        if saved.get("roll") in range(MAX_ROLL + 1):
            self.roll = saved["roll"]
        if saved.get("direction") in DIRECTIONS:
            self.direction = saved["direction"]
        if saved.get("loose") in range(MAX_LOOSE + 1):
            self.loose = saved["loose"]
