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
    # Pads. The accent stays off them: root and home are a warm orange, held is white.
    "root": "ff922b",
    "in_scale": "868e96",
    "out_of_scale": "212529",
    "held": "ffffff",
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
MODES = ("play", "knobs", "mix", "browse")

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


def led_palette(theme: Theme) -> dict[str, tuple[int, RGB]]:
    return {led(t): (FIRST_SLOT + i, theme[t]) for i, t in enumerate(LED_TOKENS)}


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
