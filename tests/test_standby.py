"""Life on the Session button and standby, through the App with time under test control."""

import pytest
from push2_python import constants as c

from pushtoo.midi.router import OUT_PORT
from pushtoo.rhythm.repeat import LIFE_TAG
from pushtoo.standby import Standby
from pushtoo.theme import led
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
