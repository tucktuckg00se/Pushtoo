"""Afterglow: a screen spike where the display reacts to playing.

Runs all of Pushtoo (pads, MIDI, LEDs) with only the renderer swapped. Each frame is
today's screen from draw_view, plus light drawn on top:

- bloom: the chord name or held notes glow in the chord's color, flash on each hit
- ribbon: the Chord screen keeps the last chords as chips, sliding left
- note trail: Keyboard draws held notes as streaks scrolling left, pitch on y
- comet arcs: a turned encoder leaves a fading tail and a bright head
- band slide: a light streak runs from the old selected button to the new one
- panic drop: Shift+Stop drops the old screen off the bottom

Frames are drawn in 24-bit color and converted to RGB565 with a 4x4 Bayer dither, so
glows fade without banding.

    uv run python spikes/afterglow.py               # live on Push (quit Pushtoo first)
    uv run python spikes/afterglow.py --frames DIR  # scripted run to PNGs, no hardware
"""

import argparse
import math
import multiprocessing as mp
import queue
import re
import signal
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

import cairo
import numpy

from pushtoo.render.screens import COLUMN, FONT, HEIGHT, WIDTH, draw_view
from pushtoo.theme import BACKGROUND, BODY, accent_name, rgb

FPS = 60
KEEPALIVE_SECONDS = 0.5
FLASH_SECONDS = 0.25  # the bright hit on a new chord or note
GLOW_TAU = 0.3  # how fast the steady glow follows held/released
TRAIL_SECONDS = 3.0  # note streaks cross the panel in this time
COMET_SECONDS = 0.45
SLIDE_SECONDS = 0.18
DROP_SECONDS = 0.35
RIBBON_CHIPS = 8

FUNCTION_COLORS = {"home": None, "away": "blue", "tension": "amber"}  # None: mode accent
BAYER_4X4 = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
BAYER = (numpy.array(BAYER_4X4) + 0.5) / 16 - 0.5
NOTE_RE = re.compile(r"^([A-G])([#b]?)(-?\d+)$")
STEPS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi_of(name: str) -> int | None:
    m = NOTE_RE.match(name)
    if not m:
        return None
    letter, accidental, octave = m.groups()
    return 12 * (int(octave) + 1) + STEPS[letter] + {"#": 1, "b": -1, "": 0}[accidental]


def chord_color(panel: dict, accent) -> tuple[float, float, float]:
    line = panel.get("role_line") or ""
    if "leads to" in line:
        return rgb("pink")
    if "borrowed" in line:
        return rgb("violet")
    name = FUNCTION_COLORS.get(panel.get("role") or "home")
    return rgb(name) if name else accent


def ease_out(p: float) -> float:
    return 1 - (1 - p) ** 3


def _font(ctx: cairo.Context, size: float, bold: bool) -> None:
    weight = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, weight)
    ctx.set_font_size(size)


def _glow(ctx: cairo.Context, x: float, y: float, rx: float, ry: float, color, alpha: float):
    """A soft elliptical light, added with SCREEN so it brightens what's under it."""
    if alpha <= 0.01:
        return
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(rx, ry)
    grad = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
    grad.add_color_stop_rgba(0, *color, alpha)
    grad.add_color_stop_rgba(0.45, *color, alpha * 0.35)
    grad.add_color_stop_rgba(1, *color, 0)
    ctx.set_source(grad)
    ctx.set_operator(cairo.OPERATOR_SCREEN)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()


def _panel_x0(view: dict) -> int:
    used = [i for i, c in enumerate(view.get("controls") or []) if c is not None]
    return (max(used) + 1) * COLUMN if used else 0


