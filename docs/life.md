---
title: Life
nav_order: 8
description: "Life turns the pads into a Game of Life that plays in time, in any layout; standby animates the Push while you're away."
---

# Life
{: .no_toc }

1. TOC
{:toc}

## Playing with Life

Tap **Session** and every pad you play also comes alive as a cell in a Game of Life, lit purple. Hold Session instead for Life only while held.

On each step (1/8 by default) the board moves on a generation, and the pads it lands on play, in whatever layout you're in: a melody in key on the Keyboard, a beat on Drums, changes on the chord grid. Switch layouts and the same board plays the new one.

## The Life page

- **Rate**: how often the board steps.
- **Rule**: Conway, HighLife, Seeds or Day & Night.
- **Plays**: only cells just born (the default), or every live cell.
- **Voices**: how many pads may sound at once.
- **Velocity**: how loud they play.

Above the display:

- **Hold** freezes the board so it plays as a loop.
- **Wrap** joins its edges.
- **Random** seeds a whole board.
- **Clear** empties it.

Turning Life off, Panic (Shift + Stop) and unplugging the Push all clear the board.

## Standby

After a while with nothing played, the pads and screen start to animate. Set how long it waits (10 minutes by default, or Off) and the scene in [Setup > Display]({{ site.baseurl }}{% link setup.md %}#display):

- **Life**: a silent Game of Life.
- **Drift**: slow waves of color.

Standby never starts while anything is sounding or the transport runs. **Shift + Session** starts it at once, and any pad wakes it and plays as usual.
