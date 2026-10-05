# ADR 0001: Render the display in a separate process

**Status:** Accepted · Oct 4, 2026

## Context

The PRD requires pad-to-MIDI latency under 3 ms at p99 (N1) and a display at 30 fps minimum, 60 fps target (N2), and says rendering must never block MIDI. Pushtoo is Python. The question was whether the renderer can run as a thread in the MIDI process, or needs its own process so it can't hold the GIL while a pad message waits.

## Measurements

Machine: i7-12700K, Arch Linux 7.2.7, Python 3.13.14 (GIL switch interval 5 ms), Push 2 over USB, ALSA sequencer under PipeWire.

**Display throughput** (`spikes/hw_probe.py display`). Each frame is 8 columns of text and arcs drawn with cairo:

| Stage                                   | Mean     | p99      |
| --------------------------------------- | -------- | -------- |
| cairo draw                              | 1.19 ms  | 1.36 ms  |
| push2-python `prepare_frame`            | 0.63 ms  | 0.80 ms  |
| USB write (blocks on display refresh)   | 14.91 ms | 15.65 ms |

- Unthrottled, the display ran at a steady 59.8 fps using 12% of one core.
- CPU work per frame is about 1.8 ms, so roughly 5% of a core at 30 fps and 11% at 60 fps.
- The USB write is mostly waiting, and the display paces itself at 60 Hz.

**Latency** (`tools/latency/latency.py`). Synthetic pads at 200 per second for 8 s, delivered from another process over ALSA to the rtmidi callback thread, and measured until arrival on "Pushtoo Out". Two runs each:

| Load in the MIDI process            | p50          | p99            | max       |
| ----------------------------------- | ------------ | -------------- | --------- |
| Idle                                | 0.04–0.08 ms | 0.17–0.19 ms   | 0.5 ms    |
| Display thread at 60 fps            | 0.03 ms      | 0.16–0.19 ms   | 0.5 ms    |
| Display thread + pure-Python thread | 4–5 ms       | 164–302 ms     | 328 ms    |

No notes were lost.

## Decision

Run the renderer, meaning layout, animation and all Python-level drawing logic, in a **separate process**. The MIDI process owns the Push MIDI ports and the virtual ports, and keeps pure-Python work on the hot path minimal. It sends draw state to the renderer and never waits on it.

A display thread that only does cairo, numpy and USB I/O is harmless, because those release the GIL. But real rendering includes Python-level layout, easing, animation (ripples, Life mode, confetti) and profile logic. The "python hog" row shows any sustained pure-Python work in the MIDI process pushes p50 to the 5 ms GIL switch interval and p99 into hundreds of milliseconds as events queue up. A separate process makes N1 a structural guarantee instead of something to re-check after every feature.

## Consequences

- **Process split.** The renderer owns the display: it holds the USB display endpoint (via push2-python's `Push2Display`) and receives state snapshots over a pipe or shared memory. The MIDI process opens push2-python for MIDI only.
- **Stale screens.** If the renderer falls behind, it drops frames and shows the latest state. MIDI is unaffected.
- **Hot-path rules.** Callbacks in the MIDI process must not do pure-Python work beyond mapping and routing. Logging, profile saves and undo-history writes go to a queue.
- **Gate check.** `tools/latency/latency.py` (synthetic mode) is the M1 → M2 gate. Since M1 it drives the real app.
- **Free-threaded Python** (3.14t) could make a single process viable later. Revisit if the process split proves costly.

## Other findings from the spike

- push2-python calls only the **first** handler registered for each action. Pushtoo's hardware layer should register one handler per action and dispatch internally.
- push2-python **ignores all input for about 1 s** after the Push's first active-sensing message, including after a reconnect. This bounds hot-plug recovery (N3) and should become a "Reconnecting…" toast.
- push2-python passes a pad's raw MIDI note (36–99) as `pad_n`, not a 0–63 index.

## M1 gate result (Oct 4, 2026)

`tools/latency/latency.py` drove the full app: push2-python dispatch, `App`, `PlayMode`, router, LED updates, and the render process redrawing after every press. 100 presses per second for 8 s per round, two runs:

| Round                                   | p50          | p99            | max      | Lost |
| --------------------------------------- | ------------ | -------------- | -------- | ---- |
| Single notes                            | 0.05–0.07 ms | 0.17–0.19 ms   | 0.73 ms  | 0    |
| Three-note chords                       | 0.20–0.21 ms | 0.47–0.53 ms   | 0.83 ms  | 0    |
| Single notes + pure-Python thread (info) | 5.1 ms      | 22–28 ms       | 50 ms    | 0    |

The gate (p99 under 3 ms, nothing lost) passes with a wide margin. Chords are slower because each pad's screen and LED refresh runs before the next pad is handled; that's still about 6x under budget. If later modes make refresh heavier, coalesce refreshes onto a timer instead of running one per event.

