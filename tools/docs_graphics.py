"""Draw the docs' graphics: a simplified Push 2 showing Pushtoo, and screen renders.

    uv run python tools/docs_graphics.py [docs_dir]

Writes docs/images/push/<scene>.svg (the whole controller, laid out as on a Push 2:
the real screen, the pads and buttons lit as Pushtoo lights them, each button's
printed name and, where Pushtoo gives it its own job, what it does) and
docs/images/screens/<name>.png (the screen alone). Everything comes from
the app itself, so re-run this after any change to the screen or the LEDs.
"""

import importlib.util
import random
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import cairo
from push2_python import constants as c

from pushtoo.fonts import FAMILY, use_bundled_fonts
from pushtoo.modes.chord import SCENE_BUTTONS
from pushtoo.render.screens import HEIGHT, WIDTH
from pushtoo.theme import LED_COLORS, OPEN_COLOR

_spec = importlib.util.spec_from_file_location(
    "render_preview", Path(__file__).with_name("render_preview.py")
)
preview = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(preview)

# Screens shown on their own, next to the paragraph they illustrate.
SCREENS = (
    "scale_selector",
    "layout_picker",
    "shift_overlay",
    "chord_idle",
    "chord_momentary_voicing",
    "chord_slash",
    "chord_random_velocity",
    "chord_timing",
    "chord_jazz_shell",
    "keyboard_over_chord",
    "drums_top",
    "keyboard_output_page",
    "keyboard_rhythm_page",
    "chord_repeat_held",
    "peek_tempo",
    "keyboard_life_page",
    "standby_life",
    "standby_drift",
    "knobs_learn_assist",
    "knobs_delete_overlay",
    "peek_master",
    "setup_aftertouch",
    "setup_display",
    "setup_clock",
    "browse",
)


def _hex(token: str) -> tuple[float, float, float]:
    value = OPEN_COLOR[token]
    while value in OPEN_COLOR:
        value = OPEN_COLOR[value]
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))


# The page around the drawing, in the docs' (and the screen's) colors.
BODY = _hex("line")
EDGE = _hex("track")
CAP = (0.07, 0.08, 0.09)  # an unlit button or pad
TEXT = _hex("text")
DIM = _hex("text_dim")
DARK_GRAY = (0.36, 0.39, 0.42)  # a white-only LED at its low level


def led_rgb(name: str) -> tuple[float, float, float] | None:
    """The color a Push LED shows for a palette name; None when it's off."""
    if name == "black":
        return None
    if name == "white":
        return _hex("white")
    if name == "dark_gray":
        return DARK_GRAY
    if name in LED_COLORS:
        return tuple(v / 255 for v in LED_COLORS[name][1])
    raise ValueError(f"unknown LED color {name!r}")


# Every control is drawn where it sits on a Push 2, at its size, measured from a
# photo of one (2000 px wide). The printed name goes on each button, as on the
# hardware; where Pushtoo gives a button its own job, a second line says what it
# does, in the button's light. The buttons above and below the screen and the side
# buttons are named by the screen beside them, as on the Push.
FUNCTIONS = {
    c.BUTTON_NOTE: "Play mode",
    c.BUTTON_DEVICE: "Knobs mode",
    c.BUTTON_MIX: "Mix mode",
    c.BUTTON_BROWSE: "Profiles",
    c.BUTTON_SESSION: "Life",
    c.BUTTON_REPEAT: "Rhythm",
    c.BUTTON_STOP: "Shift: Panic",
    c.BUTTON_UNDO: "Shift: Redo",
    c.BUTTON_PLAY: "Start/Stop",
}
# Buttons Pushtoo uses that keep their printed meaning.
SAME = {
    c.BUTTON_TAP_TEMPO,
    c.BUTTON_DELETE,
    c.BUTTON_SETUP,
    c.BUTTON_ACCENT,
    c.BUTTON_SCALE,
    c.BUTTON_LAYOUT,
    c.BUTTON_SHIFT,
}
ENCODER_LABELS = {
    c.ENCODER_TEMPO_ENCODER: "Tempo",
    c.ENCODER_SWING_ENCODER: "Swing",
    c.ENCODER_MASTER_ENCODER: "Level",
}
NAME_SIZE, FUNCTION_SIZE = 17, 15
UNUSED = (0.24, 0.26, 0.28)  # the printed name of a button Pushtoo leaves alone
OFF = (0.36, 0.39, 0.42)  # a used button whose light is off

