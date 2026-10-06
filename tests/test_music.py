import pytest

from pushtoo.music import (
    SCALES,
    DrumLayout,
    KeyboardLayout,
    PadRole,
    drum_name,
    note_name,
)


def test_bottom_left_pad_is_the_root():
    layout = KeyboardLayout(root=2, scale="Minor", octave=3)
    assert layout.note_at(0, 0) == 50  # D3
    assert note_name(50) == "D3"


def test_in_key_row_walks_the_scale():
    layout = KeyboardLayout(root=0, scale="Major", octave=3)
    assert [layout.note_at(0, col) for col in range(8)] == [48, 50, 52, 53, 55, 57, 59, 60]


def test_in_key_rows_are_a_fourth_apart_in_seven_note_scales():
    layout = KeyboardLayout(root=0, scale="Major", octave=3)
    assert layout.note_at(1, 0) == 53  # F3, three degrees up
    assert layout.note_at(2, 0) == 59  # B3


@pytest.mark.parametrize("scale", list(SCALES))
def test_every_in_key_pad_is_in_scale(scale):
    layout = KeyboardLayout(root=5, scale=scale, octave=2)
    for row in range(8):
        for col in range(8):
            note = layout.note_at(row, col)
            assert note is not None
            assert layout.role_of(note) in (PadRole.ROOT, PadRole.IN_SCALE)


def test_pentatonic_rows_step_by_the_degree_nearest_a_fourth():
    layout = KeyboardLayout(root=0, scale="Minor Pentatonic", octave=3)
    assert layout.row_step_degrees() == 2  # 0, 3, [5] -> degree 2 is the fourth
    assert layout.note_at(1, 0) == 53


def test_chromatic_layout_is_fourths():
    layout = KeyboardLayout(root=0, scale="Major", octave=3, in_key=False)
    assert layout.note_at(0, 1) == 49
    assert layout.note_at(1, 0) == 53
    assert layout.role_of(49) is PadRole.OUT_OF_SCALE


def test_notes_outside_midi_range_are_none():
    layout = KeyboardLayout(root=0, scale="Major", octave=7)
    assert layout.note_at(7, 7) is None


def test_octave_is_clamped():
    layout = KeyboardLayout(octave=7)
    layout.shift_octave(+1)
    assert layout.octave == 7


def test_root_wraps_and_scale_clamps():
    layout = KeyboardLayout(root=11, scale="Major")
    layout.step_root(+1)
    layout.step_scale(-1)
    assert layout.root == 0
    assert layout.scale == "Major"
    assert layout.key_name == "C Major"


def test_drum_banks_cover_36_to_99_starting_bottom_left():
    drums = DrumLayout()
    assert drums.note_at(0, 0) == 36  # Kick
    assert drums.note_at(0, 3) == 39
    assert drums.note_at(3, 3) == 51  # top-right of the GM bank
    assert drums.note_at(0, 4) == 52  # bottom-right bank
    assert drums.note_at(4, 0) == 68  # top-left bank
    assert drums.note_at(7, 7) == 99
    notes = {drums.note_at(r, c) for r in range(8) for c in range(8)}
    assert notes == set(range(36, 100))


def test_drum_bank_shift_is_clamped_to_midi_range():
    drums = DrumLayout(start=36)
    drums.shift_bank(-1)
    assert drums.start == 20
    drums.shift_bank(-5)
    assert drums.start == 0
    drums.shift_bank(+20)
    assert drums.note_at(7, 7) == 127


def test_drum_names_fall_back_to_note_names():
    assert drum_name(38) == "Snare"
    assert drum_name(99) == "Eb7"
