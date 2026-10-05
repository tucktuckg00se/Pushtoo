# Pushtoo

Pushtoo turns an Ableton Push 2 on Linux into a DAW-agnostic MIDI controller: plug in Push, pick the **Pushtoo Out** port in any DAW or synth, and play. The screen always shows what each control does.

> **Status:** early development (M0 Foundation). Not usable yet. See [docs/PRD.md](docs/PRD.md) for the product spec.

## Development

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and the ALSA, JACK and cairo development headers.

```sh
uv sync
uv run pytest
uv run ruff check
uv run pushtoo
```

## Layout

| Path            | Contents                                              |
| --------------- | ----------------------------------------------------- |
| `pushtoo/`      | The application package                               |
| `tests/`        | Unit tests (no hardware required)                     |
| `docs/`         | PRD and architecture decision records                 |
| `legacy/pysha/` | Original Pysha code, kept as reference while porting  |

## Credits

Pushtoo is a fork of [Pysha](https://github.com/ffont/pysha) by Frederic Font and uses a fork of his [push2-python](https://github.com/ffont/push2-python). Both are MIT licensed.
