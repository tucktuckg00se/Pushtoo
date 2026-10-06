"""Screen drawing from plain view dicts. Runs in the renderer process only.

Layout follows the PRD's 8-column grid: a 24 px top band for upper-button labels,
112 px of content, a 24 px bottom band for lower-button labels, 120 px per column.
A page's encoder controls draw in their own columns, and the mode's content panel
fills the columns to their right.

Every control gets a screen element nearest to it, in its LED's color: the bands for
the buttons above and below, the columns for the encoders, and in the Chord layout a
rail in the last column for the side buttons just right of the screen, plus a small
map of the pads.
"""

import math
import time

import cairo

from pushtoo.fonts import FAMILY
from pushtoo.theme import (
    BODY,
    DEFAULT_THEME,
    HEADING,
    LABEL,
    PEEK,
    SMALL,
    TITLE,
    VALUE,
    Theme,
    accent_name,
)
from pushtoo.ui.controls import COLUMNS, middle_ellipsis

WIDTH, HEIGHT = 960, 160
# The theme's colors as cairo RGB, set by draw_view for the frame being drawn. The
# renderer draws one frame at a time, so a module-level palette is safe.
_c: dict[str, tuple[float, float, float]] = {}
COLUMN = 120
BAND = 24
FONT = FAMILY  # bundled (pushtoo/fonts); the renderer points fontconfig at it
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
    color = _c["background"] if item["selected"] else _c["text"]
    label = _fit(ctx, item["label"], COLUMN - 10, LABEL, item["selected"])
    _centered(ctx, label, x + COLUMN / 2, y + 17, LABEL, color, item["selected"])


def _arc(ctx, cx, cy, radius, width, fraction, bipolar, accent) -> None:
    ctx.new_path()  # otherwise arc() connects from where the last text ended
    ctx.set_line_width(width)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgb(*_c["track"])
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


def _control(ctx: cairo.Context, col: int, control: dict, accent, touched=False) -> None:
    """An encoder's column. Touched, it grows a little (bigger arc, brighter name,
    larger value) so you can see which knob your finger is on, without hiding the
    rest of the screen."""
    accent = _c[control["color"]] if control.get("color") else accent
    cx = col * COLUMN + COLUMN / 2
    name_color = _c["text"] if touched else _c["text_dim"]
    _centered(ctx, _fit(ctx, control["name"], COLUMN - 12, LABEL), cx, 42, LABEL, name_color)
    cy, radius, width, size, baseline = (
        (84, 30, 7, VALUE, 133) if touched else (80, 22, 5, BODY, 128)
    )
    _arc(ctx, cx, cy, radius, width, control["fraction"], control["bipolar"], accent)
    value = _fit(ctx, control["text"], COLUMN - 8, size, True)
    _centered(ctx, value, cx, baseline, size, _c["text"], True)
    if control.get("badges"):
        _badges(ctx, control["badges"], cx, cy)


def _badges(ctx: cairo.Context, badges: list, cx: float, cy: float) -> None:
    """Chips inside the arc, lit in the color of the hardware they mirror."""
    size, gap = 14, 3
    x = cx - (len(badges) * (size + gap) - gap) / 2
    for label, color in badges:
        ctx.rectangle(x + 0.5, cy - size / 2 + 0.5, size - 1, size - 1)
        if color:
            ctx.set_source_rgb(*_c[color])
            ctx.fill()
        else:
            ctx.set_source_rgb(*_c["track"])
            ctx.set_line_width(1)
            ctx.stroke()
        text_color = _c["background"] if color else _c["text_dim"]
        _centered(ctx, label, x + size / 2, cy + 4.5, SMALL, text_color, True)
        x += size + gap


def _side_knob(ctx: cairo.Context, control: dict, accent) -> None:
    """Tempo, Swing or Master: knobs beside the display, not above a column, so they
    show as a touched knob in the edge column nearest them."""
    col = 0 if control["side"] == "left" else COLUMNS - 1
    ctx.set_source_rgb(*_c["background"])
    ctx.rectangle(col * COLUMN, BAND, COLUMN, HEIGHT - 2 * BAND)
    ctx.fill()
    _control(ctx, col, control, accent, touched=True)


