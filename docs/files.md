---
title: Files
nav_order: 13
description: "Where Pushtoo keeps profiles, themes, browser-editor overrides and saved state."
---

# Files

| Path | What it holds | Who writes it |
| --- | --- | --- |
| `~/.config/pushtoo/profiles/*.yaml` | Your [profiles]({{ site.baseurl }}{% link profiles.md %}). `default.yaml` is created, commented, on first run | You. Pushtoo never writes to them |
| `~/.config/pushtoo/profiles/<name>-user.yaml` | Changes made in [`pushtoo edit`]({{ site.baseurl }}{% link profiles.md %}#editing-in-a-browser), read over `<name>.yaml` | The browser editor |
| `~/.config/pushtoo/themes/*.yaml` | [Themes]({{ site.baseurl }}{% link themes.md %}). `oc.yaml` is written, commented, on first run | You |
| `~/.local/state/pushtoo/state.yaml` | [Setup]({{ site.baseurl }}{% link setup.md %}) and where you left off in each profile (mode, page, key, knob and fader values) | Pushtoo |

Uninstalling keeps `~/.config/pushtoo` unless you add `--purge`, which also deletes the saved state. See [Uninstalling]({{ site.baseurl }}{% link installation.md %}#uninstalling).
