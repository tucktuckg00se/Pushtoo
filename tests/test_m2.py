"""Knobs, Mix, Browse, Undo keys, profiles and state, through the App without hardware."""

import pytest
from evdev import ecodes
from push2_python import constants as c

from pushtoo.app import App
from pushtoo.keys import describe, parse_keys
from pushtoo.midi.router import OUT_PORT
from pushtoo.profiles.loader import parse
from pushtoo.ui.controls import INCREMENTS_PER_STEP
from tests.test_router import make_router

STEP = INCREMENTS_PER_STEP


class FakeRenderer:
    def __init__(self) -> None:
        self.views: list[dict] = []

    def start(self) -> None: ...

    def update(self, view: dict) -> None:
        self.views.append(view)

    def stop(self) -> None: ...


class FakeKeys:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, spec: str) -> bool:
        parse_keys(spec)
        self.sent.append(spec)
        return True

    def close(self) -> None: ...


@pytest.fixture
def env(tmp_path):
    """Builds Apps that share a config folder and state file, like restarts would."""
    apps = []

    def make(profile_text: str | None = None) -> tuple[App, list]:
        config = tmp_path / "profiles"
        if profile_text is not None:
            config.mkdir(exist_ok=True)
            (config / "default.yaml").write_text(profile_text)
        router, virtual, *_ = make_router()
        app = App(
            renderer=FakeRenderer(),
            config_dir=config,
            state_path=tmp_path / "state.yaml",
            router=router,
            keys=FakeKeys(),
            connect=False,
        )
        apps.append(app)
        return app, virtual.sent

    yield make
    for app in apps:
        app.profiles.stop()
        app.saver._stop.set()


def cc_messages(sent):
    return [m for m in sent if m[0] & 0xF0 == 0xB0]


# Knobs


def test_knobs_send_default_map_ccs(env):
    app, sent = env()
    app.button_pressed(c.BUTTON_DEVICE)
    assert app.mode is app.knobs
    app.encoder_rotated("Track1 Encoder", STEP)
    assert sent[-1] == [0xB0 | 14, 14, 1]  # ch 15, CC 14
    app.button_pressed("Lower Row 5")  # page 5 is on channel 16
    app.encoder_rotated("Track8 Encoder", STEP)
    assert sent[-1] == [0xB0 | 15, 21, 1]


def test_knob_ranges_and_bipolar_display(env):
    app, sent = env(
        """
knobs:
  pages:
    - name: Synth
      controls:
        - {name: Volume, cc: 7, channel: 1, min: 10, max: 12, default: 11}
        - {name: Detune, cc: 94, channel: 1, bipolar: true}
"""
    )
    app.button_pressed(c.BUTTON_DEVICE)
    for _ in range(5):
        app.encoder_rotated("Track1 Encoder", STEP)
    assert [m[2] for m in cc_messages(sent)] == [12]  # clamped at max, sent once
    assert app.mode.control_at(1).text() == "+0"


def test_learn_assist_sends_the_column_cc_three_times(env):
    app, sent = env()
    app.button_pressed(c.BUTTON_DEVICE)
    app.button_pressed(c.BUTTON_SHIFT)
    assert app.view()["upper"][2]["label"] == "Learn"
    app.button_pressed("Upper Row 3")
    app.button_released(c.BUTTON_SHIFT)
    assert cc_messages(sent) == [[0xBE, 16, 0]] * 3
    assert "CC 16 on ch 15" in app._toast[0]


def test_delete_plus_touch_resets_to_default(env):
    app, sent = env()
    app.button_pressed(c.BUTTON_DEVICE)
    for _ in range(3):
        app.encoder_rotated("Track1 Encoder", STEP)
    app.button_pressed(c.BUTTON_DELETE)
    app.encoder_touched("Track1 Encoder")
    app.button_released(c.BUTTON_DELETE)
    assert sent[-1] == [0xBE, 14, 0]
    assert app.knobs.values[(0, 0)] == 0


def test_touch_alone_never_changes_a_value(env):
    app, sent = env()
    app.button_pressed(c.BUTTON_DEVICE)
    app.encoder_touched("Track1 Encoder")
    assert app.view()["peek"]["name"] == "Knob 1"
    assert sent == []


def test_pads_keep_playing_in_knobs(env):
    app, sent = env()
    app.button_pressed(c.BUTTON_DEVICE)
    app.pad_pressed(0, 0, 100)
    assert sent[-1] == [0x90, 48, 100]


def test_octave_acts_on_play_from_knobs(env):
    app, sent = env()
    app.button_pressed(c.BUTTON_DEVICE)
    app.button_pressed(c.BUTTON_OCTAVE_UP)
    assert app.mode is app.knobs
    app.pad_pressed(0, 0, 100)
    assert sent[-1] == [0x90, 60, 100]


