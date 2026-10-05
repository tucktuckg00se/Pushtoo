# PRD: Pushtoo, a Push 2 Universal MIDI Controller

Oct 4, 2026 · Tucker

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
3. **Playable first.** Pushtoo boots straight into Play mode, in key, making sound. Setup is optional, never a gate.
4. **Two presses to anywhere.** Modes live on dedicated buttons; Shift reveals extra options and never hides core ones.
5. **Never lose your place.** State persists across restarts, every mapping change can be undone, and Panic always works.
6. **Fun is a feature.** Playful moments (motion, surprise, toys) are designed in, but always optional and never in the way of focused work.

## Core experience: modes and navigation

Pushtoo has five modes, each on its own Push button, so switching is always one press. Play mode has three layouts (Keyboard, Drums, and Chord), cycled with the Layout button as on stock Push. Everything sits in a simple hierarchy: **Profile → Mode → Page → Control**.

| Mode   | Push button | Pads                                                         | Encoders                                                     | Screen shows                                        |
| ------ | ----------- | ------------------------------------------------------------ | ------------------------------------------------------------ | --------------------------------------------------- |
| Play   | Note        | Three layouts, cycled with Layout: scale-aware Keyboard (in-key, chromatic, isomorphic 4ths), 4x4 Drums, and Chord (see Chord layout) | Per layout, by page: octave, velocity curve, MIDI channel, chord style and voicing | Scale map and held notes, or chord name and voicing |
| Knobs  | Device      | Unchanged from Play, so you can play and tweak at once       | 8 pages x 8 named CCs with ranges and colors                 | Named arcs with live values per column              |
| Mix    | Mix         | Mute, solo, and toggle CCs per column                        | 8 faders as CC volumes, master encoder as master             | Vertical meters and fader values                    |
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
| Mute, Solo                                                   | Mix: mute and solo modifiers                                 |
| Shift, Select                                                | Modifiers                                                    |
| Play, Record, Metronome, Tap Tempo                           | MIDI transport and tempo (see open questions)                |
| Add Device, Add Track, Clip, Master, Convert, Double Loop, Quantize, Duplicate, New, Fixed Length, Automate, User | Reserved for later features                                  |

**Scale selector**

Pressing Scale opens an overlay modeled on stock Push's scale menu, shared by every Play layout. While it's open, it borrows both button rows:

- **Buttons above the display:** In key / Chromatic toggle, then roots C, G, D, A, E, B, F#.
- **Buttons below the display:** Roots F, Bb, Eb, Ab, Db, Gb, in circle-of-fifths order like stock Push.
- **Encoder 1** scrolls the scale and mode list (Major, Minor, Dorian, Mixolydian, Lydian, Phrygian, and more). **Encoder 2** turns the root, for browsing keys by ear.
- Press Scale again, or play any pad, to close it. Pads keep sounding while it's open, so you can hear each choice.

In the Chord layout, Chromatic turns off the key hints and out-of-key dimming.

**Navigation rules**

- **The 8 buttons below the display pick pages** within the current mode, such as Style, Voicing, and Output in the Chord layout. Each page name sits directly above its button, and the current page is highlighted.
- **The 8 buttons above the display pick options** on the current page, such as a performance style. Each label sits directly under its button.
- Settings live on pages or dedicated buttons, not hidden menus, so nothing requires a Shift combination to find.
- Touching an encoder "peeks": its value goes full-size on screen without changing.
- Each mode remembers its last page and layout, and each profile stores all modes. Browse opens the profile browser.
- Key and scale are shared by every Play layout, so switching layouts never changes key.
- Pushtoo sends on one main virtual port, "Pushtoo Out". Per-mode and per-layout MIDI channels keep Keyboard, Chord, Knobs, and Mix separable in any DAW.

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
- In the selected column, pads show inversion names. In other columns, chord types that fit the key on the current root glow light teal.
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

Changing key or scale in the scale selector while holding a chord transposes or reharmonizes it live, and the teal "fits the key" hints update as you turn.

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

Push 2's LED palette is reprogrammed at startup so on-screen colors and pad colors match exactly.

**Controls and motion**

- Encoders render as 270-degree arcs with the value in the center; bipolar controls fill from 12 o'clock.
- Value changes ease over 60 ms; page changes slide over 150 ms. All motion is skippable and pauses if the frame budget is tight.
- A high-contrast theme and a large-text setting ship in v1 for dark stages and tired eyes.

