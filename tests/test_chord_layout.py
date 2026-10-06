"""The chord grid through PlayMode. Default key is C minor, chord octave 3 (C3 = 48),
so the triad row is Cm Ddim Eb Fm Gm Ab Bb Cm."""

from push2_python import constants as c

from pushtoo.modes.play import PlayMode
from pushtoo.profiles.schema import Profile
from tests.pages import open_page, tap_layout
from tests.test_router import make_router

CHORDS, BASS = 0x91, 0x92  # note-on, channels 2 and 3
CHORDS_OFF, BASS_OFF = 0x81, 0x82
TRIAD, SEVENTH, SECONDARY = 1, 2, 7
# Side buttons from the top: Smooth, Root, 1st, 2nd, Open, Drop 3, Shell, Latch.
SIDE_BUTTONS = ("1/32t", "1/32", "1/16t", "1/16", "1/8t", "1/8", "1/4t", "1/4")
VOICING = {"Smooth": "1/32t", "Root": "1/32", "1st": "1/16t", "Open": "1/8t"}
LATCH = "1/4"
KEPT = "pt_play"  # the kept voicing lights in the Play accent


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def make_chord_play(key=None):
    router, virtual, *_ = make_router()
    play = PlayMode(router)
    play.apply_settings(Profile().play)
    if key:
        play.keyboard.root, play.keyboard.scale = key
    tap_layout(play)
    tap_layout(play)
    assert play.layout.name == "Chord"
    clock = Clock()
    play.chord._clock = clock
    return play, virtual.sent, clock


def notes_on(sent, status=CHORDS):
    return [m[1] for m in sent if m[0] == status and m[2] > 0]


def tap_voicing(play, clock, name):
    play.button_pressed(VOICING[name])
    clock.now += 0.05
    play.button_released(VOICING[name])


def test_one_press_plays_a_whole_chord_with_bass():
    play, sent, _ = make_chord_play()
    play.pad_pressed(TRIAD, 0, 100)
    assert notes_on(sent) == [48, 51, 55]  # Cm
    assert notes_on(sent, BASS) == [36]


def test_rows_are_chord_flavors():
    play, sent, clock = make_chord_play()
    tap_voicing(play, clock, "Root")  # deterministic voicing for the check
    play.pad_pressed(SEVENTH, 3, 100)  # Fm7
    assert notes_on(sent) == [53, 56, 60, 63]
    assert play.view()["panel"]["chord_name"] == "Fm7"
    play.pad_pressed(SECONDARY, 3, 100)  # V7 of Fm = C7
    assert play.view()["panel"]["chord_name"] == "C7"
    assert play.view()["panel"]["role"] == "→ iv"
    assert play.view()["panel"]["role_line"] == "V7/iv · leads to iv"


def test_last_chord_pressed_wins_and_changes_retrigger():
    play, sent, _ = make_chord_play()
    play.pad_pressed(TRIAD, 0, 100)
    sent.clear()
    play.pad_pressed(TRIAD, 3, 100)  # Fm while Cm is still held
    offs = [i for i, m in enumerate(sent) if m[0] in (CHORDS_OFF, BASS_OFF)]
    ons = [i for i, m in enumerate(sent) if m[0] in (CHORDS, BASS)]
    assert offs and max(offs) < min(ons)
    sent.clear()
    play.pad_released(TRIAD, 0)  # releasing the old chord changes nothing
    assert sent == []
    play.pad_released(TRIAD, 3)
    assert sorted(m[1] for m in sent if m[0] == CHORDS_OFF)


def test_smooth_voicing_keeps_progressions_close():
    play, _, _ = make_chord_play(key=(0, "Major"))
    played = []
    for col in (0, 4, 5, 3):  # I V vi IV
        play.pad_pressed(TRIAD, col, 100)
        played.append(play.chord.notes)
        play.pad_released(TRIAD, col)
    for a, b in zip(played, played[1:], strict=False):
        assert abs(sum(a) / len(a) - sum(b) / len(b)) <= 5  # the hand barely moves
    assert played[1] != [55, 59, 62]  # G was re-voiced, not played from its root


