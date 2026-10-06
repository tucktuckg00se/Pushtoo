"""More scales, chord sets and their row kinds, new voicings, and the Keyboard over a
latched chord."""

import pytest
from push2_python import constants as c

from pushtoo.chords import (
    APPROXIMATE_PARENTS,
    CHORD_SETS,
    PARENT_SCALES,
    ROW_CHORD_KINDS,
    ROW_KINDS,
    chord_at,
    chord_name,
    drop3,
    fits_key,
    numeral_label,
    shell,
)
from pushtoo.music import SCALES, KeyboardLayout
from pushtoo.profiles.loader import ProfileError, parse
from pushtoo.render.screens import status_parts
from tests.pages import tap_layout
from tests.test_chord_layout import LATCH, TRIAD, make_chord_play, notes_on

C_MAJOR = KeyboardLayout(root=0, scale="Major")
A_MINOR = KeyboardLayout(root=9, scale="Minor")
SPICE = {"borrowed", "borrowed_dorian", "borrowed_mixolydian", "borrowed_phrygian",
         "secondary", "secondary_ii", "tritone_sub"}  # fmt: skip


def name(key, kind, degree):
    chord = chord_at(key, kind, degree)
    return chord_name(chord.pitch_class(key), chord.intervals)


# Scales


@pytest.mark.parametrize("scale", [s for s in SCALES if len(SCALES[s]) != 7])
def test_small_and_large_scales_borrow_a_seven_note_parent(scale):
    parent = PARENT_SCALES[scale]
    assert len(SCALES[parent]) == 7
    if scale not in APPROXIMATE_PARENTS:
        assert set(SCALES[scale]) <= set(SCALES[parent])


@pytest.mark.parametrize("scale", list(SCALES))
def test_every_scale_plays_and_builds_a_full_grid(scale):
    key = KeyboardLayout(root=2, scale=scale)
    assert all(key.note_at(row, col) is not None for row in range(8) for col in range(8))
    for kind in ROW_CHORD_KINDS:
        assert len({chord_at(key, kind, degree).root for degree in range(8)}) >= 6


# Row kinds


def test_new_kinds_build_the_chords_players_expect():
    assert name(C_MAJOR, "sixth", 0) == "C6" and name(C_MAJOR, "sixth", 1) == "Dm6"
    assert name(A_MINOR, "sixth", 3) == "Dm6"
    assert name(C_MAJOR, "six_nine", 0) == "C6/9"
    assert name(C_MAJOR, "eleventh", 1) == "Dm11"
    assert name(C_MAJOR, "eleventh", 4) == "G9sus4"  # the pop 11, not a natural 11 over B
    assert name(C_MAJOR, "thirteenth", 4) == "G13"
    assert name(C_MAJOR, "power", 0) == "C5"
    assert name(C_MAJOR, "quartal", 0) == "C F B E"  # stacked fourths, shown as notes
    assert name(C_MAJOR, "sus2", 0) == "Csus2"


def test_tones_that_would_rub_are_swapped():
    assert name(C_MAJOR, "sixth", 2) == "Em7"  # not E G B C
    assert name(C_MAJOR, "thirteenth", 5) == "Am11"  # not a minor 13th
    assert numeral_label(chord_at(C_MAJOR, "sixth", 2), C_MAJOR) == "iii7"


def test_spice_kinds_lead_where_they_say():
    assert name(C_MAJOR, "tritone_sub", 5) == "Bb7"
    assert numeral_label(chord_at(C_MAJOR, "tritone_sub", 5), C_MAJOR) == "subV7/vi"
    assert name(C_MAJOR, "secondary_ii", 4) == "Am7"  # ii7 of V
    assert numeral_label(chord_at(C_MAJOR, "secondary_ii", 5), C_MAJOR) == "iiø7/vi"
    phrygian = chord_at(C_MAJOR, "borrowed_phrygian", 1)
    assert numeral_label(phrygian, C_MAJOR) == "bII"  # the Neapolitan


@pytest.mark.parametrize("kind", [k for k in ROW_CHORD_KINDS if k not in SPICE])
@pytest.mark.parametrize("key", [C_MAJOR, A_MINOR, KeyboardLayout(root=4, scale="Dorian")])
def test_everyday_kinds_stay_in_key(kind, key):
    for degree in range(8):
        chord = chord_at(key, kind, degree)
        assert fits_key(chord.pitch_class(key), chord.intervals, key)


