---
title: Setup
nav_order: 10
description: "Tune the Push to your hands: pad sensitivity and dynamics, aftertouch, brightness, standby and MIDI clock."
---

# Setup
{: .no_toc }

Press **Setup** to tune the Push to your hands. Pads keep playing while you're there, so you can feel every change. Press Setup again, or `‹`, to go back.

1. TOC
{:toc}

## Pads

- **Sensitivity**: how little force reaches full velocity.
- **Dynamics**: below 0, light touches play louder; above 0, you have to dig in.
- **Min** and **Max velocity**.

The screen draws the curve and puts a dot where your last hit landed.

Above the display, **Regular**, **Reduced** or **Low** sets the Push's own pad sensitivity. Lower settings stop neighbouring pads from triggering and stop double hits.

## Aftertouch

- **Poly**: each pad's own pressure.
- **Channel**: one pressure for all the pads, for synths that only read channel pressure.
- **Off**.

Two more controls set where pressure starts and where it reaches full.

## Display

- **Pad brightness**, **button brightness** and **screen brightness**. On USB power alone, Push dims itself whatever these say.
- **Standby**: how long the Push waits with nothing played before the pads and screen start to animate (10 minutes by default, or Off). The buttons above pick the scene, **Life** or **Drift**. See [Standby]({{ site.baseurl }}{% link life.md %}#standby).

## Clock

Whether Pushtoo sends [MIDI clock]({{ site.baseurl }}{% link rhythm-and-clock.md %}#midi-clock), and whether it follows clock arriving on Pushtoo In.

## Where Setup is saved

Setup belongs to your Push, not to a profile, so it's the same whichever profile is loaded. It's saved in the [state file]({{ site.baseurl }}{% link files.md %}). A profile's `play: {velocity_curve: ...}` only sets the starting feel before Setup has been used.
