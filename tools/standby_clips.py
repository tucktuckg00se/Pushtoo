"""Render the calm standby scenes as videos, the screen above the pads, for review.

    uv run python tools/standby_clips.py [out_dir] [seconds]

Writes <scene>_<colors>.mp4 for each calm scene in each standby palette, and all.mp4
with them side by side, using the real scene code: the screen drawn as the Push draws
it, and the pads in their LED colors, relit each step and faded over a second the way
the Push fades them. LEDs look brighter than this, the dim steps most of all. Needs
ffmpeg; out_dir defaults to standby_clips/ (ignored by git).
"""

import subprocess
import sys
from pathlib import Path

import cairo

from pushtoo.fonts import use_bundled_fonts
from pushtoo.render.screens import HEIGHT, WIDTH, draw_view
from pushtoo.rhythm.life import COLUMNS, ROWS
from pushtoo.standby import FADING, Standby
from pushtoo.theme import DEFAULT_THEME, STANDBY_PALETTES, led_palette

FPS = 30  # the calm scenes move slowly
FADE_SECONDS = 1.0  # the Push's one-shot half note at 120 BPM
WARM_UP = 20.0  # seconds run before recording, so the scene is under way
MARGIN = 20
ROW = HEIGHT / 1.75  # a pad row on the screen's scale (the screen is 1.75 rows tall)
PADS_Y = MARGIN + HEIGHT + 1.35 * ROW  # the gap behind the buttons below the screen
SIZE = (WIDTH + 2 * MARGIN, int(PADS_Y + ROWS * ROW + MARGIN) // 2 * 2)
BODY = (0.09, 0.1, 0.11)
UNLIT = (0.13, 0.14, 0.15)


class _Pads:
    """Pad colors as the Push shows them: each new color faded in from the last."""

    def __init__(self, palette: str) -> None:
        self.rgb = {name: tuple(v / 255 for v in rgb) for name, (_, rgb) in
                    led_palette(DEFAULT_THEME, palette).items()}  # fmt: skip
        self.fades: dict[tuple[int, int], tuple[tuple, tuple, float]] = {}

    def _color(self, name: str) -> tuple:
        return self.rgb.get(name, UNLIT)

    def show(self, colors, t: float) -> None:
        for row in range(ROWS):
            for col in range(COLUMNS):
                now = self.at(row, col, t)
                target = self._color(colors[row][col])
                if target != self.fades.get((row, col), (None, None, 0))[1]:
                    self.fades[(row, col)] = (now, target, t)

    def at(self, row: int, col: int, t: float) -> tuple:
        start, end, since = self.fades.get((row, col), (UNLIT, UNLIT, 0.0))
        mix = min(1.0, (t - since) / FADE_SECONDS)
        return tuple(a + (b - a) * mix for a, b in zip(start, end, strict=True))


def _frame(ctx, screen, standby: Standby, pads: _Pads, t: float) -> None:
    ctx.set_source_rgb(*BODY)
    ctx.paint()
    draw_view(cairo.Context(screen), {"standby": standby.view(), "theme": dict(DEFAULT_THEME)}, t)
    ctx.set_source_surface(screen, MARGIN, MARGIN)
    ctx.paint()
    w, h = WIDTH / COLUMNS * 0.91, ROW * 0.88
    for row in range(ROWS):  # row 0 is the bottom row
        for col in range(COLUMNS):
            x = MARGIN + col * WIDTH / COLUMNS + (WIDTH / COLUMNS - w) / 2
            y = PADS_Y + (ROWS - 1 - row) * ROW + (ROW - h) / 2
            ctx.rectangle(x, y, w, h)
            ctx.set_source_rgb(*pads.at(row, col, t))
            ctx.fill()


def clip(scene: str, palette: str, path: Path, seconds: float) -> None:
    standby = Standby(scene, 0.0, seed=1, palette=palette)
    pads = _Pads(palette)
    canvas = cairo.ImageSurface(cairo.FORMAT_RGB24, *SIZE)
    screen = cairo.ImageSurface(cairo.FORMAT_RGB24, WIDTH, HEIGHT)
    ctx = cairo.Context(canvas)
    encoder = subprocess.Popen(
        [
            "ffmpeg", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "bgr0", "-s", f"{SIZE[0]}x{SIZE[1]}",
            "-r", str(FPS), "-i", "-",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
            "-movflags", "+faststart", str(path),
        ],
        stdin=subprocess.PIPE,
    )  # fmt: skip
    pads.show(standby.pad_colors(0.0), 0.0)
    for frame in range(int((WARM_UP + seconds) * FPS)):
        t = frame / FPS
        while standby.due(t):  # as the App steps it and relights the pads
            standby.step(standby.stepped_at + standby.step_seconds)
            pads.show(standby.pad_colors(standby.stepped_at), standby.stepped_at)
        if t < WARM_UP:
            continue
        _frame(ctx, screen, standby, pads, t)
        canvas.flush()
        encoder.stdin.write(bytes(canvas.get_data()))
    encoder.stdin.close()
    encoder.wait()


def main() -> None:
    use_bundled_fonts()
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "standby_clips")
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 40.0
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for scene in FADING:
        for palette in STANDBY_PALETTES:
            path = out / f"{scene.lower()}_{palette.lower()}.mp4"
            clip(scene, palette, path, seconds)
            paths.append(path)
            print(f"wrote {path}")
    # All of them at half size: a row per scene, a column per palette.
    columns = len(STANDBY_PALETTES)
    inputs = [arg for path in paths for arg in ("-i", str(path))]
    scaled = "".join(f"[{i}:v]scale=iw/2:-2[v{i}];" for i in range(len(paths)))
    # Each tile placed by the scaled sizes of those before it (w0, h0: the first's).
    widths = ["+".join(f"w{j}" for j in range(i)) or "0" for i in range(columns)]
    layout = "|".join(
        f"{widths[i % columns]}_{'0' if i < columns else 'h0'}" for i in range(len(paths))
    )
    stack = "".join(f"[v{i}]" for i in range(len(paths)))
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", *inputs,
         "-filter_complex", f"{scaled}{stack}xstack=inputs={len(paths)}:layout={layout}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(out / "all.mp4")],
        check=True,
    )  # fmt: skip
    print(f"wrote {out / 'all.mp4'}")


if __name__ == "__main__":
    main()
