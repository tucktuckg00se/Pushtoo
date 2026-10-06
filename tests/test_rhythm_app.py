"""Clock, note repeat and arpeggiator through the App, with time under test control."""

import pytest
from push2_python import constants as c

from pushtoo.midi.router import OUT_PORT
from pushtoo.rhythm.repeat import CLOCK_TAG
from pushtoo.ui.controls import INCREMENTS_PER_STEP

STEP = INCREMENTS_PER_STEP
SIDE = ("1/32t", "1/32", "1/16t", "1/16", "1/8t", "1/8", "1/4t", "1/4")


class Now:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def app(env):
    app, sent = env()
    now = Now()
    app.play.time = now
    app.play.clock.origin = 100.0  # the grid starts at t = 100
    virtual = app.router._outputs[OUT_PORT]
    return app, now, virtual


def ons(virtual):
    return [(round(at, 4), m[1], tag) for at, m, tag in virtual.scheduled if m[0] & 0xF0 == 0x90]


def tap(app, now, button, seconds=0.05):
    app.button_pressed(button)
    now.t += seconds
    app.button_released(button)


def test_repeat_tap_toggles_and_hold_is_momentary(app):
    app, now, _ = app
    tap(app, now, c.BUTTON_REPEAT)
    assert app.play.rhythm.on and app.button_colors()[c.BUTTON_REPEAT] == "white"
    tap(app, now, c.BUTTON_REPEAT)
    assert not app.play.rhythm.on
    tap(app, now, c.BUTTON_REPEAT, seconds=1.0)  # held: only while held
    assert not app.play.rhythm.on


def test_held_pad_sounds_now_then_repeats_and_release_takes_back(app):
    app, now, virtual = app
    tap(app, now, c.BUTTON_REPEAT)
    now.t = 100.01
    app.pad_pressed(0, 0, 100)
    assert ons(virtual)[0][:2] == (100.01, 48)  # C3 at once
    for k in range(20):
        app.rhythm_tick(100.01 + k * 0.02)
    times = [at for at, note, _ in ons(virtual)]
    assert times[1:4] == [100.125, 100.25, 100.375]  # sixteenths at 120 BPM
    tag = ons(virtual)[0][2]
    app.pad_released(0, 0)
    assert all(t != tag for _, _, t in ons(virtual))  # queued repeats taken back


def test_side_buttons_are_rates_in_keyboard_while_rhythm_is_on(app):
    app, now, _ = app
    tap(app, now, c.BUTTON_REPEAT)
    app.button_pressed("1/8t")
    assert app.play.rhythm.rate == "1/8t"
    rail = app.view()["panel"]["rail"]
    assert [e["label"] for e in rail] == list(SIDE)
    assert app.button_colors()["1/8t"] == "pt_rate"
    assert "Repeat 1/8t" in app.view()["panel"]["rhythm"]


def test_chord_side_buttons_stay_voicings_until_repeat_is_held(app):
    app, now, _ = app
    app.play.select_layout(2)
    app.button_pressed("1/32")  # Root voicing
    now.t += 0.05
    app.button_released("1/32")
    assert app.play.chord.voicing == "Root" and app.play.rhythm.rate == "1/16"
    app.button_pressed(c.BUTTON_REPEAT)
    assert app.view()["panel"]["rail"][0]["label"] == "1/32t"
    app.button_pressed("1/8")  # picks a rate while Repeat is held
    now.t += 0.05
    app.button_released(c.BUTTON_REPEAT)
    assert app.play.rhythm.rate == "1/8" and not app.play.rhythm.on  # rate picked, not toggled
    assert app.play.chord.voicing == "Root"


def test_chord_with_arp_plays_its_notes_one_by_one(app):
    app, now, virtual = app
    app.play.select_layout(2)
    app.play.rhythm.mode = "Arp"
    tap(app, now, c.BUTTON_REPEAT)
    now.t = 100.0
    app.pad_pressed(1, 0, 100)  # C minor
    for k in range(20):
        app.rhythm_tick(100.0 + k * 0.02)
    assert [note for _, note, _ in ons(virtual)][:4] == [48, 51, 55, 48]
    assert app.router.notes_on(OUT_PORT, 1) == set()  # nothing held: the arp plays it


def test_play_sends_start_and_clock_then_stop(app):
    app, now, virtual = app
    app.button_pressed(c.BUTTON_PLAY)
    assert app.play.clock.running
    starts = [(m, tag) for _, m, tag in virtual.scheduled if m == [0xFA]]
    assert starts == [([0xFA], 0)]
    start_at = next(at for at, m, _ in virtual.scheduled if m == [0xFA])
    app.rhythm_tick(start_at)
    ticks = [(at, tag) for at, m, tag in virtual.scheduled if m == [0xF8]]
    assert ticks and ticks[0] == (start_at, CLOCK_TAG)  # beat 0 with the Start
    app.button_pressed(c.BUTTON_PLAY)
    assert virtual.scheduled[-1][1] == [0xFC]


def test_following_a_leader_shows_on_screen_and_stops_clock_out(app):
    app, now, virtual = app
    app.play.rhythm.on = True
    app._midi_in("start", 50.0)
    for k in range(48):
        app._midi_in("clock", 50.0 + k * 60 / 140 / 24)
    assert app.play.clock.following
    assert app.view()["panel"]["tempo"] == "Following clock · 140"
    virtual.scheduled.clear()
    app.rhythm_tick(51.0)
    assert not [m for _, m, _ in virtual.scheduled if m == [0xF8]]
    app.button_pressed(c.BUTTON_PLAY)
    assert "Following" in app.view()["toast"]
    app.rhythm_tick(60.0)  # no clock for a while: lead again
    assert not app.play.clock.following


def test_tempo_encoder_moves_a_bpm_or_a_tenth_with_shift_and_peeks(app):
    app, now, _ = app
    app.encoder_rotated(c.ENCODER_TEMPO_ENCODER, STEP)
    assert app.play.clock.tempo == pytest.approx(121)
    app.button_pressed(c.BUTTON_SHIFT)
    app.encoder_rotated(c.ENCODER_TEMPO_ENCODER, STEP)
    app.button_released(c.BUTTON_SHIFT)
    assert app.play.clock.tempo == pytest.approx(121.1)
    app.encoder_touched(c.ENCODER_SWING_ENCODER)
    assert app.view()["peek"]["name"] == "Swing"
    app.encoder_released(c.ENCODER_SWING_ENCODER)
    assert "peek" not in app.view()


def test_panic_takes_back_everything_queued(app):
    app, now, virtual = app
    tap(app, now, c.BUTTON_REPEAT)
    app.pad_pressed(0, 0, 100)
    app.rhythm_tick(now.t)
    app.button_pressed(c.BUTTON_SHIFT)
    app.button_pressed(c.BUTTON_STOP)
    assert all(tag == 0 for _, _, tag in virtual.scheduled)


def test_tempo_and_rhythm_settings_survive_a_restart(env):
    app, _ = env()
    app.play.clock.set_tempo(97.5, 0.0)
    app.play.rhythm.pattern = "Down"
    state = app.play.snapshot()
    again, _ = env()
    again.play.restore(state)
    assert again.play.clock.tempo == pytest.approx(97.5)
    assert again.play.rhythm.pattern == "Down"
