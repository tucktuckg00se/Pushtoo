"""Screen drawing from plain view dicts. Runs in the renderer process only.

Layout follows the PRD's 8-column grid: a 24 px top band for upper-button labels,
112 px of content, a 24 px bottom band for lower-button labels, 120 px per column.
A page's encoder controls draw in their own columns, and the mode's content panel
fills the columns to their right.
"""

import math
import time

import cairo

from pushtoo.hw.colors import BACKGROUND, PLAY_ACCENT, TEXT, TEXT_DIM
from pushtoo.ui.controls import COLUMNS, middle_ellipsis

WIDTH, HEIGHT = 960, 160
COLUMN = 120
BAND = 24
FONT = "IBM Plex Sans Condensed"  # cairo falls back to the default sans if missing
ACCENTS = {"play": PLAY_ACCENT}
ARC_TRACK = (0.22, 0.22, 0.25)
ARC_START = math.radians(135)  # 270-degree arc from 7:30 to 4:30
ARC_SWEEP = math.radians(270)
ARC_TOP = math.radians(270)  # 12 o'clock, where bipolar controls start filling


def _font(ctx: cairo.Context, size: float, bold: bool) -> None:
    weight = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, weight)
    ctx.set_font_size(size)


def _fit(ctx: cairo.Context, text: str, max_width: float, size: float, bold=False) -> str:
    """Shorten text from the middle until it fits max_width pixels."""
    _font(ctx, size, bold)
    chars = len(text)
    while chars > 3 and ctx.text_extents(text).x_advance > max_width:
        chars -= 1
        text = middle_ellipsis(text, chars)
    return text


def _text(ctx: cairo.Context, text: str, x: float, y: float, size: float, color, bold=False):
    _font(ctx, size, bold)
    ctx.set_source_rgb(*color)
    ctx.move_to(x, y)
    ctx.show_text(text)


def _centered(ctx: cairo.Context, text: str, cx: float, y: float, size: float, color, bold=False):
    _font(ctx, size, bold)
    extents = ctx.text_extents(text)
    _text(ctx, text, cx - extents.x_advance / 2, y, size, color, bold)


def _band_label(ctx: cairo.Context, col: int, item: dict | None, top: bool, accent) -> None:
    """A button label in the top or bottom band; selected labels invert."""
    if item is None:
        return
    x = col * COLUMN
    y = 0 if top else HEIGHT - BAND
    if item["selected"]:
        ctx.set_source_rgb(*accent)
        ctx.rectangle(x + 2, y, COLUMN - 4, BAND)
        ctx.fill()
    color = BACKGROUND if item["selected"] else TEXT
    label = _fit(ctx, item["label"], COLUMN - 10, 14, item["selected"])
    _centered(ctx, label, x + COLUMN / 2, y + 17, 14, color, item["selected"])


def _arc(ctx, cx, cy, radius, width, fraction, bipolar, accent) -> None:
    ctx.new_path()  # otherwise arc() connects from where the last text ended
    ctx.set_line_width(width)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgb(*ARC_TRACK)
    ctx.arc(cx, cy, radius, ARC_START, ARC_START + ARC_SWEEP)
    ctx.stroke()
    value_angle = ARC_START + ARC_SWEEP * fraction
    start, end = (ARC_TOP, value_angle) if bipolar else (ARC_START, value_angle)
    if end < start:
        start, end = end, start
    if end - start > 0.01:
        ctx.set_source_rgb(*accent)
        ctx.arc(cx, cy, radius, start, end)
        ctx.stroke()


def _control(ctx: cairo.Context, col: int, control: dict, accent) -> None:
    cx = col * COLUMN + COLUMN / 2
    _centered(ctx, _fit(ctx, control["name"], COLUMN - 12, 14), cx, 42, 14, TEXT_DIM)
    _arc(ctx, cx, 80, 22, 5, control["fraction"], control["bipolar"], accent)
    value = _fit(ctx, control["text"], COLUMN - 8, 16, True)
    _centered(ctx, value, cx, 128, 16, TEXT, True)


def _peek(ctx: cairo.Context, control: dict, accent) -> None:
    _arc(ctx, 80, 82, 36, 8, control["fraction"], control["bipolar"], accent)
    _text(ctx, control["name"], 150, 56, 20, TEXT_DIM)
    _text(ctx, _fit(ctx, control["text"], WIDTH - 170, 48, True), 150, 112, 48, TEXT, True)


def _shift_overlay(ctx: cairo.Context, lines: list[str], accent) -> None:
    _text(ctx, "Shift", 16, 50, 20, accent, bold=True)
    for i, line in enumerate(lines):
        _text(ctx, line, 16, 80 + i * 24, 18, TEXT)


