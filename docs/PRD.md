# PRD: Pushtoo, Push 2 as an instrument

Oct 4, 2026 · Tucker · Revised Oct 5, 2026: repositioned instrument-first after the M3 design review

## Overview

Pushtoo turns an Ableton Push 2 on Linux into a playable instrument for any synth, DAW or hardware rig. Plug it in, point a synth at **Pushtoo Out**, and play: scales that are always in key, drums, a chord grid where every pad is a good-sounding chord, strumming on the touch strip, and named knobs for shaping the sound. It is a fork of [Pysha](https://github.com/ffont/pysha), runs as a desktop app, and sends standard MIDI, so it works with anything that listens.

**Problem.** Push 2 is premium hardware, but outside Ableton Live on Linux it is 64 pads and 11 encoders with no labels, no feedback and a dark screen. For deep control of one DAW there is a good answer already: [DrivenByMoss](https://mossgrabers.de) integrates Push 2 deeply with Bitwig and Reaper, including the display. What doesn't exist is Push 2 as an instrument you can play with any synth, any DAW, a live-coding tool or a rack of hardware, with a screen that teaches you as you play.

**Vision.** Plug in Push, pick a sound, and make music within a minute. Every pad sounds good, the screen explains what your hands are doing, and the instrument rewards noodling: progressions become shapes, rhythms come from a button, and leaving it alone still makes music.

**Positioning.** Pushtoo is for playing; DrivenByMoss is for DAW control. They can't share the Push at the same time, and Pushtoo doesn't try to replace it. Mixing, clip launching and DAW feedback are out of scope.

## Goals, non-goals, and success metrics

v1 succeeds if a new user is playing chords and drums on a synth within 5 minutes and wants to keep going.

**Goals**

1. Make playing feel good immediately: everything in key, every pad musical, no setup before the first sound.
2. Work with anything that takes MIDI, through virtual ports or straight to hardware ports, with no DAW scripts.
3. Make every control self-describing: anything lit or touchable has a label, value or role on screen.
4. Reach any mode, page or setting in two presses or fewer.
5. Stay out of the way: latency is sacred, and fun features never slow the pads.

**Non-goals for v1**

- DAW integration: track names, device parameters, clip launching, mixer feedback. Use DrivenByMoss for that.
- An audio engine; Pushtoo sends MIDI only.
- Push 1 or Push 3 support, and Windows or macOS packaging.

**Success metrics**

| Metric                                                    | Target                               |
| --------------------------------------------------------- | ------------------------------------ |
| Install to first note                                     | Under 5 min                          |
| A by-ear player makes a chord progression they like       | Under 2 min, 4 of 5 testers          |
| Pad press to MIDI out latency                             | Under 3 ms at p99                    |
| Display frame rate during play                            | Steady 30 fps minimum, 60 fps target |
| Testers who describe it as "fun" unprompted               | 3 of 5                               |

## Users and use cases

The primary user is a Linux musician with a Push 2 who wants to play, not operate software.

| User                 | Typical setup                                      | Core need                                                         |
| -------------------- | -------------------------------------------------- | ----------------------------------------------------------------- |
| By-ear player        | A soft synth or DAW, little theory                 | Chords and melodies that sound good without knowing why            |
| Hardware jammer      | USB-MIDI interface to synths and drum machines     | Play and shape several devices on separate channels, no computer DAW |
| DAW musician         | Bitwig, Reaper or Ardour                           | An expressive instrument to record parts with; tweak a few named knobs |
| Live performer       | Laptop or Pi on stage                              | Reliable, readable controls in the dark and a Panic that always works |
| Tinkerer             | Any of the above                                   | Edit profiles in a text file and share them                        |

**Key scenarios**

1. Open any synth, pick "Pushtoo Out", and play a I–V–vi–IV progression on the chord grid in a key you like.
2. Strum chords on the touch strip while the bass follows on its own channel.
3. Play drums on channel 10 and a bass synth on channel 2 from one Push, straight into hardware.
4. Map 8 knobs to a synth's filter and envelope, name them, and find them again tomorrow.

## Design principles

These six principles settle design disputes; when two conflict, the earlier one wins.

1. **Instant beats impressive.** Input-to-sound latency is sacred. Rendering runs in its own process and never delays MIDI.
2. **Every pad sounds good.** Defaults stay in key; anything that might clash is a deliberate, clearly colored choice.
3. **One press, one musical result.** Prefer layouts where a single press makes a complete musical thing over combinations that need two hands timed together.
4. **The screen explains the hardware.** Every lit pad, button or encoder has a matching label, color, role or value on screen.
5. **Never lose your place.** State persists across restarts, and Panic always works.
6. **Fun is a feature.** Playful moments are designed in, but optional and never in the way.

## Core experience: modes and navigation

Pushtoo's core is two modes, each on its own button. Play has three layouts, cycled with the Layout button as on stock Push. Everything sits in a simple hierarchy: **Profile → Mode → Page → Control**.

| Mode   | Push button | Pads                                                         | Encoders                                    | Screen shows                                   |
| ------ | ----------- | ------------------------------------------------------------ | ------------------------------------------- | ---------------------------------------------- |
| Play   | Note        | Keyboard (in key or chromatic, fourths), Drums (4 banks of 16), or the Chord grid | Per layout, by page: octave, strum, chord velocity, rhythm, outputs and channels | Key and held notes, drum names, or chord name, role and voicing |
| Knobs  | Device      | Keep playing the current Play layout                         | Up to 8 pages of 8 named CCs                | Named arcs with live values, in each control's color |

**Extras.** Mix mode (8 fader CCs, mute and solo pads) remains available on the Mix button for people who want it, but it isn't part of the core pitch and gets no further investment.

**Push 2 button map**

| Push 2 control                                               | Pushtoo function                                             |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| Note                                                         | Play mode                                                    |
| Layout                                                       | Tap: cycle Play's layouts (Keyboard, Drums, Chord). Hold: the buttons above the display name and pick them |
| Scale                                                        | Open the scale selector                                      |
| Device                                                       | Knobs mode                                                   |
| Browse                                                       | Profile browser                                              |
| Setup                                                        | Setup: pad feel, aftertouch, brightness, clock               |
| Mix                                                          | Mix mode (extra)                                             |
| 8 buttons below the display                                  | Pages of the current mode                                    |
| 8 buttons above the display                                  | Options on the current page; Shift + button is Learn Assist in Knobs |
| 8 encoders above the display                                 | Current page's controls; touch to peek                       |
| Tempo and Swing encoders (left)                              | Tempo and swing; touch to peek                               |
| Master encoder (right)                                       | Master level CC                                              |
| Octave up and down                                           | Shift the keyboard or chords an octave, or the drums a bank  |
| Touch strip                                                  | Pitch bend or mod wheel; strums in the Chord layout's Strum style |
| Scene buttons (right of pads)                                | Chord layout: voicing (rates while Repeat is held). Keyboard and Drums: rates while rhythm is on |
| Accent                                                       | Fixed full velocity                                          |
| Repeat                                                       | Rhythm on and off (note repeat or arpeggiator); hold for momentary |
| Undo, Shift + Undo                                           | Undo and redo keystrokes or MIDI, per profile                |
| Shift + Stop Clip                                            | Panic                                                        |
| Delete + touch an encoder                                    | Reset that control to its default                            |
| Play                                                         | Start and stop the transport (MIDI Start and Stop); pulses on beats |
| Tap Tempo                                                    | Set the tempo from the last four taps                        |
| Record, Metronome                                            | Looper (Loops milestone)                                     |
| Session, arrows, Mute, Solo, and the remaining buttons       | Unassigned                                                   |

**Scale selector**

Pressing Scale opens an overlay modeled on stock Push's scale menu, shared by every Play layout. While it's open, it borrows both button rows:

- **Buttons above the display:** In key / Chromatic toggle, then roots C, G, D, A, E, B, F#.
- **Buttons below the display:** Roots F, Bb, Eb, Ab, Db, Gb, in circle-of-fifths order like stock Push.
- **Encoder 1** scrolls the scale list. **Encoder 2** turns the root, for browsing keys by ear.
- Press Scale again to close it. Pads keep sounding while it's open, and a held chord follows the new key live.

In key / Chromatic applies to the Keyboard layout; the chord grid is always built from the key.

**Navigation rules**

- The 8 buttons below the display pick pages; the 8 above pick options. Each label sits next to its button, and the current page is highlighted.
- Each layout's first page is its main page, named for the layout and holding what you reach for while playing; the pages after it are settings, in the same order everywhere (feel, then Rhythm, then Output last). Big playing aids like the chord grid's pad map appear only on the main page, so settings pages keep the room for the setting at hand.
- Shift combinations are secondary actions, and holding Shift lists them on screen.
- Touching an encoder "peeks" without changing anything: its control grows in place (a bigger arc, a brighter name, a larger value) and the rest of the screen stays. Tempo, Swing and Master have no column, so they show the same way in the edge column nearest them (left for Tempo and Swing, right for Master).
- Each mode remembers its page and layout, and each profile remembers where you left off.
- Key and scale are shared by every Play layout.
- Extras (Mix, Browse) close with their own button or the `‹` button at the bottom right, which names the mode it returns to.
- Pushtoo sends on "Pushtoo Out" by default. Each layout can instead send straight to a hardware MIDI port, so a USB-MIDI rig needs no DAW.

**Default MIDI map**

Every default CC comes from MIDI's undefined or general-purpose ranges (14–29, 102–117), so nothing triggers sustain, modulation or volume before the user maps it.

| Source                 | Channel | Messages                                         |
| ---------------------- | ------- | ------------------------------------------------ |
| Keyboard layout        | 1       | Notes, poly aftertouch, pitch bend, mod wheel    |
| Chord layout           | 2, 3    | Chords; bass notes                               |
| Drums layout           | 10      | Notes 36–99 in four banks (General MIDI kit at 36–51) |
| Mix (extra)            | 14      | Faders CC 102–109, master CC 110, mute CC 14–21, solo CC 22–29 |
| Knobs pages 1–4        | 15      | 32 CCs: 14–29, 102–117                           |
| Knobs pages 5–8        | 16      | 32 CCs: 14–29, 102–117                           |

## Chord layout: the chord grid

Every pad is a complete chord in your key, played with one press. Columns are the steps of the key; rows are chord flavors. A progression is a hand shape: I–V–vi–IV is the same four pads in every key.

```
           col:  I     ii    iii   IV    V     vi    vii°  I'      Side buttons
row 8   Secondary dominants: V7 of each column's chord (pink)          ( Smooth )
row 7   Borrowed: same step from the parallel major/minor (violet)     ( Root   )
row 6   9th chords                                                     ( 1st    )
row 5   sus4 (sus2 where the 4th isn't in key)                         ( 2nd    )
row 4   add9                                                           ( 3rd    )
row 3   7ths                                                           ( Open   )
row 2   Triads  ← home row                                             ( Wide   )
row 1   Bass notes: each column's root, low                            ( Latch  )

In C major, row 2 is C Dm Em F G Am Bdim C and row 3 is Cmaj7 Dm7 Em7 Fmaj7 G7 Am7 Bm7b5 Cmaj7.
```

**Playing**

- One press plays one chord. The last chord pressed sounds; releasing it stops it. Changes re-trigger the whole chord.
- Each chord also sends its root to the bass channel (default 3). The bottom row plays single bass notes by hand, alongside chords. While one is held under a chord, the screen names it as a slash chord (G/B; the lowest held bass note wins, and a bass on the chord's root adds no slash).
- Rows 2–6 are always in key. Where a step's 9th would be a harsh flat 9th (iii and vii in major), the add9 and 9th rows use the 11th instead. Rows 7–8 are the deliberate spice.
- Scales with fewer than 7 notes build their chords from a parent scale (pentatonic and blues from major or minor), and the screen says so.
- Colors show what each chord does: home (I, iii, vi) orange like root pads, moving away (ii, IV) blue, tension (V, vii°) yellow, borrowed violet, secondary dominants pink, bass soft white.
- The right-hand column (I') is the first column's chord lifted an octave: under Smooth, exactly the voicing the left column would get right now, plus 12. It is a deliberate "go higher" move, never a duplicate.
- Octave moves the chord register. Accent forces full velocity.

**Voicing and Latch (side buttons, top to bottom)**

- **Smooth** (default) voices each chord with the least movement from the previous one, kept near that chord's root, so progressions glide instead of jumping. The same pad can therefore play different inversions depending on what came before, which is what makes it sound good. Measured over 5,000 random changes: about 5.5 semitones of total movement per change (a fixed voicing per pad would be about 17), and the register stays within roughly two octaves; it cannot drift away.
- **Root, 1st, 2nd, 3rd** force an inversion, so every pad plays the same notes every time; **Open** is drop-2; **Wide** puts the root an octave down and spreads the rest.
- Tap a voicing button to keep it; hold one to use it only while held. Pressing a voicing while a chord sounds re-voices it so you hear the difference. The current voicing stays lit.
- **Latch** (bottom) keeps a chord sounding after you let go, until you press another chord, tap the same pad again, or turn Latch off. One hand taps chords while the other strums or plays the bass row.

**Strum** (Style page)

A chord pad plays only its bass note, and the touch strip strums the voiced chord across 1–3 octaves, one note per tone crossed, like an Omnichord. Strummed notes ring until the chord changes or is released. In Strum style the strip runs in the Push's mod-wheel mode, because pitch-bend mode springs back to center and would strum again on release.

**Pages:** Chord, the main page (Octave and Voicing on the encoders, the pad map on screen), then the settings: Style (Press or Strum, strum range), Velocity and Timing (below), Rhythm, and Output (destination, chords channel, bass channel, Mute chords, Mute bass).

**Velocity** (Velocity page)

- **As played** or **Random**, above the display. **Min** and **Max** always apply: the pad's velocity sets a center scaled into that range, so hitting harder still plays louder.
- **Random** gives each note of each chord trigger its own velocity within **Spread** of the center, clamped to Min–Max. Spread 0 is an even chord; full Spread is anywhere in the range. **Top note** (−32…+32) offsets the highest note so a melody can stand out or sit back. The bass note plays at the center, unrandomized.
- **Accent** means as loud as the range allows: the center moves to Max, so Random spreads accented chords downward from Max. With As played, accented chords play at Max.
- Every trigger rolls fresh: a press, a retrigger, each strummed note, and each Repeat or Arp step. The screen draws each note's velocity as a bar under its name; on pages with many encoders the pad map steps aside to make room.

**Timing** (Timing page)

- **Together** or **Spread out**, above the display. Spread out rolls a chord's notes in one after another: **Roll** (0–100 ms between notes), **Direction** (Up from the lowest note, Down from the highest, Alternate flipping each chord like a strumming hand, or Random) and **Loose** (0–50 ms of random lateness per note).
- Notes only come later, never early; the first note and the bass play at the press.
- Later notes are queued on the ALSA sequencer like rhythm steps and tracked like any held note, so releasing mid-roll takes back what hasn't started and nothing hangs. Repeat and Arp steps roll too; Strum keeps its own timing on the strip.
- The status line says "Rolled ↑ 30 ms" or "Loose 12 ms" while it's on.

**Screen:** the side-button rail and the pad map (see Visual design system), then the chord name in plain words ("Fm7"; chords without a common name show their notes, never a wrong name), then a line with the Roman numeral and role ("V7 · tension", "bVII · borrowed", "V7/vi · leads to vi") and the voicing, then the notes, spelled with flats in flat keys and sharps in sharp keys. By ear first, theory one glance away.

## Setup

The Setup button opens settings that belong to the Push and the person playing it, so they're shared by every profile and saved in the session state. Pads keep playing in Setup, so every change is felt as it's made.

- **Pads:** Sensitivity (1–10), Dynamics (−10…+10) and Min and Max velocity build the 128-step velocity table Push applies in hardware. The screen draws the curve, with a dot where the last hit landed. Response (Regular, Reduced, Low) is Push's own pad sensitivity, for crosstalk and double hits.
- **Aftertouch:** Poly, Channel or Off, and the pressure where it starts and where it reaches full.
- **Display:** pad and button brightness, and screen brightness. On USB power alone, Push caps both.
- **Clock:** send MIDI clock on Pushtoo Out; follow clock on Pushtoo In.

The profile's `velocity_curve` (Linear, Soft, Hard) seeds Dynamics (0, −5, +5) on a first run only.

## Rhythm: clock, note repeat and arpeggiator

Rhythm comes from a button: hold pads and they repeat in time, or hold a chord and it arpeggiates.

**Clock**

- Pushtoo leads with its own tempo by default. When MIDI clock arrives on Pushtoo In, it follows automatically and the screen says "Following clock · 124". Two seconds without clock returns it to its own tempo.
- The Tempo encoder sets 40–240 BPM (Shift for 0.1 BPM steps); the Swing encoder sets 50–75%, delaying every other step. Touching either shows it at the screen's left edge, beside the knob.
- Tap Tempo sets the tempo from the last four taps.
- Play starts and stops the transport, sending MIDI Start and Stop, and its LED pulses on beats while running. While following, the leader's Start and Stop drive it.
- While leading, Pushtoo sends 24-ppqn MIDI clock on Pushtoo Out all the time, so synths and DAWs can lock to its tempo. Setup can turn this off, and can stop Pushtoo following incoming clock.

**Repeat and the side buttons**

- Repeat turns rhythm on or off; holding it makes rhythm last only while held.
- With rhythm on, held pads retrigger on the beat grid at the chosen rate, with a 50% gate. Pressure on a held pad sets each repeat's velocity, as on stock Push. A pad still sounds the moment it's pressed; repeats follow on the grid.
- Rates sit on the side buttons, as printed on them, top to bottom: 1/32t, 1/32, 1/16t, 1/16, 1/8t, 1/8, 1/4t, 1/4. In Keyboard and Drums the side buttons are rates while rhythm is on. In the Chord layout they stay voicings, and holding Repeat turns them into rates until it's released. The screen rail names whichever set is active.
- In the Chord layout, Repeat retriggers the whole voiced chord.

**Arpeggiator**

- A Rhythm page in Keyboard and Chord picks **Repeat** or **Arp** on the buttons above the display, with Rate on the first encoder and, for the Arp only, Pattern (Up, Down, Up-down, As played, Random), Octaves (1–4) and Gate (10–100%). Drums only repeat. Choosing Repeat or Arp turns rhythm on.
- Keyboard arpeggiates the notes you hold. Chord arpeggiates the voiced chord, and Latch keeps it going after you let go.

**Screen:** while rhythm is on, the status line shows "Repeat 1/16" or "Arp Up 1/16" and the tempo; the tempo also shows while the transport runs.

**Timing:** clock and rhythm run on their own thread and never delay pad input; the latency gate (N1) must still pass with it running. Steps are stamped 20 ms ahead on an ALSA sequencer queue, so the kernel delivers them on time whatever Python is doing; hardware destinations go through the same client and queue. Pushtoo sets Python's thread switch interval to 1 ms so the scheduling thread always gets in within the lookahead. Measured with `tools/clock/jitter.py` (see Notes from building).

## Visual design system

The display is a strict 8-column grid that mirrors the hardware, and color ties the screen to the pads.

**Form follows function.** Each physical control gets a screen element in the place nearest to it, in its LED's color. Screen space goes to state, not settings: the play screens show what's active and changes what your hands do (Accent, Chromatic, Strum, a moved octave, a hardware destination), while channels, the usual destination and the strip mode stay on their own pages. The bands name the buttons above and below the display, and the columns name the encoders. In the Chord layout, the last column is a rail naming the side buttons just to its right, top to bottom: the kept voicing is filled with the Play accent, a held one white, and Latch in the latch color; the button LEDs match. A miniature pad map in the pads' own colors labels the chord rows and lights the one you're playing. Mix's mute and solo pads show as chips under each fader. Held modifiers (Shift, Delete) list what they do. Octave buttons go dark at their limit. A side button pressed while its rail is off screen shows a toast.

**Display layout (960 x 160 px):** 8 columns of 120 px, each centered over its encoder. Top band 24 px for upper-button labels, bottom band 24 px for lower-button labels, middle 112 px for content. A selected button's label inverts.

**Typography:** IBM Plex Sans Condensed at 14 px labels, 20 px values (and touched knobs) and 48 px toasts; 12 px only for legends beside a hardware miniature. Names shorten with a middle ellipsis. Long messages wrap at 20 px instead of being cut.

**Color**

Every color is a token in a theme file (`~/.config/pushtoo/themes/*.yaml`, chosen per profile and hot-reloaded). Tokens name meanings, not hues, and one value drives both the screen and that token's LED palette slot. The default theme follows INTERSECT's Open Color theme, using mid shades (4–6) because pastels wash out to white on LEDs.

| Token          | Use                                    | Example                                                  |
| -------------- | -------------------------------------- | -------------------------------------------------------- |
| Screen         | background, track, line, text, text_dim | Black #000000; Open Color #343A40, #191C1F, #CED4DA, #868E96 |
| Mode accent    | Selected labels, mode headers          | Play lime #82C91E, Knobs yellow, Mix orange              |
| Control color  | Per encoder column, chosen in the profile | Shown on the arc and the button above the encoder     |
| Pad roles      | Root, in-scale, out-of-scale, held     | Orange, gray, near-off, white; the Play accent stays off the pads |
| Chord roles    | Home, away, tension, borrowed, secondary | Orange, blue, yellow, violet, pink                     |
| States         | Latch, mute, solo                      | Yellow, red, blue                                        |

Push 2's LED palette is reprogrammed on every connect and theme change so on-screen colors and pad colors match as closely as LEDs allow.

**Controls:** encoders render as 270-degree arcs; bipolar controls fill from 12 o'clock.

## UX details and delight

**Workflow**

- **Learn Assist.** Hold Shift and tap the button above a knob to send that knob's CC alone, three times, so DAW MIDI learn catches the right one.
- **Fine and coarse.** Shift + encoder moves values 4x finer. Delete + touch resets a control. Touch alone never changes a value.
- **Undo and redo.** Ctrl+Z and Ctrl+Shift+Z by default through a virtual keyboard (X11 and Wayland), or MIDI per profile. A toast confirms what was sent.
- **Panic.** Shift + Stop Clip sends note-offs for everything Pushtoo is holding, then All Notes Off and Reset on every channel of every output.
- **Feedback.** Every press lights its pad or button within a frame; short toasts confirm loads and explain errors in plain words.

**First run:** no setup. The screen says "Play any pad" and "Select Pushtoo Out in your DAW", and the pads glow in C minor.

**Delight (roadmap):** note repeat and arpeggiator, a drum step sequencer, a MIDI looper, living pads that ripple on press, Life mode (an idle Game of Life that can play notes in key), Dice for Knobs pages, snapshot morph on the touch strip.

## Technical architecture

Pushtoo forks Pysha and keeps its Python and pycairo core, but runs rendering in a separate process so the screen can never slow the pads ([ADR 0001](adr/0001-render-process.md)).

```
┌──────────┐      ┌──────────────── Pushtoo ────────────────────────────┐
│  Push 2  │ ◄──► │  Hardware I/O (push2-python fork): pads, buttons,   │
│          │      │  encoders, touch strip, LEDs                        │
└──────────┘      │        ▼                                            │
     ▲ USB        │  Modes: Play (Keyboard, Drums, Chord grid), Knobs;  │
     │ display    │  YAML profiles, session state                       │
     │            │        ▼                       │ view state         │
     │            │  MIDI router: virtual ports,   ▼                    │
     │            │  hardware ports, note       Renderer process        │
     │            │  tracking, Panic            (pycairo, 960x160) ─────┼──► display
     │            └──────┬──────────────────────────────────────────────┘
                         ▼
          Pushtoo Out, or hardware MIDI ports → any synth, DAW or rig
```

**Measured** (i7-12700K, Python 3.13, PipeWire). Details are in ADR 0001.

- Display: steady 60 fps at about 11% of one core.
- Pad to "Pushtoo Out" through the full app: p99 0.12–0.19 ms single notes, 0.50–0.58 ms three-note chords. A pure-Python busy thread in the same process pushes p99 to 160–300 ms, which is why rendering lives in its own process.
- push2-python ignores Push input for about 1 s after each (re)connect, which bounds hot-plug recovery.
- Under PipeWire the ports appear as "Midi-Bridge:Pushtoo: Out (capture)" and "…In (playback)".

## Requirements

P0 items ship in v1; P1 items ship in v1 if time allows; P2 items wait.

| ID   | Requirement                                                  | Priority | Status |
| ---- | ------------------------------------------------------------ | -------- | ------ |
| F1   | Virtual MIDI ports "Pushtoo Out" and "Pushtoo In" via ALSA, under PipeWire and JACK | P0 | Built |
| F2   | Keyboard layout with scales, root, octave, in-key and chromatic, velocity curves, poly aftertouch | P0 | Built |
| F19  | Drums layout: four banks of 16 from note 36 (General MIDI kit bottom-left) | P0 | Built |
| F12  | Chord grid: one-press chords by scale step and flavor, bass row, auto bass, function colors | P0 | Built |
| F28  | Chord voicing on the side buttons: Smooth voice leading, inversions, Open, Wide; tap to keep, hold for momentary | P0 | Built |
| F14  | Strum on the touch strip in the Chord layout                 | P0 | Built |
| F31  | Chord timing: Together or Spread out with Roll, Direction (Up, Down, Alternate, Random) and Loose; never early; releasing mid-roll takes back the rest | P0 | Built |
| F30  | Chord velocity: As played or Random with Min, Max, Spread and Top note; Accent centers at Max | P0 | Built |
| F22  | Touch strip as pitch bend or mod wheel                       | P0 | Built |
| F3   | Knobs mode: up to 8 pages x 8 named CC controls with ranges and colors | P0 | Built |
| F5   | Profiles as YAML in ~/.config/pushtoo, hot-reloaded, never written by Pushtoo | P0 | Built |
| F6   | Learn Assist, peek, fine adjust, reset, Undo, Panic          | P0 | Built |
| F13  | Page navigation on the buttons below the display             | P0 | Built |
| F15  | Scale selector and Layout cycling                            | P0 | Built |
| F16  | Undo and redo as keystrokes or MIDI                          | P0 | Built |
| F17  | Route any layout to a hardware MIDI port                     | P0 | Built |
| F18  | Default MIDI map, overridable per profile                    | P0 | Built |
| F29  | Setup: velocity curve (Sensitivity, Dynamics, Min, Max) with live graph, pad response, aftertouch mode and range, LED and display brightness, clock send and follow; device-wide, saved in state | P0 | Built |
| F23  | Note repeat on the Repeat button, rates on the side buttons in Keyboard and Drums | P0 | Built |
| F24  | Arpeggiator for held notes and chords                        | P0 | Built |
| F25  | Clock: internal tempo and swing on the left encoders; MIDI clock out on Pushtoo Out; follow incoming clock on Pushtoo In | P0 | Built |
| F26  | Drum step sequencer                                          | P1 | Loops |
| F27  | MIDI looper for standalone jams (Record, Play)               | P1 | Loops |
| F9   | Living pads and Life mode, each toggleable                   | P1 | Delight |
| F8   | Dice and snapshot morph for Knobs                            | P1 | Delight |
| F21  | Rename controls from the hardware; high-contrast and large-text settings | P2 | |
| F4   | Mix mode (extra): fader CCs, mute and solo pads              | P2 | Built, frozen |
| F10  | Optional browser-based profile editor                        | P2 | |
| N1   | Pad-to-MIDI latency under 3 ms at p99; rendering never blocks MIDI | P0 | Passing |
| N2   | Display at 30 fps minimum, 60 fps target                     | P0 | Passing |
| N3   | Survives Push unplug and replug without restart; held notes released on unplug | P0 | Built, hands-on check pending |
| N4   | One-command install with udev rule and bundled IBM Plex font | P0 | Beta |
| N5   | Runs on a Raspberry Pi 4 at reduced frame rate               | P1 | Beta |

Removed in this revision: DAW feedback (F7), Launch mode (F20), and auto-switching profiles per focused app (F11). They serve DAW control, which DrivenByMoss already does well.

## Milestones

| Milestone       | Scope                                                                 | Status |
| --------------- | --------------------------------------------------------------------- | ------ |
| M0 Foundation   | Fork, dependencies, virtual ports, render process, latency harness    | Done   |
| M1 Playable     | Keyboard and Drums, scale selector, velocity curves, touch strip, Panic, peek, hardware ports, hot-plug | Done; hands-on checks pending |
| M2 Design       | Design system, Knobs, YAML profiles and state, Learn Assist, Undo     | Done; hands-on checks pending |
| M3 Chords       | Chord grid with voicing and Strum                                     | Built; hardware check pending |
| M4 Rhythm       | Clock, note repeat, arpeggiator                                       | Built; hardware check pending |
| M5 Loops        | Drum step sequencer, MIDI looper                                      | Next   |
| M6 Delight      | Living pads, Life mode, Dice, snapshot morph                          |        |
| M7 Beta         | One-command installer, 5-tester study, Raspberry Pi check             |        |

The latency gate (`tools/latency/latency.py`) runs at every milestone and must pass before the next starts.

**Notes from building**

- Clock timing (`tools/clock/jitter.py`, 120 BPM, 24 ppqn, a busy Python thread competing): sleeping until each tick's deadline has p99 0.08 ms idle but 23 ms under load, because a thread holding the GIL keeps it for up to Python's 5 ms switch interval. Ticks stamped ahead on an ALSA queue hold p99 0.42 ms either way. With a 1 ms switch interval, a 20 ms lookahead holds 0.42 ms max under load, short enough that releasing a pad stops repeats at once; 10 ms needs the shorter interval too.

- Accent is applied in software: Push's velocity table also sets poly aftertouch sensitivity.
- The Push re-centers the touch strip by itself in pitch-bend mode.
- F# and Gb in the scale selector both select pitch class 6.
- Profiles are the user's files; session state lives in `~/.local/state/pushtoo/state.yaml`, keyed by profile, so hand edits and hardware changes never conflict.
- Hot reload keeps a knob's value only when its column still sends the same CC on the same channel.
- The first Chord layout (Orchid-style roots plus held chord types) was replaced after review: non-default chords needed two hands timed together, half its voicing rows repeated the others an octave up, extensions ignored the key, and some roots were unreachable in non-7-note scales.

**Risks**

| Risk                                                         | Mitigation                                                   |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| Users expect DAW control and compare Pushtoo to DrivenByMoss | Position clearly as an instrument; point DAW-control users to DrivenByMoss |
| Python rendering too slow on low-end machines                | Separate render process, frame dropping, lower Pi frame rate |
| push2-python and Pysha are unmaintained upstream             | Maintain the push2-python fork; keep dependencies small      |
| Clock timing jitter in Python (Rhythm milestone)             | Measure first; schedule MIDI clock in a dedicated thread or with ALSA queue timestamps |
| Undo keystrokes go to whichever window has focus             | Toast every shortcut sent; profiles can switch Undo to MIDI  |

**Open questions**

- [x] Pysha's license allows this fork: yes, MIT for Pysha and push2-python.
- [ ] Which audio stacks are in the v1 test matrix: PipeWire only, or also plain ALSA and JACK?
- [ ] Should Life mode play notes by default, or stay silent until switched on?
- [ ] Does the Smooth voicing need a "brightness" control (register drift up or down) once people play it?
- [x] Clock: lead or follow by default? Both, automatically: lead with Pushtoo's tempo, follow when clock arrives on Pushtoo In.
- [x] What should the spare eighth side button do in the Chord layout? Latch.