def test_voicing_tap_latches_and_hold_is_momentary():
    play, sent, clock = make_chord_play()
    tap_voicing(play, clock, "1st")
    play.pad_pressed(TRIAD, 0, 100)
    assert notes_on(sent) == [51, 55, 60]
    assert play.button_colors()[VOICING["1st"]] == KEPT
    play.pad_released(TRIAD, 0)
    play.button_pressed(VOICING["Root"])  # hold
    assert play.button_colors()[VOICING["Root"]] == "white"  # held lights white
    play.pad_pressed(TRIAD, 0, 100)
    assert notes_on(sent)[-3:] == [48, 51, 55]
    clock.now += 1.0
    play.button_released(VOICING["Root"])
    assert play.chord.active_voicing == "1st"  # back to the latched voicing


def test_pressing_a_voicing_while_holding_revoices_the_chord():
    play, sent, _ = make_chord_play()
    play.pad_pressed(TRIAD, 0, 100)
    sent.clear()
    play.button_pressed(VOICING["Open"])
    assert notes_on(sent) and sorted(notes_on(sent)) != [48, 51, 55]


def test_bass_row_plays_single_notes_alongside_chords():
    play, sent, _ = make_chord_play()
    play.pad_pressed(0, 4, 90)  # G bass
    play.pad_pressed(TRIAD, 0, 100)
    assert notes_on(sent, BASS) == [43, 36]
    play.pad_released(0, 4)
    assert [m[1] for m in sent if m[0] == BASS_OFF] == [43]


def test_mutes():
    play, sent, _ = make_chord_play()
    open_page(play, "Output")
    play.button_pressed("Upper Row 2")  # Mute bass
    play.pad_pressed(TRIAD, 0, 100)
    assert notes_on(sent, BASS) == []
    play.button_pressed("Upper Row 1")  # Mute chords
    play.pad_pressed(TRIAD, 1, 100)
    assert notes_on(sent) == [48, 51, 55]


def test_key_change_while_held_follows_the_new_key():
    play, sent, clock = make_chord_play()
    tap_voicing(play, clock, "Root")
    play.pad_pressed(TRIAD, 0, 100)
    sent.clear()
    play.button_pressed(c.BUTTON_SCALE)
    play.button_pressed("Upper Row 4")  # D: the held i is now Dm
    assert notes_on(sent) == [50, 53, 57]


def test_octave_moves_the_chords():
    play, sent, clock = make_chord_play()
    tap_voicing(play, clock, "Root")
    play.button_pressed(c.BUTTON_OCTAVE_UP)
    play.pad_pressed(TRIAD, 0, 100)
    assert notes_on(sent) == [60, 63, 67]


def test_leaving_the_layout_releases_everything():
    play, _, _ = make_chord_play()
    play.pad_pressed(TRIAD, 0, 100)
    play.pad_pressed(0, 2, 100)
    tap_layout(play)
    assert play.router.notes_on("Pushtoo Out", 1) == set()
    assert play.router.notes_on("Pushtoo Out", 2) == set()


def test_strum():
    play, sent, clock = make_chord_play()
    open_page(play, "Style")
    play.button_pressed("Upper Row 2")  # Strum
    assert play.hardware_settings()["strip_mode"] == "Mod wheel"
    play.pad_pressed(TRIAD, 0, 100)
    assert notes_on(sent) == [] and notes_on(sent, BASS) == [36]
    play.touchstrip(0)
    clock.now += 0.01
    play.touchstrip(127)
    assert notes_on(sent) == [48, 51, 55, 60, 63, 67]
    sent.clear()
    play.pad_released(TRIAD, 0)
    assert len([m for m in sent if m[0] == CHORDS_OFF]) == 6


def test_pad_colors_show_function():
    play, *_ = make_chord_play()
    colors = play.pad_colors()
    assert colors[TRIAD][0] == "pt_home"  # i: home
    assert colors[TRIAD][3] == "pt_away"  # iv: away
    assert colors[TRIAD][4] == "pt_tension"  # v: tension
    assert colors[6][0] == "pt_borrowed"
    assert colors[7][0] == "pt_secondary"  # secondary dominant
    assert colors[0][0] == "pt_root" and colors[0][3] == "pt_in_scale"  # bass row
    play.pad_pressed(TRIAD, 2, 100)
    assert play.pad_colors()[TRIAD][2] == "pt_held"


