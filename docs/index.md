---
title: Home
layout: home
nav_order: 1
description: "Pushtoo turns an Ableton Push 2 on Linux into an instrument for any synth, DAW or hardware rig: scales in key, a chord grid, strumming, rhythm, and a screen that shows what your hands are doing."
permalink: /
---

# Pushtoo

Pushtoo turns an Ableton Push 2 on Linux into an instrument for any synth, DAW or hardware rig: plug in Push, pick the **Pushtoo Out** port, and play. Scales stay in key, every chord pad sounds good, the touch strip strums, and the screen shows what your hands are doing.

![Push 2 running Pushtoo in chord mode]({{ site.baseurl }}/images/pushtoo_chord_mode_cropped.jpg)
*The chord grid: the screen shows Fmaj9, the pad map and the voicing buttons.*

[Install]({{ site.baseurl }}{% link installation.md %}){: .btn .btn-primary }
[Getting started]({{ site.baseurl }}{% link getting-started.md %}){: .btn }
[GitHub repo](https://github.com/tucktuckg00se/Pushtoo){: .btn }

Pushtoo is for *playing*. If you want deep control of a DAW from the Push (tracks, devices, clips, mixer), use [DrivenByMoss](https://mossgrabers.de) for Bitwig or Reaper instead; the two can't share the Push at the same time.

{: .note }
**Status:** beta (0.1.0b3). Testers welcome: see [Beta testing]({{ site.baseurl }}{% link beta-testing.md %}).

---

## New here?

[Install]({{ site.baseurl }}{% link installation.md %}) Pushtoo with one command, then follow **[Getting started]({{ site.baseurl }}{% link getting-started.md %})**: from plugging in to your first chords in a few minutes.

## Documentation

### Start
- [Installation]({{ site.baseurl }}{% link installation.md %}): requirements, the installer, the background service, upgrading and uninstalling
- [Getting started]({{ site.baseurl }}{% link getting-started.md %}): first sound, the three layouts and the two modes
- [Controls]({{ site.baseurl }}{% link controls-reference.md %}): every button, encoder and shortcut

### Playing
- [Chord grid]({{ site.baseurl }}{% link chord-grid.md %}): a full chord on every pad, voicings, chord sets and scales
- [Keyboard and Drums]({{ site.baseurl }}{% link keyboard-and-drums.md %}): the other two layouts, velocity and hardware outputs
- [Rhythm and clock]({{ site.baseurl }}{% link rhythm-and-clock.md %}): note repeat, the arpeggiator, tempo and MIDI clock
- [Life]({{ site.baseurl }}{% link life.md %}): a Game of Life that plays your pads, and standby
- [Knobs and Mix]({{ site.baseurl }}{% link knobs-and-mix.md %}): named CC knobs and fader pages

### Customize
- [Setup]({{ site.baseurl }}{% link setup.md %}): pad feel, aftertouch, brightness, standby and clock
- [Profiles]({{ site.baseurl }}{% link profiles.md %}): YAML profiles, the browser editor and Undo
- [Themes]({{ site.baseurl }}{% link themes.md %}): every screen and LED color
- [Files]({{ site.baseurl }}{% link files.md %}): where Pushtoo keeps everything

### Help
- [Troubleshooting]({{ site.baseurl }}{% link troubleshooting.md %}): symptom-first fixes
- [Beta testing]({{ site.baseurl }}{% link beta-testing.md %}): a 20-minute test run and how to report back
- [Development]({{ site.baseurl }}{% link development.md %}): building, testing and the project layout

## License

Pushtoo is free software under the [GNU General Public License, version 3](https://github.com/tucktuckg00se/Pushtoo/blob/main/LICENSE) or (at your option) any later version. It's a fork of [Pysha](https://github.com/ffont/pysha) by Frederic Font; see [Credits]({{ site.baseurl }}{% link development.md %}#credits).
