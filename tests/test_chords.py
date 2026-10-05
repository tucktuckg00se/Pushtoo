import pytest

from pushtoo.chords import (
    ROW_KINDS,
    apply_voicing,
    chord_at,
    chord_name,
    close,
    drop2,
    fits_key,
    invert,
    numeral,
    role,
    smooth,
    wide,
)
from pushtoo.music import KeyboardLayout

C_MAJOR = KeyboardLayout(root=0, scale="Major")
A_MINOR = KeyboardLayout(root=9, scale="Minor")
DIATONIC = ("triad", "seventh", "add9", "sus", "ninth")


def names(key, kind):
    chords = (chord_at(key, kind, degree) for degree in range(8))
    return [chord_name(chord.pitch_class(key), chord.intervals) for chord in chords]


def test_c_major_rows_read_like_a_chord_chart():
    assert names(C_MAJOR, "triad") == ["C", "Dm", "Em", "F", "G", "Am", "Bdim", "C"]
    sevenths = ["Cmaj7", "Dm7", "Em7", "Fmaj7", "G7", "Am7", "Bm7b5", "Cmaj7"]
    assert names(C_MAJOR, "seventh") == sevenths
    assert names(C_MAJOR, "borrowed") == ["Cm", "Ddim", "Eb", "Fm", "Gm", "Ab", "Bb", "Cm"]
    assert names(C_MAJOR, "secondary")[5] == "E7"  # V7/vi


def test_a_minor_uses_its_own_steps():
    assert names(A_MINOR, "triad") == ["Am", "Bdim", "C", "Dm", "Em", "F", "G", "Am"]
    assert names(A_MINOR, "borrowed")[0] == "A"  # from A major


def test_flat_nine_becomes_an_eleven():
    # Em(addb9) and Em7(b9) sound harsh; the grid uses the 11th instead.
    assert names(C_MAJOR, "add9")[2] == "Em(add11)"
    assert names(C_MAJOR, "ninth")[2] == "Em11"
    assert names(C_MAJOR, "ninth")[0] == "Cmaj9"


@pytest.mark.parametrize("scale", ["Major", "Minor", "Dorian", "Mixolydian", "Harmonic Minor"])
def test_every_diatonic_pad_is_in_key(scale):
    key = KeyboardLayout(root=5, scale=scale)
    for kind in DIATONIC:
        for degree in range(8):
            chord = chord_at(key, kind, degree)
            assert fits_key(chord.pitch_class(key), chord.intervals, key), (kind, degree)


@pytest.mark.parametrize(
    ("scale", "parent"),
    [("Minor Pentatonic", "Minor"), ("Blues", "Minor"), ("Major Pentatonic", "Major")],
)
def test_non_seven_note_scales_use_their_parent(scale, parent):
    key = KeyboardLayout(root=0, scale=scale)
    assert names(key, "triad") == names(KeyboardLayout(root=0, scale=parent), "triad")


def test_unnamed_chords_show_notes_never_a_wrong_name():
    assert chord_name(0, (0, 5, 10)) == "C F Bb"
    assert chord_name(0, (0, 4, 7)) == "C"


def test_numerals_and_roles():
    assert [numeral(C_MAJOR, d) for d in range(7)] == ["I", "ii", "iii", "IV", "V", "vi", "vii°"]
    assert [role(chord_at(C_MAJOR, "triad", d), C_MAJOR) for d in range(7)] == [
        "home", "away", "home", "away", "tension", "home", "tension",
    ]  # fmt: skip
    assert role(chord_at(C_MAJOR, "secondary", 5), C_MAJOR) == "→ vi"
    assert role(chord_at(C_MAJOR, "borrowed", 6), C_MAJOR) == "borrowed"


def test_row_kinds_cover_the_grid():
    assert len(ROW_KINDS) == 8 and ROW_KINDS[0] == "bass" and ROW_KINDS[1] == "triad"


def test_voicings():
    c = close(60, (0, 4, 7))
    assert c == [60, 64, 67]
    assert invert(c, 1) == [64, 67, 72]
    assert invert(c, 2) == [67, 72, 76]
    assert drop2(close(60, (0, 4, 7, 11))) == [55, 60, 64, 71]
    assert wide(c) == [48, 67, 76]


def test_smooth_moves_least_between_chords():
    register = 60
    c = smooth(None, close(60, (0, 4, 7)), register)
    f = smooth(c, close(65, (0, 4, 7)), 65)
    g = smooth(f, close(67, (0, 4, 7)), 67)
    assert c == [60, 64, 67]
    assert f == [60, 65, 69]  # C stays, the others step
    # F and G share no notes, so every voice moves; 6 semitones in total is the least
    # possible (e.g. C->B, F->D, A->G).
    assert sum(abs(a - b) for a, b in zip(f, g, strict=True)) == 6
    assert all(55 <= n <= 79 for n in f + g)


def test_apply_voicing_forced_inversion_and_range():
    notes = close(60, (0, 4, 7))
    assert apply_voicing("1st", notes, None, 60) == [64, 67, 72]
    assert apply_voicing("Root", close(126, (0, 4, 7)), None, 126) == [126]  # dropped above 127


def test_names_are_spelled_for_the_key():
    from pushtoo.chords import key_spelling

    c_minor = KeyboardLayout(root=0, scale="Minor")
    assert chord_name(3, (0, 5, 10), key_spelling(c_minor)) == "Eb Ab Db"
    e_major = KeyboardLayout(root=4, scale="Major")
    assert chord_name(8, (0, 3, 7), key_spelling(e_major)) == "G#m"


def test_numerals_for_the_screen():
    from pushtoo.chords import numeral_label

    def labels(key, kind):
        return [numeral_label(chord_at(key, kind, d), key) for d in range(7)]

    assert labels(C_MAJOR, "seventh") == ["Imaj7", "ii7", "iii7", "IVmaj7", "V7", "vi7", "viiø7"]
    assert labels(C_MAJOR, "borrowed") == ["i", "ii°", "bIII", "iv", "v", "bVI", "bVII"]
    assert labels(C_MAJOR, "secondary")[5] == "V7/vi"
    assert labels(A_MINOR, "triad") == ["i", "ii°", "III", "iv", "v", "VI", "VII"]
    assert labels(A_MINOR, "borrowed")[2] == "#iii"
    harmonic = KeyboardLayout(root=0, scale="Harmonic Minor")
    assert labels(harmonic, "seventh")[2] == "III+maj7"


def test_smooth_never_drifts_away():
    """Thousands of random chord changes under Smooth stay within about two octaves."""
    import random

    from pushtoo.chords import ROW_KINDS

    rng = random.Random(7)
    previous, low, high = None, 127, 0
    for _ in range(5000):
        chord = chord_at(C_MAJOR, ROW_KINDS[rng.randrange(1, 8)], rng.randrange(8))
        root = 48 + chord.root
        previous = smooth(previous, close(root, chord.intervals), root)
        low, high = min(low, previous[0]), max(high, previous[-1])
    assert high - low <= 30
