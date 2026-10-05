"""Screen drawing from plain state dicts. Runs in the renderer process only.

Layout follows the PRD's 8-column grid: 24 px top band (upper-button labels),
112 px content, 24 px bottom band (lower-button labels), 120 px per column.
"""

import time

import cairo

from pushtoo.hw.colors import BACKGROUND, PLAY_ACCENT, TEXT, TEXT_DIM

WIDTH, HEIGHT = 960, 160
COLUMN = 120
BAND = 24
FONT = "IBM Plex Sans Condensed"  # cairo falls back to the default sans if missing


def _text(ctx: cairo.Context, text: str, x: float, y: float, size: float, color, bold=False):
    weight = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, weight)
    ctx.set_font_size(size)
    ctx.set_source_rgb(*color)
    ctx.move_to(x, y)
    ctx.show_text(text)


def _centered(ctx: cairo.Context, text: str, cx: float, y: float, size: float, color, bold=False):
    weight = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, weight)
    ctx.set_font_size(size)
    extents = ctx.text_extents(text)
    _text(ctx, text, cx - extents.x_advance / 2, y, size, color, bold)


def _upper_label(ctx: cairo.Context, col: int, text: str, selected: bool) -> None:
    x = col * COLUMN
    if selected:
        ctx.set_source_rgb(*PLAY_ACCENT)
        ctx.rectangle(x + 2, 0, COLUMN - 4, BAND)
        ctx.fill()
    _centered(ctx, text, x + COLUMN / 2, 17, 14, BACKGROUND if selected else TEXT, selected)


def draw_play(ctx: cairo.Context, state: dict) -> None:
    ctx.set_source_rgb(*BACKGROUND)
    ctx.paint()

    if state.get("scale_open"):
        _draw_scale_selector(ctx, state)
    else:
        _text(ctx, state["key_name"], 16, 76, 34, PLAY_ACCENT, bold=True)
        mode = "In key" if state["in_key"] else "Chromatic"
        details = f"{mode} · Octave {state['octave']} · Ch {state['channel'] + 1}"
        _text(ctx, details, 16, 106, 18, TEXT)
        held = state.get("held_names", [])
        if held:
            _text(ctx, "  ".join(held), 520, 76, 34, TEXT, bold=True)
        elif not state.get("played_once"):
            _text(ctx, "Play any pad", 520, 66, 24, TEXT)
            _text(ctx, "Select “Pushtoo Out” in your DAW", 520, 94, 16, TEXT_DIM)

    if state.get("toast") and state.get("toast_until", 0) > time.monotonic():
        _draw_toast(ctx, state["toast"])

    # Mode name sits in the bottom band, over the first lower button.
    _centered(ctx, "Play", COLUMN / 2, HEIGHT - 7, 14, PLAY_ACCENT, bold=True)


def _draw_scale_selector(ctx: cairo.Context, state: dict) -> None:
    _upper_label(ctx, 0, "In key" if state["in_key"] else "Chromatic", True)
    # Scale names get two columns ("Major Pentatonic" is wider than one).
    scales = state["scale_names"]
    index = scales.index(state["scale"])
    _text(ctx, "Scale", 16, 44, 14, TEXT_DIM)
    for offset in (-1, 0, 1):
        i = index + offset
        if 0 <= i < len(scales):
            selected = offset == 0
            color = PLAY_ACCENT if selected else TEXT_DIM
            _text(ctx, scales[i], 16, 92 + offset * 24, 20, color, bold=selected)
    _text(ctx, "Root", 2 * COLUMN + 16, 44, 14, TEXT_DIM)
    _text(ctx, state["root_name"], 2 * COLUMN + 16, 100, 34, PLAY_ACCENT, bold=True)
    hint = "Encoder 1: scale · Encoder 2: root · Scale: close"
    _text(ctx, hint, 3 * COLUMN + 16, 98, 16, TEXT_DIM)


def _draw_toast(ctx: cairo.Context, text: str) -> None:
    ctx.set_source_rgb(*BACKGROUND)
    ctx.rectangle(0, BAND, WIDTH, HEIGHT - 2 * BAND)
    ctx.fill()
    _centered(ctx, text, WIDTH / 2, 98, 48, TEXT, bold=True)
