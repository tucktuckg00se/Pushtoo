"""Standby: the pads and the screen animate while nobody plays.

Pure logic. The App steps the scene and lights the pads from it; the renderer draws
the same scene on the screen from `view()`, smoothly between the App's steps. Life
here is silent: it only plays notes when turned on in a layout (Session).

Glow is calm: slow, dim, in one palette (Setup's standby colors). Its pads take a
level on the standby ramp once a step, and the Push fades each change in over a
second itself, so the pads glide rather than step.
"""

import math
import random
from collections import deque

import numpy as np

from pushtoo.rhythm.life import COLUMNS, ROWS, Cell, next_board, random_board
from pushtoo.theme import DEFAULT_STANDBY, OFF, STANDBY_STEPS, led, standby_led

SCENES = ("Glow", "Life", "Drift")
STEP_SECONDS = {"Glow": 1.0, "Life": 0.4, "Drift": 0.15}
FADING = ("Glow",)  # scenes whose pads fade between steps on the Push
# Drift's colors, in the order it flows through them.
DRIFT_TOKENS = ("away", "borrowed", "secondary", "root", "tension", "chord_tone")
SETTLE_STEPS = 6  # a board that died or repeats itself shows this long, then reseeds
MEMORY = 12  # boards remembered to notice repeats (blinkers, gliders on a loop)

# Glow: each pad brightens and dims on its own slow schedule, and its light rises onto
# the screen above its column.
PAD_PEAK = 0.6  # the brightest a pad gets, as a level on the ramp: a glow, not a light
PAD_PERIODS = ((40.0, 110.0), (70.0, 160.0))  # seconds: each pad's two slow swells


def glow_params(rng: random.Random) -> np.ndarray:
    """Each pad's own schedule, [row][col] = (period, period, phase, phase)."""
    (low1, high1), (low2, high2) = PAD_PERIODS
    return np.array(
        [
            [
                (rng.uniform(low1, high1), rng.uniform(low2, high2),
                 rng.uniform(0, 2 * np.pi), rng.uniform(0, 2 * np.pi))
                for _ in range(COLUMNS)
            ]
            for _ in range(ROWS)
        ]
    )  # fmt: skip


def pad_levels(params, t: float) -> np.ndarray:
    """How bright each pad is, [row][col] from 0 to 1 (row 0 is the bottom row): two
    slow swells each, so a pad rises and falls over tens of seconds, and about half
    are dark at any moment."""
    p = np.asarray(params)
    swell = 0.6 * np.sin(2 * np.pi * t / p[..., 0] + p[..., 2]) + 0.4 * np.sin(
        2 * np.pi * t / p[..., 1] + p[..., 3]
    )
    return np.maximum(swell, 0.0) ** 1.5


COLUMN_FULL = 0.4  # a column whose pads average this (few ever do) casts its fullest glow


def column_glow(params, t: float) -> np.ndarray:
    """Each column's combined brightness, 0 to 1: what its pads cast onto the screen.
    About half the pads are dark at a time, so a column's average is low; it's scaled
    so a typical column glows softly and a busy one fully."""
    return np.minimum(1.0, pad_levels(params, t).mean(axis=0) / COLUMN_FULL)


def drift_phase(row: float, col: float, t: float) -> float:
    """Where in DRIFT_TOKENS a point of the field is at `t` seconds: slow diagonal waves.
    Rows and columns are fractional on the screen, whole on the pads."""
    wobble = 0.6 * math.sin(t * 0.3 + row * 0.5)
    return (col * 0.35 + row * 0.2 + t * 0.25 + wobble) % len(DRIFT_TOKENS)


class Standby:
    def __init__(
        self, scene: str, now: float, seed: int | None = None, palette: str = DEFAULT_STANDBY
    ) -> None:
        self.scene = scene if scene in SCENES else SCENES[0]
        self.palette = palette  # Setup's standby colors, for the screen
        self.started = self.stepped_at = now
        self.board: frozenset[Cell] = frozenset()
        self.previous: frozenset[Cell] = frozenset()
        self._random = random.Random(seed)
        self._seen: deque[frozenset[Cell]] = deque(maxlen=MEMORY)
        self._settled = 0
        self.glow = glow_params(self._random)
        if self.scene == "Life":
            self._reseed()

    @property
    def fades(self) -> bool:
        """Whether the pads should glide to each step's colors (the Push fades them)."""
        return self.scene in FADING

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
        if self.scene == "Glow":
            levels = pad_levels(self.glow, now - self.started) * PAD_PEAK
            return [
                [standby_led(round(float(v) * (STANDBY_STEPS - 1))) for v in row] for row in levels
            ]
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
            "palette": self.palette,
            "glow": self.glow.tolist(),
            "board": sorted(self.board),
            "previous": sorted(self.previous),
            "started": self.started,
            "stepped_at": self.stepped_at,
            "step": self.step_seconds,
        }
