"""The beat grid: tempo, swing, tap tempo, transport, and following a leader."""

import pytest

from pushtoo.rhythm.clock import FOLLOW_TIMEOUT, PPQN, Clock


def test_steps_fall_on_the_grid():
    clock = Clock(tempo=120)  # a beat every 0.5 s from time 0
    steps = clock.steps(1 / 4, 0.0, 1.0)  # sixteenths
    assert [i for i, _ in steps] == list(range(8))
    assert [round(t, 4) for _, t in steps] == [i * 0.125 for i in range(8)]


def test_swing_moves_every_other_step_later():
    clock = Clock(tempo=120, swing=75)
    times = [round(t, 4) for _, t in clock.steps(1 / 4, 0.0, 0.5)]
    assert times == [0.0, 0.1875, 0.25, 0.4375]  # offbeats three quarters into their pair


def test_windows_never_repeat_or_drop_a_step():
    clock = Clock(tempo=133, swing=60)
    whole = clock.steps(1 / 6, 10.0, 14.0)
    pieces = [s for k in range(200) for s in clock.steps(1 / 6, 10 + k * 0.02, 10 + (k + 1) * 0.02)]
    assert pieces == whole


def test_tempo_change_keeps_the_beat_in_place():
    clock = Clock(tempo=120)
    clock.set_tempo(90, now=3.0)
    assert clock.beat_at(3.0) == pytest.approx(6.0)
    assert clock.beat_seconds == pytest.approx(60 / 90)


def test_clock_ticks_are_24_per_beat_and_never_swing():
    clock = Clock(tempo=120, swing=75)
    ticks = clock.ticks(0.0, 0.5)
    assert len(ticks) == PPQN
    assert ticks[1] == pytest.approx(0.5 / PPQN)


def test_tap_tempo_averages_the_last_taps():
    clock = Clock()
    for k in range(5):
        clock.tap(10 + k * 0.6)
    assert clock.tempo == pytest.approx(100)
    assert not clock.tap(20.0)  # a long gap starts over


def test_following_takes_the_leaders_tempo_and_beats_then_lets_go():
    clock = Clock(tempo=120)
    clock.external_start(100.0)
    period = 60 / 150 / PPQN
    for k in range(PPQN * 2):
        clock.external_tick(100.0 + k * period)
    assert clock.following and clock.running
    assert clock.tempo == pytest.approx(150)
    assert clock.beat_at(100.0 + PPQN * period) == pytest.approx(1.0)
    assert clock.ticks(100, 101) == []  # a follower sends no clock
    last = 100.0 + (PPQN * 2 - 1) * period
    assert not clock.check_leader(last + 0.5)
    assert clock.check_leader(last + FOLLOW_TIMEOUT + 0.1)
    assert not clock.following
