"""Draw the docs' graphics: a simplified Push 2 showing Pushtoo, and screen renders.

    uv run python tools/docs_graphics.py [docs_dir]

Writes docs/images/push/<scene>.svg (the whole controller: the real screen, the pads
and buttons lit as Pushtoo lights them, each control labeled with what it does in
Pushtoo) and docs/images/screens/<name>.png (the screen alone). Everything comes from
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
from pushtoo.theme import DEFAULT_THEME, LED_COLORS, OPEN_COLOR

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
        return tuple(v / 255 for v in DEFAULT_THEME[name.removeprefix("pt_")])
    raise ValueError(f"unknown LED color {name!r}")


# What each control does in Pushtoo, written on it. Controls Pushtoo doesn't use
# are drawn dim and unlabeled; the buttons above and below the screen and the side
# buttons are named by the screen next to them, as on the Push.
LABELS = {
    c.BUTTON_TAP_TEMPO: "Tap Tempo",
    c.BUTTON_DELETE: "Delete",
    c.BUTTON_UNDO: "Undo",
    c.BUTTON_STOP: "Panic\n(Shift)",
    c.BUTTON_PLAY: "Start/Stop",
    c.BUTTON_SETUP: "Setup",
    c.BUTTON_DEVICE: "Knobs",
    c.BUTTON_MIX: "Mix",
    c.BUTTON_BROWSE: "Profiles",
    c.BUTTON_REPEAT: "Rhythm",
    c.BUTTON_ACCENT: "Accent",
    c.BUTTON_SCALE: "Scale",
    c.BUTTON_LAYOUT: "Layout",
    c.BUTTON_NOTE: "Play",
    c.BUTTON_SESSION: "Life",
    c.BUTTON_OCTAVE_UP: "Octave Up",
    c.BUTTON_OCTAVE_DOWN: "Octave Down",
    c.BUTTON_SHIFT: "Shift",
}
ENCODER_LABELS = {
    c.ENCODER_TEMPO_ENCODER: "Tempo",
    c.ENCODER_SWING_ENCODER: "Swing",
    c.ENCODER_MASTER_ENCODER: "Level",
}

# Layout, in drawing units. The pads and the screen share 8 columns, as on the Push.
COL = 100  # column pitch
PAD = 88  # pad size
LEFT = 300  # x of the first column
TOP = 40
ENC_Y = TOP + 50  # encoder centers
UPPER_Y = TOP + 120
SCREEN_Y = UPPER_Y + 52
SCREEN_H = 8 * COL * HEIGHT / WIDTH
LOWER_Y = SCREEN_Y + SCREEN_H + 12
PADS_Y = LOWER_Y + 70  # top of the top pad row
SIDE_X = LEFT + 8 * COL + 20  # the side (scene) buttons
RIGHT_X = SIDE_X + 110  # the right-hand cluster
SIZE = (RIGHT_X + 220, PADS_Y + 8 * COL + 30)
BTN = (84, 40)  # a small button

# Left column, top to bottom, at the y of the row they sit in.
LEFT_BUTTONS = [
    (c.BUTTON_TAP_TEMPO, 40, UPPER_Y),
    (c.BUTTON_METRONOME, 140, UPPER_Y),
    (c.BUTTON_DELETE, 40, SCREEN_Y + 10),
    (c.BUTTON_UNDO, 40, SCREEN_Y + 70),
    (c.BUTTON_MUTE, 20, LOWER_Y),
    (c.BUTTON_SOLO, 105, LOWER_Y),
    (c.BUTTON_STOP, 190, LOWER_Y),
] + [
    (name, 40, PADS_Y + i * COL + (PAD - BTN[1]) / 2)
    for i, name in enumerate(
        (
            c.BUTTON_CONVERT,
            c.BUTTON_DOUBLE_LOOP,
            c.BUTTON_QUANTIZE,
            c.BUTTON_DUPLICATE,
            c.BUTTON_NEW,
            c.BUTTON_FIXED_LENGTH,
            c.BUTTON_RECORD,
            c.BUTTON_PLAY,
        )
    )
]
RIGHT_BUTTONS = [
    (c.BUTTON_SETUP, RIGHT_X, UPPER_Y),
    (c.BUTTON_USER, RIGHT_X + 100, UPPER_Y),
    (c.BUTTON_ADD_DEVICE, SIDE_X, SCREEN_Y + 10),
    (c.BUTTON_ADD_TRACK, SIDE_X, SCREEN_Y + 70),
    (c.BUTTON_DEVICE, RIGHT_X, SCREEN_Y + 10),
    (c.BUTTON_MIX, RIGHT_X + 100, SCREEN_Y + 10),
    (c.BUTTON_BROWSE, RIGHT_X, SCREEN_Y + 70),
    (c.BUTTON_CLIP, RIGHT_X + 100, SCREEN_Y + 70),
    (c.BUTTON_MASTER, SIDE_X, LOWER_Y),
] + [
    (name, RIGHT_X + (i % 2) * 100, PADS_Y + (2 + i // 2) * COL + (PAD - BTN[1]) / 2)
    for i, name in enumerate(
        (
            c.BUTTON_REPEAT,
            c.BUTTON_ACCENT,
            c.BUTTON_SCALE,
            c.BUTTON_LAYOUT,
            c.BUTTON_NOTE,
            c.BUTTON_SESSION,
            c.BUTTON_OCTAVE_UP,
            c.BUTTON_PAGE_LEFT,
            c.BUTTON_OCTAVE_DOWN,
            c.BUTTON_PAGE_RIGHT,
            c.BUTTON_SHIFT,
            c.BUTTON_SELECT,
        )
    )
]


def _round_rect(ctx: cairo.Context, x: float, y: float, w: float, h: float, r: float) -> None:
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -1.5708, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, 1.5708)
    ctx.arc(x + r, y + h - r, r, 1.5708, 3.1416)
    ctx.arc(x + r, y + r, r, 3.1416, 4.7124)
    ctx.close_path()


def _text(ctx, text: str, cx: float, cy: float, size: float, rgb, fit: float = 0) -> None:
    """Centered text, one line per \\n, shrunk until each line fits `fit` (if given)."""
    ctx.select_font_face(FAMILY, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    lines = text.split("\n")
    if len(lines) > 1:
        size *= 0.8
    ctx.set_font_size(size)
    while fit and size > 9 and max(ctx.text_extents(t).x_advance for t in lines) > fit:
        size -= 0.5
        ctx.set_font_size(size)
    ctx.set_source_rgb(*rgb)
    for i, line in enumerate(lines):
        y = cy + size * 0.36 + (i - (len(lines) - 1) / 2) * size * 1.1
        ctx.move_to(cx - ctx.text_extents(line).x_advance / 2, y)
        ctx.show_text(line)
    ctx.new_path()  # so the next shape doesn't start from the end of the text


def _button(ctx, name: str, x: float, y: float, colors: dict[str, str]) -> None:
    w, h = BTN
    lit = led_rgb(colors.get(name, "black"))
    label = LABELS.get(name)
    _round_rect(ctx, x, y, w, h, 5)
    ctx.set_source_rgb(*CAP)
    ctx.fill_preserve()
    ctx.set_source_rgb(*(lit if lit and label else EDGE))
    ctx.set_line_width(2 if lit and label else 1)
    ctx.stroke()
    if label:
        _text(ctx, label, x + w / 2, y + h / 2, 15, lit if lit else DIM, fit=w - 10)


def _row_button(ctx, x: float, y: float, color: str) -> None:
    """A button above or below the screen: a light bar in its LED color."""
    _round_rect(ctx, x + 6, y, COL - 12, 34, 4)
    ctx.set_source_rgb(*CAP)
    ctx.fill_preserve()
    ctx.set_source_rgb(*EDGE)
    ctx.set_line_width(1)
    ctx.stroke()
    lit = led_rgb(color)
    if lit:
        ctx.rectangle(x + 22, y + 15, COL - 44, 4)
        ctx.set_source_rgb(*lit)
        ctx.fill()


def _encoder(ctx, cx: float, cy: float, label: str | None) -> None:
    ctx.arc(cx, cy, 26, 0, 6.2832)
    ctx.set_source_rgb(*CAP)
    ctx.fill_preserve()
    ctx.set_source_rgb(*EDGE)
    ctx.set_line_width(2)
    ctx.stroke()
    if label:
        _text(ctx, label, cx, cy + 44, 15, TEXT)


def draw_push(ctx: cairo.Context, app) -> None:
    view, pads, colors = app.view(), app.pad_colors(), app.button_colors()
    w, h = SIZE
    _round_rect(ctx, 2, 2, w - 4, h - 4, 18)
    ctx.set_source_rgb(*BODY)
    ctx.fill_preserve()
    ctx.set_source_rgb(*EDGE)
    ctx.set_line_width(2)
    ctx.stroke()

    _encoder(ctx, 82, ENC_Y, ENCODER_LABELS[c.ENCODER_TEMPO_ENCODER])
    _encoder(ctx, 182, ENC_Y, ENCODER_LABELS[c.ENCODER_SWING_ENCODER])
    for i in range(8):
        _encoder(ctx, LEFT + i * COL + COL / 2, ENC_Y, None)
    _encoder(ctx, RIGHT_X + 142, ENC_Y, ENCODER_LABELS[c.ENCODER_MASTER_ENCODER])

    for i in range(8):
        _row_button(ctx, LEFT + i * COL, UPPER_Y, colors.get(f"Upper Row {i + 1}", "black"))
        _row_button(ctx, LEFT + i * COL, LOWER_Y, colors.get(f"Lower Row {i + 1}", "black"))

    screen = preview.render(view)
    ctx.save()
    ctx.translate(LEFT, SCREEN_Y)
    ctx.scale(8 * COL / WIDTH, 8 * COL / WIDTH)
    ctx.set_source_surface(screen, 0, 0)
    ctx.paint()
    ctx.restore()
    ctx.rectangle(LEFT, SCREEN_Y, 8 * COL, SCREEN_H)
    ctx.set_source_rgb(*EDGE)
    ctx.set_line_width(1)
    ctx.stroke()

    for row in range(8):  # row 0 is the bottom row
        for col in range(8):
            x, y = LEFT + col * COL + 6, PADS_Y + (7 - row) * COL
            _round_rect(ctx, x, y, PAD, PAD, 8)
            ctx.set_source_rgb(*(led_rgb(pads[row][col]) or CAP))
            ctx.fill()

    strip_x = 190
    _round_rect(ctx, strip_x, PADS_Y, 60, 8 * COL - 12, 8)
    ctx.set_source_rgb(*CAP)
    ctx.fill_preserve()
    ctx.set_source_rgb(*EDGE)
    ctx.set_line_width(1)
    ctx.stroke()
    ctx.save()
    ctx.translate(strip_x + 30, PADS_Y + 4 * COL)
    ctx.rotate(-1.5708)
    _text(ctx, "Touch strip", 0, 0, 15, DIM)
    ctx.restore()

    for i, name in enumerate(SCENE_BUTTONS):
        x, y = SIDE_X, PADS_Y + i * COL + (PAD - BTN[1]) / 2
        lit = led_rgb(colors.get(name, "black"))
        _round_rect(ctx, x, y, BTN[0], BTN[1], 5)
        ctx.set_source_rgb(*CAP)
        ctx.fill_preserve()
        ctx.set_source_rgb(*(lit or EDGE))
        ctx.set_line_width(2 if lit else 1)
        ctx.stroke()
        if lit:
            ctx.rectangle(x + 14, y + BTN[1] / 2 - 2, BTN[0] - 28, 4)
            ctx.fill()

    for name, x, y in LEFT_BUTTONS + RIGHT_BUTTONS:
        _button(ctx, name, x, y, colors)


def draw_svg(app, path: Path) -> None:
    surface = cairo.SVGSurface(str(path), *SIZE)
    surface.set_document_unit(cairo.SVGUnit.PX)
    draw_push(cairo.Context(surface), app)
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


def _setup(app) -> None:
    app.button_pressed(c.BUTTON_SETUP)
    app.encoder_rotated("Track2 Encoder", -6 * 4)  # softer Dynamics
    app.pad_pressed(0, 0, 87)


# scene -> (what to do on a fresh app, the profile it loads)
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
}


def main() -> None:
    use_bundled_fonts()  # the same font as on the Push
    docs = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent.parent / "docs")
    push_dir, screen_dir = docs / "images" / "push", docs / "images" / "screens"
    push_dir.mkdir(parents=True, exist_ok=True)
    screen_dir.mkdir(parents=True, exist_ok=True)
    for name, (scene, profile) in SCENES.items():
        with tempfile.TemporaryDirectory() as tmp:
            app = preview._app(Path(tmp), profile)
            scene(app)
            draw_svg(app, push_dir / f"{name}.svg")
            app.close()  # joins the state saver before the temp folder is removed
    # Random velocity and standby draw from unseeded generators: seed them all the same,
    # so re-running this only changes the images when the app does.
    unseeded = random.Random.seed
    random.Random.seed = lambda rng, a=None, version=2: unseeded(rng, a or 0, version)
    try:
        views = preview.sample_views()
    finally:
        random.Random.seed = unseeded
    for name in SCREENS:
        preview.render(views[name]).write_to_png(str(screen_dir / f"{name}.png"))
    print(f"wrote {len(SCENES)} drawings to {push_dir}/")
    print(f"wrote {len(SCREENS)} screens to {screen_dir}/")


if __name__ == "__main__":
    main()