## UX details and delight

The UX solves the real pains of generic controllers (MIDI learn chaos, lost values, mystery knobs), then adds toys that make people stay.

**Sensible workflow**

- **Learn Assist.** Generic controllers spray CCs while you hunt for the right knob, so DAW MIDI learn grabs the wrong one. Hold Shift and tap an upper button to send that column's CC alone, three times, cleanly. Mapping becomes one tap.
- **Name it on the box.** Rename any control from the hardware: turn encoder 1 for letters and encoder 2 for position, or pick from a list of common names (Cutoff, Res, Attack, Mix).
- **Fine and coarse.** Shift + encoder moves values 4x finer. Pressing an encoder's touch twice quickly resets it to its default.
- **Pickup mode.** If the DAW sends feedback, Pushtoo syncs its values; if not, a hollow arc shows the last-known value and "pickup" prevents jumps.
- **Undo and redo in the DAW.** Undo sends the DAW's undo shortcut (Ctrl+Z by default) and Shift + Undo sends redo (Ctrl+Shift+Z by default). Each profile can change the shortcut, for apps that use Ctrl+Y, or send a MIDI message instead for DAWs that map actions to MIDI. A short toast confirms what was sent.
- **Undo inside Pushtoo.** While an edit screen is open (renaming a control, editing a mapping), Undo and Shift + Undo revert Pushtoo's own changes instead, and the toast says so.
- **Panic.** Shift + Stop Clip sends All Notes Off and resets controllers on every channel. It works in every mode, always.
- **Feedback.** Every press lights its pad or button within one frame. Short toasts (1.5 s) confirm saves, profile loads, and errors in plain words.

**First run**

The first launch skips setup. The screen says "Play any pad," pads glow in C minor, and a single toast points to the Setup button. After the first note, a one-time hint teaches peek: "Touch any knob to see what it does."

**Fun features**

- **Living pads.** Pressed pads ripple outward in their color, synced to incoming MIDI clock when present.
- **Snapshot morph.** Save up to 8 encoder snapshots per page, then glide between two with the touch strip. Great for builds and drops.
- **Dice.** Shift + Delete randomizes the current Knobs page within each control's set range, with Undo one press away.
- **Note repeat and arp.** Hold Repeat and press pads for tempo-synced rolls, with swing and rate on the encoders.
- **Life mode.** An idle screensaver runs Conway's Game of Life on the pads. Optionally, living cells play notes in the current scale, so leaving Push alone makes music.
- **Tiny trophies.** Gentle, mutable easter eggs, such as a confetti animation for your 1,000th note in a session.

## Technical architecture

Pushtoo forks Pysha and keeps its Python and pycairo core, but separates rendering from MIDI so the screen can never slow the pads.

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
                  │  python-rtmidi,     own thread, pycairo,            │
                  │  channels per mode, 960x160, 30 to 60 fps           │
                  │  panic, MIDI clock                                  │
                  └──────┬──────────────────────────────────────────────┘
                         ▼▲
                  Virtual ports: Pushtoo Out / Pushtoo In (feedback)
                         ▼▲
                  Any DAW or app: Bitwig, Reaper, Ardour; synths via USB-MIDI