def test_side_buttons_light_the_voicing_and_latch():
    play, *_ = make_chord_play()
    colors = play.button_colors()
    assert colors["1/32t"] == KEPT  # Smooth, the top button
    assert colors["1/32"] == "dark_gray"
    assert colors[LATCH] == "dark_gray"  # Latch, the bottom button, off


def test_pentatonic_borrows_its_parents_chords():
    play, *_ = make_chord_play(key=(0, "Minor Pentatonic"))
    play.pad_pressed(TRIAD, 2, 100)
    panel = play.view()["panel"]
    assert panel["chord_name"] == "Eb"
    assert panel["parent"] == "Chords from Minor"


def test_state_round_trip():
    play, _, clock = make_chord_play()
    tap_voicing(play, clock, "Open")
    open_page(play, "Style")
    play.button_pressed("Upper Row 2")  # Strum
    play.button_pressed(c.BUTTON_OCTAVE_DOWN)
    state = play.snapshot()
    again, *_ = make_chord_play()
    again.restore(state)
    assert again.chord.strum and again.chord.octave == 2 and again.chord.voicing == "Open"


def test_voicing_buttons_work_from_knobs_mode(env):
    app, sent = env()
    tap_layout(app)
    tap_layout(app)
    app.button_pressed(c.BUTTON_DEVICE)
    app.button_pressed(VOICING["Root"])  # tapped
    app.button_released(VOICING["Root"])
    assert app.button_colors()[VOICING["Root"]] == KEPT
    app.pad_pressed(TRIAD, 0, 100)
    assert notes_on(sent) == [48, 51, 55]


def test_latch_keeps_the_chord_until_the_next_one():
    play, sent, clock = make_chord_play()
    tap_voicing(play, clock, "Root")
    play.button_pressed(LATCH)
    assert play.button_colors()[LATCH] == "pt_latch"
    play.pad_pressed(TRIAD, 0, 100)
    play.pad_released(TRIAD, 0)
    assert play.router.notes_on("Pushtoo Out", 1) == {48, 51, 55}  # still sounding
    play.pad_pressed(TRIAD, 3, 100)  # another chord replaces it
    play.pad_released(TRIAD, 3)
    assert play.router.notes_on("Pushtoo Out", 1) == {53, 56, 60}
    play.pad_pressed(TRIAD, 3, 100)  # tapping the latched chord again stops it
    assert play.router.notes_on("Pushtoo Out", 1) == set()
    play.pad_released(TRIAD, 3)
    assert play.router.notes_on("Pushtoo Out", 1) == set()


def test_turning_latch_off_releases_a_latched_chord():
    play, *_ = make_chord_play()
    play.button_pressed(LATCH)
    play.pad_pressed(TRIAD, 0, 100)
    play.pad_released(TRIAD, 0)
    play.button_pressed(LATCH)
    assert play.router.notes_on("Pushtoo Out", 1) == set()
    assert play.router.notes_on("Pushtoo Out", 2) == set()


def test_latch_lets_one_hand_strum():
    play, sent, clock = make_chord_play()
    open_page(play, "Style")
    play.button_pressed("Upper Row 2")  # Strum
    play.button_pressed(LATCH)
    play.pad_pressed(TRIAD, 0, 100)
    play.pad_released(TRIAD, 0)  # hand off the pads
    play.touchstrip(0)
    clock.now += 0.01
    play.touchstrip(127)
    assert notes_on(sent) == [48, 51, 55, 60, 63, 67]


def test_bass_row_still_releases_with_latch_on():
    play, *_ = make_chord_play()
    play.button_pressed(LATCH)
    play.pad_pressed(0, 4, 90)
    play.pad_released(0, 4)
    assert play.router.notes_on("Pushtoo Out", 2) == set()


def test_octave_column_is_the_first_column_lifted():
    play, _, _ = make_chord_play()
    for col in (3, 4, 5):  # some history so Smooth has something to follow
        play.pad_pressed(TRIAD, col, 100)
        play.pad_released(TRIAD, col)
    left = play.chord.notes_for((TRIAD, 0))
    right = play.chord.notes_for((TRIAD, 7))
    assert right == [n + 12 for n in left]


