"""Standby: the pads and the screen animate while nobody plays.

Pure logic. The App steps the scene and lights the pads from it; the renderer draws
the same scene on the screen from `view()`, smoothly between the App's steps. Life
here is silent: it only plays notes when turned on in a layout (Session).
"""

import math
import random
from collections import deque

from pushtoo.rhythm.life import COLUMNS, ROWS, Cell, next_board, random_board
from pushtoo.theme import OFF, led

SCENES = ("Life", "Drift")
STEP_SECONDS = {"Life": 0.4, "Drift": 0.15}
# Drift's colors, in the order it flows through them.
DRIFT_TOKENS = ("away", "borrowed", "secondary", "root", "tension", "chord_tone")
SETTLE_STEPS = 6  # a board that died or repeats itself shows this long, then reseeds
MEMORY = 12  # boards remembered to notice repeats (blinkers, gliders on a loop)


def drift_phase(row: float, col: float, t: float) -> float:
    """Where in DRIFT_TOKENS a point of the field is at `t` seconds: slow diagonal waves.
    Rows and columns are fractional on the screen, whole on the pads."""
    wobble = 0.6 * math.sin(t * 0.3 + row * 0.5)
    return (col * 0.35 + row * 0.2 + t * 0.25 + wobble) % len(DRIFT_TOKENS)


class Standby:
    def __init__(self, scene: str, now: float, seed: int | None = None) -> None:
        self.scene = scene if scene in SCENES else SCENES[0]
        self.started = self.stepped_at = now
        self.board: frozenset[Cell] = frozenset()
        self.previous: frozenset[Cell] = frozenset()
        self._random = random.Random(seed)
        self._seen: deque[frozenset[Cell]] = deque(maxlen=MEMORY)
        self._settled = 0
        if self.scene == "Life":
            self._reseed()

    @property
    def step_seconds(self) -> float:
        return STEP_SECONDS[self.scene]

    def due(self, now: float) -> bool:
        return now - self.stepped_at >= self.step_seconds

    def step(self, now: float) -> None:
        self.stepped_at = now
        if self.scene != "Life":
            return
        self.previous, self.board = self.board, next_board(self.board)
        if not self.board or self.board in self._seen:
            self._settled += 1
            if self._settled > SETTLE_STEPS:
                self._reseed()
        self._seen.append(self.board)

    def _reseed(self) -> None:
        self.previous, self.board = self.board, random_board(self._random, 0.35)
        self._seen.clear()
        self._settled = 0

    def pad_colors(self, now: float) -> list[list[str]]:
        if self.scene == "Life":
            life = led("life")
            return [
                [life if (r, c) in self.board else OFF for c in range(COLUMNS)] for r in range(ROWS)
            ]
        t = now - self.started
        return [
            [led(DRIFT_TOKENS[int(drift_phase(r, c, t))]) for c in range(COLUMNS)]
            for r in range(ROWS)
        ]

    def view(self) -> dict:
        return {
            "scene": self.scene,
            "board": sorted(self.board),
            "previous": sorted(self.previous),
            "started": self.started,
            "stepped_at": self.stepped_at,
            "step": self.step_seconds,
        }
