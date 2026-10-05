"""Pad-to-"Pushtoo Out" latency harness (M0 step 4, and the M1 -> M2 gate check).

Measures how long a pad message takes to get through this process (rtmidi input
thread -> GIL -> push2-python dispatch -> handler -> rtmidi output) and arrive at a
listener on the "Pushtoo Out" virtual ALSA port, under three loads: idle, a 60 fps
display thread, and a pure-Python thread that hogs the GIL.

    uv run python tools/latency/latency.py              # synthetic pads, all loads
    uv run python tools/latency/latency.py --real       # you press pads, all loads

Synthetic mode sends pad notes from a separate process over a virtual ALSA port, so
they arrive on rtmidi's callback thread exactly like real pads and must win the GIL.
Real mode can only timestamp at handler entry, so it misses GIL wait; use it to sanity
check, not as the gate. Timestamps are CLOCK_MONOTONIC, shared across processes. The
Push's own USB input latency is a fixed hardware cost and is not included.
"""

import argparse
import multiprocessing as mp
import queue
import statistics
import threading
import time
from collections import defaultdict, deque

import cairo
import mido
import numpy
import push2_python
import rtmidi
from push2_python.constants import DISPLAY_LINE_PIXELS, DISPLAY_N_LINES, FRAME_FORMAT_RGB565

OUT_PORT = "Pushtoo Out"
INJECT_PORT = "Pushtoo Latency Inject"
FIRST_PAD_NOTE, PAD_COUNT = 36, 64  # Push 2 pads send notes 36..99


def open_port_named(midi_in: rtmidi.MidiIn, wanted: str) -> None:
    for idx, name in enumerate(midi_in.get_ports()):
        if wanted in name:
            midi_in.open_port(idx)
            return
    raise SystemExit(f"no MIDI port named {wanted!r}")


def drain(q: "mp.Queue", settle: float = 0.3) -> list:
    """Collect everything from a multiprocessing queue until it stays quiet."""
    items = []
    while True:
        try:
            items.append(q.get(timeout=settle))
        except queue.Empty:
            return items


def listener(arrivals: "mp.Queue", ready: "mp.Event", stop: "mp.Event") -> None:
    midi_in = rtmidi.MidiIn(rtmidi.API_LINUX_ALSA, name="pushtoo-latency-listener")
    open_port_named(midi_in, OUT_PORT)

    def on_message(event, _data) -> None:
        now = time.monotonic_ns()
        status, note, velocity = event[0]
        if status & 0xF0 == 0x90 and velocity > 0:
            arrivals.put((note, velocity, now))

    midi_in.set_callback(on_message)
    ready.set()
    stop.wait()


