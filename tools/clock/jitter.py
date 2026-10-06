"""Clock timing gate for the Rhythm milestone: how steadily can Pushtoo send MIDI clock?

    uv run python tools/clock/jitter.py [seconds]

Sends 24-ppqn clock at 120 BPM from a test port two ways, each idle and with a busy
Python thread competing for the interpreter (as pad callbacks and screen updates do):

- sleep: a thread sleeps until each tick's deadline and sends it.
- queue: ticks are stamped about 50 ms ahead on an ALSA queue, which the kernel
  delivers on time.

A listener port stamps arrivals in the kernel, so the measurement adds no Python
jitter of its own. Jitter is each tick's distance from a perfect grid. The gate is a
p99 under 1 ms.
"""

import statistics
import sys
import threading
import time

from alsa_midi import (
    ClockEvent,
    PortCaps,
    RealTime,
    SequencerClient,
)

from pushtoo.midi.virtual import PORT_TYPE

BPM = 120
PERIOD = 60 / BPM / 24  # seconds per clock tick
LOOKAHEAD = 0.05
GATE_MS = 1.0


def _busy(stop: threading.Event) -> None:
    """Pure-Python work that holds the GIL, like a burst of pad and screen work."""
    while not stop.is_set():
        sum(i * i for i in range(20_000))


def _send_sleeping(client, port, count: int) -> None:
    start = time.perf_counter() + 0.1
    for i in range(count):
        deadline = start + i * PERIOD
        delay = deadline - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        client.event_output(ClockEvent(), port=port)
        client.drain_output()


def _send_queued(client, port, count: int) -> None:
    queue = client.create_queue("jitter")
    queue.start()
    client.drain_output()
    start = time.perf_counter()
    for i in range(count):
        at = 0.1 + i * PERIOD
        # Stay LOOKAHEAD ahead of the queue: sleep until shortly before this tick is due.
        delay = start + at - LOOKAHEAD - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        event = ClockEvent(time=RealTime(at))
        client.event_output(event, queue=queue, port=port)
        client.drain_output()
    time.sleep(LOOKAHEAD + 0.1)
    queue.close()


def measure(method: str, seconds: float, loaded: bool) -> list[float]:
    sender = SequencerClient("Pushtoo Jitter")
    out = sender.create_port("out", PortCaps.READ | PortCaps.SUBS_READ, PORT_TYPE)
    listener = SequencerClient("Pushtoo Jitter Listener")
    stamps = listener.create_queue("stamps")
    inbox = listener.create_port(
        "in",
        PortCaps.WRITE | PortCaps.SUBS_WRITE,
        timestamping=True,
        timestamp_real=True,
        timestamp_queue=stamps,
    )
    stamps.start()
    listener.drain_output()
    inbox.connect_from(out)

    count = int(seconds / PERIOD)
    arrivals: list[float] = []

    def listen() -> None:
        while len(arrivals) < count:
            event = listener.event_input(timeout=2)
            if event is None:
                return
            if isinstance(event, ClockEvent):
                arrivals.append(float(event.time))

    stop = threading.Event()
    load = threading.Thread(target=_busy, args=(stop,), daemon=True)
    if loaded:
        load.start()
    reader = threading.Thread(target=listen)
    reader.start()
    send = _send_sleeping if method == "sleep" else _send_queued
    send(sender, out, count)
    reader.join()
    stop.set()
    listener.close()
    sender.close()

    # Distance from the best-fitting perfect grid (median offset removed), in ms.
    offsets = [t - i * PERIOD for i, t in enumerate(arrivals)]
    centre = statistics.median(offsets)
    return [abs(o - centre) * 1000 for o in offsets]


def _pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(p / 100 * len(ordered)))]


def main() -> None:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 30
    print(f"{BPM} BPM, 24 ppqn, {seconds:.0f} s per run; gate p99 < {GATE_MS} ms")
    results = {}
    for method in ("sleep", "queue"):
        for loaded in (False, True):
            jitter = measure(method, seconds, loaded)
            p99 = _pct(jitter, 99)
            label = f"{method:5} {'loaded' if loaded else 'idle':6}"
            verdict = "pass" if p99 < GATE_MS else "FAIL"
            print(
                f"{label}  ticks {len(jitter):5}  p50 {_pct(jitter, 50):.3f} ms  "
                f"p99 {p99:.3f} ms  max {max(jitter):.3f} ms  {verdict}"
            )
            results[(method, loaded)] = p99
    for method in ("sleep", "queue"):
        ok = all(results[(method, loaded)] < GATE_MS for loaded in (False, True))
        print(f"{method}: {'passes' if ok else 'fails'} the gate")


if __name__ == "__main__":
    main()
