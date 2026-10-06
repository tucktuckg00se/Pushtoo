"""Random velocities for chord notes."""

import random

from pushtoo.rhythm.velocity import VelocitySpread

CHORD = [48, 51, 55]


def spread(**kw):
    return VelocitySpread(rng=random.Random(1), **kw)


def test_as_played_scales_the_pad_into_the_range():
    v = spread(min=40, max=100)
    assert v.velocities(CHORD, 127, accent=False) == [100, 100, 100]
    assert v.velocities(CHORD, 1, accent=False) == [40, 40, 40]


def test_accent_is_as_loud_as_the_range_allows():
    assert spread(max=110).velocities(CHORD, 20, accent=True) == [110] * 3
    loud = spread(random=True, min=1, max=110, spread=20)
    for _ in range(50):
        values = loud.velocities(CHORD, 20, accent=True)
        assert all(90 <= x <= 110 for x in values)  # down from Max, never above


def test_spread_zero_keeps_every_note_at_the_center():
    assert spread(random=True, spread=0).velocities(CHORD, 64, accent=False) == [64] * 3


def test_random_stays_inside_min_and_max_and_covers_the_range():
    v = spread(random=True, min=30, max=90, spread=127)
    seen = {x for _ in range(400) for x in v.velocities(CHORD, 64, accent=False)}
    assert min(seen) == 30 and max(seen) == 90


def test_notes_vary_from_each_other():
    v = spread(random=True, spread=30)
    assert len(set(v.velocities(CHORD, 80, accent=False))) > 1


def test_top_note_offset_lifts_only_the_highest_note():
    v = spread(random=True, spread=0, top=20)
    assert v.velocities([55, 48, 51], 64, accent=False) == [84, 64, 64]


def test_min_and_max_never_cross():
    v = spread(min=60, max=80)
    v.set_min(100)
    v.set_max(10)
    assert v.min == v.max == 80


def test_snapshot_round_trip():
    v = spread(random=True, min=20, max=110, spread=12, top=-5)
    again = VelocitySpread()
    again.restore(v.snapshot())
    assert again.snapshot() == v.snapshot()