# Chord sets


def test_classic_is_the_grid_as_it_was():
    assert ROW_KINDS == ("bass", *CHORD_SETS["Classic"])
    assert all(len(rows) == 7 for rows in CHORD_SETS.values())


def test_main_page_buttons_pick_a_set_and_the_map_relabels():
    play, *_ = make_chord_play()
    upper, _ = play.button_rows()
    assert [item["label"] for item in upper[:7]] == list(CHORD_SETS)
    play.button_pressed("Upper Row 3")  # Jazz
    assert play.chord.chord_set == "Jazz"
    assert play.view()["panel"]["row_names"][1:3] == ["7th", "6/9"]


def test_a_held_chord_revoices_into_the_new_set():
    play, sent, _ = make_chord_play()
    play.pad_pressed(TRIAD, 0, 100)  # Classic: Cm
    play.chord.set_chord_set("Jazz")  # row 1 is now 7ths: Cm7
    assert {n % 12 for n in notes_on(sent)[-4:]} == {0, 3, 7, 10}  # Cm7, voiced smoothly


def test_the_scale_menu_chooses_sets_too():
    play, *_ = make_chord_play()
    play.button_pressed(c.BUTTON_SCALE)
    play.encoder_turned(2, 6 * 2)
    assert play.chord.chord_set == "Jazz"
    assert play.view()["panel"]["chord_set"] == "Jazz"


def test_a_profile_adds_its_own_sets_and_bad_ones_name_the_line():
    profile = parse(
        "play:\n  chord:\n    channel: 2\n    sets:\n"
        "      Mine: [triad, sixth, ninth, quartal, power, borrowed, tritone_sub]\n"
    )
    play, *_ = make_chord_play()
    play.apply_settings(profile.play)
    assert "Mine" in play.chord.sets
    with pytest.raises(ProfileError, match="line 5"):
        parse("play:\n  chord:\n    channel: 2\n    sets:\n      Bad: [triad, banjo]\n")


# Voicings


def test_drop3_and_shell_shapes():
    assert drop3([60, 64, 67, 71]) == [52, 60, 67, 71]  # E drops an octave
    assert shell([60, 64, 67, 71], 60) == [60, 64, 71]  # root, 3rd, 7th
    assert shell([60, 64, 67], 60) == [60, 64, 67]  # a triad stays whole


def test_side_buttons_are_shortcuts_and_the_encoder_reaches_the_rest():
    play, *_ = make_chord_play()
    assert [e["label"] for e in play.chord.rail()][:7] == list(play.chord.voicing_buttons)
    play.encoder_turned(1, 6 * 7)  # Voicing encoder: Smooth -> Wide
    assert play.chord.voicing == "Wide"
    assert all(e["state"] != "kept" for e in play.chord.rail())  # no button for Wide


def test_brightness_moves_smooth_up():
    play, sent, _ = make_chord_play()
    play.pad_pressed(TRIAD, 3, 100)
    plain = notes_on(sent)[-3:]
    play.chord.brightness = 6
    play.chord.notes = []
    play.chord.revoice()
    assert min(notes_on(sent)[-3:]) > min(plain)


# Keyboard over a latched chord


def test_latched_chord_plays_on_under_the_keyboard_and_lights_its_notes(env):
    app, sent = env()
    app.play.select_layout(2)
    app.button_pressed(LATCH)
    app.pad_pressed(TRIAD, 3, 100)  # Fm
    app.pad_released(TRIAD, 3)
    tap_layout(app)  # to Keyboard
    assert app.play.layout.name == "Keyboard"
    assert app.router.notes_on("Pushtoo Out", 1)  # still sounding
    colors = app.play.pad_colors()
    assert colors[0][3] == "pt_chord_tone"  # F
    assert colors[0][1] != "pt_chord_tone"  # D isn't in Fm
    assert "over Fm" in status_parts(app.view()["panel"])


def test_a_held_chord_stops_on_a_layout_switch(env):
    app, _ = env()
    app.play.select_layout(2)
    app.pad_pressed(TRIAD, 3, 100)
    tap_layout(app)
    assert not app.router.notes_on("Pushtoo Out", 1)
    assert "over" not in " ".join(status_parts(app.view()["panel"]))