ORIGIN = (100, 88)  # the photo's corner of the drawing
SIZE = (1820, 1484)
BODY_RECT = (110, 98, 1800, 1464)
COL, ROW = 137.5, 105.6  # pad pitch: the pads are wider than tall
PADS = (420, 655)  # top-left of the top-left pad
PAD = (125, 93)
SCREEN = (420, 328, 1100, 1100 * HEIGHT / WIDTH)
UPPER_Y, LOWER_Y, ROW_H = 230, 572, 46
SIDE_X, SIDE = 1575, (92, 89)  # the side (scene) buttons, one per pad row
STRIP = (257, 660, 105, 830)
ENCODERS = [
    (c.ENCODER_TEMPO_ENCODER, 180),
    (c.ENCODER_SWING_ENCODER, 315),
    *((f"Track{i + 1} Encoder", PADS[0] + (i + 0.5) * COL) for i in range(8)),
    (c.ENCODER_MASTER_ENCODER, 1780),
]
ENCODER_Y, ENCODER_R = 150, 38

# name: (x, y, w, h), as on the Push
BUTTONS = {
    c.BUTTON_TAP_TEMPO: (137, 226, 118, 52),
    c.BUTTON_METRONOME: (257, 226, 118, 52),
    c.BUTTON_DELETE: (130, 332, 86, 86),
    c.BUTTON_UNDO: (130, 420, 86, 86),
    c.BUTTON_MUTE: (125, 568, 80, 49),
    c.BUTTON_SOLO: (207, 568, 80, 49),
    c.BUTTON_STOP: (289, 568, 80, 49),
    c.BUTTON_CONVERT: (122, 658, 86, 85),
    c.BUTTON_DOUBLE_LOOP: (122, 745, 86, 85),
    c.BUTTON_QUANTIZE: (122, 832, 86, 85),
    c.BUTTON_DUPLICATE: (122, 935, 86, 86),
    c.BUTTON_NEW: (122, 1023, 86, 86),
    c.BUTTON_FIXED_LENGTH: (122, 1131, 86, 78),
    c.BUTTON_AUTOMATE: (122, 1211, 86, 78),
    c.BUTTON_RECORD: (122, 1291, 86, 89),
    c.BUTTON_PLAY: (122, 1398, 86, 87),
    c.BUTTON_SETUP: (1688, 228, 88, 52),
    c.BUTTON_USER: (1778, 228, 88, 52),
    c.BUTTON_ADD_DEVICE: (1572, 332, 91, 87),
    c.BUTTON_ADD_TRACK: (1572, 421, 91, 87),
    c.BUTTON_DEVICE: (1692, 335, 88, 86),
    c.BUTTON_MIX: (1782, 335, 88, 86),
    c.BUTTON_BROWSE: (1692, 423, 88, 86),
    c.BUTTON_CLIP: (1782, 423, 88, 86),
    c.BUTTON_MASTER: (1575, 572, 90, 48),
    c.BUTTON_REPEAT: (1702, 983, 88, 87),
    c.BUTTON_ACCENT: (1792, 983, 88, 87),
    c.BUTTON_SCALE: (1702, 1090, 88, 50),
    c.BUTTON_LAYOUT: (1792, 1090, 88, 50),
    c.BUTTON_NOTE: (1702, 1142, 88, 91),
    c.BUTTON_SESSION: (1792, 1142, 88, 91),
    c.BUTTON_SHIFT: (1702, 1452, 88, 48),
    c.BUTTON_SELECT: (1792, 1452, 88, 48),
}
PRINTED = {
    c.BUTTON_RECORD: "",  # a circle
    c.BUTTON_PLAY: "",  # a triangle
}
ARROWS = (1695, 573, 180, 180)  # Up, Down, Left, Right: one square, split in four
OCTAVE = (1702, 1252, 180, 183)  # Octave Up, Octave Down, Page Left, Page Right


def _round_rect(ctx: cairo.Context, x: float, y: float, w: float, h: float, r: float) -> None:
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -1.5708, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, 1.5708)
    ctx.arc(x + r, y + h - r, r, 1.5708, 3.1416)
    ctx.arc(x + r, y + r, r, 3.1416, 4.7124)
    ctx.close_path()


