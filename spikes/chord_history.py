"""Chord history on the Chord screen: four ways to show the last few chords played.

Today's screen from draw_view, plus the recent chords drawn in one of these styles:

- chips: function-colored chips under the role line, newest on the right
- chart: a lead-sheet line, | Cm | Gm | Fm7 |, with each numeral in its function color
- crumbs: one quiet line next to "Play · Chord", oldest to newest
- echo: earlier chords trail after the big chord name, smaller and dimmer

Static, like today: nothing animates. Consecutive repeats of the same chord count once.

    uv run python spikes/chord_history.py --style chart       # live on Push (quit Pushtoo)
    uv run python spikes/chord_history.py --frames DIR        # every style to PNGs
"""

import argparse
import multiprocessing as mp
import queue
import signal
import sys
import tempfile
import threading
import time
from pathlib import Path

import cairo
import numpy

from pushtoo.render.screens import COLUMN, FONT, HEIGHT, WIDTH, draw_view
from pushtoo.theme import BACKGROUND, BODY, LABEL, TEXT, TEXT_DIM, accent_name, rgb

STYLES = ("chips", "chart", "crumbs", "echo")
KEEP = 12  # more than any style can show
KEEPALIVE_SECONDS = 0.5


def function_color(panel: dict, accent) -> tuple[float, float, float]:
    line = panel.get("role_line") or ""
    if "leads to" in line:
        return rgb("pink")
    if "borrowed" in line:
        return rgb("violet")
    return {"away": rgb("blue"), "tension": rgb("amber")}.get(panel.get("role"), accent)


class History:
    """Recent chords, derived only from successive view dicts."""

    def __init__(self) -> None:
        self.chords: list[dict] = []  # {name, numeral, color}
        self.prev: dict = {}

    def observe(self, view: dict) -> None:
        panel, old = view.get("panel") or {}, self.prev
        self.prev = panel
        if panel.get("kind") != "chord" or not panel.get("sounding"):
            return
        name = panel.get("chord_name")
        if old.get("sounding") and name == old.get("chord_name"):
            return  # still the same press
        if self.chords and self.chords[-1]["name"] == name:
            return  # pressed again: a repeat counts once
        accent = rgb(accent_name(view.get("accent", "play")))
        numeral = (panel.get("role_line") or "").split(" · ")[0]
        self.chords.append(
            {"name": name, "numeral": numeral, "color": function_color(panel, accent)}
        )
        del self.chords[:-KEEP]


def _font(ctx: cairo.Context, size: float, bold: bool = False) -> None:
    weight = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, weight)
    ctx.set_font_size(size)


def _width(ctx, text: str, size: float, bold: bool = False) -> float:
    _font(ctx, size, bold)
    return ctx.text_extents(text).x_advance


def _text(ctx, text, x, y, size, color, bold=False) -> None:
    _font(ctx, size, bold)
    ctx.set_source_rgb(*color)
    ctx.move_to(x, y)
    ctx.show_text(text)


def _mix(a, b, t: float):
    return tuple(x + (y - x) * t for x, y in zip(a, b, strict=True))


def _panel_x0(view: dict) -> int:
    used = [i for i, c in enumerate(view.get("controls") or []) if c is not None]
    return (max(used) + 1) * COLUMN if used else 0


def _status_end(ctx, view: dict, x0: float) -> float:
    """Where today's status line ends, so the history never covers it."""
    p = view["panel"]
    parts = [p["key_name"], f"Ch {p['channel'] + 1}", p["destination"]]
    if p.get("parent"):
        parts.insert(1, p["parent"])
    if p.get("strum"):
        parts.insert(0, "Strum the touch strip")
    if p.get("latch"):
        parts.insert(0, "Latch")
    if p.get("accent"):
        parts.append("Accent")
    return x0 + 16 + _width(ctx, " · ".join(parts), BODY)


def _round_rect(ctx, x, y, w, h, r) -> None:
    import math

    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def _fit_from_newest(widths: list[float], room: float, gap: float) -> int:
    """How many of the newest items fit in room."""
    used, count = 0.0, 0
    for w in reversed(widths):
        need = w + (gap if count else 0)
        if used + need > room:
            break
        used += need
        count += 1
    return count


