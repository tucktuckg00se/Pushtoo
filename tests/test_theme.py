"""Every LED color Pushtoo asks for must exist in the Push palette.

push2-python silently maps unknown color names to green (RGB) or white (BW), so a
missing or renamed name lights a button that should be dark. That happened once:
programming palette slot 0 renamed "black", and every "off" button turned green.
"""

from push2_python import constants as c
from push2_python.constants import DEFAULT_COLOR_PALETTE
from push2_python.push2_map import push2_map

from pushtoo.theme import LED_COLORS

RGB_NAMES = {rgb for rgb, _ in DEFAULT_COLOR_PALETTE.values() if rgb} | set(LED_COLORS)
BW_NAMES = {bw for _, bw in DEFAULT_COLOR_PALETTE.values() if bw} | set(LED_COLORS)
RGB_BUTTONS = {b["Name"] for b in push2_map["Parts"]["Buttons"] if b.get("Color")}


def check(app) -> None:
    for name, color in app.button_colors().items():
        valid = RGB_NAMES if name in RGB_BUTTONS else BW_NAMES
        assert color in valid, f"{name} asks for unknown color {color!r}"
    for row in app.mode.pad_colors():
        for color in row:
            assert color in RGB_NAMES, f"pad asks for unknown color {color!r}"


def test_every_mode_and_layout_uses_known_colors(env):
    app, _ = env()
    check(app)  # Keyboard
    app.button_pressed(c.BUTTON_SCALE)
    check(app)
    app.button_pressed(c.BUTTON_SCALE)
    for _ in range(2):  # Drums, then Chord
        app.button_pressed(c.BUTTON_LAYOUT)
        check(app)
    app.pad_pressed(1, 0, 100)
    check(app)
    for button in (c.BUTTON_DEVICE, c.BUTTON_MIX, c.BUTTON_BROWSE):
        app.button_pressed(button)
        check(app)
    app.button_pressed(c.BUTTON_SHIFT)
    app.button_pressed(c.BUTTON_DELETE)
    check(app)


def test_programmed_slots_leave_named_defaults_alone():
    used_defaults = {"black", "white", "dark_gray", "light_gray"}
    protected = {
        slot
        for slot, (rgb, bw) in DEFAULT_COLOR_PALETTE.items()
        if rgb in used_defaults or bw in used_defaults
    }
    assert not protected & {slot for slot, _ in LED_COLORS.values()}