class Afterglow:
    """Animation state, derived only from successive view dicts."""

    def __init__(self) -> None:
        self.prev: dict | None = None
        self.glow = 0.0
        self.flash_at = -1e9
        self.glow_color = (1.0, 1.0, 1.0)
        self.ribbon: deque = deque(maxlen=RIBBON_CHIPS)  # (name, color, born)
        self.streaks: list[list] = []  # [midi, t_on, t_off or None]
        self.comets: dict[int, deque] = {}  # column -> (t, fraction)
        self.slides: list[tuple] = []  # (top, from_col, to_col, t0)
        self.drop: tuple[dict, float] | None = None
        self.last_tick = None

    # Observing

    def observe(self, view: dict, now: float) -> None:
        prev = self.prev or {}
        panel, old = view.get("panel") or {}, prev.get("panel") or {}
        accent = rgb(accent_name(view.get("accent", "play")))

        if panel.get("kind") == "chord":
            name = panel.get("chord_name")
            fresh = panel.get("sounding") and (
                not old.get("sounding")
                or name != old.get("chord_name")
                or panel.get("notes") != old.get("notes")
            )
            if fresh and name:
                self.flash_at = now
                self.glow_color = chord_color(panel, accent)
                self.ribbon.append((name, self.glow_color, now))

        if panel.get("kind") == "keyboard":
            held = {midi_of(n) for n in panel.get("held") or []} - {None}
            was = {s[0] for s in self.streaks if s[2] is None}
            for note in held - was:
                self.streaks.append([note, now, None])
                self.flash_at = now
                self.glow_color = accent
            for s in self.streaks:
                if s[2] is None and s[0] not in held:
                    s[2] = now

        old_controls = prev.get("controls") or []
        for col, control in enumerate(view.get("controls") or []):
            before = old_controls[col] if col < len(old_controls) else None
            if control and before and control["name"] == before["name"]:
                if control["fraction"] != before["fraction"]:
                    trail = self.comets.setdefault(col, deque(maxlen=24))
                    if not trail:
                        trail.append((now, before["fraction"]))
                    trail.append((now, control["fraction"]))

        for top, key in ((True, "upper"), (False, "lower")):
            a, b = _selected(prev.get(key)), _selected(view.get(key))
            same_row = _labels(prev.get(key)) == _labels(view.get(key))
            if a is not None and b is not None and a != b and same_row:
                self.slides.append((top, a, b, now))

        toast = view.get("toast") or ""
        if toast.startswith("Panic") and toast != (prev.get("toast") or "") and self.prev:
            self.drop = (dict(self.prev, toast=None), now)
        self.prev = view

    def busy(self, now: float) -> bool:
        return (
            self.glow > 0.01
            or now - self.flash_at < FLASH_SECONDS * 4
            or any(s[2] is None or now - s[2] < TRAIL_SECONDS for s in self.streaks)
            or any(t and now - t[-1][0] < COMET_SECONDS for t in self.comets.values())
            or bool(self.slides)
            or self.drop is not None
            or any(now - born < 0.3 for _, _, born in self.ribbon)
        )

    # Drawing

    def draw(self, ctx: cairo.Context, view: dict, now: float) -> None:
        self._tick(view, now)
        ctx.set_operator(cairo.OPERATOR_OVER)  # the light layers below switch to SCREEN
        if self.drop and now - self.drop[1] < DROP_SECONDS:
            self._draw_drop(ctx, view, now)
            return
        self.drop = None
        draw_view(ctx, view, now)
        if view.get("peek") or view.get("shift"):
            return
        accent = rgb(accent_name(view.get("accent", "play")))
        panel = view.get("panel") or {}
        if panel.get("kind") == "chord":
            self._chord_bloom(ctx, view, panel)
            self._ribbon(ctx, view, panel, now)
        if panel.get("kind") == "keyboard":
            self._trail(ctx, view, panel, now, accent)
        self._comets(ctx, view, now, accent)
        self._slides(ctx, now, accent)

    def _tick(self, view: dict, now: float) -> None:
        dt = 0 if self.last_tick is None else min(now - self.last_tick, 0.1)
        self.last_tick = now
        panel = view.get("panel") or {}
        held = panel.get("sounding") or bool(panel.get("held"))
        target = 0.5 if held else 0.0
        self.glow += (target - self.glow) * (1 - math.exp(-dt / GLOW_TAU))
        self.streaks = [s for s in self.streaks if s[2] is None or now - s[2] < TRAIL_SECONDS]
        self.slides = [s for s in self.slides if now - s[3] < SLIDE_SECONDS]

    def _level(self, now: float) -> float:
        flash = math.exp(-(now - self.flash_at) / FLASH_SECONDS) if now >= self.flash_at else 0
        return min(1.0, self.glow + 0.7 * flash)

    def _chord_bloom(self, ctx, view, panel) -> None:
        name = panel.get("chord_name")
        if not name:
            return
        x0 = _panel_x0(view)
        _font(ctx, 34, True)
        w = ctx.text_extents(name).x_advance
        level = self._level(self.last_tick)
        _glow(ctx, x0 + 16 + w / 2, 72, w / 2 + 90, 50, self.glow_color, 0.85 * level)

    def _ribbon(self, ctx, view, panel, now) -> None:
        if not self.ribbon:
            return
        x0 = _panel_x0(view)
        # Leave the status line alone: chips fit between its end and the right edge.
        parts = [
            p
            for p in (
                "Latch" if panel.get("latch") else None,
                "Strum the touch strip" if panel.get("strum") else None,
                panel.get("key_name"),
                panel.get("parent"),
                f"Ch {panel.get('channel', 0) + 1}",
                panel.get("destination"),
                "Accent" if panel.get("accent") else None,
            )
            if p
        ]
        _font(ctx, BODY, False)
        status_end = x0 + 16 + ctx.text_extents(" · ".join(parts)).x_advance
        left = max(status_end + 20, x0 + (WIDTH - x0) * 0.5)
        _font(ctx, 13, True)
        # Lay chips out right to left, newest at the right edge, then slide the whole
        # row in by the newest chip's width so older chips ease left as it arrives.
        chips, x = [], WIDTH - 12
        for name, color, _born in reversed(self.ribbon):
            w = ctx.text_extents(name).x_advance + 14
            if x - w < left:
                break
            chips.append((name, color, x - w, w))
            x -= w + 6
        enter = ease_out(min(1.0, (now - self.ribbon[-1][2]) / 0.25))
        shift = (1 - enter) * (chips[0][3] + 6) if chips else 0
        ctx.set_operator(cairo.OPERATOR_OVER)
        for i, (name, color, cx, w) in enumerate(chips):
            cx += shift
            fade = 1.0 - 0.1 * i
            _round_rect(ctx, cx, 101, w, 21, 4)
            if i == 0 and panel.get("sounding"):
                ctx.set_source_rgba(*color, enter)
                ctx.fill()
                ctx.set_source_rgb(*BACKGROUND)
            else:
                ctx.set_source_rgba(*color, 0.3 * fade)
                ctx.fill()
                ctx.set_source_rgba(*(0.55 * c + 0.45 for c in color), fade)
            ctx.move_to(cx + 7, 116)
            ctx.show_text(name)

    def _trail(self, ctx, view, panel, now, accent) -> None:
        if not self.streaks:
            return
        x0 = _panel_x0(view)
        left, right = x0 + (WIDTH - x0) / 2, WIDTH - 10
        notes = [s[0] for s in self.streaks]
        lo, hi = min(notes), max(notes)
        if hi - lo < 12:
            lo -= (12 - (hi - lo)) // 2
            hi = lo + 12
        speed = (right - left) / TRAIL_SECONDS
        ctx.set_operator(cairo.OPERATOR_SCREEN)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        for note, t_on, t_off in self.streaks:
            y = 126 - (note - lo) / (hi - lo) * 90
            head = right - (now - t_off) * speed if t_off else right
            tail = max(left, right - (now - t_on) * speed)
            if head <= left:
                continue
            ctx.set_line_width(5)
            grad = cairo.LinearGradient(tail, 0, head, 0)
            grad.add_color_stop_rgba(0, *accent, 0)
            grad.add_color_stop_rgba(1, *accent, 0.6)
            ctx.set_source(grad)
            ctx.move_to(tail, y)
            ctx.line_to(head, y)
            ctx.stroke()
            if t_off is None:
                _glow(ctx, right, y, 16, 9, (1, 1, 1), 0.5 + 0.5 * self._level(now))

    def _comets(self, ctx, view, now, accent) -> None:
        controls = view.get("controls") or []
        for col, trail in list(self.comets.items()):
            control = controls[col] if col < len(controls) else None
            if not trail or control is None or now - trail[-1][0] > COMET_SECONDS:
                if trail and now - trail[-1][0] > COMET_SECONDS:
                    trail.clear()
                continue
            color = rgb(control["color"]) if control.get("color") else accent
            cx, cy, r = col * COLUMN + COLUMN / 2, 80, 22
            points = [(t, f) for t, f in trail if now - t < COMET_SECONDS]
            ctx.set_operator(cairo.OPERATOR_SCREEN)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            for (_t0, f0), (t1, f1) in zip(points, points[1:], strict=False):
                age = (now - t1) / COMET_SECONDS
                a0, a1 = sorted((math.radians(135 + 270 * f0), math.radians(135 + 270 * f1)))
                if a1 - a0 < 0.01:
                    continue
                ctx.set_line_width(10)
                ctx.set_source_rgba(*color, 0.45 * (1 - age))
                ctx.new_path()
                ctx.arc(cx, cy, r, a0, a1)
                ctx.stroke()
            heat = 1 - (now - trail[-1][0]) / COMET_SECONDS
            angle = math.radians(135 + 270 * control["fraction"])
            hx, hy = cx + r * math.cos(angle), cy + r * math.sin(angle)
            _glow(ctx, hx, hy, 14, 14, color, 0.9 * heat)
            _glow(ctx, cx, 122, 34, 12, color, 0.35 * heat)

    def _slides(self, ctx, now, accent) -> None:
        for top, a, b, t0 in self.slides:
            p = ease_out((now - t0) / SLIDE_SECONDS)
            pos = a + (b - a) * p
            x1, x2 = sorted((a * COLUMN + COLUMN / 2, pos * COLUMN + COLUMN / 2))
            y = 2 if top else HEIGHT - 4
            ctx.set_operator(cairo.OPERATOR_SCREEN)
            ctx.set_source_rgba(*accent, 0.7 * (1 - p))
            _round_rect(ctx, x1, y, max(4, x2 - x1), 2, 1)
            ctx.fill()
            _glow(ctx, pos * COLUMN + COLUMN / 2, y + 1, 50, 10, accent, 0.6 * (1 - p))

    def _draw_drop(self, ctx, view, now) -> None:
        old, t0 = self.drop
        p = (now - t0) / DROP_SECONDS
        snap = cairo.ImageSurface(cairo.FORMAT_RGB24, WIDTH, HEIGHT)
        draw_view(cairo.Context(snap), old, now)
        ctx.set_operator(cairo.OPERATOR_OVER)
        ctx.set_source_rgb(*BACKGROUND)
        ctx.paint()
        ctx.set_source_surface(snap, 0, p * p * HEIGHT)
        ctx.paint_with_alpha(1 - p * 0.6)