def draw_chips(ctx, view, chords, sounding) -> None:
    x0 = _panel_x0(view)
    left = max(_status_end(ctx, view, x0) + 20, x0 + (WIDTH - x0) * 0.5)
    widths = [_width(ctx, c["name"], 13, True) + 14 for c in chords]
    n = _fit_from_newest(widths, WIDTH - 12 - left, 6)
    x = WIDTH - 12
    for i, (chord, w) in enumerate(zip(reversed(chords[-n:]), reversed(widths[-n:]), strict=True)):
        x -= w
        fade = 1.0 - 0.1 * i
        _round_rect(ctx, x, 101, w, 21, 4)
        if i == 0 and sounding:
            ctx.set_source_rgb(*chord["color"])
            ctx.fill()
            color = BACKGROUND
        else:
            ctx.set_source_rgb(*_mix(BACKGROUND, chord["color"], 0.3 * fade))
            ctx.fill()
            color = _mix(BACKGROUND, _mix(chord["color"], (1, 1, 1), 0.45), fade)
        _text(ctx, chord["name"], x + 7, 116, 13, color, True)
        x -= 6


def draw_chart(ctx, view, chords, sounding) -> None:
    """A lead-sheet line: | Cm | Gm | Fm7 |, numerals under the names."""
    x0 = _panel_x0(view)
    left = max(_status_end(ctx, view, x0) + 24, x0 + (WIDTH - x0) * 0.5)
    pad = 12
    widths = [
        max(_width(ctx, c["name"], BODY, True), _width(ctx, c["numeral"], 12)) + 2 * pad
        for c in chords
    ]
    n = _fit_from_newest(widths, WIDTH - 16 - left, 0)
    shown, sizes = chords[-n:], widths[-n:]
    x = WIDTH - 16 - sum(sizes)
    ctx.set_line_width(1)
    for i, (chord, w) in enumerate(zip(shown, sizes, strict=True)):
        newest = i == n - 1
        ctx.set_source_rgb(*TEXT_DIM)
        ctx.move_to(x + 0.5, 99)
        ctx.line_to(x + 0.5, 131)
        ctx.stroke()
        name_color = rgb(accent_name(view.get("accent", "play"))) if newest and sounding else TEXT
        _text(ctx, chord["name"], x + pad, 113, BODY, name_color if newest else TEXT_DIM, newest)
        _text(ctx, chord["numeral"], x + pad, 129, 12, chord["color"])
        x += w
    if n:
        ctx.set_source_rgb(*TEXT_DIM)
        ctx.move_to(x - 0.5, 99)
        ctx.line_to(x - 0.5, 131)
        ctx.stroke()


def draw_crumbs(ctx, view, chords, sounding) -> None:
    """One quiet line after the title: Cm  Gm  Fm7  Ab, the newest brightest."""
    x0 = _panel_x0(view)
    start = x0 + 16 + _width(ctx, view["panel"]["title"], LABEL) + 22
    sep = "  ›  "
    sep_w = _width(ctx, sep, LABEL)
    widths = [_width(ctx, c["name"], LABEL, True) for c in chords]
    n = _fit_from_newest(widths, WIDTH - 16 - start, sep_w)
    x = start
    for i, chord in enumerate(chords[-n:]):
        newest = i == n - 1
        age = n - 1 - i
        color = TEXT if newest else _mix(TEXT_DIM, BACKGROUND, min(0.6, age * 0.1))
        if i:
            _text(ctx, sep, x, 44, LABEL, _mix(TEXT_DIM, BACKGROUND, 0.4))
            x += sep_w
        _text(ctx, chord["name"], x, 44, LABEL, color, True)
        x += widths[len(chords) - n + i]


def draw_echo(ctx, view, chords, sounding) -> None:
    """Earlier chords trail after the big name, each smaller and dimmer."""
    p = view["panel"]
    if not p.get("chord_name") or not chords:
        return
    x0 = _panel_x0(view)
    limit = x0 + (WIDTH - x0) * 0.5 - 16
    x = x0 + 16 + _width(ctx, p["chord_name"], 34, True) + 18
    earlier = chords[:-1] if chords[-1]["name"] == p["chord_name"] else chords
    for age, chord in enumerate(reversed(earlier)):
        size = max(14, 24 - age * 3)
        w = _width(ctx, chord["name"], size, True)
        if x + w > limit:
            break
        color = _mix(TEXT_DIM, BACKGROUND, min(0.65, age * 0.16))
        _text(ctx, chord["name"], x, 84, size, color, True)
        x += w + 14


