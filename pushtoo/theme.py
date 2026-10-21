"""Pushtoo's design tokens (PRD: Visual design system).

One color language for screen and LEDs. A theme gives every token one color; tokens
name what a color means ("home", "latch", "knobs"), so a theme can't make two roles
collide by accident. Every token except the screen-only ones has its own slot in
Push's LED palette, which is reprogrammed on every connect and theme change, so an
arc on screen and the button or pad it belongs to show the same color.

The default theme follows INTERSECT's Open Color theme (https://yeun.github.io/
open-color/), with mid shades on the pads, since pastels wash out to white on LEDs.
"""

import re
from collections.abc import Mapping
from types import MappingProxyType

from pushtoo.music import PadRole

RGB = tuple[int, int, int]
Theme = Mapping[str, RGB]

# Every token and its Open Color default: a hex color, or another token's name.
# The order fixes each token's LED palette slot.
OPEN_COLOR: dict[str, str] = {
    # Screen only
    "background": "000000",
    "track": "343a40",  # arc tracks, chips that are off
    "line": "191c1f",  # dividers
    "text": "ced4da",
    "text_dim": "868e96",
    # Mode accents
    "play": "82c91e",
    "knobs": "fcc419",
    "mix": "ff922b",
    "browse": "f1f3f5",
    "setup": "adb5bd",
    # Pads. The accent stays off them: root and home are a warm orange, held is white.
    "root": "ff922b",
    "in_scale": "868e96",
    "out_of_scale": "212529",
    "held": "ffffff",
    "chord_tone": "38d9a9",  # Keyboard pads in the chord playing on under them
    # What each chord does on the chord grid
    "home": "root",
    "away": "4dabf7",
    "tension": "ffd43b",  # lighter than root's orange, so the two differ on the pads
    "borrowed": "9775fa",
    "secondary": "f06595",
    # States
    "latch": "fcc419",
    "mute": "ff6b6b",
    "solo": "4dabf7",
    "rate": "22b8cf",  # the chosen rate on the side buttons
    "life": "cc5de8",  # Life's cells and the Session button
    # Colors a profile can give a knob
    "red": "ff6b6b",
    "orange": "ff922b",
    "amber": "fab005",
    "yellow": "ffe066",
    "green": "51cf66",
    "teal": "20c997",
    "blue": "4dabf7",
    "violet": "9775fa",
    "pink": "f06595",
    "white": "f1f3f5",
    "coral": "ffa8a8",
    "gray": "868e96",
}
TOKENS = tuple(OPEN_COLOR)
SCREEN_ONLY = ("background", "track", "line", "text", "text_dim")
CONTROL_COLOR_NAMES = TOKENS[TOKENS.index("red") :]
MODES = ("play", "knobs", "mix", "browse", "setup")

_HEX = re.compile(r"#?([0-9a-fA-F]{6})")


class ThemeError(Exception):
    """A theme value that can't be used; `key` lets the loader find its line."""

    def __init__(self, key: str | None, message: str) -> None:
        super().__init__(message)
        self.key = key


def resolve(raw: Mapping[str, str]) -> Theme:
    """A theme from the given values, the defaults filling in whatever is missing."""
    for key in raw:
        if key not in OPEN_COLOR:
            raise ThemeError(key, f"unknown color {key!r}")
    values = {**OPEN_COLOR, **raw}
    theme: dict[str, RGB] = {}
    for token in TOKENS:
        value, seen = values[token].strip(), [token]
        while value in values:  # a reference to another token
            if value in seen:
                chain = " → ".join([*seen, value])
                raise ThemeError(token, f"{chain} goes round in a circle")
            seen.append(value)
            value = values[value].strip()
        match = _HEX.fullmatch(value)
        if match is None:
            raise ThemeError(seen[-1], f"{seen[-1]}: {value!r} is not RRGGBB or a color name")
        hex_ = match.group(1)
        theme[token] = (int(hex_[0:2], 16), int(hex_[2:4], 16), int(hex_[4:6], 16))
    return MappingProxyType(theme)


