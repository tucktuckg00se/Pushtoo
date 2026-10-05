"""Screen drawing from plain view dicts. Runs in the renderer process only.

Layout follows the PRD's 8-column grid: a 24 px top band for upper-button labels,
112 px of content, a 24 px bottom band for lower-button labels, 120 px per column.
A page's encoder controls draw in their own columns, and the mode's content panel
fills the columns to their right.
"""

import math
import time

import cairo

from pushtoo.theme import (
    ARC_TRACK,
    BACKGROUND,
    BODY,
    HEADING,
    LABEL,
    PEEK,
    TEXT,
    TEXT_DIM,
    TITLE,
    VALUE,
    accent_name,
    rgb,
)
from pushtoo.ui.controls import COLUMNS, middle_ellipsis

WIDTH, HEIGHT = 960, 160
COLUMN = 120
BAND = 24
FONT = "IBM Plex Sans Condensed"  # cairo falls back to the default sans if missing
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
    if not item["label"]:
        return  # an unlabeled button only shows its LED color
    color = BACKGROUND if item["selected"] else TEXT
    label = _fit(ctx, item["label"], COLUMN - 10, LABEL, item["selected"])
    _centered(ctx, label, x + COLUMN / 2, y + 17, LABEL, color, item["selected"])


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
    accent = rgb(control["color"]) if control.get("color") else accent
    cx = col * COLUMN + COLUMN / 2
    _centered(ctx, _fit(ctx, control["name"], COLUMN - 12, LABEL), cx, 42, LABEL, TEXT_DIM)
    _arc(ctx, cx, 80, 22, 5, control["fraction"], control["bipolar"], accent)
    value = _fit(ctx, control["text"], COLUMN - 8, BODY, True)
    _centered(ctx, value, cx, 128, BODY, TEXT, True)


def _peek(ctx: cairo.Context, control: dict, accent) -> None:
    accent = rgb(control["color"]) if control.get("color") else accent
    _arc(ctx, 80, 82, 36, 8, control["fraction"], control["bipolar"], accent)
    _text(ctx, control["name"], 150, 56, VALUE, TEXT_DIM)
    _text(ctx, _fit(ctx, control["text"], WIDTH - 170, PEEK, True), 150, 112, PEEK, TEXT, True)


