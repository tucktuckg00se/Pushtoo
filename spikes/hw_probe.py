"""Throwaway hardware probe for Push 2 (M0 step 3).

Measures display throughput split into cairo draw, push2-python frame
preparation and USB write, and logs input and connection events.

    uv run python spikes/hw_probe.py display --seconds 10
    uv run python spikes/hw_probe.py events --seconds 30
    uv run python spikes/hw_probe.py hotplug --seconds 60   # unplug/replug during the run
"""

import argparse
import math
import statistics
import time

import cairo
import numpy
import push2_python
from push2_python.constants import DISPLAY_LINE_PIXELS, DISPLAY_N_LINES, FRAME_FORMAT_RGB565

W, H = DISPLAY_LINE_PIXELS, DISPLAY_N_LINES


def draw_test_frame(ctx: cairo.Context, t: float) -> None:
    """Roughly the workload of a busy Pushtoo screen: 8 columns of text and arcs."""
    ctx.set_source_rgb(0.055, 0.059, 0.071)
    ctx.paint()
    ctx.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    for col in range(8):
        x = col * 120
        value = (math.sin(t * 2 + col) + 1) / 2
        ctx.set_source_rgb(0.2, 0.8, 0.75)
        ctx.rectangle(x + 2, 0, 116, 24)
        ctx.fill()
        ctx.set_source_rgb(0, 0, 0)
        ctx.set_font_size(14)
        ctx.move_to(x + 8, 17)
        ctx.show_text(f"Cutoff {col + 1}")
        ctx.set_line_width(6)
        ctx.set_source_rgb(0.3, 0.3, 0.3)
        start = math.radians(135)
        ctx.arc(x + 60, 85, 30, start, start + math.radians(270))
        ctx.stroke()
        ctx.set_source_rgb(1.0, 0.7, 0.2)
        ctx.arc(x + 60, 85, 30, start, start + math.radians(270 * value))
        ctx.stroke()
        ctx.set_source_rgb(1, 1, 1)
        ctx.set_font_size(20)
        ctx.move_to(x + 42, 92)
        ctx.show_text(f"{int(value * 127):3d}")


def summarize(name: str, samples_ms: list[float]) -> str:
    samples = sorted(samples_ms)
    p99 = samples[min(len(samples) - 1, int(len(samples) * 0.99))]
    return (
        f"{name:>8}: mean {statistics.fmean(samples):6.2f} ms  "
        f"p99 {p99:6.2f} ms  max {samples[-1]:6.2f} ms"
    )


def run_display(push: push2_python.Push2, seconds: float) -> None:
    surface = cairo.ImageSurface(cairo.FORMAT_RGB16_565, W, H)
    ctx = cairo.Context(surface)
    draw_ms, prep_ms, send_ms = [], [], []
    cpu_start, wall_start = time.process_time(), time.perf_counter()
    frames = 0
    while time.perf_counter() - wall_start < seconds:
        t0 = time.perf_counter()
        draw_test_frame(ctx, t0)
        surface.flush()
        frame = numpy.ndarray(shape=(H, W), dtype=numpy.uint16, buffer=surface.get_data())
        t1 = time.perf_counter()
        prepared = push.display.prepare_frame(frame.transpose(), input_format=FRAME_FORMAT_RGB565)
        t2 = time.perf_counter()
        push.display.send_to_display(prepared)
        t3 = time.perf_counter()
        draw_ms.append((t1 - t0) * 1000)
        prep_ms.append((t2 - t1) * 1000)
        send_ms.append((t3 - t2) * 1000)
        frames += 1
    wall = time.perf_counter() - wall_start
    cpu = time.process_time() - cpu_start
    print(f"frames {frames} in {wall:.1f} s -> {frames / wall:.1f} fps (unthrottled)")
    print(f"CPU {cpu / wall * 100:.0f}% of one core while unthrottled")
    for name, samples in (("draw", draw_ms), ("prepare", prep_ms), ("usb", send_ms)):
        print(summarize(name, samples))
    total = [a + b + c for a, b, c in zip(draw_ms, prep_ms, send_ms, strict=True)]
    print(summarize("total", total))
    # The USB write mostly blocks waiting on the display's refresh, so only draw and
    # prepare count as CPU work.
    cpu_per_frame = (statistics.fmean(draw_ms) + statistics.fmean(prep_ms)) / 1000
    for fps in (30, 60):
        print(f"estimated CPU at {fps} fps: {cpu_per_frame * fps * 100:.0f}% of one core")


def register_event_logging() -> None:
    def log(*parts) -> None:
        print(f"{time.monotonic():.3f}", *parts, flush=True)

    @push2_python.on_pad_pressed()
    def _pad_on(_, pad_n, pad_ij, velocity):
        log("pad on ", pad_n, pad_ij, velocity)

    @push2_python.on_pad_released()
    def _pad_off(_, pad_n, pad_ij, velocity):
        log("pad off", pad_n, pad_ij, velocity)

    @push2_python.on_pad_aftertouch()
    def _pad_at(_, pad_n, pad_ij, velocity):
        log("pad at ", pad_n, pad_ij, velocity)

    @push2_python.on_encoder_rotated()
    def _enc(_, encoder_name, increment):
        log("encoder", encoder_name, increment)

    @push2_python.on_encoder_touched()
    def _enc_touch(_, encoder_name):
        log("touch  ", encoder_name)

    @push2_python.on_button_pressed()
    def _btn(_, name):
        log("button ", name)

    @push2_python.on_touchstrip()
    def _strip(_, value):
        log("strip  ", value)

    @push2_python.on_midi_connected()
    def _midi_on(_):
        log("MIDI connected")

    @push2_python.on_midi_disconnected()
    def _midi_off(_):
        log("MIDI disconnected")

    @push2_python.on_display_connected()
    def _disp_on(_):
        log("display connected")

    @push2_python.on_display_disconnected()
    def _disp_off(_):
        log("display disconnected")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["display", "events", "hotplug"])
    parser.add_argument("--seconds", type=float, default=10)
    args = parser.parse_args()

    if args.mode != "display":
        register_event_logging()
    push = push2_python.Push2()
    try:
        if args.mode == "display":
            run_display(push, args.seconds)
        elif args.mode == "events":
            print(f"Logging events for {args.seconds:.0f} s; play pads, turn knobs...")
            time.sleep(args.seconds)
        else:
            print(f"Running display for {args.seconds:.0f} s; unplug and replug Push now.")
            surface = cairo.ImageSurface(cairo.FORMAT_RGB16_565, W, H)
            ctx = cairo.Context(surface)
            end = time.perf_counter() + args.seconds
            while time.perf_counter() < end:
                draw_test_frame(ctx, time.perf_counter())
                surface.flush()
                frame = numpy.ndarray(shape=(H, W), dtype=numpy.uint16, buffer=surface.get_data())
                push.display.display_frame(frame.transpose(), input_format=FRAME_FORMAT_RGB565)
                time.sleep(1 / 30)
    finally:
        push.stop_active_sensing_thread()


if __name__ == "__main__":
    main()
