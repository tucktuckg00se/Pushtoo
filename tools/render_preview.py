"""Render every Pushtoo screen to PNG without hardware, for design review.

    uv run python tools/render_preview.py [out_dir]

Writes one PNG per view plus contact_sheet.png with all of them stacked.
"""

import sys
import tempfile
import time
from pathlib import Path

import cairo
from push2_python import constants as c

from pushtoo.app import App
from pushtoo.midi.router import MidiRouter
from pushtoo.modes.play import PlayMode
from pushtoo.render.screens import HEIGHT, WIDTH, draw_view

SAMPLE_PORTS = ["USB MIDI Interface:USB MIDI Interface MIDI 1 24:0"]


class _NullOutput:
    def send_message(self, message) -> None:
        pass

    def close_port(self) -> None:
        pass


class _NullRenderer:
    def start(self) -> None: ...
    def update(self, view: dict) -> None: ...
    def stop(self) -> None: ...


class _NullKeys:
    def send(self, spec: str) -> bool:
        return True

    def close(self) -> None: ...


SYNTH_PROFILE = """
name: Synth
knobs:
  pages:
    - name: Filter
      controls:
        - {name: Cutoff, cc: 74, channel: 1, color: orange, default: 90}
        - {name: Resonance, cc: 71, channel: 1, color: orange, default: 30}
        - {name: Env Amount, cc: 47, channel: 1, color: yellow, bipolar: true, default: 80}
        - {name: Detune, cc: 94, channel: 1, color: violet, bipolar: true}
    - name: Envelope
      controls:
        - {name: Attack, cc: 73, channel: 1, color: green}
"""


def _app(tmp: Path, profile: str | None = None) -> App:
    config = tmp / "profiles"
    config.mkdir(parents=True, exist_ok=True)
    if profile is not None:
        (config / "default.yaml").write_text(profile)
        (config / "live-set.yaml").write_text("name: Live Set\n")
    app = App(
        renderer=_NullRenderer(),
        config_dir=config,
        state_path=tmp / "state.yaml",
        router=_router(),
        keys=_NullKeys(),
        connect=False,
    )
    app.profiles.stop()
    return app


def _m2_views(views: dict[str, dict]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        app = _app(Path(tmp) / "a")
        app.button_pressed(c.BUTTON_DEVICE)
        for column, turns in enumerate((20, 64, 5, 100, 0, 30, 127, 45)):
            app.encoder_rotated(f"Track{column + 1} Encoder", 6 * turns)
        views["knobs_default_map"] = app.view()
        app.button_pressed(c.BUTTON_SHIFT)
        views["knobs_learn_assist"] = app.view()
        app.button_released(c.BUTTON_SHIFT)

        app.button_pressed(c.BUTTON_MIX)
        app.pad_pressed(7, 1, 100)
        app.pad_pressed(6, 3, 100)
        views["mix"] = app.view()
        app.encoder_touched(c.ENCODER_MASTER_ENCODER)
        views["peek_master"] = app.view()
        app.saver._stop.set()

        app = _app(Path(tmp) / "b", SYNTH_PROFILE)
        app.button_pressed(c.BUTTON_DEVICE)
        views["knobs_custom_page"] = app.view()
        app.button_pressed(c.BUTTON_BROWSE)
        views["browse"] = app.view()
        app.saver._stop.set()


def _router() -> MidiRouter:
    return MidiRouter(
        virtual_out=_NullOutput(),
        list_ports=lambda: SAMPLE_PORTS,
        open_port=lambda name: _NullOutput(),
    )


def _play() -> PlayMode:
    return PlayMode(_router())


def sample_views() -> dict[str, dict]:
    views: dict[str, dict] = {}

    play = _play()
    views["keyboard_first_run"] = play.view()

    play.pad_pressed(0, 0, 100)
    play.pad_pressed(0, 2, 100)
    play.pad_pressed(0, 4, 100)
    views["keyboard_held"] = play.view()
    peek = play.view()
    peek["peek"] = play.control_at(1).view()
    views["peek_velocity"] = peek
    shift = play.view()
    shift["shift"] = ["Stop: Panic (all notes off)", "Turn an encoder: fine adjust"]
    views["shift_overlay"] = shift
    toast = play.view()
    toast |= {"toast": "Panic: all notes off", "toast_until": time.monotonic() + 60}
    views["toast"] = toast

    play = _play()
    play.button_pressed("Lower Row 3")  # Output page
    play.encoder_turned(0, 6)
    views["keyboard_output_page"] = play.view()
    play.button_pressed("Lower Row 2")
    views["keyboard_strip_page"] = play.view()

    play = _play()
    play.button_pressed(c.BUTTON_LAYOUT)
    play.pad_pressed(0, 1, 100)
    play.pad_released(0, 1)
    play.button_pressed(c.BUTTON_ACCENT)
    views["drums"] = play.view()

    play = _play()
    play.button_pressed(c.BUTTON_SCALE)
    play.button_pressed("Upper Row 4")  # D
    play.encoder_turned(0, 6 * 8)  # Minor -> Major Pentatonic
    views["scale_selector"] = play.view()

    _m2_views(views)
    return views


def render(view: dict) -> cairo.ImageSurface:
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, WIDTH, HEIGHT)
    draw_view(cairo.Context(surface), view)
    return surface


def main() -> None:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "render_preview")
    out_dir.mkdir(parents=True, exist_ok=True)
    views = sample_views()
    gap = 12
    sheet = cairo.ImageSurface(cairo.FORMAT_RGB24, WIDTH, len(views) * (HEIGHT + gap))
    sheet_ctx = cairo.Context(sheet)
    sheet_ctx.set_source_rgb(0.6, 0.1, 0.1)  # visible gaps between screens
    sheet_ctx.paint()
    for i, (name, view) in enumerate(views.items()):
        surface = render(view)
        surface.write_to_png(str(out_dir / f"{name}.png"))
        sheet_ctx.set_source_surface(surface, 0, i * (HEIGHT + gap))
        sheet_ctx.paint()
    sheet.write_to_png(str(out_dir / "contact_sheet.png"))
    print(f"wrote {len(views)} screens to {out_dir}/")


if __name__ == "__main__":
    main()
