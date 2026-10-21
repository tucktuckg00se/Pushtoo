"""Life on the Session button and standby, through the App with time under test control."""

import numpy as np
import pytest
from push2_python import constants as c

from pushtoo.midi.router import OUT_PORT
from pushtoo.render.screens import GLOW_SCREEN, glow_levels
from pushtoo.rhythm.repeat import LIFE_TAG
from pushtoo.setup import DeviceSettings
from pushtoo.standby import SCENES, Standby, column_glow
from pushtoo.theme import (
    DEFAULT_THEME,
    OFF,
    STANDBY_STEPS,
    led,
    resolve,
    standby_led,
    standby_stops,
)
from tests.test_rhythm_app import Now, ons, tap


@pytest.fixture
def app(env):
    app, _ = env()
    now = Now()
    app.play.time = now
    app.play.clock.origin = 100.0  # the grid starts at t = 100
    return app, now, app.router._outputs[OUT_PORT]


def test_session_tap_toggles_life_and_held_is_momentary(app):
    app, now, _ = app
    tap(app, now, c.BUTTON_SESSION)
    assert app.play.life.on and app.button_colors()[c.BUTTON_SESSION] == "white"
    tap(app, now, c.BUTTON_SESSION)
    assert not app.play.life.on
    tap(app, now, c.BUTTON_SESSION, seconds=1.0)
    assert not app.play.life.on


def test_pads_seed_cells_that_play_light_and_step(app):
    app, now, virtual = app
    tap(app, now, c.BUTTON_SESSION)
    for col in (2, 3, 4):  # a blinker on the bottom row
        app.pad_pressed(3, col, 100)
        app.pad_released(3, col)
    assert app.play.pad_colors()[3][3] == led("life")
    for k in range(30):
        app.rhythm_tick(100.0 + k * 0.02)
    life_ons = [on for on in ons(virtual) if on[2] == LIFE_TAG]
    assert life_ons and app.play.life.cells == {(2, 3), (3, 3), (4, 3)}
    assert app.play.pad_colors()[2][3] == led("life")


def test_life_off_clears_the_board_and_takes_back_its_notes(app):
    app, now, virtual = app
    tap(app, now, c.BUTTON_SESSION)
    app.play.life.plays, app.play.life.hold = "All", True
    app.pad_pressed(3, 3, 100)
    app.rhythm_tick(100.24)  # queues the step at 100.25
    assert any(tag == LIFE_TAG for _, _, tag in virtual.scheduled)
    tap(app, now, c.BUTTON_SESSION)
    assert not app.play.life.cells
    assert not any(tag == LIFE_TAG for _, _, tag in virtual.scheduled)


def test_panic_and_unplug_stop_repeats_and_empty_life(app):
    app, now, virtual = app
    tap(app, now, c.BUTTON_REPEAT)
    tap(app, now, c.BUTTON_SESSION)
    app.pad_pressed(0, 0, 100)  # held: no release will come after an unplug
    app.push_disconnected()
    assert not app.play.rhythm.held and not app.play.life.cells
    before = len(ons(virtual))
    for k in range(20):
        app.rhythm_tick(101.0 + k * 0.02)
    assert len(ons(virtual)) == before  # nothing repeats after the unplug


def test_shift_session_starts_standby_and_a_pad_wakes_and_plays(app):
    app, now, virtual = app
    app.button_pressed(c.BUTTON_SHIFT)
    app.button_pressed(c.BUTTON_SESSION)
    app.button_released(c.BUTTON_SESSION)
    app.button_released(c.BUTTON_SHIFT)
    assert app.standby is not None and "standby" in app.view()
    assert not app.play.life.on  # Shift+Session isn't Life
    app.pad_pressed(0, 0, 100)
    assert app.standby is None
    assert [m for m in virtual.sent if m[0] & 0xF0 == 0x90][-1][1] == 48  # C3 played


def test_standby_starts_after_the_timeout_only_when_quiet(app):
    app, now, _ = app
    app.device.standby_minutes = 1
    app._last_input = now.t
    app.rhythm_tick(now.t + 59)
    assert app.standby is None
    app.pad_pressed(0, 0, 100)  # held past the timeout: still playing
    app.rhythm_tick(now.t + 120)
    assert app.standby is None
    app.pad_released(0, 0)
    app.rhythm_tick(now.t + 200)
    assert app.standby is not None


