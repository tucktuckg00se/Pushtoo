# Pushtoo

Pushtoo turns an Ableton Push 2 on Linux into a DAW-agnostic MIDI controller: plug in Push, pick the **Pushtoo Out** port in any DAW or synth, and play. The screen always shows what each control does.

> **Status:** early development (M2 Design). Play, Knobs and Mix modes and YAML profiles work; the Chord layout comes in M3. See [docs/PRD.md](docs/PRD.md) for the product spec.

## Playing

1. Plug in Push 2 and run `uv run pushtoo`.
2. In your DAW or synth, choose the MIDI input **Pushtoo Out**. Under PipeWire it may appear as `Midi-Bridge:Pushtoo: Out (capture)`.
3. Play the pads. Pushtoo starts in C minor on MIDI channel 1.

Pushtoo has three modes, each on its own button: **Note** (Play), **Device** (Knobs) and **Mix**. Pads keep playing in Knobs mode, and in all but the top two rows in Mix mode.

| Control                         | What it does                                                         |
| ------------------------------- | -------------------------------------------------------------------- |
| Note, Device, Mix               | Play, Knobs and Mix modes                                            |
| Browse                          | Profile list: encoder 1 picks, top-left button loads                 |
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
| Undo, Shift + Undo              | Undo and redo in your DAW (Ctrl+Z and Ctrl+Shift+Z by default)       |
| Master encoder (right)          | Master level CC, in every mode                                       |
| Hold Shift                      | Lists what Shift does in the current mode                            |

**Knobs mode** gives you up to 8 pages of 8 named controls, defined in your profile. Each column's top button glows in that control's color. To map a control in your DAW, start the DAW's MIDI learn, hold **Shift** and tap the button above the knob: Pushtoo sends just that control's CC, three times, so the DAW catches the right one. Hold **Delete** and touch a knob to reset it to its default.

**Mix mode** turns the 8 encoders into faders. The top pad row toggles mute and the second row toggles solo for each column; the bottom six rows keep playing.

Drums use four banks of 16 pads. The bottom-left bank is the General MIDI kit (notes 36–51), and the screen names each drum as you play it. On the **Output** page, any layout can send straight to a hardware MIDI port instead of Pushtoo Out, so a USB-MIDI synth works without a DAW.

Unplugging the Push releases held notes; plug it back in and Pushtoo reconnects on its own.

## Profiles

On first run Pushtoo creates `~/.config/pushtoo/profiles/default.yaml`, a commented profile you can edit while Pushtoo runs. Changes apply when you save. If an edit has a mistake, the Push screen shows the file, line and field, and Pushtoo keeps using the last working version. Add more `.yaml` files to the folder and switch between them with **Browse**.

```yaml
name: Synth
output: Pushtoo Out          # or a hardware MIDI port
knobs:
  pages:
    - name: Filter
      controls:
        - {name: Cutoff, cc: 74, channel: 1, color: orange}
        - {name: Resonance, cc: 71, channel: 1, color: orange}
        - {name: Detune, cc: 94, channel: 1, color: violet, bipolar: true}
undo:
  redo: {keys: ctrl+y}       # for apps that use Ctrl+Y
```

Leave out any section to use the defaults. Without a `knobs` section you get 8 pages of 8 knobs on channels 15 and 16, using MIDI CCs that no synth treats specially, so nothing changes until you map it.

Pushtoo never writes to your profiles. Where you left off (mode, page, key, knob and fader values) is saved separately in `~/.local/state/pushtoo/state.yaml` and restored per profile.

**About Undo keystrokes.** Undo goes to whichever window has focus, through a virtual keyboard (`/dev/uinput`), which works under X11 and Wayland. Keys are physical positions: on a non-QWERTY layout, `ctrl+z` presses the key where Z sits on QWERTY. If your DAW maps actions to MIDI, use `undo: {midi: {cc: ..., channel: ...}}` instead, which reaches the DAW regardless of focus. On a headless system, install `packaging/udev/50-pushtoo.rules` for uinput access.

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
