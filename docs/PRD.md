# PRD: Pushtoo, a Push 2 Universal MIDI Controller

Oct 4, 2026 · Tucker · Revised Oct 4, 2026 after the PRD review and M0 hardware spike

## Overview

Pushtoo turns an Ableton Push 2 on Linux into a DAW-agnostic MIDI controller with a better screen, clearer workflow, and more joy than Push gets outside Ableton Live. It is a fork of [Pysha](https://github.com/ffont/pysha), runs as a desktop app, and exposes virtual MIDI ports that any DAW, synth, or hardware rig can use.

**Problem.** Push 2 is premium hardware, but its deep workflow lives only inside Live, which has no official Linux build. In User mode on Linux it becomes 64 pads and 11 encoders with no labels, no feedback, and a dark screen. Users either write DAW-specific scripts or settle for a generic controller that forgets what every knob does.

**Vision.** Plug in Push, open any app, and play within a minute. The screen always tells you what your hands are touching, two presses reach anything, and the instrument rewards noodling.

## Goals, non-goals, and success metrics

v1 succeeds if a new user can control a synth in any Linux DAW within 5 minutes and wants to keep playing afterward.

**Goals**

1. Work with any DAW or MIDI app through standard virtual MIDI ports, with no DAW scripts required.
2. Make every control self-describing: anything lit or touchable has a label or value on screen.
3. Reach any mode, page, or setting in two presses or fewer.
4. Feel fun and alive without adding latency or getting in a pro's way.

**Non-goals for v1**

- Deep DAW integration such as track names, device parameters, or clip state (possible later via optional bridges).
- Audio engine or sample playback; Pushtoo sends MIDI only.
- Push 1 or Push 3 support, and Windows or macOS packaging.

**Success metrics**

| Metric                                          | Target                               |
| ----------------------------------------------- | ------------------------------------ |
| Install to first note                           | Under 5 min                          |
| Pad press to MIDI out latency                   | Under 3 ms at p99                    |
| Display frame rate during play                  | Steady 30 fps minimum, 60 fps target |
| New user maps a filter cutoff in a DAW, no docs | Under 60 s, 4 of 5 test users        |
| Testers who describe it as "fun" unprompted     | 3 of 5                               |

## Users and use cases

The primary user is a Linux musician who owns a Push 2 and works across more than one app.

| User            | Typical setup                                  | Core need                                                    |
| --------------- | ---------------------------------------------- | ------------------------------------------------------------ |
| DAW producer    | Bitwig, Reaper, or Ardour on a Linux desktop   | Play melodies in key and tweak plugin parameters without the mouse |
| Hardware jammer | USB-MIDI interface to synths and drum machines | Play and modulate several devices on separate MIDI channels  |
| Live performer  | Laptop on stage with a DAW or live-coding tool | Reliable, readable controls in the dark and a panic button that always works |
| Tinkerer        | Any of the above                               | Edit profiles in a text file and share them                  |

**Key scenarios**

1. Open Reaper, pick the "Pushtoo Out" port, and play a pad melody in D minor.
2. Map 8 encoders to a synth's filter, envelope, and FX, name them, and recall the page tomorrow.
3. Control a drum machine on channel 10 and a bass synth on channel 2 from one Push without reconfiguring.
4. Mid-set, find out what an encoder does by touching it, without changing its value.

## Design principles

These six principles settle design disputes; when two conflict, the earlier one wins.

1. **Instant beats impressive.** Input-to-sound latency is sacred. Animations run on their own thread and never delay MIDI.
2. **The screen explains the hardware.** Every lit pad, button, or encoder has a matching label, color, or value on screen, aligned to its physical position.
3. **Playable first.** Pushtoo boots straight into Play mode, in key, ready to play the moment a DAW or synth listens on "Pushtoo Out". Setup is optional, never a gate.
4. **Two presses to anywhere.** Modes live on dedicated buttons. Shift adds secondary actions, and holding Shift shows them on screen, so nothing is hidden.
5. **Never lose your place.** State persists across restarts, every mapping change can be undone, and Panic always works.
6. **Fun is a feature.** Playful moments (motion, surprise, toys) are designed in, but always optional and never in the way of focused work.

## Core experience: modes and navigation

Pushtoo has five modes, each on its own Push button, so switching is always one press. Play mode has three layouts (Keyboard, Drums, and Chord), cycled with the Layout button as on stock Push. Everything sits in a simple hierarchy: **Profile → Mode → Page → Control**.

| Mode   | Push button | Pads                                                         | Encoders                                                     | Screen shows                                        |
| ------ | ----------- | ------------------------------------------------------------ | ------------------------------------------------------------ | --------------------------------------------------- |
| Play   | Note        | Three layouts, cycled with Layout: scale-aware Keyboard (in-key, chromatic, isomorphic 4ths), 4x4 Drums, and Chord (see Chord layout) | Per layout, by page: octave, velocity curve, MIDI channel, chord style and voicing | Scale map and held notes, or chord name and voicing |
| Knobs  | Device      | Unchanged from Play, so you can play and tweak at once       | 8 pages x 8 named CCs with ranges and colors                 | Named arcs with live values per column              |
| Mix    | Mix         | Mute, solo, and toggle CCs per column                        | 8 faders as CC volumes, master encoder as master             | Fader values; meters when DAW feedback (F7) is on   |
| Launch | Session     | 8x8 grid sending notes for DAW clip launch via MIDI learn    | Scene and bank scrolling                                     | Grid labels and DAW feedback when available         |
| Setup  | Setup       | Profile slots                                                | Global settings                                              | Ports, theme, brightness, about                     |

**Push 2 button map**

Dedicated buttons keep modes one press away; cycling through modes with a single button would break the two-presses rule. Functions follow stock Push wherever the stock meaning makes sense outside Live.

| Push 2 control                                               | Pushtoo function                                             |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| Note                                                         | Play mode                                                    |
| Layout                                                       | Cycle Play's layouts: Keyboard, Drums, Chord                 |
| Scale                                                        | Open the scale selector (see below)                          |
| Device                                                       | Knobs mode                                                   |
| Mix                                                          | Mix mode                                                     |
| Session                                                      | Launch mode                                                  |
| Setup                                                        | Setup mode                                                   |
| Browse                                                       | Profile browser                                              |
| 8 buttons below the display                                  | Pages of the current mode                                    |
| 8 buttons above the display                                  | Options on the current page                                  |
| 8 encoders above the display                                 | Current page's controls; touch to peek                       |
| Tempo and Swing encoders (left)                              | Internal tempo and swing for arp, repeat, and animations when no MIDI clock arrives |
| Master encoder (right)                                       | Master level CC                                              |
| Octave up and down                                           | Shift the keyboard, or the chord voicing ladder, by an octave |
| Page left and right                                          | Previous and next page; in Launch, scroll banks              |
| Arrow buttons                                                | Launch: scroll scenes and tracks                             |
| Touch strip                                                  | Pitch bend or mod wheel; strums in the Chord layout          |
| Scene buttons (right of pads)                                | Note repeat rates in Keyboard and Drums; chord extensions in Chord |
| Repeat, Accent                                               | Note repeat; fixed full velocity                             |
| Undo, Shift + Undo                                           | DAW undo and redo (see UX details)                           |
| Delete, Shift + Delete                                       | Clear the selected mapping; Dice                             |
| Stop Clip, Shift + Stop Clip                                 | Launch: stop clips; Panic                                    |
| Mute, Solo                                                   | Unassigned for now; Mix mode's top pad rows toggle mute and solo |
| Shift, Select                                                | Modifiers                                                    |
| Play, Record, Metronome, Tap Tempo                           | MIDI transport and tempo (see open questions)                |
| Add Device, Add Track, Clip, Master, Convert, Double Loop, Quantize, Duplicate, New, Fixed Length, Automate, User | Reserved for later features                                  |

**Scale selector**

Pressing Scale opens an overlay modeled on stock Push's scale menu, shared by every Play layout. While it's open, it borrows both button rows:

- **Buttons above the display:** In key / Chromatic toggle, then roots C, G, D, A, E, B, F#.
- **Buttons below the display:** Roots F, Bb, Eb, Ab, Db, Gb, in circle-of-fifths order like stock Push.
- **Encoder 1** scrolls the scale and mode list (Major, Minor, Dorian, Mixolydian, Lydian, Phrygian, and more). **Encoder 2** turns the root, for browsing keys by ear.
- Press Scale again to close it. Pads keep sounding while it's open, so you can audition each choice.

In the Chord layout, Chromatic turns off the key hints and out-of-key dimming.

**Navigation rules**

- **The 8 buttons below the display pick pages** within the current mode, such as Style, Voicing, and Output in the Chord layout. Each page name sits directly above its button, and the current page is highlighted.
- **The 8 buttons above the display pick options** on the current page, such as a performance style. Each label sits directly under its button.
- Settings live on pages or dedicated buttons, not hidden menus. Shift combinations (Redo, Dice, Panic, Learn Assist, fine adjust) are secondary actions, and holding Shift lists them on screen.
- Touching an encoder "peeks": its value goes full-size on screen without changing.
- Each mode remembers its last page and layout, and each profile stores all modes. Browse opens the profile browser.
- Key and scale are shared by every Play layout, so switching layouts never changes key.
- Pushtoo sends on one main virtual port, "Pushtoo Out", by default. Per-mode and per-layout MIDI channels (see Default MIDI map) keep Keyboard, Drums, Chord, Knobs, and Mix separable in any DAW. Any channel can instead go straight to a hardware MIDI port (F17), so a USB-MIDI rig needs no DAW in between.

**Default MIDI map**

Every default CC comes from MIDI's undefined or general-purpose ranges (14–29, 102–117), so nothing triggers sustain, modulation, or volume on a synth before the user maps it.

| Source                 | Channel | Messages                                         |
| ---------------------- | ------- | ------------------------------------------------ |
| Keyboard layout        | 1       | Notes, poly aftertouch, pitch bend, mod wheel    |
| Chord layout           | 2, 3, 4 | Chords, bass, arp                                |
| Drums layout           | 10      | Notes 36–51 (General MIDI drum map)              |
| Launch                 | 13      | Notes 36–99, one per pad                         |
| Mix                    | 14      | Faders CC 102–109, master CC 110, mute CC 14–21, solo CC 22–29 |
| Knobs pages 1–4        | 15      | 32 CCs: 14–29, 102–117                           |
| Knobs pages 5–8        | 16      | 32 CCs: 14–29, 102–117                           |

## Chord layout

The Chord layout turns Push into a chord instrument built for playing by ear: one tap plays a chord that fits the key, and a progression keeps the same shape in every key. It borrows the [Telepathic Instruments Orchid](https://telepathicinstruments.com/products/orchid-orc-1)'s two-handed idea of roots plus chord types, but places roots relative to the key, the way Push's scale mode places notes. It's a layout of Play mode: press Note, then Layout until Chord appears.

Layout in C major:

```
              [ Screen: chord name, notes, page labels ]
Pages       [Style] [Voicing] [Output] [    ] [    ] [    ] [    ] [    ]
                                                                        Extensions
 ↑ Row 8    [    ] [    ] [    ] [    ] [    ] [    ] [    ] [    ]    ( +6  )
 │ Row 7    [    ] [    ] [    ] [    ] [    ] [    ] [    ] [    ]    ( +9  )
 │ Row 6    [    ] [    ] [    ] [    ] [    ] [    ] [    ] [    ]    ( +11 )
 │ Row 5    [    ] [    ] [    ] [    ] [    ] [    ] [    ] [    ]    ( +13 )
 │ Row 4    [    ] [    ] [    ] [    ] [    ] [    ] [    ] [    ]    (     )
 Voicing    [Auto] [Maj ] [Min ] [ 7  ] [Maj7] [ m7 ] [Sus4] [Dim ]    (     )
 Out-of-key [ C# ] [ D# ] [    ] [ F# ] [ G# ] [ A# ] [    ] [    ]    (     )
 In-key     [ C* ] [ D  ] [ E  ] [ F  ] [ G  ] [ A  ] [ B  ] [ C* ]    (     )

 * = home note (root accent color). Chord type runs across the columns;
     each row up is the next voicing, so higher rows sound brighter.
```

Changing the key slides the root rows so the home note is always at the far left.

**Pad layout**

- **Row 1 (bottom): in-key roots.** The home note is always the leftmost pad, followed by the other scale notes, then the home note an octave up on the right. Home pads use the root accent color.
- **Row 2: out-of-key roots.** These sit in the gaps between in-key roots, like black keys on a piano. Unused pads stay dark.
- **Rows 3 to 8: chord type across, voicing up.** Columns are Auto, Maj, Min, 7, Maj7, m7, Sus4, and Dim. Each row up is the next inversion, one chord tone higher, so higher rows sound brighter.
- **Pads are only musical.** Every setting lives on knobs, pages, or buttons, never on pads.

**Playing**

- Tap a root alone to play its Auto chord: the chord that fits the key on that root, or major for out-of-key roots.
- Hold a type or voicing pad to change what the roots play. Sound starts on whichever press comes second, and the last grid choice stays selected so one-handed root playing keeps its color. Tapping Auto returns to the in-key default.
- The screen shows inversion names for the selected column. In other columns, chord types that fit the key on the current root glow in the hint color, which is distinct from the root accent.
- When the Strum style is active, the touch strip strums the held chord, Omnichord-style.

**Side buttons**

The 8 scene buttons to the right of the pads add extensions (+6, +9, +11, +13) that stack on any chord. The other 4 are reserved for later features.

**Pages (buttons below the display)**

Key and scale come from the Scale button, so the pages hold only chord settings.

| Page    | Encoders                                                     | Buttons above the display               |
| ------- | ------------------------------------------------------------ | --------------------------------------- |
| Style   | Settings for the current style, such as strum speed, arp rate, and swing | Off, Strum, Arp, Harp, Slop             |
| Voicing | Auto-smooth on or off, voicing spread, bass note on or off, octave | Close, Open, and Spread voicing presets |
| Output  | MIDI channels for chords, bass, and arp; velocity            | Mute chords, bass, or arp               |

Changing key or scale in the scale selector while holding a chord transposes or reharmonizes it live, and the "fits the key" hints update as you turn.

**By-ear defaults**

- The screen shows plain chord names. Theory labels such as Roman numerals are an optional setting.
- In key is on by default; out-of-key roots are dimmed but still playable.
- Scales and modes appear in one plain list of names.

## Visual design system

The display is a strict 8-column grid that mirrors the hardware, and color ties the screen to the pads. This is where Pushtoo beats the stock Ableton UI: larger type, values that are always visible, and one color language across screen and LEDs.

**Display layout (960 x 160 px)**

- 8 columns of 120 px, each centered over its encoder and between its upper and lower buttons.
- Top band, 24 px: upper-button labels. Bottom band, 24 px: lower-button labels. Middle, 112 px: content.
- A selected button's label inverts (accent background, dark text), so the current page is readable at arm's length.

**Typography**

- One condensed sans family (for example IBM Plex Sans Condensed), at three sizes: 14 px labels, 20 px values, 48 px peek and toasts.
- Names truncate with a middle ellipsis ("Filt…Cut") rather than clipping.

**Color**

| Token         | Use                                    | Example                                                      |
| ------------- | -------------------------------------- | ------------------------------------------------------------ |
| Background    | Display base                           | Near-black #0E0F12                                           |
| Mode accent   | Selected labels, mode headers          | Play teal, Knobs amber, Mix coral, Launch violet, Setup gray |
| Control color | Per encoder column, chosen by the user | Matches the pads or LEDs it relates to                       |
| Pad roles     | Root, in-scale, out-of-scale, held     | Accent, soft white, dim, full white                          |
| Hint          | Chord types that fit the key           | A pale tint distinct from every mode accent                  |

Push 2's LED palette is reprogrammed on every connect so on-screen colors and pad colors match as closely as LEDs allow.

**Controls and motion**

- Encoders render as 270-degree arcs with the value in the center; bipolar controls fill from 12 o'clock.
- Value changes ease over 60 ms; page changes slide over 150 ms. All motion is skippable and pauses if the frame budget is tight.
- A high-contrast theme and a large-text setting ship in v1 for dark stages and tired eyes.

## UX details and delight

The UX solves the real pains of generic controllers (MIDI learn chaos, lost values, mystery knobs), then adds toys that make people stay.

**Sensible workflow**

- **Learn Assist.** Generic controllers spray CCs while you hunt for the right knob, so DAW MIDI learn grabs the wrong one. Hold Shift and tap an upper button to send that column's CC alone, three times, cleanly. Mapping becomes one tap.
- **Name it on the box.** Rename any control from the hardware: turn encoder 1 for letters and encoder 2 for position, or pick from a list of common names (Cutoff, Res, Attack, Mix).
- **Fine and coarse.** Shift + encoder moves values 4x finer. Holding Delete and touching an encoder resets it to its default, as on stock Push. Touch alone never changes a value.
- **Pickup mode.** If the DAW sends feedback, Pushtoo syncs its values; if not, a hollow arc shows the last-known value and "pickup" prevents jumps.
- **Undo and redo in the DAW.** Undo sends the DAW's undo shortcut (Ctrl+Z by default) and Shift + Undo sends redo (Ctrl+Shift+Z by default). Each profile can change the shortcut, for apps that use Ctrl+Y, or send a MIDI message instead for DAWs that map actions to MIDI. A short toast confirms what was sent.
- **Undo inside Pushtoo.** While an edit screen is open (renaming a control, editing a mapping), Undo and Shift + Undo revert Pushtoo's own changes instead, and the toast says so.
- **Panic.** Shift + Stop Clip sends All Notes Off and resets controllers on every channel. It works in every mode, always.
- **Feedback.** Every press lights its pad or button within one frame. Short toasts (1.5 s) confirm saves, profile loads, and errors in plain words.

**First run**

The first launch skips setup. The screen says "Play any pad" and "Select Pushtoo Out in your DAW," pads glow in C minor, and a single toast points to the Setup button. After the first note, a one-time hint teaches peek: "Touch any knob to see what it does."

**Fun features**

- **Living pads.** Pressed pads ripple outward in their color, synced to incoming MIDI clock when present.
- **Snapshot morph.** Save up to 8 encoder snapshots per page, then glide between two with the touch strip. Great for builds and drops.
- **Dice.** Shift + Delete randomizes the current Knobs page within each control's set range, with Undo one press away.
- **Note repeat and arp.** Hold Repeat and press pads for tempo-synced rolls, with swing and rate on the encoders.
- **Life mode.** An idle screensaver runs Conway's Game of Life on the pads. Optionally, living cells play notes in the current scale, so leaving Push alone makes music.
- **Tiny trophies.** Gentle, mutable easter eggs, such as a confetti animation for your 1,000th note in a session.

## Technical architecture

Pushtoo forks Pysha and keeps its Python and pycairo core, but runs rendering in a separate process so the screen can never slow the pads ([ADR 0001](adr/0001-render-process.md)).

```
                  ┌──────────────── Pushtoo (Pysha fork) ───────────────┐
┌──────────┐      │  Hardware I/O                                       │
│  Push 2  │ ◄──► │  push2-python: MIDI in, LED colors;                 │
│ pads,    │      │  display frames over libusb                         │
│ knobs:   │      │            ▲                     ▲                  │
│ MIDI     │      │            ▼                     │ frames           │
│ screen:  │      │  Mode manager + mapping engine   │                  │
│ USB      │      │  Play, Knobs, Mix, Launch, Setup modes;             │
└──────────┘      │  YAML profiles, undo history     │                  │
                  │       │                │         │                  │
                  │       ▼                ▼         │                  │
                  │  MIDI router        Renderer ────┘                  │
                  │  python-rtmidi,     own process, pycairo,           │
                  │  channels per mode, 960x160, 30 to 60 fps           │
                  │  panic, MIDI clock                                  │
                  └──────┬──────────────────────────────────────────────┘
                         ▼▲
                  Virtual ports: Pushtoo Out / Pushtoo In (feedback)
                         ▼▲
                  Any DAW or app: Bitwig, Reaper, Ardour; synths via USB-MIDI
```

Input flows from Push through the mode manager to the MIDI router and out the virtual ports; DAW feedback returns the same way. The renderer runs in its own process, owns the display's USB connection, and always draws the newest state it has received. The MIDI process never waits on it.

**Measured in M0** (i7-12700K, Python 3.13, PipeWire). Details are in ADR 0001.

- Display: steady 60 fps. CPU cost is about 1.8 ms per frame (11% of one core at 60 fps); the rest of each frame is the USB write waiting on the display.
- Pad to "Pushtoo Out": p99 about 0.2 ms with the display running. A pure-Python busy thread in the same process pushed p99 to 160–300 ms, which is why rendering lives in its own process.
- push2-python ignores Push input for about 1 s after each (re)connect, which bounds hot-plug recovery.
- Under PipeWire the ports appear as "Midi-Bridge:Pushtoo: Out (capture)" and "…In (playback)". rtmidi creates one ALSA client per port, so `aconnect -l` lists two clients named "Pushtoo".

**Key changes from Pysha**

- Update dependencies (mido, python-rtmidi, push2-python) for current Python 3 releases. push2-python is unmaintained upstream, so Pushtoo uses a fork with its simulator's web dependencies made optional.
- Replace hard-coded Squarp Pyramid routing with the generic virtual-port router.
- Move rendering to a dedicated process that drops stale frames rather than delaying MIDI.
- Replace in-code mappings with YAML profiles and a schema, validated on load with clear error toasts.
- Add a hot-plug watcher and a udev rule installer for display access without root.
- Add a keystroke output through Linux uinput (for example with python-evdev), so buttons like Undo can send shortcuts. Unlike X11-only tools, uinput works under both X11 and Wayland; the installer's udev rule grants access without root.

## Requirements

P0 items ship in v1; P1 items ship in v1 if time allows; P2 items wait for later.

| ID   | Requirement                                                  | Priority |
| ---- | ------------------------------------------------------------ | -------- |
| F1   | Create virtual MIDI ports "Pushtoo Out" and "Pushtoo In" via ALSA, working under PipeWire and JACK | P0       |
| F2   | Play mode with scales, root, octave, in-key and chromatic layouts, velocity curves, poly aftertouch | P0       |
| F19  | Drums layout: 4x4 pads on the General MIDI drum map, starting at note 36 | P0       |
| F22  | Touch strip as pitch bend or mod wheel, chosen per profile   | P0       |
| F3   | Knobs mode with 8 pages x 8 encoders, each with name, CC, channel, range, color, default | P0       |
| F4   | Mix mode as described in Core experience                     | P0       |
| F5   | Profiles stored as human-readable YAML in ~/.config/pushtoo, hot-reloaded on save | P0       |
| F6   | Learn Assist, peek, fine adjust, Undo, and Panic             | P0       |
| F12  | Chord layout with key-relative roots, type and voicing grid, extension buttons, and Output page | P0       |
| F13  | Page navigation on the buttons below the display in every mode | P0       |
| F15  | Scale selector on the Scale button, and Layout cycling Play's layouts | P0       |
| F16  | Undo and redo sent to the DAW as configurable keystrokes or MIDI, with Pushtoo's own undo in edit screens | P0       |
| F17  | Route any mode or layout channel to a hardware MIDI port instead of "Pushtoo Out" | P0       |
| F18  | Default MIDI map as specified in Core experience, overridable per profile | P0       |
| F7   | Read DAW feedback on "Pushtoo In" to update values, LEDs, and Mix meters | P1       |
| F20  | Launch mode as described in Core experience                  | P1       |
| F21  | Rename controls from the hardware; high-contrast theme and large-text setting | P1       |
| F8   | Snapshot morph, Dice, note repeat and arpeggiator            | P1       |
| F14  | Chord layout Style and Voicing pages: Strum, Arp, Harp, Slop, touch-strip strumming, auto-smooth | P1       |
| F9   | Life mode and other fun extras, each toggleable in Setup     | P1       |
| F10  | Optional browser-based profile editor                        | P2       |
| F11  | Auto-switch profile based on the focused desktop app         | P2       |
| N1   | Pad-to-MIDI latency under 3 ms at p99; rendering never blocks MIDI | P0       |
| N2   | Display at 30 fps minimum, 60 fps target, on a mid-range laptop | P0       |
| N3   | Survives Push unplug and replug without restart; held notes are released on unplug | P0       |
| N4   | One-command install, including a udev rule for display USB access | P0       |
| N5   | Runs on a Raspberry Pi 4 at reduced frame rate               | P1       |

## Milestones, risks, and open questions

The revised plan puts a playable controller in hands by week 6 and a tested beta by week 20, assuming one part-time developer. The original 14-week plan left several P0 items unscheduled.

| Milestone        | Weeks    | Scope                                                                 |
| ---------------- | -------- | --------------------------------------------------------------------- |
| M0 Foundation    | 1 to 2   | Fork, dependencies, virtual ports, render process, latency harness, minimal Play mode (done) |
| M1 Playable      | 3 to 6   | Keyboard and Drums layouts, scale selector and Layout cycling, velocity curves, touch strip, Panic, peek, hardware port output, hot-plug (built; hands-on checks pending) |
| Gate             |          | Pad latency under 3 ms at p99 with the real app (`tools/latency`): passed, p99 0.19 ms single notes, 0.53 ms chords |
| M2 Design        | 7 to 11  | Design system, Knobs and Mix modes, YAML profiles and default MIDI map, Learn Assist, Undo keystrokes (built; hands-on checks pending) |
| M3 Chords        | 12 to 16 | Chord layout (F12); P1 items as time allows: Launch, Dice, DAW feedback |
| Gate             |          | Feature freeze                                                        |
| M4 Beta          | 17 to 20 | One-command installer, 5-tester study, Raspberry Pi check             |

M2 cannot start until the latency gate passes, and nothing new enters after the M3 feature freeze.

**M1 notes**

- Accent is applied in software. Push's velocity table also sets poly aftertouch sensitivity, so a fixed-127 table would break aftertouch.
- The Push returns the touch strip to center by itself in pitch-bend mode, so Pushtoo sends no reset.
- F# and Gb in the scale selector both select pitch class 6 and display as F#.
- Session state (key, layout, octave) is not saved yet; M2's profiles will store it.

**M2 notes**

- Profiles are the user's files: Pushtoo reads and hot-reloads them but never writes them. Session state (mode, pages, key, octave, layout outputs, knob and fader values) lives in `~/.local/state/pushtoo/state.yaml`, keyed by profile. This removes the two-writers conflict between hand edits and hardware changes.
- Hot reload keeps a knob's value only when its column still sends the same CC on the same channel; a remapped control starts from its default.
- Mix mode's pads: the top row toggles mute, the second row solo, and the bottom six rows keep playing the current Play layout. The Mute and Solo buttons are unassigned.
- Pushtoo's own undo inside edit screens waits for edit screens (on-hardware rename, F21).
- The latency gate still passes with profiles, state saving and the app lock: p99 0.12–0.15 ms single notes, 0.50–0.58 ms chords.

**Risks**

| Risk                                                         | Mitigation                                                   |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| Python rendering is too slow on low-end machines             | Separate render process (measured: 60 fps at 11% of a desktop core), frame dropping, lower Pi frame rate; port rendering to C++ with Ableton's JUCE example if needed |
| push2-python and Pysha are unmaintained upstream             | Maintain a fork of push2-python; keep the dependency surface small |
| Without DAW feedback, on-screen values drift from reality    | Pickup mode, hollow "last-known" arcs, optional feedback port |
| Display access needs USB permissions                         | Ship a udev rule with the installer and a clear error toast  |
| Fun features crowd the core                                  | All fun features are P1, toggleable, and grouped under one Setup switch |
| Undo keystrokes go to whichever window has focus, which may not be the DAW | Toast shows every shortcut sent; profiles can switch Undo to MIDI, which reaches the DAW regardless of focus |

**Open questions**

- [x] Confirm Pysha's license allows this fork and redistribution. Yes: Pysha and push2-python are MIT; keep their copyright notices.
- [ ] Which audio stacks are in the v1 test matrix: PipeWire only, or also plain ALSA and JACK?
- [ ] Should Life mode play notes by default, or stay silent until switched on?
- [ ] Is Push 3 controller-mode support worth planning for v2?
- [ ] Check that the Orchid's patent-pending voicing dial doesn't cover the Chord layout's voicing ladder before public release.
- [ ] What should the 4 reserved scene buttons in the Chord layout do?
- [ ] Chord layout: does a lone root tap play Auto or the last grid selection, and does pressing a type pad while a root sounds retrigger or morph the chord? Decide before M3.
- [ ] Touch strip precedence when pitch bend, Chord strumming, and Snapshot morph all want it.
- [ ] Should Play, Record, Metronome, and Tap Tempo send MIDI transport messages, DAW keystrokes (like Space for play), or be configurable per profile?
- [ ] Which reserved buttons (Duplicate, Quantize, New, and others) are worth mapping to DAW shortcuts?
