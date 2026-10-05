import pytest

from pushtoo.chords import (
    INTERVALS,
    auto_intervals,
    chord_name,
    fits_key,
    grid_at,
    inversion_name,
    root_at,
    voice,
)
from pushtoo.music import NOTE_NAMES, KeyboardLayout

C_MAJOR = KeyboardLayout(root=0, scale="Major")
A_MINOR = KeyboardLayout(root=9, scale="Minor")


@pytest.mark.parametrize(
    ("root", "name"),
    [(0, "C"), (2, "Dm"), (4, "Em"), (5, "F"), (7, "G"), (9, "Am"), (11, "Bdim")],
)
def test_auto_chords_are_the_diatonic_triads_of_c_major(root, name):
    assert chord_name(root, auto_intervals(root, C_MAJOR)) == name


def test_auto_chords_follow_the_key_in_minor():
    names = [chord_name(r, auto_intervals(r, A_MINOR)) for r in (9, 11, 0, 2, 4, 5, 7)]
    assert names == ["Am", "Bdim", "C", "Dm", "Em", "F", "G"]


def test_out_of_key_roots_get_major():
    assert auto_intervals(1, C_MAJOR) == INTERVALS["Maj"]  # C# in C major


def test_inversions_lift_the_lowest_tone():
    c = (0, 4, 7)
    assert voice(60, c, 0) == [60, 64, 67]
    assert voice(60, c, 1) == [64, 67, 72]
    assert voice(60, c, 2) == [67, 72, 76]
    assert voice(60, c, 3) == [72, 76, 79]  # an octave up: brighter, same chord


def test_extensions_stack_on_any_chord():
    assert voice(60, (0, 4, 7), 0, extensions=(14, 21)) == [60, 64, 67, 74, 81]
    assert chord_name(0, (0, 4, 7), ["+9", "+13"]) == "C (9, 13)"


def test_notes_outside_midi_range_are_dropped():
    assert voice(124, (0, 4, 7), 0) == [124]


def test_fits_key_marks_hint_chords():
    assert fits_key(2, INTERVALS["m7"], C_MAJOR)  # Dm7 is diatonic
    assert not fits_key(2, INTERVALS["Maj"], C_MAJOR)  # D major has F#


def test_c_major_root_rows_match_the_prd_diagram():
    in_key = [NOTE_NAMES[root_at(0, col, C_MAJOR, 3).note % 12] for col in range(8)]
    assert in_key == ["C", "D", "E", "F", "G", "A", "B", "C"]
    assert root_at(0, 0, C_MAJOR, 3).home and root_at(0, 7, C_MAJOR, 3).home
    assert root_at(0, 7, C_MAJOR, 3).note == 60  # an octave above the home pad
    sharps = [root_at(1, col, C_MAJOR, 3) for col in range(8)]
    names = [NOTE_NAMES[p.note % 12] if p else None for p in sharps]
    assert names == ["C#", "Eb", None, "F#", "Ab", "Bb", None, None]
    assert not any(p.in_key for p in sharps if p)


def test_home_note_is_always_bottom_left():
    for root in range(12):
        key = KeyboardLayout(root=root, scale="Dorian")
        assert root_at(0, 0, key, 3).note % 12 == root


def test_pentatonic_root_row_continues_into_the_next_octave():
    key = KeyboardLayout(root=0, scale="Minor Pentatonic")
    notes = [root_at(0, col, key, 3).note for col in range(8)]
    assert notes == [48, 51, 53, 55, 58, 60, 63, 65]


def test_grid_maps_type_across_and_voicing_up():
    assert grid_at(0, 0) is None and grid_at(1, 3) is None
    assert grid_at(2, 0) == ("Auto", 0)
    assert grid_at(2, 5) == ("m7", 0)
    assert grid_at(7, 7) == ("Dim", 5)
    assert inversion_name(1) == "1st inversion"
    assert inversion_name(5) == "Voicing 6"
