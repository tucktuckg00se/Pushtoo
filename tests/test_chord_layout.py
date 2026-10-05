"""The Chord layout through PlayMode: Auto roots, held types, re-triggers, extensions,
live key changes, Strum and LEDs. Default key is C minor, chord octave 3 (C3 = 48)."""

from push2_python import constants as c

from pushtoo.modes.play import PlayMode
from pushtoo.profiles.schema import Profile
from tests.test_router import make_router

CHORDS, BASS = 0x91, 0x92  # note-on, channels 2 and 3
CHORDS_OFF, BASS_OFF = 0x81, 0x82


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def make_chord_play():
    router, virtual, *_ = make_router()
    play = PlayMode(router)
    play.apply_settings(Profile().play)
    play.button_pressed(c.BUTTON_LAYOUT)
    play.button_pressed(c.BUTTON_LAYOUT)
    assert play.layout.name == "Chord"
    clock = Clock()
    play.chord._clock = clock
    return play, virtual.sent, clock


def notes_on(sent, status=CHORDS):
    return [m[1] for m in sent if m[0] == status and m[2] > 0]


def test_root_alone_plays_its_auto_chord_with_bass():
    play, sent, _ = make_chord_play()
    play.pad_pressed(0, 0, 100)
    assert notes_on(sent) == [48, 51, 55]  # C minor's Cm
    assert notes_on(sent, BASS) == [36]
    play.pad_pressed(0, 1, 90)  # D in C minor: Ddim
    assert notes_on(sent)[3:] == [50, 53, 56]


def test_out_of_key_root_plays_major():
    play, sent, _ = make_chord_play()
    play.pad_pressed(1, 0, 100)  # C# above C
    assert notes_on(sent) == [49, 53, 56]


def test_held_type_applies_to_the_next_root():
    play, sent, _ = make_chord_play()
    play.pad_pressed(2, 4, 100)  # Maj7, root position
    assert sent == []  # a type pad alone is silent
    play.pad_pressed(0, 0, 100)
    assert notes_on(sent) == [48, 52, 55, 59]


def test_type_pressed_while_root_held_retriggers_whole_chord():
    play, sent, _ = make_chord_play()
    play.pad_pressed(0, 0, 100)
    sent.clear()
    play.pad_pressed(3, 1, 100)  # Maj, 1st inversion
    offs = [i for i, m in enumerate(sent) if m[0] in (CHORDS_OFF, BASS_OFF)]
    ons = [i for i, m in enumerate(sent) if m[0] in (CHORDS, BASS)]
    assert max(offs) < min(ons)  # every old note stops before the new chord starts
    assert sorted(m[1] for m in sent if m[0] == CHORDS_OFF) == [48, 51, 55]
    assert notes_on(sent) == [52, 55, 60]


def test_releasing_the_type_keeps_the_chord_until_the_root_lets_go():
    play, sent, _ = make_chord_play()
    play.pad_pressed(0, 0, 100)
    play.pad_pressed(2, 1, 100)
    sent.clear()
    play.pad_released(2, 1)
    assert sent == []
    play.pad_released(0, 0)
    assert sorted(m[1] for m in sent if m[0] == CHORDS_OFF) == [48, 52, 55]
    assert [m[1] for m in sent if m[0] == BASS_OFF] == [36]
    play.pad_pressed(0, 0, 100)  # the next root alone is Auto again
    assert notes_on(sent)[-3:] == [48, 51, 55]


def test_mutes_silence_chords_or_bass():
    play, sent, _ = make_chord_play()
    play.button_pressed("Lower Row 2")  # Output page
    play.button_pressed("Upper Row 2")  # Mute bass
    play.pad_pressed(0, 0, 100)
    assert notes_on(sent, BASS) == []
    play.button_pressed("Upper Row 1")  # Mute chords: held chord re-triggers silently
    assert notes_on(sent) == [48, 51, 55]
    assert all(m[0] in (CHORDS_OFF, BASS_OFF) for m in sent[3:])


def test_extensions_latch_and_retrigger_held_chords():
    play, sent, _ = make_chord_play()
    play.pad_pressed(0, 0, 100)
    sent.clear()
    play.button_pressed("1/4t")  # +9
    assert notes_on(sent) == [48, 51, 55, 62]
    assert play.view()["panel"]["chord_name"] == "Cm (9)"
    assert play.button_colors()["1/4t"] == "pt_hint"
    assert play.button_colors()["1/16"] == "black"  # spare buttons stay dark
    play.pad_released(0, 0)
    play.pad_pressed(0, 3, 100)  # still latched for the next chord: Fm add 9
    assert notes_on(sent)[-4:] == [53, 56, 60, 67]