DEFAULT_THEME = resolve({})

# LED palette: name -> (palette index on Push, RGB). Slots start at 64, clear of the
# entries push2-python names by default. Off is push2-python's own "black" (slot 0):
# reprogramming a slot renames it, and push2-python silently maps unknown names to
# green, so default slots stay untouched.
OFF = "black"
FIRST_SLOT = 64
LED_TOKENS = tuple(t for t in TOKENS if t not in SCREEN_ONLY)


def led(token: str) -> str:
    """LED palette name for a token."""
    return f"pt_{token}"


# Standby's colors: one of the UI's own, dark to bright, chosen in Setup. The mode
# accents rise from black to the accent; Mono climbs the screen's grays. They follow
# the theme. The pads get the chosen one as a fine ramp of dim steps in the slots after
# the tokens' (and below the named defaults from 122 up), and fade between
# neighbouring steps with the Push's own transitions.
STANDBY_PALETTES: dict[str, str | None] = {
    "Play": "play",
    "Knobs": "knobs",
    "Mix": "mix",
    "Mono": None,
}
DEFAULT_STANDBY = "Play"
ACCENT_STOPS = (0.0, 0.18, 0.45, 0.75, 1.0)  # an accent, from black up to itself
MONO_STOPS = ("background", "line", "track", "text_dim", "text")
STANDBY_STEPS = 26
STANDBY_LEVEL = 0.55  # the pads' brightest step: they glow, they don't shine


def standby_stops(theme: Mapping[str, tuple], palette: str) -> list[tuple]:
    """A standby palette's colors, dark to bright, in whatever units the theme's are."""
    accent = STANDBY_PALETTES.get(palette, STANDBY_PALETTES[DEFAULT_STANDBY])
    if accent is None:
        return [tuple(theme[token]) for token in MONO_STOPS]
    return [tuple(v * k for v in theme[accent]) for k in ACCENT_STOPS]


def standby_color(theme: Theme, palette: str, level: float) -> RGB:
    """The palette's color at a level from 0 (its dark end) to 1 (its bright end)."""
    stops = standby_stops(theme, palette)
    level = min(1.0, max(0.0, level)) * (len(stops) - 1)
    low = min(int(level), len(stops) - 2)
    mix = level - low
    a, b = stops[low], stops[low + 1]
    return tuple(round(x + (y - x) * mix) for x, y in zip(a, b, strict=True))


def standby_led(step: int) -> str:
    """LED palette name for a step of the standby ramp, 0 (off) to STANDBY_STEPS - 1."""
    step = min(STANDBY_STEPS - 1, max(0, step))
    return OFF if step == 0 else f"pt_standby_{step}"


def led_palette(theme: Theme, standby: str = DEFAULT_STANDBY) -> dict[str, tuple[int, RGB]]:
    palette = {led(t): (FIRST_SLOT + i, theme[t]) for i, t in enumerate(LED_TOKENS)}
    first = FIRST_SLOT + len(LED_TOKENS)
    for step in range(1, STANDBY_STEPS):
        level = step / (STANDBY_STEPS - 1)
        rgb = tuple(round(v * STANDBY_LEVEL) for v in standby_color(theme, standby, level))
        palette[standby_led(step)] = (first + step - 1, rgb)
    return palette


LED_COLORS = led_palette(DEFAULT_THEME)  # the names and slots; any theme's are the same

PAD_ROLE_COLORS = {
    PadRole.ROOT: led("root"),
    PadRole.IN_SCALE: led("in_scale"),
    PadRole.OUT_OF_SCALE: led("out_of_scale"),
}


def accent_name(mode: str) -> str:
    """The token of a mode's accent color."""
    return mode if mode in MODES else "play"


# Type scale (px). The PRD's three core sizes are LABEL, VALUE and PEEK. SMALL is only
# for legends that sit beside a miniature of the hardware.
SMALL = 12
LABEL = 14
BODY = 16
VALUE = 20
HEADING = 28
TITLE = 34
PEEK = 48
