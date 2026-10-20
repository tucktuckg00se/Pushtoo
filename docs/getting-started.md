---
title: Getting started
nav_order: 3
description: "From plugging in a Push 2 to playing scales, drums and chords: the first sound, the three layouts and the two modes."
---

# Getting started
{: .no_toc }

1. TOC
{:toc}

## First sound

1. Plug in Push 2. If you didn't set up the [background service]({{ site.baseurl }}{% link installation.md %}#running-in-the-background), run `pushtoo`.
2. In your DAW or synth, choose the MIDI input **Pushtoo Out**.
   - Under PipeWire it may appear as `Midi-Bridge:Pushtoo: Out (capture)`.
   - Pushtoo marks its port as leading to a device, so DAWs that list only hardware MIDI ports on JACK or PipeWire, such as REAPER, list it too. In REAPER, enable it in **Preferences > MIDI Devices**.
3. Play the pads. Pushtoo starts in C minor on MIDI channel 1.

No sound? See [Troubleshooting]({{ site.baseurl }}{% link troubleshooting.md %}).

## Button names

Pushtoo uses Push 2's buttons for its own features, so some printed labels don't match what they do. The screen and the button lights always show the Pushtoo function.

| Printed label | In Pushtoo |
| --- | --- |
| **Note** | Play mode |
| **Device** | Knobs mode |
| **Session** | [Life]({{ site.baseurl }}{% link life.md %}) on or off |
| **Repeat** | [Rhythm]({{ site.baseurl }}{% link rhythm-and-clock.md %}): note repeat or the arpeggiator |
| **Layout** | Switch between Keyboard, Drums and the chord grid |
| Side buttons (1/32t to 1/4) | The rhythm rate, or the chord voicing in the Chord layout |

## Two modes

Pushtoo has two main modes, each on its own button:

- **Note** (Play): the pads play notes in the current layout.
- **Device** ([Knobs]({{ site.baseurl }}{% link knobs-and-mix.md %})): the encoders send the CCs your profile names. The pads keep playing, so you can play and tweak at once.

In Play mode, the screen names the current layout and shows only what's active and changes what you play: Accent, Chromatic, Strum, a moved chord octave, or a hardware destination in place of Pushtoo Out. Channels and the touch strip mode stay on their pages.

## Three layouts

Tap **Layout** to cycle through them; it switches when you let go. Or hold Layout and press the button above a layout's name to go straight there.

| Layout | Channel | What the pads do |
| --- | --- | --- |
| **Keyboard** | 1 | Notes in your scale, roots in orange |
| **Drums** | 10 | Four banks of 16 drum pads, starting with the General MIDI kit |
| **Chord** (the chord grid) | 2 (chords), 3 (bass) | A full chord in your key on every pad |

More: [Keyboard and Drums]({{ site.baseurl }}{% link keyboard-and-drums.md %}), [Chord grid]({{ site.baseurl }}{% link chord-grid.md %}).

## Pages and encoders

- The **buttons below the display** pick a page. The first is each layout's main page, named for it (Keyboard: octave; Drums: notes; Chord: octave, voicing and the pad map). The rest are its settings, ending with **Output** (destination port and channel).
- The **buttons above the display** are options on the current page.
- The **encoders above the display** are the current page's controls. Touch one and it grows a little on screen, so you can see which knob you're on. Hold **Shift** while turning for 4x finer steps.
- Hold **Shift** at any time to see what Shift does in the current mode.

## Pick a key

Press **Scale**. The top buttons pick In key or Chromatic and the roots C G D A E B F#; the bottom buttons pick F Bb Eb Ab Db Gb. Encoder 1 picks the scale, encoder 2 the root and encoder 3 the chord grid's [chord set]({{ site.baseurl }}{% link chord-grid.md %}#chord-sets). Press Scale again to close it.

## Next

- Learn every control: [Controls]({{ site.baseurl }}{% link controls-reference.md %})
- Play chords: [Chord grid]({{ site.baseurl }}{% link chord-grid.md %})
- Tune the pads to your hands: [Setup]({{ site.baseurl }}{% link setup.md %})
- Name your knobs: [Profiles]({{ site.baseurl }}{% link profiles.md %})
