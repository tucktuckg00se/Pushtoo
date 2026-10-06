"""Chord note timing: Together, or rolled in and loose."""

import random

import pytest

from pushtoo.midi.router import OUT_PORT
from pushtoo.render.screens import status_parts
from pushtoo.rhythm.repeat import CHORD_TAG
from pushtoo.rhythm.timing import TimingSpread

CHORD = [55, 48, 51]  # G, C, Eb: offsets come back in this order
TRIAD = 1


def timing(**kw):
    return TimingSpread(rng=random.Random(2), **kw)


def ms(offsets):
    return [round(o * 1000, 3) for o in offsets]


def test_together_starts_every_note_at_once():
    assert timing(roll=40).offsets(CHORD) == [0.0, 0.0, 0.0]


def test_roll_up_starts_from_the_lowest_note():
    assert ms(timing(spread=True, roll=30).offsets(CHORD)) == [60, 0, 30]


def test_roll_down_starts_from_the_highest():
    assert ms(timing(spread=True, roll=30, direction="Down").offsets(CHORD)) == [0, 60, 30]


def test_alternate_flips_every_chord():
    t = timing(spread=True, roll=10, direction="Alternate")
    assert ms(t.offsets(CHORD)) == [20, 0, 10]
    assert ms(t.offsets(CHORD)) == [0, 20, 10]
    assert ms(t.offsets(CHORD)) == [20, 0, 10]


def test_loose_only_ever_makes_notes_later():
    t = timing(spread=True, roll=0, loose=25)
    for _ in range(100):
        assert all(0 <= o <= 0.025 for o in t.offsets(CHORD))


def test_snapshot_round_trip():
    t = timing(spread=True, roll=44, direction="Random", loose=7)
    again = TimingSpread()
    again.restore(t.snapshot())
    assert again.snapshot() == t.snapshot()


@pytest.fixture
def rolled(env):
    app, sent = env()
    app.play.select_layout(2)
    chord = app.play.chord
    chord.timing.spread, chord.timing.roll = True, 30
    chord._clock = lambda: 100.0
    return app, sent, app.router._outputs[OUT_PORT]


def test_rolled_chord_queues_later_notes_and_plays_the_first_and_bass_now(rolled):
    app, sent, virtual = rolled
    app.pad_pressed(TRIAD, 0, 100)  # Cm: C3 Eb3 G3
    assert [m[1] for m in sent if m[0] == 0x91] == [48]  # lowest note at once
    assert [m[1] for m in sent if m[0] == 0x92] == [36]  # bass on time
    queued = [(round(at, 3), m[1], tag) for at, m, tag in virtual.scheduled]
    assert queued == [(100.03, 51, CHORD_TAG), (100.06, 55, CHORD_TAG)]
    assert "Rolled ↑ 30 ms" in status_parts(app.view()["panel"])


def test_releasing_before_the_roll_finishes_takes_the_rest_back(rolled):
    app, sent, virtual = rolled
    app.pad_pressed(TRIAD, 0, 100)
    app.pad_released(TRIAD, 0)
    assert virtual.scheduled == []  # nothing left to start later
    offs = sorted(m[1] for m in sent if m[0] == 0x81)
    assert offs == [48, 51, 55]  # and nothing hangs


def test_repeats_roll_too(rolled):
    app, _, virtual = rolled
    app.play.time = lambda: 100.0
    app.play.clock.origin = 100.0
    app.play.set_rhythm(True)
    app.pad_pressed(TRIAD, 0, 100)
    for k in range(10):
        app.rhythm_tick(100.0 + k * 0.02)
    on = sorted((round(at, 3), m[1]) for at, m, _ in virtual.scheduled if m[0] == 0x91)
    assert on[:6] == [
        (100.0, 48),
        (100.03, 51),
        (100.06, 55),
        (100.125, 48),
        (100.155, 51),
        (100.185, 55),
    ]


def test_timing_page_shows_its_encoders_only_when_spread_out(env):
    app, _ = env()
    app.play.select_layout(2)
    app.button_pressed("Lower Row 3")  # Timing
    assert all(control is None for control in app.view()["controls"])
    app.button_pressed("Upper Row 2")  # Spread out
    assert [c["name"] for c in app.view()["controls"][:3]] == ["Roll", "Direction", "Loose"]