DRAW = {"chips": draw_chips, "chart": draw_chart, "crumbs": draw_crumbs, "echo": draw_echo}


def draw(ctx: cairo.Context, view: dict, history: History, style: str, now: float) -> None:
    draw_view(ctx, view, now)
    panel = view.get("panel") or {}
    hidden = view.get("peek") or view.get("shift") or (view.get("toast_until", 0) > now)
    if panel.get("kind") == "chord" and history.chords and not hidden:
        DRAW[style](ctx, view, history.chords, panel.get("sounding"))


# Live renderer (same interface as pushtoo.render.process.Renderer)


def _run(states: "mp.Queue", style: str) -> None:
    from push2_python.constants import FRAME_FORMAT_RGB565
    from push2_python.display import Push2Display

    from pushtoo.render.process import _DisplayOnlyPush

    owner = _DisplayOnlyPush()  # Push2Display keeps only a weak reference
    display = Push2Display(owner)
    surface = cairo.ImageSurface(cairo.FORMAT_RGB16_565, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)
    history = History()
    state: dict | None = None
    while True:
        try:
            state = states.get(timeout=KEEPALIVE_SECONDS)
            history.observe(state)
            while True:
                state = states.get_nowait()
                history.observe(state)
        except queue.Empty:
            pass
        if state is None:
            continue
        if state.get("quit"):
            return
        draw(ctx, state, history, style, time.monotonic())
        surface.flush()
        frame = numpy.ndarray((HEIGHT, WIDTH), dtype=numpy.uint16, buffer=surface.get_data())
        display.display_frame(frame.transpose(), input_format=FRAME_FORMAT_RGB565)


class HistoryRenderer:
    def __init__(self, style: str) -> None:
        self._states: mp.Queue = mp.Queue()
        self._process = mp.Process(target=_run, args=(self._states, style), name="history-render")

    def start(self) -> None:
        self._process.start()

    def update(self, state: dict) -> None:
        self._states.put(state)

    def stop(self) -> None:
        self._states.put({"quit": True})
        self._process.join(2)
        if self._process.is_alive():
            self._process.terminate()


def live(style: str) -> None:
    from pushtoo.app import App

    app = App(renderer=HistoryRenderer(style))
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    print(f"Chord history ({style}) running. Ctrl+C to quit.")
    stop.wait()
    app.close()


# Offline: the same progression in every style


PROGRESSION = [(1, 0), (1, 4), (2, 3), (1, 5), (1, 2), (1, 6), (1, 3), (7, 0), (1, 0)]


def frames(out: Path) -> None:
    from push2_python import constants as c

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    from render_preview import _app

    out.mkdir(parents=True, exist_ok=True)
    surface = cairo.ImageSurface(cairo.FORMAT_RGB16_565, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)
    with tempfile.TemporaryDirectory() as tmp:
        app = _app(Path(tmp))
        app.button_pressed(c.BUTTON_LAYOUT)
        app.button_pressed(c.BUTTON_LAYOUT)
        history = History()
        moments: dict[str, tuple[dict, list]] = {}
        for i, (row, col) in enumerate(PROGRESSION):
            app.pad_pressed(row, col, 100)
            history.observe(app.view())
            if i == len(PROGRESSION) - 1:
                moments["2_long_sounding"] = (app.view(), list(history.chords))
            app.pad_released(row, col)
            history.observe(app.view())
            if i == 3:
                moments["1_four_released"] = (app.view(), list(history.chords))
        app.close()
    for style in STYLES:
        for moment, (view, chords) in moments.items():
            h = History()
            h.chords = chords
            draw(ctx, view, h, style, 0.0)
            surface.write_to_png(str(out / f"{style}_{moment}.png"))
    print(f"wrote {len(STYLES) * len(moments)} frames to {out}/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--style", choices=STYLES, default="chart")
    parser.add_argument("--frames", type=Path, help="render every style to PNGs instead")
    args = parser.parse_args()
    if args.frames:
        frames(args.frames)
    else:
        live(args.style)
    return 0


if __name__ == "__main__":
    sys.exit(main())
