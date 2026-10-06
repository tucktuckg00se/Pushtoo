from push2_python import constants as c

from pushtoo.midi.router import OUT_PORT
from pushtoo.modes.play import PlayMode
from pushtoo.render.screens import status_parts
from pushtoo.ui.controls import INCREMENTS_PER_STEP
from tests.test_router import make_router

USB = "USB MIDI:USB MIDI MIDI 1"
STEP = INCREMENTS_PER_STEP


def make_play():
    router, virtual, opened, present = make_router()
    return PlayMode(router), virtual, opened


def test_keyboard_pad_plays_in_key_on_channel_1():
    play, virtual, _ = make_play()
    play.pad_pressed(0, 0, 100)
    assert virtual.sent == [[0x90, 48, 100]]  # C3, default C minor octave 3


def test_layout_button_switches_to_drums_on_channel_10():
    play, virtual, _ = make_play()
    assert play.button_pressed(c.BUTTON_LAYOUT)
    play.pad_pressed(0, 0, 90)
    assert virtual.sent == [[0x99, 36, 90]]
    assert play.view()["panel"]["kind"] == "drums"
    assert play.view()["panel"]["last_hit"] == "Kick"


def test_accent_forces_full_velocity():
    play, virtual, _ = make_play()
    play.button_pressed(c.BUTTON_ACCENT)
    play.pad_pressed(0, 0, 20)
    assert virtual.sent[-1] == [0x90, 48, 127]


def test_octave_buttons_move_drum_banks():
    play, virtual, _ = make_play()
    play.button_pressed(c.BUTTON_LAYOUT)
    play.button_pressed(c.BUTTON_OCTAVE_UP)
    play.pad_pressed(0, 0, 90)
    assert virtual.sent[-1] == [0x99, 52, 90]


def test_scale_selector_buttons_pick_roots_and_toggle_in_key():
    play, *_ = make_play()
    play.button_pressed(c.BUTTON_SCALE)
    play.button_pressed("Upper Row 4")  # C G [D]
    assert play.keyboard.root == 2
    play.button_pressed("Lower Row 2")  # F [Bb]
    assert play.keyboard.root == 10
    play.button_pressed("Upper Row 1")
    assert not play.keyboard.in_key
    assert play.layout.page == 0  # lower buttons picked roots, not pages
    assert play.view()["panel"]["kind"] == "scale_selector"


def test_scale_selector_encoders_pick_scale_and_root():
    play, *_ = make_play()
    play.button_pressed(c.BUTTON_SCALE)
    play.encoder_turned(0, STEP)
    play.encoder_turned(1, -STEP)
    assert play.keyboard.scale == "Dorian"
    assert play.keyboard.root == 11


def test_f_sharp_lights_only_the_upper_root_button():
    play, *_ = make_play()
    play.button_pressed(c.BUTTON_SCALE)
    play.button_pressed("Lower Row 6")  # Gb
    colors = play.button_colors()
    assert colors["Upper Row 8"] == "white"
    assert colors["Lower Row 6"] == "dark_gray"


def test_key_change_while_held_releases_the_original_pitch():
    play, virtual, _ = make_play()
    play.pad_pressed(0, 0, 100)
    play.button_pressed(c.BUTTON_SCALE)
    play.button_pressed("Upper Row 4")  # D
    play.pad_released(0, 0)
    assert virtual.sent[-1] == [0x80, 48, 0]


def test_output_page_routes_new_notes_and_releases_old_ones_where_they_started():
    play, virtual, opened = make_play()
    play.pad_pressed(0, 0, 100)  # held on Pushtoo Out
    play.button_pressed("Lower Row 3")  # Output page, refreshes destinations
    assert play.page.name == "Output"
    play.encoder_turned(0, STEP)
    assert play.layout.destination == USB
    play.pad_pressed(0, 1, 100)
    assert opened[USB].sent == [[0x90, 50, 100]]
    play.pad_released(0, 0)
    assert virtual.sent[-1] == [0x80, 48, 0]


def test_each_layout_remembers_its_page():
    play, *_ = make_play()
    play.button_pressed("Lower Row 2")
    play.button_pressed(c.BUTTON_LAYOUT)  # Drums
    assert play.page.name == "Play"
    play.button_pressed(c.BUTTON_LAYOUT)  # Chord
    assert play.page.name == "Style"
    play.button_pressed(c.BUTTON_LAYOUT)  # back to Keyboard
    assert play.page.name == "Strip"