def _fit(ctx, text: str, size: float, width: float, bold: bool) -> float:
    weight = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
    ctx.select_font_face(FAMILY, cairo.FONT_SLANT_NORMAL, weight)
    ctx.set_font_size(size)
    while size > 10 and ctx.text_extents(text).x_advance > width:
        size -= 0.5
        ctx.set_font_size(size)
    return size


def _text(ctx, text, x, y, size, rgb, width=10_000, bold=False, center=False) -> None:
    """Text with its baseline at y, starting at x (or centered on it)."""
    _fit(ctx, text, size, width, bold)
    advance = ctx.text_extents(text).x_advance
    ctx.move_to(x - advance / 2 if center else x, y)
    ctx.set_source_rgb(*rgb)
    ctx.show_text(text)
    ctx.new_path()  # so the next shape doesn't start from the end of the text


def _plate(ctx, x, y, w, h, edge=EDGE, width=1.5) -> None:
    _round_rect(ctx, x, y, w, h, 6)
    ctx.set_source_rgb(*CAP)
    ctx.fill_preserve()
    ctx.set_source_rgb(*edge)
    ctx.set_line_width(width)
    ctx.stroke()


def _button(ctx, name: str, colors: dict[str, str]) -> None:
    x, y, w, h = BUTTONS[name]
    lit = led_rgb(colors.get(name, "black"))
    used = name in FUNCTIONS or name in SAME
    shown = lit if used and lit else (OFF if used else UNUSED)
    _plate(ctx, x, y, w, h, shown if used and lit else EDGE, 3 if used and lit else 1.5)
    printed = PRINTED.get(name, name)
    function = FUNCTIONS.get(name)
    pad = 9
    # One size for printed names and one for functions, on every button, so they read
    # as two kinds of label; only a label too long for its button shrinks.
    tall = h > 60
    if printed:
        baseline = y + pad + NAME_SIZE * 0.8 if tall or function else y + h / 2 + NAME_SIZE * 0.36
        _text(ctx, printed, x + pad, baseline, NAME_SIZE, shown, w - 2 * pad, bold=used)
    if function:  # what it does in Pushtoo, at the bottom
        _text(ctx, function, x + pad, y + h - pad + 1, FUNCTION_SIZE, shown, w - 2 * pad, bold=True)
    if name == c.BUTTON_RECORD:
        ctx.arc(x + w / 2, y + h / 2, 17, 0, 6.2832)
    elif name == c.BUTTON_PLAY:
        cy = y + h / 2 - (10 if function else 0)
        ctx.move_to(x + w / 2 - 11, cy - 15)
        ctx.line_to(x + w / 2 + 15, cy)
        ctx.line_to(x + w / 2 - 11, cy + 15)
        ctx.close_path()
    if name in (c.BUTTON_RECORD, c.BUTTON_PLAY):
        ctx.set_source_rgb(*shown)
        ctx.set_line_width(2.5)
        ctx.stroke()


def _split_square(ctx, rect, top=None, bottom=None) -> None:
    """A square split corner to corner into four buttons. top and bottom are
    (label, LED color) for the halves Pushtoo uses."""
    x, y, w, h = rect
    _plate(ctx, x, y, w, h)
    ctx.move_to(x, y)
    ctx.line_to(x + w, y + h)
    ctx.move_to(x + w, y)
    ctx.line_to(x, y + h)
    ctx.set_source_rgb(*EDGE)
    ctx.set_line_width(1.5)
    ctx.stroke()
    cx = x + w / 2
    for part, sign in ((top, -1), (bottom, 1)):
        if part is None:
            continue
        label, color = part
        rgb = led_rgb(color) or OFF
        baseline = y + h * (0.27 if sign < 0 else 0.84)
        _text(ctx, label, cx, baseline, 19, rgb, bold=True, center=True)
        tip = y + h / 2 + sign * h * 0.13  # a chevron pointing out of the square
        ctx.move_to(cx - 10, tip - sign * 5)
        ctx.line_to(cx, tip + sign * 5)
        ctx.line_to(cx + 10, tip - sign * 5)
        ctx.set_source_rgb(*rgb)
        ctx.set_line_width(3)
        ctx.stroke()


