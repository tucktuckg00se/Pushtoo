from pushtoo.rhythm.arp import sequence

C_MAJOR = [64, 60, 67]  # played E, C, G


def test_up_and_down_sort_by_pitch():
    assert sequence(C_MAJOR, "Up") == [60, 64, 67]
    assert sequence(C_MAJOR, "Down") == [67, 64, 60]


def test_up_down_doesnt_repeat_the_turns():
    assert sequence(C_MAJOR, "Up-down") == [60, 64, 67, 64]


def test_as_played_keeps_the_order_you_pressed():
    assert sequence(C_MAJOR, "As played") == [64, 60, 67]


def test_octaves_stack_the_pattern_higher():
    assert sequence(C_MAJOR, "Up", octaves=2) == [60, 64, 67, 72, 76, 79]
    assert sequence([120], "Up", octaves=2) == [120]  # stays inside MIDI


def test_nothing_held_plays_nothing():
    assert sequence([], "Random") == []
