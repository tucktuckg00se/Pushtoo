# Pushtoo

Pushtoo turns an Ableton Push 2 on Linux into an instrument for any synth, DAW or hardware rig: plug in Push, pick the **Pushtoo Out** port, and play. Scales stay in key, every chord pad sounds good, the touch strip strums, and the screen shows what your hands are doing.

Pushtoo is for *playing*. If you want deep control of a DAW from the Push (tracks, devices, clips, mixer), use [DrivenByMoss](https://mossgrabers.de) for Bitwig or Reaper instead; the two can't share the Push at the same time.

> **Status:** early development. Keyboard, Drums and the chord grid, note repeat, the arpeggiator and the clock, Knobs, and YAML profiles work; loops (a step sequencer and a MIDI looper) are next. See [docs/PRD.md](docs/PRD.md) for the product spec.

## Playing

1. Plug in Push 2 and run `uv run pushtoo`.
2. In your DAW or synth, choose the MIDI input **Pushtoo Out**. Under PipeWire it may appear as `Midi-Bridge:Pushtoo: Out (capture)`. Pushtoo marks its port as leading to a device, so DAWs that list only hardware MIDI ports on JACK or PipeWire, such as REAPER, list it too: enable it in REAPER's Preferences > MIDI Devices.
3. Play the pads. Pushtoo starts in C minor on MIDI channel 1.

Pushtoo has two main modes, each on its own button: **Note** (Play) and **Device** (Knobs). Pads keep playing in Knobs mode, so you can play and tweak at once. In Play mode, the screen names the current layout and shows only what's active and changes what you play: Accent, Chromatic, Strum, a moved chord octave, or a hardware destination in place of Pushtoo Out. Channels and the touch strip mode stay on their pages.

| Control                         | What it does                                                         |
| ------------------------------- | -------------------------------------------------------------------- |
| Note, Device                    | Play and Knobs modes                                                 |
| Browse                          | Profile list: encoder 1 picks, top-left button loads. Browse again, or the `‹` button at the bottom right, goes back |
| Layout                          | Tap to cycle Keyboard (channel 1), Drums (channel 10) and the chord grid (channels 2 and 3). Hold it and press the button above a layout's name to go straight there |
| Scale                           | Open or close the scale selector: top buttons pick In key/Chromatic and C G D A E B F#, bottom buttons pick F Bb Eb Ab Db Gb, encoder 1 picks the scale, encoder 2 the root |
| Octave up / down                | Keyboard and chords: shift an octave. Drums: shift one bank of 16 notes. A button goes dark when it can't go further |
| Buttons below the display       | Pages: **Play** (octave or drum notes, velocity curve), **Strip** (pitch bend or mod wheel), **Output** (destination port and channel) |
| Buttons above the display       | Options on the current page                                          |
| Encoders above the display      | The current page's controls. Touch one to see its value full-size    |
| Shift + encoder                 | Fine adjust (4x finer)                                               |
| Accent                          | Every note at full velocity                                          |
| Repeat                          | Rhythm on or off: held pads repeat in time, or arpeggiate. Hold it for rhythm only while held |
| Side buttons (with rhythm on)   | The rate, as printed on them: 1/32t to 1/4. In the Chord layout, hold Repeat to pick one |
| Play                            | Start and stop: sends MIDI Start and Stop; the button flashes on each beat |
| Tap Tempo                       | Set the tempo from your last four taps                               |
| Tempo and Swing encoders (left) | Tempo (Shift for 0.1 BPM steps) and swing. Touch one to see its value |
| Touch strip                     | Pitch bend or mod wheel, set on the Strip page                       |
| Shift + Stop                    | Panic: all notes off on every output                                 |
| Undo, Shift + Undo              | Undo and redo in your DAW (Ctrl+Z and Ctrl+Shift+Z by default)       |
| Master encoder (right)          | Master level CC, in every mode                                       |
| Hold Shift                      | Lists what Shift does in the current mode                            |
| Hold Delete                     | In Knobs mode: touch a knob to reset it (the screen says so while Delete is held) |

**The chord grid** (the Chord layout) makes every pad a full chord in your key, played with one press. Columns are the steps of the key, so a progression is a hand shape: I–V–vi–IV is the same four pads in any key. Rows, bottom to top: bass notes, triads (the home row), 7ths, add9, sus, 9ths, borrowed chords from the parallel major or minor (violet), and secondary dominants that pull toward the chord in their column (pink). Colors show what each chord does: home chords in orange, chords that move away in blue, tension in yellow. The screen has a small map of the pads in the same colors, with each row's name beside it. With nothing playing it also shows a color legend; while you play, it lights the row you pressed.

The side buttons pick the **voicing**. The right-hand edge of the screen, next to them, names each button from top to bottom: the voicing you kept is filled in the Play accent, one you're holding is white, and Latch turns yellow when it's on. The buttons light up the same way. **Smooth** (top, the default) moves as little as possible from one chord to the next so progressions glide; the same pad may voice differently depending on what you played before. The others force an inversion (Root, 1st, 2nd, 3rd) or spread the chord out (Open, Wide), so a pad always plays the same notes. Tap one to keep it, or hold it to use it only while held. The bottom side button is **Latch**: chords keep sounding after you let go, so one hand can tap chords while the other strums. While Latch is holding a chord, the screen says "Latched · tap it again to stop". If you press a side button from Knobs or Mix, a short message says what it did. The right-hand column is the first column's chord an octave higher, and the screen says "octave up" when you play it. The screen shows each chord's name, its Roman numeral and what it does ("V7 · tension"). Hold a bass-row pad under a chord and the name shows the bass after a slash, such as G/B. On the **Style** page, **Press** plays the chord on pad press and **Strum** turns the touch strip into a strum plate: hold a chord and slide across the strip. Each chord's root also plays on channel 3 for a bass synth; the **Output** page changes channels and mutes chords or bass.

**Rhythm.** Tap **Repeat** and held pads repeat at the rate lit on the side buttons; press harder on a pad and its repeats get louder. The **Rhythm** page (Keyboard and Chord) switches between **Repeat** and **Arp**, the arpeggiator, with its Pattern (Up, Down, Up-down, As played, Random), Octaves and Gate. In the Chord layout, Repeat retriggers the chord and Arp plays it note by note; Latch keeps it going. Pushtoo keeps its own tempo and sends MIDI clock on Pushtoo Out, so a synth or DAW can follow it. If your DAW sends clock to **Pushtoo In**, Pushtoo follows instead and says "Following clock" on screen. Steps are scheduled ahead on the ALSA sequencer, so timing holds steady (under 1 ms) however busy Pushtoo is.

**Knobs mode** gives you up to 8 pages of 8 named controls, defined in your profile. Each column's top button glows in that control's color. To map a control in your DAW, start the DAW's MIDI learn, hold **Shift** and tap the button above the knob: Pushtoo sends just that control's CC, three times, so the DAW catches the right one. Hold **Delete** and touch a knob to reset it to its default.

**Mix mode** (an extra, on the Mix button) turns the 8 encoders into fader CCs, with mute and solo toggles on the top two pad rows. Each fader shows M and S chips that light red and blue, the same as their pads. Press Mix again, or the `‹` button at the bottom right of the display, to go back to where you were.

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

## Themes

Every color on the screen and the LEDs comes from a theme. The default follows the Open Color theme of [INTERSECT](https://github.com/tucktuckg00se/INTERSECT): a lime accent on a dark slate screen. On first run Pushtoo writes it, fully commented, to `~/.config/pushtoo/themes/oc.yaml`. Edit it while Pushtoo runs and the screen and pads change when you save.

To make your own, add a file to that folder and point your profile at it with `theme: <file name without .yaml>`. A theme only needs the colors it changes; everything else comes from Open Color:

```yaml
name: Teal
play: 20c997        # the Play accent: labels, arcs, the kept voicing
tension: ff922b
```

Colors are hex `RRGGBB` or the name of another color in the theme (`home: play`). Colors name what they mean: `play`, `knobs` and `mix` are the mode accents; `root`, `in_scale`, `out_of_scale` and `held` color the pads; `home`, `away`, `tension`, `borrowed` and `secondary` color the chord grid; `latch`, `mute` and `solo` are states; `background`, `track`, `line`, `text` and `text_dim` are the screen; and `red` to `gray` are the colors a profile can give its knobs. If a theme has a mistake, the Push screen shows the file, line and color, and Pushtoo keeps the last working version.

## Development

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and the ALSA, JACK and cairo development headers.

```sh
uv sync
uv run pytest
uv run ruff check
uv run pushtoo
uv run python tools/render_preview.py   # every screen as PNG, no hardware needed
uv run python tools/latency/latency.py  # latency gate; needs Push attached
uv run python tools/clock/jitter.py     # clock timing gate (p99 < 1 ms); needs ALSA
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