def draw_push(ctx: cairo.Context, app, now: float | None = None) -> None:
    """The Push as the app lights it, or as standby shows it at `now`."""
    view, colors = app.view(), app.lit_buttons()
    pads = app.pad_colors() if now is None else app.standby.pad_colors(now)
    view["now"] = now
    ctx.translate(-ORIGIN[0], -ORIGIN[1])
    x, y, w, h = BODY_RECT
    _round_rect(ctx, x, y, w, h, 22)
    ctx.set_source_rgb(*BODY)
    ctx.fill_preserve()
    ctx.set_source_rgb(*EDGE)
    ctx.set_line_width(2)
    ctx.stroke()

    for name, cx in ENCODERS:
        ctx.arc(cx, ENCODER_Y, ENCODER_R, 0, 6.2832)
        ctx.set_source_rgb(*CAP)
        ctx.fill_preserve()
        ctx.set_source_rgb(*EDGE)
        ctx.set_line_width(2)
        ctx.stroke()
        if name in ENCODER_LABELS:
            _text(ctx, ENCODER_LABELS[name], cx, ENCODER_Y + 60, 19, TEXT, bold=True, center=True)

    for i in range(8):
        x = PADS[0] + i * COL + 6
        for y, row in ((UPPER_Y, "Upper"), (LOWER_Y, "Lower")):
            _plate(ctx, x, y, PAD[0], ROW_H)
            lit = led_rgb(colors.get(f"{row} Row {i + 1}", "black"))
            if lit:  # the light strip along the button
                ctx.rectangle(x + 20, y + ROW_H / 2 - 2.5, PAD[0] - 40, 5)
                ctx.set_source_rgb(*lit)
                ctx.fill()

    x, y, w, h = SCREEN
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(w / WIDTH, w / WIDTH)
    ctx.set_source_surface(preview.render(view), 0, 0)
    ctx.paint()
    ctx.restore()
    ctx.rectangle(x, y, w, h)
    ctx.set_source_rgb(*EDGE)
    ctx.set_line_width(1.5)
    ctx.stroke()

    for row in range(8):  # row 0 is the bottom row
        for col in range(8):
            _round_rect(ctx, PADS[0] + col * COL + 6, PADS[1] + (7 - row) * ROW, *PAD, 8)
            ctx.set_source_rgb(*(led_rgb(pads[row][col]) or CAP))
            ctx.fill()

    x, y, w, h = STRIP
    _plate(ctx, x, y, w, h)
    ctx.save()
    ctx.translate(x + w / 2 + 7, y + h / 2)
    ctx.rotate(-1.5708)
    _text(ctx, "Touch strip", 0, 0, 19, OFF, bold=True, center=True)
    ctx.restore()

    for i, name in enumerate(SCENE_BUTTONS):
        y = PADS[1] + i * ROW + (PAD[1] - SIDE[1]) / 2
        lit = led_rgb(colors.get(name, "black"))
        _plate(ctx, SIDE_X, y, *SIDE, lit or EDGE, 3 if lit else 1.5)
        _text(ctx, name, SIDE_X + 9, y + 24, NAME_SIZE, lit or UNUSED)
        ctx.move_to(SIDE_X + SIDE[0] - 30, y + SIDE[1] - 40)  # the printed arrow
        ctx.line_to(SIDE_X + SIDE[0] - 20, y + SIDE[1] - 28)
        ctx.line_to(SIDE_X + SIDE[0] - 30, y + SIDE[1] - 16)
        ctx.set_source_rgb(*(lit or UNUSED))
        ctx.set_line_width(2)
        ctx.stroke()

    for name in BUTTONS:
        _button(ctx, name, colors)
    _split_square(ctx, ARROWS)
    _split_square(
        ctx,
        OCTAVE,
        top=("Octave", colors.get(c.BUTTON_OCTAVE_UP, "black")),
        bottom=("Octave", colors.get(c.BUTTON_OCTAVE_DOWN, "black")),
    )


def draw_svg(app, path: Path, now: float | None = None) -> None:
    surface = cairo.SVGSurface(str(path), *SIZE)
    surface.set_document_unit(cairo.SVGUnit.PX)
    draw_push(cairo.Context(surface), app, now)
    surface.finish()


def _to_layout(app, name: str) -> None:
    while app.play.layout.name != name:
        preview._tap_layout(app)


