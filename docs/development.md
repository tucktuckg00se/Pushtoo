---
title: Development
nav_order: 16
description: "Building and testing Pushtoo from source, screen previews without hardware, the latency and clock gates, and the project layout."
---

# Development
{: .no_toc }

1. TOC
{:toc}

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/).
- The system packages from [the installer's step 1]({{ site.baseurl }}{% link installation.md %}#install): cairo and its headers, pkg-config, a C compiler, the ALSA library and libusb.

Stop the background service while developing (`systemctl --user stop pushtoo`), since only one Pushtoo runs at a time.

## Commands

```sh
uv sync
uv run pytest
uv run ruff check
uv run pushtoo                           # -v for a detailed log, --fps to set the screen rate
uv run pushtoo doctor
uvx --from shellcheck-py shellcheck -s sh install.sh
uv run python tools/render_preview.py   # every screen as PNG, no hardware needed
uv run python tools/latency/latency.py  # latency gate; needs Push attached
uv run python tools/clock/jitter.py     # clock timing gate (p99 < 1 ms); needs ALSA
```

## These docs

The site is built by GitHub Pages from `docs/` with [Just the Docs](https://just-the-docs.com). To preview it locally:

```sh
cd docs
bundle install
bundle exec jekyll serve
```

## Project structure

| Path | Contents |
| --- | --- |
| `pushtoo/` | The application package |
| `tests/` | Unit tests (no hardware required) |
| `tools/` | Screen previews, the latency gate and the clock gate |
| `spikes/` | A throwaway hardware probe: display throughput, input and hotplug events |
| `packaging/` | The udev rule and the systemd user service |
| `install.sh` | The one-command installer |
| `docs/` | This site, the PRD and architecture decision records |
| `legacy/pysha/` | Original Pysha code, kept as reference while porting |
| `LICENSES/` | Licenses of included work (Pysha, IBM Plex) |

## Credits

Pushtoo is a fork of [Pysha](https://github.com/ffont/pysha) by Frederic Font and uses a fork of his [push2-python](https://github.com/ffont/push2-python). Both are MIT licensed; Pysha's MIT notice is kept in [LICENSES/MIT-Pysha.txt](https://github.com/tucktuckg00se/Pushtoo/blob/main/LICENSES/MIT-Pysha.txt). The screen font is IBM Plex Sans Condensed, under the SIL Open Font License.

## License

Pushtoo is free software under the [GNU General Public License, version 3](https://github.com/tucktuckg00se/Pushtoo/blob/main/LICENSE) or (at your option) any later version. Versions up to commit `55fea34` were released under the MIT License.
