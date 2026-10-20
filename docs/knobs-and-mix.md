---
title: Knobs and Mix
nav_order: 9
description: "Knobs mode gives you pages of named, colored CC controls from your profile; Mix mode turns the encoders into faders with mute and solo pads."
---

# Knobs and Mix
{: .no_toc }

1. TOC
{:toc}

## Knobs mode

Press **Device** for Knobs mode: up to 8 pages of 8 named controls, defined in your [profile]({{ site.baseurl }}{% link profiles.md %}). Each column's top button glows in that control's color. The pads keep playing, so you can play and tweak at once.

Without a `knobs` section in your profile you get 8 pages of 8 knobs on channels 15 and 16, using MIDI CCs that no synth treats specially, so nothing changes until you map it.

### Mapping a knob in your DAW

1. Start your DAW's MIDI learn.
2. Hold **Shift** and tap the button above the knob.

Pushtoo sends just that control's CC, three times, so the DAW catches the right one.

### Resetting a knob

Hold **Delete** and touch a knob to reset it to its default. The screen says so while Delete is held.

## Mix mode

**Mix mode** (an extra, on the **Mix** button) turns the 8 encoders into fader CCs, with mute and solo toggles on the top two pad rows. Each fader shows M and S chips that light red and blue, the same as their pads.

Press Mix again, or the `‹` button at the bottom right of the display, to go back to where you were.

## Master level

The master encoder (top right) sends a master level CC in every mode.