def _hold(app, *pads: tuple[int, int]) -> None:
    for row, col in pads:
        app.pad_pressed(row, col, 100)


def _overview(app) -> None:
    pass


def _keyboard(app) -> None:
    _hold(app, (0, 0), (0, 2), (0, 4))


def _drums(app) -> None:
    _to_layout(app, "Drums")
    app.pad_pressed(0, 2, 96)  # Snare


def _chord(app) -> None:
    _to_layout(app, "Chord")
    _hold(app, (2, 3))  # Fm7


def _chord_latch(app) -> None:
    _to_layout(app, "Chord")
    app.button_pressed("1/4")  # Latch, the bottom side button
    app.button_released("1/4")
    preview._page(app, "Style")
    app.button_pressed("Upper Row 2")  # Strum
    app.pad_pressed(1, 3, 100)
    app.pad_released(1, 3)


def _rhythm(app) -> None:
    app.button_pressed(c.BUTTON_REPEAT)
    app.button_released(c.BUTTON_REPEAT)  # a tap: rhythm on
    app.button_pressed("1/8t")
    app.button_released("1/8t")
    _hold(app, (0, 0))


def _life(app) -> None:
    app.button_pressed(c.BUTTON_SESSION)
    app.button_released(c.BUTTON_SESSION)  # a tap: Life on
    for pad in ((3, 2), (3, 3), (3, 4), (4, 4), (5, 3)):  # a glider
        app.pad_pressed(*pad, 100)
        app.pad_released(*pad)
    app.toast("", 0)


def _knobs(app) -> None:
    app.button_pressed(c.BUTTON_DEVICE)


def _mix(app) -> None:
    app.button_pressed(c.BUTTON_MIX)
    app.pad_pressed(7, 1, 100)
    app.pad_pressed(6, 3, 100)


def _glow(app) -> float:
    return preview.start_calm(app, "Glow")


def _setup(app) -> None:
    app.button_pressed(c.BUTTON_SETUP)
    app.encoder_rotated("Track2 Encoder", -6 * 4)  # softer Dynamics
    app.pad_pressed(0, 0, 87)


# scene -> (what to do on a fresh app, the profile it loads). A scene that animates
# returns the moment to draw it at.
SCENES: dict[str, tuple[Callable, str | None]] = {
    "overview": (_overview, None),
    "keyboard": (_keyboard, None),
    "drums": (_drums, None),
    "chord": (_chord, None),
    "chord_latch": (_chord_latch, None),
    "rhythm": (_rhythm, None),
    "life": (_life, None),
    "knobs": (_knobs, preview.SYNTH_PROFILE),
    "mix": (_mix, None),
    "setup": (_setup, None),
    "standby_glow": (_glow, None),
}


def main() -> None:
    use_bundled_fonts()  # the same font as on the Push
    docs = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent.parent / "docs")
    push_dir, screen_dir = docs / "images" / "push", docs / "images" / "screens"
    push_dir.mkdir(parents=True, exist_ok=True)
    screen_dir.mkdir(parents=True, exist_ok=True)
    # Random velocity and standby draw from unseeded generators: seed them all the same,
    # so re-running this only changes the images when the app does. That seeds the temp
    # folders' names too, so they go in a fresh folder of their own, where the same
    # names can't run into leftovers.
    private = tempfile.TemporaryDirectory()
    tempfile.tempdir = private.name
    unseeded = random.Random.seed
    random.Random.seed = lambda rng, a=None, version=2: unseeded(rng, a or 0, version)
    try:
        for name, (scene, profile) in SCENES.items():
            with tempfile.TemporaryDirectory() as tmp:
                app = preview._app(Path(tmp), profile)
                draw_svg(app, push_dir / f"{name}.svg", scene(app))
                app.close()  # joins the state saver before the temp folder is removed
        views = preview.sample_views()
    finally:
        random.Random.seed = unseeded
        tempfile.tempdir = None
        private.cleanup()
    for name in SCREENS:
        preview.render(views[name]).write_to_png(str(screen_dir / f"{name}.png"))
    print(f"wrote {len(SCENES)} drawings to {push_dir}/")
    print(f"wrote {len(SCREENS)} screens to {screen_dir}/")


if __name__ == "__main__":
    main()