```

Input flows from Push through the mode manager to the MIDI router and out the virtual ports; DAW feedback returns the same way. The renderer draws frames on its own thread and hands them to the hardware layer.

**Key changes from Pysha**

- Update dependencies (mido, python-rtmidi, push2-python) for current Python 3 releases.
- Replace hard-coded Squarp Pyramid routing with the generic virtual-port router.
- Move rendering to a dedicated thread with a frame budget, dropping frames rather than delaying MIDI.
- Replace in-code mappings with YAML profiles and a schema, validated on load with clear error toasts.
- Add a hot-plug watcher and a udev rule installer for display access without root.
- Add a keystroke output through Linux uinput (for example with python-evdev), so buttons like Undo can send shortcuts. Unlike X11-only tools, uinput works under both X11 and Wayland; the installer's udev rule grants access without root.

## Requirements

P0 items ship in v1; P1 items ship in v1 if time allows; P2 items wait for later.

| ID   | Requirement                                                  | Priority |
| ---- | ------------------------------------------------------------ | -------- |
| F1   | Create virtual MIDI ports "Pushtoo Out" and "Pushtoo In" via ALSA, working under PipeWire and JACK | P0       |
| F2   | Play mode with scales, root, octave, in-key and chromatic layouts, velocity curves, aftertouch | P0       |
| F3   | Knobs mode with 8 pages x 8 encoders, each with name, CC, channel, range, color, default | P0       |
| F4   | Mix and Launch modes as described in Core experience         | P0       |
| F5   | Profiles stored as human-readable YAML in ~/.config/pushtoo, hot-reloaded on save | P0       |
| F6   | Learn Assist, peek, fine adjust, Undo, and Panic             | P0       |
| F12  | Chord layout with key-relative roots, type and voicing grid, extension buttons, and Output page | P0       |
| F13  | Page navigation on the buttons below the display in every mode | P0       |
| F15  | Scale selector on the Scale button, and Layout cycling Play's layouts | P0       |
| F16  | Undo and redo sent to the DAW as configurable keystrokes or MIDI, with Pushtoo's own undo in edit screens | P0       |
| F7   | Read DAW feedback on "Pushtoo In" to update values and LEDs  | P1       |
| F8   | Snapshot morph, Dice, note repeat and arpeggiator            | P1       |
| F14  | Chord layout Style and Voicing pages: Strum, Arp, Harp, Slop, touch-strip strumming, auto-smooth | P1       |
| F9   | Life mode and other fun extras, each toggleable in Setup     | P1       |
| F10  | Optional browser-based profile editor                        | P2       |
| F11  | Auto-switch profile based on the focused desktop app         | P2       |
| N1   | Pad-to-MIDI latency under 3 ms at p99; rendering never blocks MIDI | P0       |
| N2   | Display at 30 fps minimum, 60 fps target, on a mid-range laptop | P0       |
| N3   | Survives Push unplug and replug without restart              | P0       |
| N4   | One-command install, including a udev rule for display USB access | P0       |
| N5   | Runs on a Raspberry Pi 4 at reduced frame rate               | P1       |

## Milestones, risks, and open questions

The proposed plan gets a playable controller into hands by week 5 and a tested beta by week 14, assuming one part-time developer.

| Milestone     | Weeks    | Scope                                    |
| ------------- | -------- | ---------------------------------------- |
| M0 Foundation | 1 to 2   | Fork, update dependencies, virtual ports |
| M1 Playable   | 3 to 5   | Play and Mix modes, Panic, peek          |
| Gate          |          | Pad latency under 3 ms                   |
| M2 Design     | 6 to 9   | Design system, Knobs mode, profiles      |
| M3 Delight    | 10 to 12 | Chord layout, Dice, DAW feedback         |
| Gate          |          | Feature freeze                           |
| M4 Beta       | 13 to 14 | 5-tester study, install script           |

M2 cannot start until pad latency is under 3 ms, and nothing new enters after the M3 feature freeze.

**Risks**

| Risk                                                         | Mitigation                                                   |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| Python rendering is too slow on low-end machines             | Separate render thread, frame dropping, lower Pi frame rate; port rendering to C++ with Ableton's JUCE example if needed |
| Without DAW feedback, on-screen values drift from reality    | Pickup mode, hollow "last-known" arcs, optional feedback port |
| Display access needs USB permissions                         | Ship a udev rule with the installer and a clear error toast  |
| Fun features crowd the core                                  | All fun features are P1, toggleable, and grouped under one Setup switch |
| Undo keystrokes go to whichever window has focus, which may not be the DAW | Toast shows every shortcut sent; profiles can switch Undo to MIDI, which reaches the DAW regardless of focus |

**Open questions**

- [ ] Confirm Pysha's license allows this fork and redistribution.
- [ ] Which audio stacks are in the v1 test matrix: PipeWire only, or also plain ALSA and JACK?
- [ ] Should Life mode play notes by default, or stay silent until switched on?
- [ ] Is Push 3 controller-mode support worth planning for v2?
- [ ] Check that the Orchid's patent-pending voicing dial doesn't cover the Chord layout's voicing ladder before public release.
- [ ] What should the 4 reserved scene buttons in the Chord layout do?
- [ ] Should Play, Record, Metronome, and Tap Tempo send MIDI transport messages, DAW keystrokes (like Space for play), or be configurable per profile?
- [ ] Which reserved buttons (Duplicate, Quantize, New, and others) are worth mapping to DAW shortcuts?