# Mix


def test_mix_faders_and_master(env):
    app, sent = env()
    app.button_pressed(c.BUTTON_MIX)
    app.encoder_rotated("Track2 Encoder", STEP)
    assert sent[-1] == [0xBD, 103, 101]  # ch 14, starts at 100
    app.button_pressed(c.BUTTON_NOTE)
    app.encoder_rotated(c.ENCODER_MASTER_ENCODER, -STEP)  # master works in any mode
    assert sent[-1] == [0xBD, 110, 99]


def test_mix_pads_toggle_mute_and_solo_and_bottom_rows_play(env):
    app, sent = env()
    app.button_pressed(c.BUTTON_MIX)
    app.pad_pressed(7, 0, 100)
    app.pad_released(7, 0)
    assert sent[-1] == [0xBD, 14, 127]
    assert app.mix.pad_colors()[7][0] == "pt_coral"
    app.pad_pressed(7, 0, 100)
    assert sent[-1] == [0xBD, 14, 0]
    app.pad_pressed(6, 3, 100)
    assert sent[-1] == [0xBD, 25, 127]
    assert app.mix.pad_colors()[6][3] == "pt_blue"
    app.pad_pressed(0, 0, 90)
    assert sent[-1] == [0x90, 48, 90]
    assert app.mode.control_at(3).text() == "100 S"


# Undo


def test_undo_and_redo_send_keystrokes(env):
    app, _ = env()
    app.button_pressed(c.BUTTON_UNDO)
    app.button_pressed(c.BUTTON_SHIFT)
    app.button_pressed(c.BUTTON_UNDO)
    assert app.keys.sent == ["ctrl+z", "ctrl+shift+z"]
    assert app._toast[0] == "Redo → Ctrl+Shift+Z"


def test_undo_can_be_midi(env):
    app, sent = env("undo:\n  undo: {midi: {cc: 118, channel: 16}}\n")
    app.button_pressed(c.BUTTON_UNDO)
    assert sent[-1] == [0xBF, 118, 127]
    assert app.keys.sent == []


def test_key_specs():
    assert parse_keys("ctrl+shift+z") == [ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTSHIFT, ecodes.KEY_Z]
    assert parse_keys("Ctrl + Y") == [ecodes.KEY_LEFTCTRL, ecodes.KEY_Y]
    assert parse_keys("space") == [ecodes.KEY_SPACE]
    assert parse_keys("f5") == [ecodes.KEY_F5]
    assert describe("ctrl+shift+z") == "Ctrl+Shift+Z"
    for bad in ("ctrl+", "ctrl+shift", "ctrl+banana", "f13"):
        with pytest.raises(ValueError):
            parse_keys(bad)


# Modes and navigation


def test_scale_from_another_mode_opens_the_selector_in_play(env):
    app, _ = env()
    app.button_pressed(c.BUTTON_DEVICE)
    app.button_pressed(c.BUTTON_SCALE)
    assert app.mode is app.play and app.play.scale_open


def test_mode_buttons_light_the_active_mode(env):
    app, _ = env()
    app.button_pressed(c.BUTTON_MIX)
    colors = app.button_colors()
    assert colors[c.BUTTON_MIX] == "white"
    assert colors[c.BUTTON_NOTE] == "dark_gray"
    assert colors[c.BUTTON_SESSION] == "black"


def test_knob_upper_buttons_light_in_column_colors(env):
    app, _ = env()
    app.button_pressed(c.BUTTON_DEVICE)
    colors = app.button_colors()
    assert colors["Upper Row 1"] == "pt_red"
    assert colors["Upper Row 8"] == "pt_violet"


# Profiles and state


def test_hot_reload_applies_and_errors_keep_the_last_good_profile(env):
    app, sent = env()
    app._profile_changed(parse("mix: {channel: 3}\n"))
    app.button_pressed(c.BUTTON_MIX)
    app.encoder_rotated("Track1 Encoder", STEP)
    assert sent[-1][0] == 0xB2
    from pushtoo.profiles.loader import ProfileError

    app._profile_changed(ProfileError("default.yaml line 2: mix.channel: too big"))
    assert app.profile.mix.channel == 3
    assert app._toast[0].startswith("Profile error: default.yaml line 2")


def test_state_survives_a_restart(env):
    app, _ = env()
    app.button_pressed(c.BUTTON_SCALE)
    app.button_pressed("Upper Row 4")  # D
    app.button_pressed(c.BUTTON_SCALE)
    app.button_pressed(c.BUTTON_DEVICE)
    app.encoder_rotated("Track3 Encoder", 5 * STEP)
    app.button_pressed(c.BUTTON_MIX)
    app.pad_pressed(7, 2, 100)
    app.button_pressed(c.BUTTON_DEVICE)
    app.saver.flush()

    again, sent = env()
    assert again.mode is again.knobs
    assert again.play.keyboard.root == 2
    assert again.knobs.values[(0, 2)] == 5
    assert again.mix.mute[2]
    assert sent == []  # restoring never sends MIDI


