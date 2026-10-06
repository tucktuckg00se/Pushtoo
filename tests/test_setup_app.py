"""Setup mode and the chord grid's random velocities, through the App."""

import random

import mido
from push2_python import constants as c
from push2_python.constants import PUSH2_SYSEX_PREFACE_BYTES

from pushtoo.hw.push import PushController
from pushtoo.midi.router import OUT_PORT
from pushtoo.render.screens import status_parts
from pushtoo.setup import DeviceSettings, hardware
from pushtoo.ui.controls import INCREMENTS_PER_STEP
from tests.pages import open_page

STEP = INCREMENTS_PER_STEP
TRIAD = 1


def test_setup_opens_and_closes_like_browse(env):
    app, _ = env()
    app.button_pressed(c.BUTTON_SETUP)
    assert app.mode is app.setup
    assert app.view()["lower"][7]["label"] == "‹ Play"
    app.button_pressed(c.BUTTON_SETUP)
    assert app.mode is app.play
    app.button_pressed(c.BUTTON_DEVICE)
    app.button_pressed(c.BUTTON_SETUP)
    app.button_pressed("Lower Row 8")
    assert app.mode is app.knobs


def test_setup_changes_reach_the_hardware_settings_and_survive_a_restart(env):
    app, _ = env()
    app.button_pressed(c.BUTTON_SETUP)
    app.encoder_rotated("Track1 Encoder", STEP * 3)  # Sensitivity 5 -> 8
    app.button_pressed("Upper Row 3")  # Response: Low
    assert app.device.sensitivity == 8 and app.device.response == "Low"
    assert (
        hardware(app.device)["velocity_table"][64]
        > hardware(DeviceSettings())["velocity_table"][64]
    )
    app.close()
    again, _ = env()
    assert again.device.sensitivity == 8 and again.device.response == "Low"


def test_first_run_takes_the_profiles_old_velocity_curve(env, tmp_path):
    (tmp_path / "profiles").mkdir()
    app, _ = env("name: Soft\nplay: {velocity_curve: Soft}\n")
    assert app.device.dynamics == -5


def test_pads_keep_playing_and_the_screen_shows_the_last_hit(env):
    app, sent = env()
    app.button_pressed(c.BUTTON_SETUP)
    app.pad_pressed(0, 0, 87)
    assert sent[-1] == [0x90, 48, 87]
    panel = app.view()["panel"]
    assert panel["kind"] == "setup" and panel["last_velocity"] == 87
    assert len(panel["table"]) == 128


def test_aftertouch_modes_route_pressure(env):
    app, sent = env()
    app.pad_pressed(0, 0, 100)
    app.pad_aftertouch(0, 0, 50)
    assert sent[-1] == [0xA0, 48, 50]  # Poly by default
    app.device.aftertouch = "Off"
    app.pad_aftertouch(0, 0, 60)
    assert sent[-1] == [0xA0, 48, 50]
    app.channel_pressure(70)
    assert sent[-1] == [0xA0, 48, 50]  # channel pressure only in Channel mode
    app.device.aftertouch = "Channel"
    app.channel_pressure(70)
    assert sent[-1] == [0xD0, 70]


def test_clock_settings_turn_sending_and_following_off(env):
    app, _ = env()
    virtual = app.router._outputs[OUT_PORT]
    app.device.send_clock = False
    app.rhythm_tick(100.0)
    assert not [m for _, m, _ in virtual.scheduled if m == [0xF8]]
    app.device.follow_clock = False
    app._midi_in("clock", 1.0)
    assert not app.play.clock.following


class _FakePads:
    def __init__(self, log):
        self.log = log

    def set_velocity_curve(self, table):
        self.log.append(("curve", table))

    def set_polyphonic_aftertouch(self):
        self.log.append(("poly",))

    def set_channel_aftertouch(self):
        self.log.append(("channel",))

    def set_channel_aftertouch_range(self, low, high):
        self.log.append(("range", low, high))


class _FakePush:
    def __init__(self):
        self.log: list = []
        self.pads = _FakePads(self.log)

    def send_midi_to_push(self, message: mido.Message):
        self.log.append(("sysex", list(message.bytes())[len(PUSH2_SYSEX_PREFACE_BYTES) : -1]))


def test_push_controller_sends_only_what_changed():
    controller = object.__new__(PushController)
    controller.push = _FakePush()
    controller._applied = {}
    controller.connected = True
    settings = DeviceSettings(response="Low", pad_brightness=50, screen_brightness=100)
    controller.apply_settings(hardware(settings))
    log = controller.push.log
    assert ("sysex", [0x28, 0, 0, 2]) in log  # all pads, low sensitivity
    assert ("sysex", [0x06, 64]) in log  # LED brightness 50%
    assert ("sysex", [0x08, 127, 1]) in log  # display brightness 255
    assert ("poly",) in log and ("range", 401, 2048) in log
    assert log[0][0] == "curve"
    log.clear()
    controller.apply_settings(hardware(settings))
    assert log == []


# Random velocities in the chord grid


def chord_app(env, **spread):
    app, sent = env()
    app.play.select_layout(2)
    chord = app.play.chord
    chord.spread.rng = random.Random(3)
    for key, value in spread.items():
        setattr(chord.spread, key, value)
    return app, sent


def chord_velocities(sent):
    return [m[2] for m in sent if m[0] == 0x91]


def test_random_gives_each_note_its_own_velocity_and_a_steady_bass(env):
    app, sent = chord_app(env, random=True, spread=40)
    app.pad_pressed(TRIAD, 0, 80)
    velocities = chord_velocities(sent)
    assert len(velocities) == 3 and len(set(velocities)) > 1
    assert [m[2] for m in sent if m[0] == 0x92] == [80]  # bass at the center
    assert app.view()["panel"]["velocities"] == velocities


def test_accent_centers_random_chords_at_max(env):
    app, sent = chord_app(env, random=True, spread=10, max=110)
    app.button_pressed(c.BUTTON_ACCENT)
    app.pad_pressed(TRIAD, 0, 20)
    assert all(100 <= v <= 110 for v in chord_velocities(sent))


def test_the_velocity_page_shows_spread_only_for_random(env):
    app, _ = chord_app(env)
    open_page(app, "Velocity")
    names = [c["name"] if c else None for c in app.view()["controls"]]
    assert names[:4] == ["Min", "Max", None, None]
    app.button_pressed("Upper Row 2")  # Random
    names = [c["name"] if c else None for c in app.view()["controls"]]
    assert names[:4] == ["Min", "Max", "Spread", "Top note"]
    assert "Random velocity" in status_parts(app.view()["panel"])


def test_repeats_roll_fresh_velocities_each_step(env):
    app, _ = chord_app(env, random=True, spread=50)
    app.play.time = lambda: 100.0
    app.play.clock.origin = 100.0
    app.play.set_rhythm(True)
    app.pad_pressed(TRIAD, 0, 80)
    for k in range(20):
        app.rhythm_tick(100.0 + k * 0.02)
    virtual = app.router._outputs[OUT_PORT]
    hits = {}
    for at, m, _ in virtual.scheduled:
        if m[0] == 0x91:
            hits.setdefault(round(at, 4), []).append(m[2])
    steps = list(hits.values())
    assert len(steps) >= 3 and len({tuple(s) for s in steps}) > 1
