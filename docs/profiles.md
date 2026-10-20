---
title: Profiles
nav_order: 11
description: "YAML profiles for knobs, outputs, chord sets and Undo; live reload; the pushtoo edit browser editor."
---

# Profiles
{: .no_toc }

A profile names your knobs, picks outputs and chord sets, and sets what Undo sends. Keep one per synth or rig and switch between them with **Browse**.

1. TOC
{:toc}

## Your first profile

On first run Pushtoo creates `~/.config/pushtoo/profiles/default.yaml`, a commented profile you can edit while Pushtoo runs.

- Changes apply when you save.
- If an edit has a mistake, the Push screen shows the file, line and field, and Pushtoo keeps using the last working version.
- Add more `.yaml` files to the folder and switch between them with **Browse** (encoder 1 picks, the top-left button loads).

## Example

```yaml
name: Synth
output: Pushtoo Out          # or a hardware MIDI port
knobs:
  pages:
    - name: Filter
      controls:
        - {name: Cutoff, cc: 74, channel: 1, color: orange}
        - {name: Resonance, cc: 71, channel: 1, color: orange}
        - {name: Detune, cc: 94, channel: 1, color: violet, bipolar: true}
undo:
  redo: {keys: ctrl+y}       # for apps that use Ctrl+Y
```

Leave out any section to use the defaults. Knob colors are the theme's [knob colors]({{ site.baseurl }}{% link themes.md %}#color-names). Chord-grid settings (`sets`, `favorite_sets`, `voicing_buttons`) are described on the [Chord grid]({{ site.baseurl }}{% link chord-grid.md %}#your-own-sets) page.

## Editing in a browser

```sh
pushtoo edit          # edit default.yaml
pushtoo edit rig      # edit rig.yaml
pushtoo edit --no-browser   # only print the address
```

`pushtoo edit` opens a profile editor at a local address that only this machine can reach. Knobs pages are laid out like the eight encoders, with names, CCs, channels, ranges and colors, and every other section is a form. It checks each change the way Pushtoo will and won't save a mistake.

It never touches your file. What you change goes in `<name>-user.yaml` next to it, which Pushtoo reads over your file: maps merge key by key, and a list, like a knob page, is replaced whole. So your comments stay put.

- A running Pushtoo picks the change up within a second.
- **Back to the file** in the editor, or deleting the `-user.yaml` file, drops the edits.
- `--no-browser` is for a Pi you reach from another machine: open the printed address through an SSH tunnel.

Pushtoo itself never writes to your profiles. Where you left off (mode, page, key, knob and fader values) is saved separately in the [state file]({{ site.baseurl }}{% link files.md %}) and restored per profile.

## Undo

**Undo** and **Shift + Undo** send Ctrl+Z and Ctrl+Shift+Z by default, to whichever window has focus, through a virtual keyboard (`/dev/uinput`). This works under X11 and Wayland.

- Keys are physical positions: on a non-QWERTY layout, `ctrl+z` presses the key where Z sits on QWERTY.
- Change the keys with `undo: {redo: {keys: ...}}`, as in the example above.
- If your DAW maps actions to MIDI, use `undo: {midi: {cc: ..., channel: ...}}` instead, which reaches the DAW regardless of focus.
- Virtual keystrokes need the udev rule from [step 4 of the installer]({{ site.baseurl }}{% link installation.md %}#install), also on a headless system.