def test_browse_loads_another_profile(env, tmp_path):
    app, _ = env()
    (tmp_path / "profiles" / "live.yaml").write_text("name: Live\nmix: {channel: 5}\n")
    app.button_pressed(c.BUTTON_BROWSE)
    assert app.mode is app.browse
    assert [p.stem for p in app.browse.paths] == ["default", "live"]
    app.encoder_rotated("Track1 Encoder", STEP)
    app.button_pressed("Upper Row 1")
    assert app.profile.name == "Live"
    assert app.mode is app.play
    assert app._toast[0] == "Loaded Live"


def test_broken_profile_at_startup_falls_back_to_defaults(env):
    app, _ = env("mix: {channel: 99}\n")
    assert app.profile.mix.channel == 14
    assert app._toast[0].startswith("Profile error: default.yaml line 1")


def test_every_mode_view_renders(env):
    import cairo

    from pushtoo.render.screens import draw_view

    app, _ = env()
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 960, 160)
    for button in (c.BUTTON_NOTE, c.BUTTON_DEVICE, c.BUTTON_MIX, c.BUTTON_BROWSE):
        app.button_pressed(button)
        draw_view(cairo.Context(surface), app.view())


def test_default_output_is_pushtoo_out(env):
    app, _ = env()
    assert app.profile.output == OUT_PORT


def test_key_sender_presses_then_releases_in_separate_frames(monkeypatch):
    import evdev

    from pushtoo import keys

    events = []

    class FakeUInput:
        def __init__(self, name):
            events.append(("open", name))

        def write(self, kind, code, value):
            events.append((code, value))

        def syn(self):
            events.append("syn")

        def close(self):
            events.append("close")

    monkeypatch.setattr(evdev, "UInput", FakeUInput)
    monkeypatch.setattr(keys, "DEVICE_SETTLE_SECONDS", 0)
    errors = []
    sender = keys.KeySender(on_error=errors.append)
    assert sender.send("ctrl+z")
    assert not sender.send("ctrl+nope")
    sender.close()
    ctrl, z = ecodes.KEY_LEFTCTRL, ecodes.KEY_Z
    assert events == [
        ("open", "Pushtoo keys"),
        (ctrl, 1),
        (z, 1),
        "syn",
        (z, 0),
        (ctrl, 0),
        "syn",
        "close",
    ]
    assert errors and "nope" in errors[0]


def test_key_sender_reports_missing_uinput(monkeypatch):
    import evdev

    from pushtoo import keys

    def no_access(name):
        raise PermissionError("/dev/uinput")

    monkeypatch.setattr(evdev, "UInput", no_access)
    errors = []
    sender = keys.KeySender(on_error=errors.append)
    sender.send("ctrl+z")
    sender.close()
    assert errors == ["Keystrokes need /dev/uinput access: see packaging/udev"]


def test_reload_keeps_values_only_for_unchanged_mappings(env):
    app, _ = env()
    app.button_pressed(c.BUTTON_DEVICE)
    app.encoder_rotated("Track1 Encoder", 3 * STEP)
    app.encoder_rotated("Track2 Encoder", 3 * STEP)
    same_first = "{name: Renamed, cc: 14, channel: 15}"
    remapped = "{name: Cutoff, cc: 74, channel: 15}"
    app._profile_changed(
        parse(f"knobs: {{pages: [{{name: P, controls: [{same_first}, {remapped}]}}]}}\n")
    )
    assert app.knobs.values[(0, 0)] == 3  # same CC and channel, renamed: kept
    assert app.knobs.values[(0, 1)] == 0  # new mapping: starts fresh


def test_long_toasts_wrap_instead_of_vanishing():
    import cairo

    from pushtoo.render.screens import _wrap

    ctx = cairo.Context(cairo.ImageSurface(cairo.FORMAT_RGB24, 960, 160))
    message = (
        "Profile error: default.yaml line 1: knobs.pages[0].controls[0].cc: "
        "Input should be less than or equal to 127"
    )
    # Font metrics vary by machine (CI lacks IBM Plex), so check properties, not line count.
    for width in (928, 400):
        lines = _wrap(ctx, message, width, 20, max_lines=3)
        assert 1 <= len(lines) <= 3
        assert "".join(lines).replace(" ", "") == message.replace(" ", "")  # nothing cut
        ctx.set_font_size(20)
        assert all(ctx.text_extents(line).x_advance <= width for line in lines)
    assert len(_wrap(ctx, message, 400, 20, max_lines=3)) > 1
