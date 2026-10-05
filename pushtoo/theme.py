"""Pushtoo's design tokens (PRD: Visual design system).

One color language for screen and LEDs: every named color has a screen RGB and its
own slot in Push's LED palette, which is reprogrammed on every connect, so an arc on
screen and the button or pad it belongs to show the same color.
"""

from pushtoo.music import PadRole

RGB = tuple[int, int, int]

# Colors a profile can give a control, plus a few reserved for modes.
NAMED_COLORS: dict[str, RGB] = {
    "red": (230, 60, 60),
    "orange": (240, 130, 40),
    "amber": (245, 180, 40),
    "yellow": (235, 225, 60),
    "green": (80, 200, 90),
    "teal": (32, 200, 180),
    "blue": (60, 130, 240),
    "violet": (150, 100, 240),
    "pink": (240, 100, 180),
    "white": (230, 230, 230),
    "coral": (250, 110, 90),
    "gray": (150, 150, 155),
}
CONTROL_COLOR_NAMES = tuple(n for n in NAMED_COLORS if n not in ("coral", "gray"))

MODE_ACCENTS = {
    "play": "teal",
    "knobs": "amber",
    "mix": "coral",
    "launch": "violet",
    "setup": "gray",
    "browse": "white",
}

_PAD_ROLES: dict[str, RGB] = {
    "pt_off": (0, 0, 0),
    "pt_root": NAMED_COLORS["teal"],  # Play accent
    "pt_in_scale": (150, 150, 150),  # soft white
    "pt_out_of_scale": (18, 18, 22),  # dim
    "pt_held": (255, 255, 255),  # full white
}
FIRST_NAMED_SLOT = 104

# LED palette: name -> (palette index on Push, RGB). Named colors are "pt_<name>".
LED_COLORS: dict[str, tuple[int, RGB]] = {
    "pt_off": (0, _PAD_ROLES["pt_off"]),
    **{name: (100 + i, color) for i, (name, color) in enumerate(list(_PAD_ROLES.items())[1:])},
    **{
        f"pt_{name}": (FIRST_NAMED_SLOT + i, color)
        for i, (name, color) in enumerate(NAMED_COLORS.items())
    },
}

PAD_ROLE_COLORS = {
    PadRole.ROOT: "pt_root",
    PadRole.IN_SCALE: "pt_in_scale",
    PadRole.OUT_OF_SCALE: "pt_out_of_scale",
}


def led(name: str) -> str:
    """LED palette name for a named color."""
    return f"pt_{name}"


def rgb(name: str) -> tuple[float, float, float]:
    """Cairo RGB for a named color."""
    r, g, b = NAMED_COLORS[name]
    return r / 255, g / 255, b / 255


def accent_name(mode: str) -> str:
    return MODE_ACCENTS.get(mode, "teal")


# Display colors as cairo RGB floats.
BACKGROUND = (0x0E / 255, 0x0F / 255, 0x12 / 255)
TEXT = (0.92, 0.92, 0.92)
TEXT_DIM = (0.5, 0.5, 0.55)
ARC_TRACK = (0.22, 0.22, 0.25)

# Type scale (px). The PRD's three core sizes are LABEL, VALUE and PEEK.
LABEL = 14
BODY = 16
VALUE = 20
HEADING = 28
TITLE = 34
PEEK = 48
