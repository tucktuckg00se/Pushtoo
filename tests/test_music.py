import pytest

from pushtoo.music import SCALES, KeyboardLayout, PadRole, note_name


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
