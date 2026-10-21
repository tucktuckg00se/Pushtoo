---
title: Installation
nav_order: 2
description: "Install Pushtoo on Arch, Debian, Ubuntu, Raspberry Pi OS or Fedora with one command: what the installer asks, the background service, upgrading and uninstalling."
---

# Installation
{: .no_toc }

1. TOC
{:toc}

## Requirements

- An **Ableton Push 2**. Plug in its power supply as well as USB: on USB power alone the Push dims itself.
- **Linux**: Arch, Debian, Ubuntu, Raspberry Pi OS or Fedora. A Raspberry Pi 4 is enough.
- Something that makes sound from MIDI: a DAW, a soft synth, or a hardware synth over USB-MIDI.

You don't need to install Python yourself: the installer uses [uv](https://docs.astral.sh/uv/), which gives Pushtoo its own Python, apart from the rest of your system.

## Install

One command:

```sh
curl -fsSL https://raw.githubusercontent.com/tucktuckg00se/Pushtoo/main/install.sh | sh
```

Or from a clone: `./install.sh`.

The installer **asks before every step**, recaps your answers, and changes nothing until you confirm. It uses `sudo` only for steps 1, 4 and 5, and only if you say yes.

| Question | What it does | Why |
| --- | --- | --- |
| 1. Install system packages? | Installs, with your package manager, cairo and its headers, pkg-config, a C compiler, the ALSA library and libusb. It shows the exact command first. | Two of Pushtoo's parts (pycairo, evdev) are built from source. |
| 2. Install uv? | Only asked if `uv` is missing: Astral's official installer puts it in `~/.local/bin`. | uv installs Pushtoo in its own environment, with its own Python, so nothing else on your system is affected. |
| 3. Install Pushtoo? | `uv tool install` gives you a `pushtoo` command in `~/.local/bin`. It shows the version you have, if any, and the one it installs. Re-running the installer upgrades it. | |
| 4. Install the udev rule? | Copies [packaging/udev/50-pushtoo.rules](https://github.com/tucktuckg00se/Pushtoo/blob/main/packaging/udev/50-pushtoo.rules) to `/etc/udev/rules.d/`. | Lets your user open the Push's display and type Undo shortcuts without root, also headless (SSH, a Raspberry Pi, the background service). |
| 5. Join the audio group? | Only asked if you're not in it: adds you with `usermod -aG audio`. Takes effect at your next login. | The udev rule grants access to that group. |
| 6. Start Pushtoo automatically when you log in? | Installs a systemd user service ([packaging/systemd/pushtoo.service](https://github.com/tucktuckg00se/Pushtoo/blob/main/packaging/systemd/pushtoo.service)). | Pushtoo waits in the background for the Push, so plugging it in is all it takes. |
| 7. Start it now? | Starts the service straight away. | |

### Installer options

| Option | Effect |
| --- | --- |
| `--yes` | Answer every question with its default (yes) |
| `--no-packages`, `--no-udev`, `--no-service`, `--no-start` | Skip that step |
| `--main` | Install the latest code instead of the release |
| `--help` | List everything |

When the installer has no terminal to ask on, it stops and asks for these flags rather than guessing.

After installing, run `pushtoo doctor` to check that everything is in place, then go to [Getting started]({{ site.baseurl }}{% link getting-started.md %}).

## Running in the background

The service starts at login and waits for the Push, using under 1% CPU while it waits. Unplug and replug the Push whenever you like: held notes are released and Pushtoo reconnects on its own. When the service stops, it sends all notes off first, so nothing hangs in your synth.

```sh
systemctl --user status pushtoo          # is it running?
journalctl --user -u pushtoo -f          # its log
systemctl --user stop pushtoo            # stop it (it starts again at next login)
systemctl --user disable --now pushtoo   # stop it starting at login
systemctl --user enable --now pushtoo    # start it at login again
```

Only one Pushtoo runs at a time. If you run `pushtoo` while the service is up, it says so and exits; stop the service first to run it by hand (with `-v` for a detailed log).

## Upgrading

Run the installer again.

## Uninstalling

```sh
./install.sh --uninstall
# or, without a clone:
curl -fsSL https://raw.githubusercontent.com/tucktuckg00se/Pushtoo/main/install.sh | sh -s -- --uninstall
```

This removes the service, the `pushtoo` command and the udev rule, asking about each. It keeps your profiles and themes in `~/.config/pushtoo` unless you add `--purge`, which also deletes them and the saved state. The audio group and system packages are left as they are.