def test_key_change_while_held_reharmonizes_live():
    play, sent, _ = make_chord_play()
    play.pad_pressed(0, 0, 100)
    sent.clear()
    play.button_pressed(c.BUTTON_SCALE)
    play.button_pressed("Upper Row 4")  # D: the held home pad is now D minor's Dm
    assert notes_on(sent) == [50, 53, 57]


def test_octave_buttons_move_held_chords():
    play, sent, _ = make_chord_play()
    play.pad_pressed(0, 0, 100)
    play.button_pressed(c.BUTTON_OCTAVE_UP)
    assert notes_on(sent)[-3:] == [60, 63, 67]


def test_leaving_the_layout_releases_held_chords():
    play, sent, _ = make_chord_play()
    play.pad_pressed(0, 0, 100)
    play.button_pressed(c.BUTTON_LAYOUT)
    play.pad_released(0, 0)  # now a Keyboard pad: must not leave the chord stuck
    assert sorted(m[1] for m in sent if m[0] == CHORDS_OFF) == [48, 51, 55]
    assert play.router.notes_on("Pushtoo Out", 1) == set()


def test_strum_plays_bass_on_press_and_tones_as_the_strip_is_crossed():
    play, sent, clock = make_chord_play()
    play.button_pressed("Upper Row 2")  # Style page: Strum
    assert play.hardware_settings()["strip_mode"] == "Mod wheel"
    play.pad_pressed(0, 0, 100)
    assert notes_on(sent) == [] and notes_on(sent, BASS) == [36]
    play.touchstrip(0)
    clock.now += 0.01
    play.touchstrip(127)  # one sweep: every tone crossed, in order
    assert notes_on(sent) == [48, 51, 55, 60, 63, 67]
    clock.now += 0.5  # finger lifted and put down mid-strip: no sweep from the old spot
    play.touchstrip(64)
    assert notes_on(sent)[-1:] == [60]
    assert sent[-2] == [CHORDS_OFF, 60, 0]  # re-crossing a tone re-triggers it
    sent.clear()
    play.pad_released(0, 0)
    assert sorted(m[1] for m in sent if m[0] == CHORDS_OFF) == [48, 51, 55, 60, 63, 67]


def test_strip_without_a_chord_does_nothing_in_strum():
    play, sent, _ = make_chord_play()
    play.button_pressed("Upper Row 2")
    play.touchstrip(64)
    assert sent == []


def test_pad_colors_show_home_held_and_fitting_types():
    play, *_ = make_chord_play()
    colors = play.pad_colors()
    assert colors[0][0] == "pt_root" and colors[0][7] == "pt_root"  # home notes
    assert colors[1][1] == "pt_off"  # above D sits Eb, which is in key: no pad
    assert colors[1][2] == "pt_out_of_scale"  # above Eb: E, out of key in C minor
    assert colors[2][2] == "pt_hint"  # Cm fits C minor
    assert colors[2][1] == "pt_out_of_scale"  # C major does not
    assert colors[2][0] == "pt_in_scale"  # Auto
    play.pad_pressed(0, 0, 100)
    assert play.pad_colors()[0][0] == "pt_held"
    play.button_pressed(c.BUTTON_SCALE)
    play.button_pressed("Upper Row 1")  # Chromatic: hints and dimming off
    assert play.pad_colors()[2][1] == "pt_out_of_scale"
    assert play.pad_colors()[2][2] == "pt_out_of_scale"


def test_panel_names_the_chord_and_voicing():
    play, *_ = make_chord_play()
    play.pad_pressed(4, 5, 100)  # m7, 2nd inversion
    play.pad_pressed(0, 3, 100)  # F
    panel = play.view()["panel"]
    assert panel["kind"] == "chord"
    assert panel["chord_name"] == "Fm7"
    assert panel["inversion"] == "2nd inversion"
    assert panel["notes"] == ["C4", "Eb4", "F4", "Ab4"]


def test_chord_settings_come_from_the_profile_and_survive_restarts():
    play, *_ = make_chord_play()
    assert (play.layout.channel, play.chord.bass_channel) == (1, 2)
    play.button_pressed("Upper Row 2")  # Strum
    play.button_pressed(c.BUTTON_OCTAVE_DOWN)
    state = play.snapshot()
    again, *_ = make_chord_play()
    again.restore(state)
    assert again.chord.strum and again.chord.octave == 2


def test_extensions_work_and_stay_lit_from_knobs_mode(env):
    app, sent = env()
    app.button_pressed(c.BUTTON_LAYOUT)
    app.button_pressed(c.BUTTON_LAYOUT)
    app.button_pressed(c.BUTTON_DEVICE)  # Knobs; pads still play the Chord layout
    app.button_pressed("1/4")  # +6
    assert app.button_colors()["1/4"] == "pt_hint"
    app.pad_pressed(0, 0, 100)
    assert notes_on(sent) == [48, 51, 55, 57]
