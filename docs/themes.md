---
title: Themes
nav_order: 12
description: "Every screen and LED color in Pushtoo comes from a theme file: the default Open Color theme, making your own, and every color name."
---

# Themes
{: .no_toc }

Every color on the screen and the LEDs comes from a theme.

1. TOC
{:toc}

## The default theme

The default follows the Open Color theme of [INTERSECT](https://github.com/tucktuckg00se/INTERSECT): a lime accent on a dark slate screen. On first run Pushtoo writes it, fully commented, to `~/.config/pushtoo/themes/oc.yaml`. Edit it while Pushtoo runs and the screen and pads change when you save.

## Making your own

Add a file to that folder and point your [profile]({{ site.baseurl }}{% link profiles.md %}) at it with `theme: <file name without .yaml>`. A theme only needs the colors it changes; everything else comes from Open Color:

```yaml
name: Teal
play: 20c997        # the Play accent: labels, arcs, the kept voicing
tension: ff922b
```

Colors are hex `RRGGBB` or the name of another color in the theme (`home: play`). If a theme has a mistake, the Push screen shows the file, line and color, and Pushtoo keeps the last working version.

## Color names

Colors are named for what they mean:

| Group | Names |
| --- | --- |
| Mode accents | `play`, `knobs`, `mix` |
| Pads | `root`, `in_scale`, `out_of_scale`, `held` |
| Chord grid | `home`, `away`, `tension`, `borrowed`, `secondary` |
| States | `latch`, `mute`, `solo`, `rate`, `life` |
| Screen | `background`, `track`, `line`, `text`, `text_dim` |
| Knob colors (for a profile's `color:`) | `red` to `gray` |

The commented `oc.yaml` lists every color with its default.
