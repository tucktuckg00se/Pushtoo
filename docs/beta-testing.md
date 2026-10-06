# Beta testing Pushtoo

Thanks for trying Pushtoo 0.1.0b3. This takes about 20 minutes. You need an Ableton Push 2, a Linux machine (or a Raspberry Pi 4), and something that makes sound from MIDI: a DAW, a soft synth, or a hardware synth over USB-MIDI.

## 1. Install (5 minutes)

```sh
curl -fsSL https://raw.githubusercontent.com/tucktuckg00se/Pushtoo/main/install.sh | sh
```

Answer the questions (the defaults are fine), then run `pushtoo doctor`. Note anything marked ✗ or anything that surprised you.

## 2. Play (15 minutes)

Try these, in any order. There's no wrong way; we want to know where you got stuck.

1. **First sound.** Plug in the Push, pick **Pushtoo Out** in your DAW or synth, and play the pads. How long did it take to hear something?
2. **Keys.** Press **Scale**, pick a scale and a root, and play. Did the screen explain what you were doing?
3. **The chord grid.** Press **Layout** until you reach Chord. Play I–vi–IV–V (columns 1, 6, 4, 5 on the second row). Try a few chord sets with the buttons above the screen.
4. **Rhythm.** Hold a chord and tap **Repeat**, then try the Arp on the Rhythm page.
5. **Feel.** Press **Setup** and change Sensitivity until the pads feel right to you.
6. **Life.** Tap **Session**, play a few pads close together, and let them evolve. Try it in each layout.
7. **Standby.** Hold Shift and press **Session**, then play any pad to wake it.
8. **Unplug and replug** the Push while playing. Did it come back by itself?

## 3. Tell us

Open an issue at https://github.com/tucktuckg00se/Pushtoo/issues with:

- what you tried, what you expected, and what happened
- the output of `pushtoo doctor`
- the log: `journalctl --user -u pushtoo --since "1 hour ago"` (with the background service), or what `pushtoo -v` printed in the terminal
- your distro, and your DAW or synth

And one line on how it felt to play: that matters as much as any bug.

## Raspberry Pi checklist

For testers with a Raspberry Pi 4 (Raspberry Pi OS, 64-bit). Install as above, then from a clone of the repository:

1. **Latency:** stop the service (`systemctl --user stop pushtoo`) and run `uv run python tools/latency/latency.py` with the Push attached. It must pass (pads to MIDI under 3 ms at p99).
2. **Clock:** `uv run python tools/clock/jitter.py`. The queue rows must pass (p99 under 1 ms).
3. **Load:** start Pushtoo again, play chords with the arpeggiator running at 1/16 for a few minutes, and watch `top`. Note Pushtoo's CPU use, and whether the screen keeps up (it runs at 30 frames a second on a Pi).