def _overlay(ctx: cairo.Context, overlay: dict, accent) -> None:
    """What a held modifier button (Shift, Delete) does, listed while it's held."""
    _text(ctx, overlay["title"], 16, 50, VALUE, accent, bold=True)
    # Two columns of two, so four actions fit above the bottom band.
    for i, line in enumerate(overlay["lines"][:4]):
        x = 16 + (i // 2) * (WIDTH // 2)
        line = _fit(ctx, line, WIDTH / 2 - 32, BODY + 2)
        _text(ctx, line, x, 86 + (i % 2) * 28, BODY + 2, _c["text"])


def _layout_title(ctx, panel, x) -> float:
    """The current layout's name (holding Layout lists them all). Returns where the
    title ends."""
    _text(ctx, panel["layout"], x, 44, LABEL, _c["text_dim"])
    return x + ctx.text_extents(panel["layout"]).x_advance


def status_parts(panel: dict) -> list[str]:
    """The details line: state that changes what your hands do, not settings. Channels,
    the usual destination and the strip mode live on their own pages."""
    parts = []
    if panel["kind"] == "chord":
        parts.append(panel["key_name"])  # the whole grid is built from the key
        if panel["parent"]:
            parts.append(panel["parent"])
        if panel["octave_moved"]:
            parts.append(f"Oct {panel['octave']}")
        if panel["strum"]:
            parts.append("Strum the strip")
        if panel["timing"]:
            parts.append(panel["timing"])
    elif panel["kind"] == "keyboard":
        if panel.get("over"):
            parts.append(f"over {panel['over']}")
        if not panel["in_key"]:
            parts.append("Chromatic")
    if panel.get("random_velocity"):
        parts.append("Random velocity")
    if panel["accent"]:
        parts.append("Accent")
    if not panel["default_destination"]:
        parts.append(f"→ {panel['destination']}")  # otherwise a silent DAW is a mystery
    parts += [text for text in (panel.get("rhythm"), panel.get("tempo")) if text]
    return parts


def _panel_keyboard(ctx, panel, x0, width, accent) -> None:
    _layout_title(ctx, panel, x0 + 16)
    key = _fit(ctx, panel["key_name"], width / 2 - 24, TITLE, True)
    _text(ctx, key, x0 + 16, 84, TITLE, accent, True)
    _details(ctx, panel, x0, width)
    _notes_or_hint(ctx, panel, x0 + width / 2, width / 2)


def _panel_drums(ctx, panel, x0, width, accent) -> None:
    _layout_title(ctx, panel, x0 + 16)
    name = _fit(ctx, panel["last_hit"] or "Drums", width / 2 - 24, TITLE, True)
    _text(ctx, name, x0 + 16, 84, TITLE, accent, True)
    _details(ctx, panel, x0, width)
    _notes_or_hint(ctx, panel, x0 + width / 2, width / 2)


def _details(ctx, panel, x0, width) -> None:
    parts = status_parts(panel)
    _text(ctx, _fit(ctx, " · ".join(parts), width - 32, BODY), x0 + 16, 116, BODY, _c["text"])


def _notes_or_hint(ctx, panel, x0, width) -> None:
    if panel["held"]:
        held = _fit(ctx, "  ".join(panel["held"]), width - 16, HEADING, True)
        _text(ctx, held, x0, 84, HEADING, _c["text"], True)
    elif panel["first_run"]:
        _text(ctx, "Play any pad", x0, 70, VALUE + 2, _c["text"])
        if panel["default_destination"]:  # a hardware port needs no DAW
            hint = _fit(ctx, "Select “Pushtoo Out” in your DAW", width - 16, BODY - 1)
            _text(ctx, hint, x0, 94, BODY - 1, _c["text_dim"])


def _panel_scale_selector(ctx, panel, x0, width, accent) -> None:
    """Each value above its encoder: Scale, Root, Chords (the chord grid's set)."""
    _choice_list(ctx, "Scale", panel["scale_names"], panel["scale"], 0, accent)
    _text(ctx, "Root", COLUMN + 8, 44, LABEL, _c["text_dim"])
    _text(ctx, panel["root_name"], COLUMN + 8, 100, TITLE, accent, bold=True)
    _choice_list(ctx, "Chords", panel["chord_sets"], panel["chord_set"], 2, accent)
    hint = "Buttons: root · Scale: close"
    hint = _fit(ctx, hint, WIDTH - 3 * COLUMN - 24, BODY - 1)
    _text(ctx, hint, 3 * COLUMN + 16, 98, BODY - 1, _c["text_dim"])


def _choice_list(ctx, title, names, current, col, accent) -> None:
    """A column's list: the one before and after dim, the current one large; a long
    name wraps onto two lines rather than spilling into the next encoder's column."""
    x, width = col * COLUMN + 8, COLUMN - 12
    index = names.index(current)
    _text(ctx, title, x, 44, LABEL, _c["text_dim"])
    if index > 0:
        _text(ctx, _fit(ctx, names[index - 1], width, BODY), x, 64, BODY, _c["text_dim"])
    lines = _wrap(ctx, current, width, BODY + 2, max_lines=2)
    for i, line in enumerate(lines):
        _text(ctx, _fit(ctx, line, width, BODY + 2, True), x, 88 + i * 19, BODY + 2, accent, True)
    if index + 1 < len(names):
        below = 88 + len(lines) * 19 + 4
        _text(ctx, _fit(ctx, names[index + 1], width, BODY), x, below, BODY, _c["text_dim"])


CHORD_LEGEND = (  # (label, theme token)
    ("home", "home"),
    ("away", "away"),
    ("tension", "tension"),
    ("borrowed", "borrowed"),
    ("leads to", "secondary"),
)
CELL, PITCH = 12, 13  # pad map cell size and spacing
MAP_LABELS = 64  # width of the row-name column beside the pad map
MAP_MIN_PANEL = 420  # narrower chord panels leave the map out


def _led_rgb(name: str) -> tuple[float, float, float]:
    """Screen color of an LED palette name ("pt_<token>")."""
    return _c.get(name.removeprefix("pt_"), _c["track"])  # anything else is off


def _pad_map(ctx, panel, x, y) -> None:
    """The pads in miniature, in their own colors, with each row's chord kind beside
    it. The sounding row's name lights up."""
    for row, line in enumerate(panel["grid"]):
        top = y + (len(panel["grid"]) - 1 - row) * PITCH
        for col, name in enumerate(line):
            ctx.set_source_rgb(*_led_rgb(name))
            ctx.rectangle(x + col * PITCH, top, CELL, CELL)
            ctx.fill()
        current = row == panel["row"]
        label = _fit(ctx, panel["row_names"][row], MAP_LABELS - 4, SMALL, current)
        color = _c["text"] if current else _c["text_dim"]
        _text(ctx, label, x + 8 * PITCH + 4, top + 10, SMALL, color, current)


def _legend(ctx, x, y, max_x) -> None:
    for label, color in CHORD_LEGEND:
        _font(ctx, SMALL, False)
        width = 14 + ctx.text_extents(label).x_advance
        if x + width > max_x:
            return
        ctx.set_source_rgb(*_c[color])
        ctx.rectangle(x, y - 9, 10, 10)
        ctx.fill()
        _text(ctx, label, x + 14, y, SMALL, _c["text"])
        x += width + 12


def _rail(ctx: cairo.Context, rail: list[dict], accent) -> None:
    """The side buttons sit just right of the screen; this column names them, top to
    bottom, lit like their LEDs. A held voicing is white, the kept one the accent."""
    x0 = WIDTH - COLUMN
    row = HEIGHT / len(rail)
    ctx.set_source_rgb(*_c["line"])
    ctx.rectangle(x0, 0, 1, HEIGHT)
    for i, entry in enumerate(rail):
        if entry.get("apart"):  # a different kind of button, like Latch below voicings
            ctx.rectangle(x0 + 8, row * i, COLUMN - 16, 1)
    ctx.fill()
    fills = {"kept": accent, "held": _c["text"], "latch_on": _c["latch"], "rate": _c["rate"]}
    for i, entry in enumerate(rail):
        top = i * row
        fill = fills.get(entry["state"])
        if fill:
            ctx.set_source_rgb(*fill)
            ctx.rectangle(x0 + 4, top + 2, COLUMN - 8, row - 3)
            ctx.fill()
        color = _c["background"] if fill else _c["text"]
        _text(ctx, entry["label"], x0 + 12, top + row / 2 + 5, LABEL, color, bool(fill))
        # A small arrow pointing at the button.
        cy = top + row / 2
        ctx.set_source_rgb(*(_c["background"] if fill else _c["text_dim"]))
        ctx.move_to(WIDTH - 16, cy - 4)
        ctx.line_to(WIDTH - 10, cy)
        ctx.line_to(WIDTH - 16, cy + 4)
        ctx.close_path()
        ctx.fill()


def _panel_chord(ctx, panel, x0, width, accent) -> None:
    if panel.get("main", True) and width >= MAP_MIN_PANEL:
        _pad_map(ctx, panel, x0 + 12, 28)
        x = x0 + 12 + 8 * PITCH + MAP_LABELS + 8
    else:  # settings pages show the chord, not the grid
        x = x0 + 16
    width = x0 + width - x - 12
    title_end = _layout_title(ctx, panel, x)
    if panel["latched"]:
        # Right of the title, shortened where the panel is narrow; the rail's amber
        # Latch row still says it if even "Latched" doesn't fit.
        _font(ctx, LABEL, True)
        for latched in ("Latched · tap it again to stop", "Latched"):
            right = x + width - ctx.text_extents(latched).x_advance
            if right >= title_end + 16:
                _text(ctx, latched, right, 44, LABEL, _c["latch"], True)
                break

    details = _fit(ctx, " · ".join(status_parts(panel)), width, BODY)

    name, role_line, notes = panel["chord_name"], None, panel["notes"]
    if panel["bass_note"] and not panel["sounding"]:
        bass_line = f"Bass note · Ch {panel['bass_channel'] + 1}"
        name, role_line, notes = panel["bass_note"], bass_line, []
    elif name is not None:
        role_line = f"{panel['role_line']} · {panel['voicing']}"
    if name is None:
        _text(ctx, "Tap any pad", x, 78, HEADING, accent, True)
        _legend(ctx, x, 101, x + width)
        _text(ctx, details, x, 126, BODY, _c["text"])
        return
    color = accent if panel["sounding"] or panel["bass_note"] else _c["text_dim"]
    _text(ctx, _fit(ctx, name, width * 0.4, TITLE, True), x, 84, TITLE, color, True)
    right = x + width * 0.42
    _text(ctx, _fit(ctx, role_line, width * 0.58, BODY), right, 64, BODY, _c["text"])
    _notes_with_velocity(ctx, notes, panel.get("velocities") or [], right, width * 0.58, accent)
    _text(ctx, details, x, 116, BODY, _c["text"])


def _notes_with_velocity(ctx, notes, velocities, x, width, accent) -> None:
    """The chord's notes, each with a bar beneath it as long as its velocity, so a
    Random chord looks as uneven as it sounds."""
    _font(ctx, BODY, False)
    gap = ctx.text_extents(" ").x_advance
    widths = [ctx.text_extents(n).x_advance for n in notes]
    if not velocities or sum(widths) + gap * (len(notes) - 1) > width:
        _text(ctx, _fit(ctx, " ".join(notes), width, BODY), x, 88, BODY, _c["text_dim"])
        return
    for name, w, velocity in zip(notes, widths, velocities, strict=False):
        _text(ctx, name, x, 88, BODY, _c["text_dim"])
        if velocity is not None:
            ctx.set_source_rgb(*_c["track"])
            ctx.rectangle(x, 93, w, 3)
            ctx.fill()
            ctx.set_source_rgb(*accent)
            ctx.rectangle(x, 93, w * velocity / 127, 3)
            ctx.fill()
        x += w + gap


def _panel_knobs(ctx, panel, x0, width, accent) -> None:
    _text(ctx, panel["title"], x0 + 16, 44, LABEL, _c["text_dim"])
    dest = _fit(ctx, f"Sending to {panel['destination']}", width - 32, BODY)
    _text(ctx, dest, x0 + 16, 84, BODY, _c["text"])
    hint = _fit(ctx, "Shift + upper button: Learn Assist", width - 32, BODY - 1)
    _text(ctx, hint, x0 + 16, 110, BODY - 1, _c["text_dim"])


def _panel_browse(ctx, panel, x0, width, accent) -> None:
    _text(ctx, panel["title"], x0 + 16, 44, LABEL, _c["text_dim"])
    names, selected = panel["names"], panel["selected"]
    if not names:
        _text(ctx, "No profiles found", x0 + 16, 84, VALUE, _c["text"])
        return
    for offset in (-1, 0, 1):
        i = selected + offset
        if 0 <= i < len(names):
            label = names[i] + ("  (active)" if names[i] == panel["active"] else "")
            color = accent if offset == 0 else _c["text_dim"]
            label = _fit(ctx, label, width - 32, VALUE, offset == 0)
            _text(ctx, label, x0 + 16, 88 + offset * 26, VALUE, color, bold=offset == 0)


def _panel_setup(ctx, panel, x0, width, accent) -> None:
    page = panel["page"]
    _text(ctx, f"Setup · {page}", x0 + 16, 44, LABEL, _c["text_dim"])
    if page == "Pads":
        _curve_graph(ctx, panel["table"], panel["last_velocity"], x0 + 16, 52, 150, 76, accent)
        right = x0 + 186
        if panel["last_velocity"] is None:
            _text(ctx, "Play a pad", right, 84, VALUE, _c["text"])
            hint = _fit(ctx, "Its velocity shows on the curve", width - 200, BODY - 1)
            _text(ctx, hint, right, 108, BODY - 1, _c["text_dim"])
        else:
            _text(ctx, "Last hit", right, 64, LABEL, _c["text_dim"])
            _text(ctx, str(panel["last_velocity"]), right, 110, PEEK, accent, True)
    elif page == "Aftertouch":
        mode = panel["aftertouch"]
        if mode == "Off":
            _text(ctx, "Aftertouch off", x0 + 16, 84, VALUE, _c["text"])
            return
        label = "Each pad's pressure" if mode == "Poly" else "Pressure on any pad"
        _text(ctx, _fit(ctx, label, width - 32, BODY), x0 + 16, 74, BODY, _c["text"])
        bar = width - 32
        ctx.set_source_rgb(*_c["track"])
        ctx.rectangle(x0 + 16, 88, bar, 10)
        ctx.fill()
        ctx.set_source_rgb(*accent)
        ctx.rectangle(x0 + 16, 88, bar * panel["last_pressure"] / 127, 10)
        ctx.fill()
        _text(ctx, f"Last: {panel['last_pressure']}", x0 + 16, 122, BODY, _c["text_dim"])
    elif page == "Display":
        note = "On USB power alone, Push dims itself whatever these say"
        _text(ctx, _fit(ctx, note, width - 32, BODY - 1), x0 + 16, 84, BODY - 1, _c["text_dim"])
    elif page == "Clock":
        color = accent if panel["following"] else _c["text"]
        _text(ctx, _fit(ctx, panel["clock"], width - 32, VALUE), x0 + 16, 84, VALUE, color)


def _curve_graph(ctx, table, last, x, y, w, h, accent) -> None:
    """Force (left to right) against velocity (bottom to top), with the last hit."""
    ctx.set_source_rgb(*_c["track"])
    ctx.rectangle(x, y, w, h)
    ctx.set_line_width(1)
    ctx.stroke()
    ctx.set_source_rgb(*accent)
    ctx.set_line_width(2)
    for step, velocity in enumerate(table):
        px, py = x + w * step / 127, y + h - h * velocity / 127
        (ctx.line_to if step else ctx.move_to)(px, py)
    ctx.stroke()
    if last is not None:
        step = next((i for i, v in enumerate(table) if v >= last), 127)
        ctx.set_source_rgb(*_c["text"])
        ctx.arc(x + w * step / 127, y + h - h * last / 127, 4, 0, 2 * math.pi)
        ctx.fill()


PANELS = {
    "keyboard": _panel_keyboard,
    "drums": _panel_drums,
    "scale_selector": _panel_scale_selector,
    "chord": _panel_chord,
    "knobs": _panel_knobs,
    "browse": _panel_browse,
    "setup": _panel_setup,
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
    ctx.set_source_rgb(*_c["background"])
    ctx.rectangle(0, BAND, WIDTH, HEIGHT - 2 * BAND)
    ctx.fill()
    _font(ctx, PEEK, True)
    if ctx.text_extents(text).x_advance <= WIDTH - 32:
        _centered(ctx, text, WIDTH / 2, 98, PEEK, _c["text"], bold=True)
        return
    # Long messages (profile errors) wrap at a readable size instead of being cut.
    lines = _wrap(ctx, text, WIDTH - 32, VALUE, max_lines=3)
    top = 80 - (len(lines) - 1) * 13
    for i, line in enumerate(lines):
        _text(ctx, line, 16, top + i * 26, VALUE, _c["text"])


def _use_theme(theme: Theme) -> None:
    _c.clear()
    _c.update({token: (r / 255, g / 255, b / 255) for token, (r, g, b) in theme.items()})


def draw_view(ctx: cairo.Context, view: dict, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    _use_theme(view.get("theme") or DEFAULT_THEME)
    accent = _c[accent_name(view.get("accent", "play"))]
    ctx.set_source_rgb(*_c["background"])
    ctx.paint()

    for col in range(COLUMNS):
        _band_label(ctx, col, view["upper"][col], top=True, accent=accent)
        _band_label(ctx, col, view["lower"][col], top=False, accent=accent)

    if view.get("overlay"):
        _overlay(ctx, view["overlay"], accent)
    else:
        controls = view["controls"]
        used = [i for i, control in enumerate(controls) if control is not None]
        for col in used:
            _control(ctx, col, controls[col], accent, touched=col == view.get("touched"))
        x0 = (max(used) + 1) * COLUMN if used else 0
        panel = view.get("panel")
        if panel and panel["kind"] in PANELS and x0 < WIDTH:
            rail = COLUMN if panel.get("rail") else 0  # the side buttons' column
            PANELS[panel["kind"]](ctx, panel, x0, WIDTH - x0 - rail, accent)
        if panel and panel.get("rail"):
            _rail(ctx, panel["rail"], _c["play"])

    if view.get("peek"):
        _side_knob(ctx, view["peek"], accent)

    if view.get("toast") and view.get("toast_until", 0) > now:
        _toast(ctx, view["toast"])
