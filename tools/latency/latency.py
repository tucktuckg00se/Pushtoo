"""Pad-to-"Pushtoo Out" latency through the real app: the M1 -> M2 gate (PRD N1).

Runs the full Pushtoo app (MIDI process, render process, LEDs) and measures from a
pad message reaching the app's MIDI input to the resulting note arriving at a
listener on "Pushtoo Out":

    uv run python tools/latency/latency.py              # synthetic pads (the gate)
    uv run python tools/latency/latency.py --real       # you press pads

Synthetic pads come from a separate process over a virtual ALSA port and land on
rtmidi's callback thread exactly like real pads, so GIL waits are included. Real
mode can only timestamp at the app's handler, which misses that wait; use it as a
sanity check. Timestamps are CLOCK_MONOTONIC, shared across processes. The Push's
own USB input latency is a fixed hardware cost and is not included.

Rounds:
  single notes   one pad at a time
  chords         three pads at once, so later notes wait behind earlier refreshes
  python hog     single notes plus a busy pure-Python thread (informational only:
                 shows why rendering must stay out of the MIDI process, ADR 0001)
"""

import argparse
import multiprocessing as mp
import queue
import statistics
import tempfile
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

import mido
import rtmidi
from push2_python.pads import pad_n_to_pad_ij

from pushtoo.app import App
from pushtoo.hw.push import pad_ij_to_row_col
from pushtoo.midi.router import OUT_PORT

INJECT_PORT = "Pushtoo Latency Inject"
FIRST_PAD_NOTE, PAD_COUNT = 36, 64  # Push 2 pads send notes 36..99
GATE_P99_MS = 3.0


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


def injector(sends, ready, go, seconds: float, rate: int, chord: int) -> None:
    """Presses `chord` pads at once, `rate` times per second. Reports (pad, velocity,
    time) per press; velocity doubles as an id so arrivals can be matched."""
    midi_out = rtmidi.MidiOut(rtmidi.API_LINUX_ALSA, name="pushtoo-latency-injector")
    midi_out.open_virtual_port(INJECT_PORT)
    ready.set()
    go.wait()
    interval, end, i = 1 / rate, time.monotonic() + seconds, 0
    while time.monotonic() < end:
        pads = []
        for k in range(chord):
            pad = FIRST_PAD_NOTE + (i * chord + k * 9) % PAD_COUNT
            velocity = 1 + (i * chord + k) % 127
            sends.put((pad, velocity, time.monotonic_ns()))
            midi_out.send_message([0x90, pad, velocity])
            pads.append(pad)
        for pad in pads:
            midi_out.send_message([0x80, pad, 0])
        i += 1
        time.sleep(interval)
    time.sleep(0.5)  # keep the port open until the last notes are delivered


def start_python_load(stop: threading.Event) -> None:
    def run() -> None:
        while not stop.is_set():
            total = 0
            for i in range(20_000):
                total += i * i

    threading.Thread(target=run, daemon=True).start()


def expected_notes(app: App) -> dict[int, int]:
    """Pad MIDI note -> the note the app's current layout plays for it."""
    notes = {}
    for pad in range(FIRST_PAD_NOTE, FIRST_PAD_NOTE + PAD_COUNT):
        row, col = pad_ij_to_row_col(pad_n_to_pad_ij(pad))
        note = app.play.keyboard.note_at(row, col)
        if note is not None:
            notes[pad] = note
    return notes


def match(sends: list, arrivals: list) -> tuple[list[float], int]:
    pending: dict[tuple[int, int], deque[int]] = defaultdict(deque)
    for note, velocity, sent_at in sends:
        pending[(note, velocity)].append(sent_at)
    latencies_ms = []
    for note, velocity, arrived_at in arrivals:
        waiting = pending.get((note, velocity))
        if waiting:
            latencies_ms.append((arrived_at - waiting.popleft()) / 1e6)
    return latencies_ms, len(sends) - len(latencies_ms)


