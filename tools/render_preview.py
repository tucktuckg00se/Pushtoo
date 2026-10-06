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

    def send_at(self, message, at, tag=0) -> None:
        pass

    def cancel(self, tag=None) -> None:
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
        app.button_pressed(c.BUTTON_DELETE)
        views["knobs_delete_overlay"] = app.view()
        app.button_released(c.BUTTON_DELETE)
        app.button_pressed(c.BUTTON_LAYOUT)  # held: the upper buttons pick a layout
        views["layout_picker"] = app.view()
        app.button_released(c.BUTTON_LAYOUT)
        app.button_pressed(c.BUTTON_NOTE)
        app.button_pressed(c.BUTTON_LAYOUT)  # Chord
        app.button_released(c.BUTTON_LAYOUT)
        app.button_pressed(c.BUTTON_LAYOUT)  # Keyboard
        app.button_released(c.BUTTON_LAYOUT)
        app.button_pressed(c.BUTTON_REPEAT)
        app.button_released(c.BUTTON_REPEAT)  # a tap: rhythm on
        app.button_pressed("1/8t")
        app.button_pressed(c.BUTTON_PLAY)
        views["keyboard_repeat_rates"] = app.view()
        app.button_pressed("Lower Row 4")
        views["keyboard_rhythm_page"] = app.view()
        app.encoder_touched(c.ENCODER_TEMPO_ENCODER)
        views["peek_tempo"] = app.view()
        app.encoder_released(c.ENCODER_TEMPO_ENCODER)
        app.button_pressed(c.BUTTON_PLAY)
        app.button_pressed(c.BUTTON_REPEAT)
        app.button_released(c.BUTTON_REPEAT)  # off again
        app.button_pressed(c.BUTTON_LAYOUT)  # Drums
        app.button_released(c.BUTTON_LAYOUT)
        app.button_pressed(c.BUTTON_LAYOUT)  # Chord
        app.button_released(c.BUTTON_LAYOUT)
        app.button_pressed(c.BUTTON_REPEAT)  # held: the side buttons are rates
        views["chord_repeat_held"] = app.view()
        app.button_released(c.BUTTON_REPEAT)

        app.button_pressed(c.BUTTON_MIX)
        app.pad_pressed(7, 1, 100)
        app.pad_pressed(6, 3, 100)
        views["mix"] = app.view()
        app.encoder_touched(c.ENCODER_MASTER_ENCODER)
        views["peek_master"] = app.view()
        app.close()  # joins the state saver before the temp folder is removed

        app = _app(Path(tmp) / "b", SYNTH_PROFILE)
        app.button_pressed(c.BUTTON_DEVICE)
        views["knobs_custom_page"] = app.view()
        app.button_pressed(c.BUTTON_BROWSE)
        views["browse"] = app.view()
        app.close()  # joins the state saver before the temp folder is removed


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
    shift["overlay"] = {
        "title": "Shift",
        "lines": ["Stop: Panic (all notes off)", "Turn an encoder: fine adjust"],
    }
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

    _chord_views(views)
    _m2_views(views)
    return views


def _chord_views(views: dict[str, dict]) -> None:
    play = _play()
    play.button_pressed(c.BUTTON_LAYOUT)
    play.button_pressed(c.BUTTON_LAYOUT)
    views["chord_idle"] = play.view()
    play.pad_pressed(1, 0, 100)  # Cm
    play.pad_released(1, 0)
    play.pad_pressed(1, 4, 100)  # Gm, smoothly voiced from Cm
    views["chord_sounding"] = play.view()
    play.pad_released(1, 4)
    play.pad_pressed(7, 5, 100)  # V7 of Ab
    views["chord_secondary_dominant"] = play.view()
    play.pad_released(7, 5)
    clock = [0.0]
    play.chord._clock = lambda: clock[0]  # so the hold below counts as a hold
    play.button_pressed("1/8")  # hold Open (sixth side button from the top)
    play.pad_pressed(2, 3, 100)  # Fm7
    views["chord_momentary_voicing"] = play.view()
    play.pad_released(2, 3)
    clock[0] += 1.0
    play.button_released("1/8")
    play.button_pressed("1/4")  # Latch (bottom side button)
    play.button_pressed("Upper Row 2")  # Strum
    play.pad_pressed(1, 3, 100)
    play.pad_released(1, 3)
    views["chord_latched_strum"] = play.view()
    play.button_pressed("Lower Row 2")
    views["chord_output_page"] = play.view()

    play = _play()
    play.keyboard.scale = "Minor Pentatonic"
    play.button_pressed(c.BUTTON_LAYOUT)
    play.button_pressed(c.BUTTON_LAYOUT)
    play.pad_pressed(4, 2, 100)  # sus on III
    views["chord_pentatonic"] = play.view()

    play = _play()
    play.button_pressed(c.BUTTON_LAYOUT)
    play.button_pressed(c.BUTTON_LAYOUT)
    play.pad_pressed(1, 7, 100)  # the right column: the first chord an octave up
    views["chord_lift"] = play.view()
    play.pad_released(1, 7)
    play.pad_pressed(0, 4, 100)  # a bass note
    views["chord_bass_note"] = play.view()
    play.pad_released(0, 4)
    play.pad_pressed(1, 3, 100)  # Fm
    play.pad_pressed(0, 5, 100)  # over Ab in the bass
    views["chord_slash"] = play.view()


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