def _shift_overlay(ctx: cairo.Context, lines: list[str], accent) -> None:
    _text(ctx, "Shift", 16, 50, VALUE, accent, bold=True)
    # Two columns of two, so four actions fit above the bottom band.
    for i, line in enumerate(lines[:4]):
        x = 16 + (i // 2) * (WIDTH // 2)
        line = _fit(ctx, line, WIDTH / 2 - 32, BODY + 2)
        _text(ctx, line, x, 86 + (i % 2) * 28, BODY + 2, TEXT)


def _panel_keyboard(ctx, panel, x0, width, accent) -> None:
    _text(ctx, panel["title"], x0 + 16, 44, LABEL, TEXT_DIM)
    key = _fit(ctx, panel["key_name"], width / 2 - 24, TITLE, True)
    _text(ctx, key, x0 + 16, 84, TITLE, accent, True)
    details = ["In key" if panel["in_key"] else "Chromatic", f"Ch {panel['channel'] + 1}"]
    _details(ctx, panel, details, x0, width)
    _notes_or_hint(ctx, panel, x0 + width / 2, width / 2)


def _panel_drums(ctx, panel, x0, width, accent) -> None:
    _text(ctx, panel["title"], x0 + 16, 44, LABEL, TEXT_DIM)
    name = _fit(ctx, panel["last_hit"] or "Drums", width / 2 - 24, TITLE, True)
    _text(ctx, name, x0 + 16, 84, TITLE, accent, True)
    _details(ctx, panel, [f"Ch {panel['channel'] + 1}"], x0, width)
    _notes_or_hint(ctx, panel, x0 + width / 2, width / 2)


def _details(ctx, panel, parts: list[str], x0, width) -> None:
    parts = [*parts, panel["destination"]]
    if panel["accent"]:
        parts.append("Accent")
    _text(ctx, _fit(ctx, " · ".join(parts), width - 32, BODY), x0 + 16, 116, BODY, TEXT)


def _notes_or_hint(ctx, panel, x0, width) -> None:
    if panel["held"]:
        held = _fit(ctx, "  ".join(panel["held"]), width - 16, HEADING, True)
        _text(ctx, held, x0, 84, HEADING, TEXT, True)
    elif panel["first_run"]:
        _text(ctx, "Play any pad", x0, 70, VALUE + 2, TEXT)
        hint = _fit(ctx, "Select “Pushtoo Out” in your DAW", width - 16, BODY - 1)
        _text(ctx, hint, x0, 94, BODY - 1, TEXT_DIM)


def _panel_scale_selector(ctx, panel, x0, width, accent) -> None:
    # Scale names get two columns ("Major Pentatonic" is wider than one).
    scales = panel["scale_names"]
    index = scales.index(panel["scale"])
    _text(ctx, "Scale", 16, 44, LABEL, TEXT_DIM)
    for offset in (-1, 0, 1):
        i = index + offset
        if 0 <= i < len(scales):
            selected = offset == 0
            color = accent if selected else TEXT_DIM
            _text(ctx, scales[i], 16, 92 + offset * 24, VALUE, color, bold=selected)
    _text(ctx, "Root", 2 * COLUMN + 16, 44, LABEL, TEXT_DIM)
    _text(ctx, panel["root_name"], 2 * COLUMN + 16, 100, TITLE, accent, bold=True)
    hint = "Buttons or encoder 2: root · Encoder 1: scale · Scale: close"
    hint = _fit(ctx, hint, WIDTH - 3 * COLUMN - 32, BODY - 1)
    _text(ctx, hint, 3 * COLUMN + 16, 98, BODY - 1, TEXT_DIM)


def _panel_chord(ctx, panel, x0, width, accent) -> None:
    _text(ctx, panel["title"], x0 + 16, 44, LABEL, TEXT_DIM)
    name = panel["chord_name"]
    if name is None:
        _text(ctx, "Tap any pad", x0 + 16, 84, TITLE, accent, True)
        hint = "Every pad is a chord in your key · bottom row: bass notes"
        _text(ctx, _fit(ctx, hint, width - 32, BODY), x0 + 16, 116, BODY, TEXT_DIM)
        return
    color = accent if panel["sounding"] else TEXT_DIM
    _text(ctx, _fit(ctx, name, width * 0.45, TITLE, True), x0 + 16, 84, TITLE, color, True)
    right = x0 + width * 0.5
    label = f"{panel['role_line']} · {panel['voicing']}"
    _text(ctx, _fit(ctx, label, width * 0.5 - 16, BODY), right, 64, BODY, TEXT)
    notes = _fit(ctx, " ".join(panel["notes"]), width * 0.5 - 16, BODY)
    _text(ctx, notes, right, 88, BODY, TEXT_DIM)
    parts = [panel["key_name"], f"Ch {panel['channel'] + 1}", panel["destination"]]
    if panel["parent"]:
        parts.insert(1, panel["parent"])
    if panel["strum"]:
        parts.insert(0, "Strum the touch strip")
    if panel["latch"]:
        parts.insert(0, "Latch")
    if panel["accent"]:
        parts.append("Accent")
    _text(ctx, _fit(ctx, " · ".join(parts), width - 32, BODY), x0 + 16, 116, BODY, TEXT)


def _panel_knobs(ctx, panel, x0, width, accent) -> None:
    _text(ctx, panel["title"], x0 + 16, 44, LABEL, TEXT_DIM)
    dest = _fit(ctx, f"Sending to {panel['destination']}", width - 32, BODY)
    _text(ctx, dest, x0 + 16, 84, BODY, TEXT)
    hint = _fit(ctx, "Shift + upper button: Learn Assist", width - 32, BODY - 1)
    _text(ctx, hint, x0 + 16, 110, BODY - 1, TEXT_DIM)


def _panel_browse(ctx, panel, x0, width, accent) -> None:
    _text(ctx, panel["title"], x0 + 16, 44, LABEL, TEXT_DIM)
    names, selected = panel["names"], panel["selected"]
    if not names:
        _text(ctx, "No profiles found", x0 + 16, 84, VALUE, TEXT)
        return
    for offset in (-1, 0, 1):
        i = selected + offset
        if 0 <= i < len(names):
            label = names[i] + ("  (active)" if names[i] == panel["active"] else "")
            color = accent if offset == 0 else TEXT_DIM
            label = _fit(ctx, label, width - 32, VALUE, offset == 0)
            _text(ctx, label, x0 + 16, 88 + offset * 26, VALUE, color, bold=offset == 0)


PANELS = {
    "keyboard": _panel_keyboard,
    "drums": _panel_drums,
    "scale_selector": _panel_scale_selector,
    "chord": _panel_chord,
    "knobs": _panel_knobs,
    "browse": _panel_browse,
}


def _wrap(ctx: cairo.Context, text: str, max_width: float, size: float, max_lines: int):
    """Greedy word wrap; the last line is shortened if the text still doesn't fit."""
    _font(ctx, size, False)
    lines: list[str] = []
    for word in text.split():
        candidate = f"{lines[-1]} {word}" if lines else word
        if lines and ctx.text_extents(candidate).x_advance <= max_width:
            lines[-1] = candidate
        else:
            lines.append(word)
    if len(lines) > max_lines:
        lines = [*lines[: max_lines - 1], " ".join(lines[max_lines - 1 :])]
    return [_fit(ctx, line, max_width, size) for line in lines]


def _toast(ctx: cairo.Context, text: str) -> None:
    ctx.set_source_rgb(*BACKGROUND)
    ctx.rectangle(0, BAND, WIDTH, HEIGHT - 2 * BAND)
    ctx.fill()
    _font(ctx, PEEK, True)
    if ctx.text_extents(text).x_advance <= WIDTH - 32:
        _centered(ctx, text, WIDTH / 2, 98, PEEK, TEXT, bold=True)
        return
    # Long messages (profile errors) wrap at a readable size instead of being cut.
    lines = _wrap(ctx, text, WIDTH - 32, VALUE, max_lines=3)
    top = 80 - (len(lines) - 1) * 13
    for i, line in enumerate(lines):
        _text(ctx, line, 16, top + i * 26, VALUE, TEXT)


def draw_view(ctx: cairo.Context, view: dict, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    accent = rgb(accent_name(view.get("accent", "play")))
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
