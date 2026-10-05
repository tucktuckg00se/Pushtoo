"""Pushtoo's color roles, shared by the LED palette and the display (PRD: Color)."""

from pushtoo.music import PadRole

# name: (palette index on Push, RGB 0..255)
LED_COLORS: dict[str, tuple[int, tuple[int, int, int]]] = {
    "pt_off": (0, (0, 0, 0)),
    "pt_root": (100, (32, 200, 180)),  # Play mode teal accent
    "pt_in_scale": (101, (150, 150, 150)),  # soft white
    "pt_out_of_scale": (102, (18, 18, 22)),  # dim
    "pt_held": (103, (255, 255, 255)),  # full white
}

PAD_ROLE_COLORS = {
    PadRole.ROOT: "pt_root",
    PadRole.IN_SCALE: "pt_in_scale",
    PadRole.OUT_OF_SCALE: "pt_out_of_scale",
}

# Display colors as cairo RGB floats.
BACKGROUND = (0x0E / 255, 0x0F / 255, 0x12 / 255)
TEXT = (0.92, 0.92, 0.92)
TEXT_DIM = (0.5, 0.5, 0.55)
PLAY_ACCENT = tuple(c / 255 for c in LED_COLORS["pt_root"][1])
