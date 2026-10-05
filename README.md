# Pushtoo

Pushtoo turns an Ableton Push 2 on Linux into a DAW-agnostic MIDI controller: plug in Push, pick the **Pushtoo Out** port in any DAW or synth, and play. The screen always shows what each control does.

> **Status:** early development (M1 Playable). Play mode works; Knobs, Mix and profiles come in M2. See [docs/PRD.md](docs/PRD.md) for the product spec.

## Playing

1. Plug in Push 2 and run `uv run pushtoo`.
2. In your DAW or synth, choose the MIDI input **Pushtoo Out**. Under PipeWire it may appear as `Midi-Bridge:Pushtoo: Out (capture)`.
3. Play the pads. Pushtoo starts in C minor on MIDI channel 1.

| Control                         | What it does                                                         |
| ------------------------------- | -------------------------------------------------------------------- |
| Layout                          | Switch between Keyboard (channel 1) and Drums (channel 10)           |
| Scale                           | Open or close the scale selector: top buttons pick In key/Chromatic and C G D A E B F#, bottom buttons pick F Bb Eb Ab Db Gb, encoder 1 picks the scale, encoder 2 the root |
| Octave up / down                | Keyboard: shift an octave. Drums: shift one bank of 16 notes         |
| Buttons below the display       | Pages: **Play** (octave or drum notes, velocity curve), **Strip** (pitch bend or mod wheel), **Output** (destination port and channel) |
| Buttons above the display       | Options on the current page                                          |
| Encoders above the display      | The current page's controls. Touch one to see its value full-size    |
| Shift + encoder                 | Fine adjust (4x finer)                                               |
| Accent                          | Every note at full velocity                                          |
| Touch strip                     | Pitch bend or mod wheel, set on the Strip page                       |
| Shift + Stop                    | Panic: all notes off on every output                                 |

Drums use four banks of 16 pads. The bottom-left bank is the General MIDI kit (notes 36–51), and the screen names each drum as you play it. On the **Output** page, any layout can send straight to a hardware MIDI port instead of Pushtoo Out, so a USB-MIDI synth works without a DAW.

Unplugging the Push releases held notes; plug it back in and Pushtoo reconnects on its own.

## Development

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and the ALSA, JACK and cairo development headers.

```sh
uv sync
uv run pytest
uv run ruff check
uv run pushtoo
uv run python tools/render_preview.py   # every screen as PNG, no hardware needed
uv run python tools/latency/latency.py  # latency gate; needs Push attached
```

## Layout

| Path            | Contents                                              |
| --------------- | ----------------------------------------------------- |
| `pushtoo/`      | The application package                               |
| `tests/`        | Unit tests (no hardware required)                     |
| `tools/`        | Screen previews and the latency gate                  |
| `docs/`         | PRD and architecture decision records                 |
| `legacy/pysha/` | Original Pysha code, kept as reference while porting  |

## Credits

Pushtoo is a fork of [Pysha](https://github.com/ffont/pysha) by Frederic Font and uses a fork of his [push2-python](https://github.com/ffont/push2-python). Both are MIT licensed.