def _panel_keyboard(ctx, panel, x0, width, accent) -> None:
    _text(ctx, panel["title"], x0 + 16, 44, 14, TEXT_DIM)
    key = _fit(ctx, panel["key_name"], width / 2 - 24, 34, True)
    _text(ctx, key, x0 + 16, 84, 34, accent, True)
    details = ["In key" if panel["in_key"] else "Chromatic", f"Ch {panel['channel'] + 1}"]
    _details(ctx, panel, details, x0, width)
    _notes_or_hint(ctx, panel, x0 + width / 2, width / 2)


def _panel_drums(ctx, panel, x0, width, accent) -> None:
    _text(ctx, panel["title"], x0 + 16, 44, 14, TEXT_DIM)
    name = _fit(ctx, panel["last_hit"] or "Drums", width / 2 - 24, 34, True)
    _text(ctx, name, x0 + 16, 84, 34, accent, True)
    _details(ctx, panel, [f"Ch {panel['channel'] + 1}"], x0, width)
    _notes_or_hint(ctx, panel, x0 + width / 2, width / 2)


def _details(ctx, panel, parts: list[str], x0, width) -> None:
    parts = [*parts, panel["destination"]]
    if panel["accent"]:
        parts.append("Accent")
    _text(ctx, _fit(ctx, " · ".join(parts), width - 32, 16), x0 + 16, 116, 16, TEXT)


def _notes_or_hint(ctx, panel, x0, width) -> None:
    if panel["held"]:
        held = _fit(ctx, "  ".join(panel["held"]), width - 16, 28, True)
        _text(ctx, held, x0, 84, 28, TEXT, True)
    elif panel["first_run"]:
        _text(ctx, "Play any pad", x0, 70, 22, TEXT)
        hint = _fit(ctx, "Select “Pushtoo Out” in your DAW", width - 16, 15)
        _text(ctx, hint, x0, 94, 15, TEXT_DIM)


def _panel_scale_selector(ctx, panel, x0, width, accent) -> None:
    # Scale names get two columns ("Major Pentatonic" is wider than one).
    scales = panel["scale_names"]
    index = scales.index(panel["scale"])
    _text(ctx, "Scale", 16, 44, 14, TEXT_DIM)
    for offset in (-1, 0, 1):
        i = index + offset
        if 0 <= i < len(scales):
            selected = offset == 0
            color = accent if selected else TEXT_DIM
            _text(ctx, scales[i], 16, 92 + offset * 24, 20, color, bold=selected)
    _text(ctx, "Root", 2 * COLUMN + 16, 44, 14, TEXT_DIM)
    _text(ctx, panel["root_name"], 2 * COLUMN + 16, 100, 34, accent, bold=True)
    hint = "Buttons or encoder 2: root · Encoder 1: scale · Scale: close"
    hint = _fit(ctx, hint, WIDTH - 3 * COLUMN - 32, 15)
    _text(ctx, hint, 3 * COLUMN + 16, 98, 15, TEXT_DIM)


PANELS = {
    "keyboard": _panel_keyboard,
    "drums": _panel_drums,
    "scale_selector": _panel_scale_selector,
}


def _toast(ctx: cairo.Context, text: str) -> None:
    ctx.set_source_rgb(*BACKGROUND)
    ctx.rectangle(0, BAND, WIDTH, HEIGHT - 2 * BAND)
    ctx.fill()
    _centered(ctx, _fit(ctx, text, WIDTH - 32, 48, True), WIDTH / 2, 98, 48, TEXT, bold=True)


def draw_view(ctx: cairo.Context, view: dict, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    accent = ACCENTS.get(view.get("accent"), PLAY_ACCENT)
    ctx.set_source_rgb(*BACKGROUND)
    ctx.paint()

    for col in range(COLUMNS):
        _band_label(ctx, col, view["upper"][col], top=True, accent=accent)
        _band_label(ctx, col, view["lower"][col], top=False, accent=accent)

    if view.get("peek"):
        _peek(ctx, view["peek"], accent)
    elif view.get("shift"):
        _shift_overlay(ctx, view["shift"], accent)
    else:
        controls = view["controls"]
        used = [i for i, control in enumerate(controls) if control is not None]
        for col in used:
            _control(ctx, col, controls[col], accent)
        x0 = (max(used) + 1) * COLUMN if used else 0
        panel = view.get("panel")
        if panel and panel["kind"] in PANELS and x0 < WIDTH:
            PANELS[panel["kind"]](ctx, panel, x0, WIDTH - x0, accent)

    if view.get("toast") and view.get("toast_until", 0) > now:
        _toast(ctx, view["toast"])