def synthetic_round(app, arrivals, seconds, rate, chord) -> tuple[list[float], int]:
    sends, ready, go = mp.Queue(), mp.Event(), mp.Event()
    args = (sends, ready, go, seconds, rate, chord)
    proc = mp.Process(target=injector, args=args, daemon=True)
    proc.start()
    if not ready.wait(5):
        raise SystemExit("injector did not start")

    push = app.push.push
    midi_in = rtmidi.MidiIn(rtmidi.API_LINUX_ALSA, name="pushtoo-fake-push")
    open_port_named(midi_in, INJECT_PORT)
    midi_in.set_callback(lambda event, _: push.on_midi_message(mido.Message.from_bytes(event[0])))

    drain(arrivals, settle=0.05)
    go.set()
    proc.join(seconds + 10)
    midi_in.close_port()
    layout_note = expected_notes(app)
    sent = [(layout_note[pad], velocity, t) for pad, velocity, t in drain(sends)]
    return match(sent, drain(arrivals))


def real_round(app, arrivals, seconds) -> tuple[list[float], int]:
    entries = []
    original = app.pad_pressed

    def timed(row, col, velocity):
        note = app.play.keyboard.note_at(row, col)
        if note is not None:
            entries.append((note, velocity, time.monotonic_ns()))
        original(row, col, velocity)

    drain(arrivals, settle=0.05)
    app.pad_pressed = timed
    print(f"  press pads for {seconds:.0f} s...")
    time.sleep(seconds)
    app.pad_pressed = original
    return match(entries, drain(arrivals))


def report(label: str, samples: list[float], missing: int, gate: bool) -> bool:
    if not samples:
        print(f"{label:>14}: no samples")
        return not gate
    samples.sort()
    p99 = samples[min(len(samples) - 1, int(len(samples) * 0.99))]
    passed = p99 < GATE_P99_MS and not missing
    verdict = ("PASS" if passed else "FAIL") if gate else "info"
    print(
        f"{label:>14}: n={len(samples):5d}  p50 {statistics.median(samples):6.3f} ms  "
        f"p99 {p99:6.3f} ms  max {samples[-1]:6.3f} ms  lost {missing}  [{verdict}]"
    )
    return passed or not gate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true", help="measure real pad presses")
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--rate", type=int, default=100, help="synthetic presses per second")
    args = parser.parse_args()

    # Temporary profile and state folders, so a gate run never touches the user's.
    scratch = tempfile.TemporaryDirectory(prefix="pushtoo-latency-")
    root = Path(scratch.name)
    app = App(config_dir=root / "profiles", state_path=root / "state.yaml")
    # push2-python ignores all input until Push's first active-sensing message, then
    # for one more second, to skip a startup burst.
    deadline = time.monotonic() + 10
    while app.push.push.last_active_sensing_received is None and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(1.2)

    arrivals, ready, stop_listener = mp.Queue(), mp.Event(), mp.Event()
    proc = mp.Process(target=listener, args=(arrivals, ready, stop_listener), daemon=True)
    proc.start()
    if not ready.wait(5):
        raise SystemExit("listener did not start")

    all_passed = True
    try:
        if args.real:
            samples, missing = real_round(app, arrivals, args.seconds)
            report("real pads", samples, missing, gate=False)
        else:
            rounds = (("single notes", 1, False), ("chords", 3, False), ("python hog", 1, True))
            for label, chord, hog in rounds:
                stop_load = threading.Event()
                if hog:
                    start_python_load(stop_load)
                samples, missing = synthetic_round(app, arrivals, args.seconds, args.rate, chord)
                all_passed &= report(label, samples, missing, gate=not hog)
                stop_load.set()
                time.sleep(0.3)
            print("GATE PASSED" if all_passed else "GATE FAILED")
    finally:
        app.close()
        stop_listener.set()
        proc.join(2)
        scratch.cleanup()
    raise SystemExit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
