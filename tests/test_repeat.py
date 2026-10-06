"""Note repeat and arpeggiator timing, with the clock frozen at 120 BPM from time 0."""

import pytest

from pushtoo.rhythm.clock import Clock
from pushtoo.rhythm.repeat import Rhythm

ON, OFF = 0x90, 0x80


def ons(events):
    return [(round(at, 4), msg[1], msg[2]) for at, _, msg, _ in events if msg[0] & 0xF0 == ON]


@pytest.fixture
def rhythm():
    r = Rhythm()
    r.on = True
    return r, Clock(tempo=120)


def test_a_press_sounds_now_then_repeats_on_the_grid(rhythm):
    r, clock = rhythm
    first = r.press("pad", "Out", 0, [60], 100, clock, now=0.01)
    assert ons(first) == [(0.01, 60, 100)]
    later = r.events(clock, 0.0, 0.5)
    # The step at 0.0 came before the press; 0.125 onward repeat.
    assert ons(later) == [(0.125, 60, 100), (0.25, 60, 100), (0.375, 60, 100)]


def test_a_step_right_after_the_press_is_skipped(rhythm):
    r, clock = rhythm
    r.press("pad", "Out", 0, [60], 100, clock, now=0.12)  # 5 ms before a step
    assert ons(r.events(clock, 0.12, 0.3)) == [(0.25, 60, 100)]


def test_every_note_on_has_a_note_off_half_a_step_later(rhythm):
    r, clock = rhythm
    r.press("pad", "Out", 3, [60, 64], 90, clock, now=0.0)
    events = r.events(clock, 0.1, 0.2)
    offs = [(round(at, 4), msg) for at, _, msg, tag in events if msg[0] & 0xF0 == OFF]
    assert offs == [(0.1875, [0x83, 60, 0]), (0.1875, [0x83, 64, 0])]
    assert all(tag == 0 for _, _, msg, tag in events if msg[0] & 0xF0 == OFF)


def test_pressure_sets_the_velocity_of_later_repeats(rhythm):
    r, clock = rhythm
    r.press("pad", "Out", 0, [60], 100, clock, now=0.0)
    r.pressure("pad", 30)
    assert ons(r.events(clock, 0.1, 0.2)) == [(0.125, 60, 30)]


def test_release_hands_back_the_tag_to_take_back(rhythm):
    r, clock = rhythm
    r.press("pad", "Out", 0, [60], 100, clock, now=0.0)
    tag = next(t for _, _, msg, t in r.events(clock, 0.1, 0.2) if t)
    assert r.release("pad") == tag
    assert r.events(clock, 0.2, 1.0) == []


def test_arp_plays_one_note_per_step_in_pattern(rhythm):
    r, clock = rhythm
    r.mode, r.pattern = "Arp", "Up"
    first = r.press("chord", "Out", 1, [67, 60, 64], 100, clock, now=0.0)
    assert ons(first) == [(0.0, 60, 100)]
    assert [n for _, n, _ in ons(r.events(clock, 0.1, 0.6))] == [64, 67, 60, 64]


def test_arp_gate_sets_note_length(rhythm):
    r, clock = rhythm
    r.mode, r.gate = "Arp", 20
    r.press("pad", "Out", 0, [60], 100, clock, now=0.0)
    events = r.events(clock, 0.1, 0.2)
    on_at = next(at for at, _, m, _ in events if m[0] & 0xF0 == ON)
    off_at = next(at for at, _, m, _ in events if m[0] & 0xF0 == OFF)
    assert off_at - on_at == pytest.approx(0.125 * 0.2)
