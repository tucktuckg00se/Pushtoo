---
title: Troubleshooting
nav_order: 14
description: "Symptom-first fixes for Pushtoo: pushtoo doctor, missing MIDI ports, a dim Push, Undo, and running headless."
---

# Troubleshooting
{: .no_toc }

Start with:

```sh
pushtoo doctor
```

It checks Python, the screen font, MIDI, whether the Push is plugged in and its display is accessible, Undo keystrokes and the service, and says how to fix whatever isn't right. It only looks, so it's safe to run any time.

1. TOC
{:toc}

## I can't find Pushtoo Out in my DAW

- Under PipeWire it may be listed as `Midi-Bridge:Pushtoo: Out (capture)`.
- DAWs that list only hardware MIDI ports on JACK or PipeWire, such as REAPER, still list Pushtoo, because it marks its port as leading to a device. In REAPER, enable it in **Preferences > MIDI Devices**.
- Check that Pushtoo is running: `systemctl --user status pushtoo`, or run `pushtoo` by hand.

## `pushtoo` says it's already running

Only one Pushtoo runs at a time. Stop the background service first (`systemctl --user stop pushtoo`), then run `pushtoo -v` for a detailed log. See [Running in the background]({{ site.baseurl }}{% link installation.md %}#running-in-the-background).

## The Push is dim

On USB power alone, Push dims itself whatever the brightness settings say. Plug in its power supply. Brightness is in [Setup > Display]({{ site.baseurl }}{% link setup.md %}#display).

## The screen stays blank, or Undo does nothing

Both need the udev rule and the audio group ([installer steps 4 and 5]({{ site.baseurl }}{% link installation.md %}#install)), which give your user access to the Push's display and to `/dev/uinput` without root. This matters on headless systems too (SSH, a Raspberry Pi, the background service). Group membership takes effect at your next login.

## Undo presses the wrong key

Undo keys are physical positions: on a non-QWERTY layout, `ctrl+z` presses the key where Z sits on QWERTY. Undo also goes to whichever window has focus. To reach your DAW regardless of focus, send MIDI instead: see [Undo]({{ site.baseurl }}{% link profiles.md %}#undo).

## Notes are stuck

Press **Shift + Stop** (Panic) for all notes off on every output. Unplugging the Push, or stopping the service, also releases held notes. Pushtoo reconnects when you plug it back in.

## My profile or theme change didn't apply

If a file has a mistake, the Push screen shows the file, line and field, and Pushtoo keeps using the last working version. Fix the line and save again.

## Still stuck?

[Open an issue](https://github.com/tucktuckg00se/Pushtoo/issues) with the output of `pushtoo doctor` and the log (`journalctl --user -u pushtoo`, or `pushtoo -v`).
