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
from pushtoo.fonts import use_bundled_fonts
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


def _tap_layout(target) -> None:
    target.button_pressed(c.BUTTON_LAYOUT)
    target.button_released(c.BUTTON_LAYOUT)


def _page(target, name: str) -> None:
    """Press the button below the page called `name` (on a mode, or an App's mode)."""
    mode = getattr(target, "mode", target)
    target.button_pressed(f"Lower Row {[p.name for p in mode.pages].index(name) + 1}")


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
        _page(app, "Rhythm")
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
        _page(app, "Velocity")
        app.button_pressed("Upper Row 2")  # Random
        app.encoder_rotated("Track3 Encoder", 6 * 30)  # Spread
        app.pad_pressed(2, 3, 90)  # Fm7
        views["chord_random_velocity"] = app.view()
        app.pad_released(2, 3)
        _page(app, "Timing")
        app.button_pressed("Upper Row 2")  # Spread out
        views["chord_timing"] = app.view()
        app.button_pressed(c.BUTTON_SETUP)
        views["setup_pads_idle"] = app.view()
        app.encoder_rotated("Track2 Encoder", -6 * 4)  # softer Dynamics
        app.pad_pressed(0, 0, 87)
        views["setup_pads"] = app.view()
        app.pad_released(0, 0)
        app.button_pressed("Lower Row 2")
        app.pad_pressed(0, 0, 87)
        app.pad_aftertouch(0, 0, 70)
        views["setup_aftertouch"] = app.view()
        app.pad_released(0, 0)
        app.button_pressed("Lower Row 3")
        views["setup_display"] = app.view()
        app.button_pressed("Lower Row 4")
        views["setup_clock"] = app.view()
        app.button_pressed(c.BUTTON_SETUP)

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


def _life_views(views: dict[str, dict]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        app = _app(Path(tmp) / "a")
        app.button_pressed(c.BUTTON_SESSION)
        app.button_released(c.BUTTON_SESSION)  # a tap: Life on
        for pad in ((3, 2), (3, 3), (3, 4), (4, 4), (5, 3)):  # a glider
            app.pad_pressed(*pad, 100)
            app.pad_released(*pad)
        app.toast("", 0)
        views["keyboard_life"] = app.view()
        _page(app, "Life")
        views["keyboard_life_page"] = app.view()
        app.button_pressed(c.BUTTON_SHIFT)
        views["shift_overlay_standby"] = app.view()
        app.button_pressed(c.BUTTON_SESSION)
        standby = app.view()
        standby["standby"]["started"] -= 10  # past the hint
        standby["standby"]["stepped_at"] -= 1  # fully faded in
        views["standby_life"] = standby
        hint = app.view()
        hint["standby"]["stepped_at"] -= 1
        views["standby_life_hint"] = hint
        app.button_released(c.BUTTON_SHIFT)
        app.device.standby_scene = "Drift"
        app.start_standby()
        drift = app.view()
        drift["standby"]["started"] -= 20
        views["standby_drift"] = drift


def sample_views() -> dict[str, dict]:
    views: dict[str, dict] = {}

    play = _play()
    views["keyboard_first_run"] = play.view()

    play.pad_pressed(0, 0, 100)
    play.pad_pressed(0, 2, 100)
    play.pad_pressed(0, 4, 100)
    views["keyboard_held"] = play.view()
    peek = play.view()
    peek["touched"] = 0  # a finger on the Octave encoder
    views["peek_octave"] = peek
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
    _page(play, "Output")
    play.encoder_turned(0, 6)
    views["keyboard_output_page"] = play.view()
    _page(play, "Strip")
    views["keyboard_strip_page"] = play.view()

    play = _play()
    _tap_layout(play)
    views["drums_first_run"] = play.view()
    play.pad_pressed(0, 2, 96)  # Snare, held
    views["drums_snare"] = play.view()
    play.pad_released(0, 2)
    play.button_pressed(c.BUTTON_ACCENT)
    views["drums"] = play.view()
    play.button_pressed(c.BUTTON_ACCENT)
    play.button_pressed(c.BUTTON_OCTAVE_UP)  # to the top: 64-127
    play.pad_pressed(5, 3, 60)
    views["drums_top"] = play.view()

    play = _play()
    play.button_pressed(c.BUTTON_SCALE)
    play.button_pressed("Upper Row 4")  # D
    play.encoder_turned(0, 6 * 8)  # Minor -> Major Pentatonic
    views["scale_selector"] = play.view()

    _chord_views(views)
    _m2_views(views)
    _life_views(views)
    return views


def _chord_views(views: dict[str, dict]) -> None:
    play = _play()
    play.button_pressed(c.BUTTON_LAYOUT)
    play.button_released(c.BUTTON_LAYOUT)
    play.button_pressed(c.BUTTON_LAYOUT)
    play.button_released(c.BUTTON_LAYOUT)
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
    play.button_pressed("1/8t")  # hold Open (fifth side button from the top)
    play.pad_pressed(2, 3, 100)  # Fm7
    views["chord_momentary_voicing"] = play.view()
    play.pad_released(2, 3)
    clock[0] += 1.0
    play.button_released("1/8t")
    play.button_pressed("1/4")  # Latch (bottom side button)
    _page(play, "Style")
    play.button_pressed("Upper Row 2")  # Strum
    play.pad_pressed(1, 3, 100)
    play.pad_released(1, 3)
    views["chord_latched_strum"] = play.view()
    _page(play, "Output")
    views["chord_output_page"] = play.view()

    play = _play()
    play.keyboard.scale = "Minor Pentatonic"
    play.button_pressed(c.BUTTON_LAYOUT)
    play.button_released(c.BUTTON_LAYOUT)
    play.button_pressed(c.BUTTON_LAYOUT)
    play.button_released(c.BUTTON_LAYOUT)
    play.pad_pressed(4, 2, 100)  # sus on III
    views["chord_pentatonic"] = play.view()

    play = _play()
    _tap_layout(play)
    _tap_layout(play)
    play.button_pressed("Upper Row 4")  # the Jazz chord set
    play.chord.voicing = "Shell"
    play.pad_pressed(4, 4, 100)  # 11th row, V
    views["chord_jazz_shell"] = play.view()
    play.pad_released(4, 4)
    play.chord.voicing = "Smooth"
    play.button_pressed("1/4")  # Latch
    play.pad_pressed(2, 3, 100)  # a latched chord
    play.pad_released(2, 3)
    _tap_layout(play)  # to Keyboard: the chord plays on, its notes lit
    views["keyboard_over_chord"] = play.view()

    play = _play()
    play.button_pressed(c.BUTTON_LAYOUT)
    play.button_released(c.BUTTON_LAYOUT)
    play.button_pressed(c.BUTTON_LAYOUT)
    play.button_released(c.BUTTON_LAYOUT)
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
    use_bundled_fonts()  # the same font as on the Push
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