def injector(sends: "mp.Queue", ready: "mp.Event", go: "mp.Event", seconds: float, rate: int):
    midi_out = rtmidi.MidiOut(rtmidi.API_LINUX_ALSA, name="pushtoo-latency-injector")
    midi_out.open_virtual_port(INJECT_PORT)
    ready.set()
    go.wait()
    interval, end, i = 1 / rate, time.monotonic() + seconds, 0
    while time.monotonic() < end:
        note = FIRST_PAD_NOTE + i % PAD_COUNT
        velocity = 1 + (i // PAD_COUNT) % 127
        sends.put((note, velocity, time.monotonic_ns()))
        midi_out.send_message([0x90, note, velocity])
        midi_out.send_message([0x80, note, 0])
        i += 1
        time.sleep(interval)
    time.sleep(0.5)  # keep the port open until the last notes are delivered


class PadForwarder:
    """Forwards pad presses to Pushtoo Out, as the real router will.

    push2-python only calls the first handler registered for an action, so the
    handler is registered once and each round swaps in fresh state.
    """

    def __init__(self, midi_out: rtmidi.MidiOut) -> None:
        self.midi_out = midi_out
        self.real = False
        self.handler_entries: list[tuple[int, int, int]] = []
        push2_python.on_pad_pressed()(self.on_pad)

    def on_pad(self, _, pad_n, pad_ij, velocity) -> None:
        # pad_n is the pad's MIDI note (36..99), not an index
        if self.real:
            self.handler_entries.append((pad_n, velocity, time.monotonic_ns()))
        self.midi_out.send_message([0x90, pad_n, velocity])
        self.midi_out.send_message([0x80, pad_n, 0])


def start_display_load(push: push2_python.Push2, stop: threading.Event) -> None:
    def run() -> None:
        surface = cairo.ImageSurface(cairo.FORMAT_RGB16_565, DISPLAY_LINE_PIXELS, DISPLAY_N_LINES)
        ctx = cairo.Context(surface)
        while not stop.is_set():
            ctx.set_source_rgb(time.monotonic() % 1, 0.3, 0.5)
            ctx.paint()
            for i in range(64):
                ctx.arc(15 * i, 80, 30, 0, 6.28)
                ctx.stroke()
            surface.flush()
            frame = numpy.ndarray(
                shape=(DISPLAY_N_LINES, DISPLAY_LINE_PIXELS),
                dtype=numpy.uint16,
                buffer=surface.get_data(),
            )
            push.display.display_frame(frame.transpose(), input_format=FRAME_FORMAT_RGB565)

    threading.Thread(target=run, daemon=True).start()


def start_python_load(stop: threading.Event) -> None:
    """Pure-Python busy work that holds the GIL, as a slow Python renderer would."""

    def run() -> None:
        while not stop.is_set():
            total = 0
            for i in range(20_000):
                total += i * i

    threading.Thread(target=run, daemon=True).start()


def match(sends: list, arrivals: list) -> tuple[list[float], int]:
    pending: dict[tuple[int, int], deque[int]] = defaultdict(deque)
    for note, velocity, sent_at in sends:
        pending[(note, velocity)].append(sent_at)
    latencies_ms = []
    for note, velocity, arrived_at in arrivals:
        queue_ = pending.get((note, velocity))
        if queue_:
            latencies_ms.append((arrived_at - queue_.popleft()) / 1e6)
    return latencies_ms, len(sends) - len(latencies_ms)


def run_synthetic_round(push, arrivals, seconds: float, rate: int) -> tuple[list[float], int]:
    sends, ready, go = mp.Queue(), mp.Event(), mp.Event()
    proc = mp.Process(target=injector, args=(sends, ready, go, seconds, rate), daemon=True)
    proc.start()
    if not ready.wait(5):
        raise SystemExit("injector did not start")

    midi_in = rtmidi.MidiIn(rtmidi.API_LINUX_ALSA, name="pushtoo-fake-push")
    open_port_named(midi_in, INJECT_PORT)
    midi_in.set_callback(lambda event, _: push.on_midi_message(mido.Message.from_bytes(event[0])))

    drain(arrivals, settle=0.05)
    go.set()
    proc.join(seconds + 10)
    midi_in.close_port()
    return match(drain(sends), drain(arrivals))


def run_real_round(forwarder, arrivals, seconds: float) -> tuple[list[float], int]:
    drain(arrivals, settle=0.05)
    forwarder.handler_entries = []
    forwarder.real = True
    print(f"  press pads for {seconds:.0f} s...")
    time.sleep(seconds)
    forwarder.real = False
    return match(forwarder.handler_entries, drain(arrivals))


def report(label: str, samples: list[float], missing: int) -> None:
    if not samples:
        print(f"{label:>14}: no samples")
        return
    samples.sort()
    p99 = samples[min(len(samples) - 1, int(len(samples) * 0.99))]
    verdict = "PASS" if p99 < 3.0 and not missing else "FAIL"
    print(
        f"{label:>14}: n={len(samples):5d}  p50 {statistics.median(samples):6.3f} ms  "
        f"p99 {p99:6.3f} ms  max {samples[-1]:6.3f} ms  lost {missing}  "
        f"[{verdict}: <3 ms p99, none lost]"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true", help="measure real pad presses")
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--rate", type=int, default=200, help="synthetic presses per second")
    args = parser.parse_args()

    midi_out = rtmidi.MidiOut(rtmidi.API_LINUX_ALSA, name="Pushtoo")
    midi_out.open_virtual_port(OUT_PORT)

    arrivals, ready, stop_listener = mp.Queue(), mp.Event(), mp.Event()
    proc = mp.Process(target=listener, args=(arrivals, ready, stop_listener), daemon=True)
    proc.start()
    if not ready.wait(5):
        raise SystemExit("listener did not start")

    forwarder = PadForwarder(midi_out)
    push = push2_python.Push2()
    # push2-python ignores all input until Push's first active-sensing message, then
    # for one more second, to skip a startup burst.
    deadline = time.monotonic() + 10
    while push.last_active_sensing_received is None and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(1.2)
    try:
        for label in ("idle", "display 60fps", "python hog"):
            stop_load = threading.Event()
            if label != "idle":
                start_display_load(push, stop_load)
            if label == "python hog":
                start_python_load(stop_load)
            time.sleep(0.5)
            if args.real:
                print(f"{label}:")
                samples, missing = run_real_round(forwarder, arrivals, args.seconds)
            else:
                samples, missing = run_synthetic_round(push, arrivals, args.seconds, args.rate)
            report(label, samples, missing)
            stop_load.set()
            time.sleep(0.2)
    finally:
        push.stop_active_sensing_thread()
        stop_listener.set()
        proc.join(2)


if __name__ == "__main__":
    main()