# The screen explains the side buttons and pads


def rail_states(play):
    return {entry["label"]: entry["state"] for entry in play.view()["panel"]["rail"]}


def test_rail_names_the_side_buttons_in_hardware_order():
    play, _, clock = make_chord_play()
    rail = play.view()["panel"]["rail"]
    labels = [entry["label"] for entry in rail]
    assert labels == ["Smooth", "Root", "1st", "2nd", "Open", "Drop 3", "Shell", "Latch"]
    assert rail_states(play)["Smooth"] == "kept"
    play.button_pressed(VOICING["Open"])  # held
    states = rail_states(play)
    assert states["Open"] == "held" and states["Smooth"] == "off"
    clock.now += 1.0
    play.button_released(VOICING["Open"])
    play.button_pressed(LATCH)
    states = rail_states(play)
    assert states["Smooth"] == "kept" and states["Latch"] == "latch_on"


def test_side_button_leds_match_the_rail():
    play, _, clock = make_chord_play()
    play.button_pressed(VOICING["Root"])
    play.button_pressed(LATCH)
    leds = {"kept": KEPT, "held": "white", "latch_on": "pt_latch", "off": "dark_gray"}
    colors = play.button_colors()
    for button, entry in zip(SIDE_BUTTONS, play.view()["panel"]["rail"], strict=True):
        assert colors[button] == leds[entry["state"]]


def test_screen_says_when_latch_holds_a_chord():
    play, *_ = make_chord_play()
    play.button_pressed(LATCH)
    play.pad_pressed(TRIAD, 0, 100)
    assert not play.view()["panel"]["latched"]  # your finger holds it
    play.pad_released(TRIAD, 0)
    assert play.view()["panel"]["latched"]


def test_pad_map_mirrors_the_pads_and_lights_the_row():
    play, *_ = make_chord_play()
    panel = play.view()["panel"]
    assert panel["grid"] == play.pad_colors()
    assert panel["row"] is None
    assert panel["row_names"][SEVENTH] == "7th"
    play.pad_pressed(SEVENTH, 3, 100)
    assert play.view()["panel"]["row"] == SEVENTH


def test_right_column_says_octave_up():
    play, *_ = make_chord_play()
    play.pad_pressed(TRIAD, 7, 100)
    assert play.view()["panel"]["role_line"] == "i · home · octave up"


def test_bass_row_names_its_note():
    play, *_ = make_chord_play()
    play.pad_pressed(0, 4, 100)  # G, an octave below the chord register
    panel = play.view()["panel"]
    assert panel["bass_note"] == "G2" and panel["row"] == 0
    play.pad_released(0, 4)
    assert play.view()["panel"]["bass_note"] is None


def test_chord_pages_leave_the_rail_column_free():
    play, *_ = make_chord_play()
    for index in range(len(play.pages)):
        play.button_pressed(f"Lower Row {index + 1}")
        upper, lower = play.button_rows()
        assert upper[7] is None and lower[7] is None


def test_side_buttons_outside_the_chord_screen_toast(env):
    app, _ = env()
    tap_layout(app)
    tap_layout(app)
    app.button_pressed(c.BUTTON_DEVICE)
    app.button_pressed(VOICING["Open"])
    assert app.view()["toast"] == "Voicing: Open (held)"
    app.button_pressed(LATCH)
    assert app.view()["toast"] == "Latch on"


def test_bass_note_under_a_chord_makes_a_slash_chord():
    play, *_ = make_chord_play()
    play.pad_pressed(TRIAD, 4, 100)  # Gm
    play.pad_pressed(0, 6, 100)  # Bb in the bass
    panel = play.view()["panel"]
    assert panel["chord_name"] == "Gm/Bb"
    assert panel["notes"][0] == "Bb2"
    play.pad_pressed(0, 1, 100)  # D, lower than Bb: the lowest held bass wins
    assert play.view()["panel"]["chord_name"] == "Gm/D"
    play.pad_released(0, 1)
    play.pad_released(0, 6)
    play.pad_pressed(0, 4, 100)  # G under Gm is just Gm
    assert play.view()["panel"]["chord_name"] == "Gm"