def _selected(items) -> int | None:
    for i, item in enumerate(items or []):
        if item and item.get("selected"):
            return i
    return None


def _labels(items) -> list:
    return [item and item.get("label") for item in items or []]


def _round_rect(ctx, x, y, w, h, r) -> None:
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def to_rgb565(surface: cairo.ImageSurface) -> numpy.ndarray:
    """24-bit surface -> RGB565 with a 4x4 ordered dither, shaped (WIDTH, HEIGHT)."""
    surface.flush()
    stride = surface.get_stride()
    data = numpy.ndarray((HEIGHT, stride), dtype=numpy.uint8, buffer=surface.get_data())
    px = data[:, : WIDTH * 4].reshape(HEIGHT, WIDTH, 4).astype(numpy.float32)
    tile = numpy.tile(BAYER, (HEIGHT // 4 + 1, WIDTH // 4 + 1))[:HEIGHT, :WIDTH]
    b = numpy.clip(numpy.rint(px[..., 0] * 31 / 255 + tile), 0, 31).astype(numpy.uint16)
    g = numpy.clip(numpy.rint(px[..., 1] * 63 / 255 + tile), 0, 63).astype(numpy.uint16)
    r = numpy.clip(numpy.rint(px[..., 2] * 31 / 255 + tile), 0, 31).astype(numpy.uint16)
    return ((r << 11) | (g << 5) | b).transpose().copy()


def rgb565_to_png(frame: numpy.ndarray, path: Path) -> None:
    """What the Push will show, back as a PNG for review."""
    f = frame.transpose().astype(numpy.uint32)
    r, g, b = (f >> 11) & 31, (f >> 5) & 63, f & 31
    out = numpy.zeros((HEIGHT, WIDTH, 4), dtype=numpy.uint8)
    out[..., 2], out[..., 1], out[..., 0] = r * 255 // 31, g * 255 // 63, b * 255 // 31
    surface = cairo.ImageSurface.create_for_data(out, cairo.FORMAT_RGB24, WIDTH, HEIGHT)
    surface.write_to_png(str(path))


# Live renderer (same interface as pushtoo.render.process.Renderer)


def _run(states: "mp.Queue") -> None:
    from push2_python.constants import FRAME_FORMAT_RGB565
    from push2_python.display import Push2Display

    from pushtoo.render.process import _DisplayOnlyPush

    owner = _DisplayOnlyPush()  # Push2Display keeps only a weak reference
    display = Push2Display(owner)
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)
    glow = Afterglow()
    state: dict | None = None
    last_frame = 0.0
    while True:
        now = time.monotonic()
        busy = glow.busy(now)
        timeout = 1 / FPS if busy else KEEPALIVE_SECONDS
        dirty = False
        try:
            state = states.get(timeout=max(0.0, timeout - (now - last_frame)))
            dirty = True
            while True:
                state = states.get_nowait()
        except queue.Empty:
            pass
        if state is None:
            continue
        if state.get("quit"):
            return
        now = time.monotonic()
        if dirty:
            glow.observe(state, now)
        if not (dirty or busy) and now - last_frame < KEEPALIVE_SECONDS:
            continue
        wait = 1 / FPS - (now - last_frame)
        if wait > 0:
            time.sleep(wait)
            now = time.monotonic()
        ctx.set_operator(cairo.OPERATOR_OVER)
        glow.draw(ctx, state, now)
        display.display_frame(to_rgb565(surface), input_format=FRAME_FORMAT_RGB565)
        last_frame = now


class AfterglowRenderer:
    def __init__(self) -> None:
        self._states: mp.Queue = mp.Queue()
        self._process = mp.Process(target=_run, args=(self._states,), name="afterglow-render")

    def start(self) -> None:
        self._process.start()

    def update(self, state: dict) -> None:
        self._states.put(state)

    def stop(self) -> None:
        self._states.put({"quit": True})
        self._process.join(2)
        if self._process.is_alive():
            self._process.terminate()


def live() -> None:
    from pushtoo.app import App

    app = App(renderer=AfterglowRenderer())
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    print("Afterglow running. Ctrl+C to quit.")
    stop.wait()
    app.close()


# Offline: a scripted performance rendered to PNGs


def frames(out: Path) -> None:
    from push2_python import constants as c

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    from render_preview import _app

    out.mkdir(parents=True, exist_ok=True)
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)
    glow = Afterglow()
    base = time.monotonic()
    shots: list[tuple[float, str]] = []
    script: list[tuple[float, object]] = []

    def at(t: float, action, *snap: tuple[float, str]) -> None:
        script.append((t, action))
        shots.extend(snap)

    with tempfile.TemporaryDirectory() as tmp:
        app = _app(Path(tmp))
        # Keyboard: three notes, released one by one
        at(0.0, lambda: app.pad_pressed(0, 0, 100), (0.05, "01_kb_hit"))
        at(0.3, lambda: app.pad_pressed(0, 2, 100))
        at(0.6, lambda: app.pad_pressed(0, 4, 100), (1.2, "02_kb_held"))
        at(1.5, lambda: [app.pad_released(0, i) for i in (0, 2, 4)], (2.4, "03_kb_trail"))
        # Chord grid: Cm, Gm, Fm7, Ab, then let go
        at(3.0, lambda: [app.button_pressed(c.BUTTON_LAYOUT), app.button_pressed(c.BUTTON_LAYOUT)])
        for i, (row, col) in enumerate(((1, 0), (1, 4), (2, 3), (1, 5))):
            t = 3.2 + i * 0.6
            at(t, lambda r=row, k=col: app.pad_pressed(r, k, 100))
            at(t + 0.45, lambda r=row, k=col: app.pad_released(r, k))
        shots.extend(
            [
                (3.25, "04_chord_first_hit"),
                (5.05, "05_chord_ribbon_flash"),
                (5.5, "06_chord_ribbon_settled"),
            ]
        )
        # Style page -> Output page: band slide
        at(5.8, lambda: app.button_pressed("Lower Row 2"), (5.86, "07_band_slide"))
        # Knobs: sweep encoder 1
        at(6.4, lambda: app.button_pressed(c.BUTTON_DEVICE))
        for i in range(10):
            at(6.6 + i * 0.03, lambda: app.encoder_rotated("Track1 Encoder", 6))
        shots.append((6.95, "08_knob_comet"))
        # Panic
        at(
            7.4,
            lambda: [
                app.button_pressed(c.BUTTON_SHIFT),
                app.button_pressed(c.BUTTON_STOP),
                app.button_released(c.BUTTON_SHIFT),
            ],
            (7.52, "09_panic_drop"),
        )

        events = sorted(script, key=lambda e: e[0])
        times = sorted({t for t, _ in shots} | {round(i / FPS, 4) for i in range(int(8 * FPS))})
        names = dict(shots)
        e = 0
        for t in times:
            while e < len(events) and events[e][0] <= t:
                events[e][1]()
                glow.observe(app.view(), base + events[e][0])
                e += 1
            glow.draw(ctx, glow.prev or app.view(), base + t)
            if t in names:
                rgb565_to_png(to_rgb565(surface), out / f"{names[t]}.png")
        app.close()
    print(f"wrote {len(shots)} frames to {out}/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--frames", type=Path, help="render a scripted run to PNGs instead")
    args = parser.parse_args()
    if args.frames:
        frames(args.frames)
    else:
        live()
    return 0


if __name__ == "__main__":
    sys.exit(main())