def test_touch_strip_sends_pitch_bend_or_mod_wheel():
    play, virtual, _ = make_play()
    play.touchstrip(0)
    assert virtual.sent[-1] == [0xE0, 0, 64]
    play.button_pressed("Lower Row 2")  # Strip page
    play.button_pressed("Upper Row 2")  # Mod wheel
    assert play.hardware_settings()["strip_mode"] == "Mod wheel"
    play.touchstrip(90)
    assert virtual.sent[-1] == [0xB0, 1, 90]


def test_velocity_control_changes_hardware_curve():
    play, *_ = make_play()
    assert play.encoder_turned(1, STEP)
    assert play.hardware_settings()["velocity_curve"] == "Soft"


def test_held_pads_light_white():
    play, *_ = make_play()
    play.pad_pressed(0, 0, 100)
    assert play.pad_colors()[0][0] == "pt_held"
    assert play.pad_colors()[0][1] != "pt_held"


def test_view_has_eight_columns_everywhere():
    play, *_ = make_play()
    for toggle in (None, c.BUTTON_SCALE, c.BUTTON_LAYOUT):
        if toggle:
            play.button_pressed(toggle)
        view = play.view()
        assert len(view["upper"]) == len(view["lower"]) == len(view["controls"]) == 8


def test_unknown_destination_still_renders():
    play, *_ = make_play()
    play.layout.destination = "Gone:Port"
    play.button_pressed("Lower Row 3")
    assert play.view()["controls"][0]["text"] == "—"
    assert OUT_PORT in play.router.destinations()


def test_octave_buttons_go_dark_at_their_limits():
    play, *_ = make_play()
    for layout in ("Keyboard", "Drums", "Chord"):
        assert play.layout.name == layout
        for _ in range(12):
            play.button_pressed(c.BUTTON_OCTAVE_UP)
        colors = play.button_colors()
        assert colors[c.BUTTON_OCTAVE_UP] == "dark_gray"
        assert colors[c.BUTTON_OCTAVE_DOWN] == "white"
        for _ in range(12):
            play.button_pressed(c.BUTTON_OCTAVE_DOWN)
        colors = play.button_colors()
        assert colors[c.BUTTON_OCTAVE_UP] == "white"
        assert colors[c.BUTTON_OCTAVE_DOWN] == "dark_gray"
        play.button_pressed(c.BUTTON_LAYOUT)


def test_details_show_state_not_settings():
    play, *_ = make_play()
    panel = play.view()["panel"]
    assert panel["layout"] == "Keyboard"
    assert status_parts(panel) == []  # in key, Pushtoo Out, no Accent: nothing to say
    play.keyboard.in_key = False
    play.button_pressed(c.BUTTON_ACCENT)
    play.layout.destination = "USB MIDI:USB MIDI MIDI 1"
    assert status_parts(play.view()["panel"]) == ["Chromatic", "Accent", "→ USB MIDI MIDI 1"]
    play.button_pressed(c.BUTTON_LAYOUT)
    play.button_pressed(c.BUTTON_LAYOUT)
    play.button_pressed(c.BUTTON_ACCENT)
    assert status_parts(play.view()["panel"]) == ["C Minor"]
    play.button_pressed(c.BUTTON_OCTAVE_UP)
    play.button_pressed("Upper Row 2")  # Style page: Strum
    assert status_parts(play.view()["panel"]) == ["C Minor", "Oct 4", "Strum the strip"]


def test_holding_layout_picks_a_layout_with_the_upper_buttons(env):
    app, _ = env()
    app.button_pressed(c.BUTTON_LAYOUT)  # a tap still moves to the next layout
    assert app.play.layout.name == "Drums"
    view = app.view()
    assert view["overlay"]["title"] == "Layout"
    assert [item["label"] for item in view["upper"][:3]] == ["Keyboard", "Drums", "Chord"]
    assert view["upper"][1]["selected"]
    app.button_pressed("Upper Row 3")
    assert app.play.layout.name == "Chord"
    app.button_released(c.BUTTON_LAYOUT)
    assert "overlay" not in app.view()
    assert app.play.layout.name == "Chord"


def test_layout_picker_works_from_knobs_mode(env):
    app, _ = env()
    app.button_pressed(c.BUTTON_DEVICE)
    app.button_pressed(c.BUTTON_LAYOUT)
    app.button_pressed("Upper Row 1")
    app.button_released(c.BUTTON_LAYOUT)
    assert app.mode is app.knobs and app.play.layout.name == "Keyboard"
