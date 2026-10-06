"""Life (PRD F9): a Game of Life on the pads that plays in the current layout.

Pure logic, like Rhythm: pads seed cells, the clock steps generations, and each step
returns timed notes. Which notes a cell plays is asked of the layout (`notes_at`), so
the same board plays a melody on the Keyboard, a beat on Drums and changes on the
Chord grid. Every note-on carries LIFE_TAG and every note-off none, so turning Life
off takes back what it queued without leaving a note hanging.
"""

import random
from collections.abc import Callable, Iterable

from pushtoo.midi.notes import NOTE_OFF, NOTE_ON
from pushtoo.rhythm.clock import Clock
from pushtoo.rhythm.repeat import LIFE_TAG, RATES, Scheduled

ROWS = COLUMNS = 8
Cell = tuple[int, int]  # (row, col), row 0 at the bottom, as pads are
# Birth and survival neighbour counts.
RULES: dict[str, tuple[frozenset[int], frozenset[int]]] = {
    "Conway": (frozenset({3}), frozenset({2, 3})),
    "HighLife": (frozenset({3, 6}), frozenset({2, 3})),
    "Seeds": (frozenset({2}), frozenset()),
    "Day & Night": (frozenset({3, 6, 7, 8}), frozenset({3, 4, 6, 7, 8})),
}
RULE_NAMES = tuple(RULES)
PLAYS = ("Births", "All")  # what sounds on a step: cells just born, or every live cell
MAX_VOICES = 8
GATE = 50  # percent of a step
VELOCITY = 96

# (destination, channel, notes) for a pad; no notes means the pad plays nothing.
NotesAt = Callable[[int, int], tuple[str, int, list[int]]]


def next_board(cells: frozenset[Cell], rule: str = "Conway", wrap: bool = True) -> frozenset[Cell]:
    """One generation of an 8x8 board."""
    born, survive = RULES[rule]
    counts: dict[Cell, int] = {}
    for r, c in cells:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr or dc:
                    n = (r + dr, c + dc)
                    if wrap:
                        n = (n[0] % ROWS, n[1] % COLUMNS)
                    elif not (0 <= n[0] < ROWS and 0 <= n[1] < COLUMNS):
                        continue
                    counts[n] = counts.get(n, 0) + 1
    return frozenset(
        cell for cell, n in counts.items() if n in (survive if cell in cells else born)
    )


def random_board(rng: random.Random, density: float = 0.3) -> frozenset[Cell]:
    return frozenset((r, c) for r in range(ROWS) for c in range(COLUMNS) if rng.random() < density)


class Life:
    def __init__(self) -> None:
        self.on = False
        self.rule = "Conway"
        self.rate = "1/8"
        self.plays = "Births"
        self.voices = 4  # at most this many pads sound on a step
        self.velocity = VELOCITY
        self.wrap = True
        self.hold = False  # the board stops changing and its cells play on
        self.cells: frozenset[Cell] = frozenset()
        self.generation = 0  # counts every change to the board, so the pads can follow
        self._random = random.Random(0)

    # The board

    def seed(self, row: int, col: int) -> None:
        if (row, col) not in self.cells:
            self.cells = self.cells | {(row, col)}
            self.generation += 1

    def clear(self) -> None:
        if self.cells:
            self.cells = frozenset()
            self.generation += 1

    def randomize(self) -> None:
        self.cells = random_board(self._random)
        self.generation += 1

    def step(self) -> frozenset[Cell]:
        """One generation; returns the cells just born."""
        before = self.cells
        self.cells = next_board(before, self.rule, self.wrap)
        if self.cells != before:
            self.generation += 1
        return self.cells - before

    # The grid

    def events(self, clock: Clock, start: float, end: float, notes_at: NotesAt) -> list[Scheduled]:
        """Every note for Life's steps in [start, end)."""
        if not self.cells:
            return []
        step = RATES[self.rate] * clock.beat_seconds
        found: list[Scheduled] = []
        for _, at in clock.steps(RATES[self.rate], start, end):
            if self.hold:
                playing: Iterable[Cell] = self.cells
            else:
                born = self.step()
                playing = born if self.plays == "Births" else self.cells
            found += self._hits(sorted(playing), at, step * GATE / 100, notes_at)
        return found

    def _hits(self, cells: list[Cell], at: float, length: float, notes_at: NotesAt):
        if len(cells) > self.voices:
            cells = sorted(self._random.sample(cells, self.voices))
        found: list[Scheduled] = []
        sounded: set[tuple[str, int, int]] = set()
        for row, col in cells:
            destination, channel, notes = notes_at(row, col)
            for note in notes:
                if (destination, channel, note) in sounded:
                    continue  # two pads with one note (in-key rows overlap) play it once
                sounded.add((destination, channel, note))
                found.append((at, destination, [NOTE_ON | channel, note, self.velocity], LIFE_TAG))
                found.append((at + length, destination, [NOTE_OFF | channel, note, 0], 0))
        return found
