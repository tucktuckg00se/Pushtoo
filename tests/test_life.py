"""Life's engine: pure logic on a frozen clock, like test_repeat."""

from pushtoo.midi.notes import NOTE_OFF, NOTE_ON
from pushtoo.rhythm.clock import Clock
from pushtoo.rhythm.life import Life, next_board
from pushtoo.rhythm.repeat import LIFE_TAG

BLINKER = frozenset({(3, 2), (3, 3), (3, 4)})


def notes_at(row, col):
    return "out", 0, [row * 8 + col]


def test_a_blinker_turns_and_turns_back():
    turned = next_board(BLINKER)
    assert turned == {(2, 3), (3, 3), (4, 3)}
    assert next_board(turned) == BLINKER


def test_the_board_wraps_at_its_edges_unless_told_not_to():
    edge = frozenset({(0, 0), (0, 1), (0, 7)})  # a blinker across the left and right edges
    assert next_board(edge) == {(7, 0), (0, 0), (1, 0)}
    assert next_board(edge, wrap=False) == frozenset()  # apart, each dies alone


def test_seeds_rule_has_no_survivors():
    assert next_board(frozenset({(3, 3), (3, 4)}), "Seeds") == {(2, 3), (2, 4), (4, 3), (4, 4)}


def test_births_play_on_each_step_with_their_note_offs_untagged():
    life, clock = Life(), Clock(tempo=120)  # 1/8 is 0.25 s
    life.on = True
    for cell in BLINKER:
        life.seed(*cell)
    events = life.events(clock, 0.0, 0.3, notes_at)
    ons = [(at, m[1]) for at, _, m, tag in events if m[0] & 0xF0 == NOTE_ON and tag == LIFE_TAG]
    offs = [(at, m[1]) for at, _, m, tag in events if m[0] & 0xF0 == NOTE_OFF and tag == 0]
    # Step 0 turns the blinker upright: (2,3) and (4,3) are born; step 1 turns it back.
    assert ons == [(0.0, 19), (0.0, 35), (0.25, 26), (0.25, 28)]
    assert len(offs) == len(ons)
    assert all(off > on for (on, _), (off, _) in zip(ons, offs, strict=True))


def test_all_plays_every_live_cell_up_to_the_voices():
    life, clock = Life(), Clock(tempo=120)
    life.plays, life.voices = "All", 2
    for cell in BLINKER:
        life.seed(*cell)
    events = life.events(clock, 0.0, 0.01, notes_at)
    assert len([e for e in events if e[2][0] & 0xF0 == NOTE_ON]) == 2


def test_hold_keeps_the_board_and_plays_it():
    life, clock = Life(), Clock(tempo=120)
    life.hold = True
    for cell in BLINKER:
        life.seed(*cell)
    life.events(clock, 0.0, 1.0, notes_at)
    assert life.cells == BLINKER


def test_one_note_from_two_pads_plays_once():
    life, clock = Life(), Clock(tempo=120)
    life.plays, life.hold = "All", True
    life.seed(0, 0)
    life.seed(1, 0)
    events = life.events(clock, 0.0, 0.01, lambda r, c: ("out", 0, [60]))
    assert len(events) == 2  # one note-on, one note-off


def test_an_empty_board_is_silent():
    assert Life().events(Clock(), 0.0, 10.0, notes_at) == []