def test_standby_off_never_starts(app):
    app, now, _ = app
    app.device.standby_minutes = 0
    app.rhythm_tick(now.t + 10_000)
    assert app.standby is None


def test_standby_life_reseeds_when_the_board_dies():
    standby = Standby("Life", 0.0, seed=1)
    standby.board = frozenset()
    for k in range(10):
        standby.step(float(k))
    assert standby.board


def test_standby_pads_show_the_scene():
    drift = Standby("Drift", 0.0)
    colors = drift.pad_colors(5.0)
    assert len(colors) == 8 and all(len(row) == 8 for row in colors)
    assert all(color.startswith("pt_") for row in colors for color in row)


def test_glow_is_the_default_and_standby_colors_are_remembered():
    assert SCENES[0] == "Glow" and DeviceSettings().standby_scene == "Glow"
    assert DeviceSettings().standby_colors == "Play"
    saved = {"standby_scene": "Drift", "standby_colors": "Knobs"}
    restored = DeviceSettings.restore(saved, DeviceSettings())
    assert (restored.standby_scene, restored.standby_colors) == ("Drift", "Knobs")
    gone = DeviceSettings.restore(
        {"standby_scene": "Trails", "standby_colors": "Night"}, DeviceSettings()
    )
    assert (gone.standby_scene, gone.standby_colors) == ("Glow", "Play")


def test_glow_pads_wander_on_their_own_gently():
    # Each step a pad moves at most a few of the ramp's 25 fine steps (the Push fades
    # it there over a second), most hold still, and over time every pad is both lit
    # and dark.
    standby = Standby("Glow", 0.0, seed=4)
    assert standby.fades
    ramp = {standby_led(i): i for i in range(STANDBY_STEPS)} | {OFF: 0}
    steps = np.array(
        [[[ramp[v] for v in row] for row in standby.pad_colors(float(k))] for k in range(600)]
    )
    moves = np.abs(np.diff(steps, axis=0))
    assert moves.max() <= 4
    assert (moves > 0).mean() < 0.5
    assert (steps.max(axis=0) >= 5).all() and (steps.min(axis=0) == 0).all()


def test_the_screen_glows_above_the_pads_that_glow():
    standby = Standby("Glow", 0.0, seed=4)
    glow = standby.glow.copy()
    glow[..., 2] = glow[..., 3] = -np.pi / 2  # every pad dark at t = 0 ...
    glow[:, 5, 2] = glow[:, 5, 3] = np.pi / 2  # ... but column 5, at its brightest
    assert column_glow(glow, 0.0)[5] == pytest.approx(1.0)
    level = glow_levels(glow, 0.0)
    above = level[:, 5 * 120 + 60]
    assert above[-1] > 0.4 and above[-1] > above[len(above) // 2] > above[0]  # rises
    assert level[:, 1 * 120 + 60].max() < 0.01  # dark above dark pads


def test_the_glow_stays_dim_at_the_bottom_edge():
    # The glow rises from the bottom edge, so it's kept dim: averaged over ten minutes
    # the bottom row stays well under its cap.
    standby = Standby("Glow", 0.0, seed=4)
    bottom = np.mean([glow_levels(standby.glow, t)[-1].mean() for t in range(0, 600, 10)])
    assert bottom < 0.6 * GLOW_SCREEN


def test_standby_colors_are_the_uis_own():
    # Each mode accent rises from black to the accent itself; Mono climbs the screen's
    # grays. A custom theme changes them with it.
    for palette, token in (("Play", "play"), ("Knobs", "knobs"), ("Mix", "mix")):
        stops = standby_stops(DEFAULT_THEME, palette)
        assert stops[0] == (0, 0, 0) and stops[-1] == DEFAULT_THEME[token]
    assert standby_stops(DEFAULT_THEME, "Mono")[-1] == DEFAULT_THEME["text"]
    teal = resolve({"play": "20c997"})
    assert standby_stops(teal, "Play")[-1] == (0x20, 0xC9, 0x97)


def test_standby_takes_setups_colors(app):
    app, now, _ = app
    app.device.standby_scene, app.device.standby_colors = "Glow", "Mono"
    app.start_standby()
    assert app.view()["standby"]["palette"] == "Mono" and app._pads_fade()
    app.device.standby_scene = "Life"
    app.start_standby()
    assert not app._pads_fade()
