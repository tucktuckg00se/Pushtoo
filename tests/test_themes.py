"""Color themes: Open Color by default, user files that override any token."""

import os

import cairo
import pytest
from push2_python import constants as c

from pushtoo.render.screens import HEIGHT, WIDTH, draw_view
from pushtoo.theme import DEFAULT_THEME, FIRST_SLOT, LED_COLORS, OPEN_COLOR, TOKENS
from pushtoo.themes.loader import ThemeFileError, parse


def test_open_color_is_the_default():
    assert DEFAULT_THEME["play"] == (0x82, 0xC9, 0x1E)  # INTERSECT oc's lime accent
    assert DEFAULT_THEME["background"] == (0, 0, 0)
    # The accent is only an accent: it stays off the pads.
    assert DEFAULT_THEME["root"] == DEFAULT_THEME["home"] != DEFAULT_THEME["play"]
    assert DEFAULT_THEME["held"] == (0xFF, 0xFF, 0xFF)


def test_packaged_file_matches_the_built_in_theme():
    from importlib import resources

    text = (resources.files("pushtoo.themes") / "oc.yaml").read_text()
    assert dict(parse(text)) == dict(DEFAULT_THEME)


def test_missing_keys_fall_back_and_references_follow():
    theme = parse("play: 112233\naway: teal")
    assert theme["play"] == (0x11, 0x22, 0x33)
    assert parse("root: 445566")["home"] == (0x44, 0x55, 0x66)
    assert theme["away"] == DEFAULT_THEME["teal"]
    assert theme["mix"] == DEFAULT_THEME["mix"]


def test_all_digit_colors_stay_colors():
    assert parse("track: 212529")["track"] == (0x21, 0x25, 0x29)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("name: x\nplay: lime", "t.yaml line 2: play: 'lime' is not RRGGBB"),
        ("\nbackgrund: 000000", "t.yaml line 2: unknown color 'backgrund'"),
        ("root: home", "t.yaml line 1: root → home → root goes round in a circle"),
        ("- 1", "t.yaml: expected lines of `color: RRGGBB`"),
    ],
)
def test_errors_name_the_line(text, message):
    with pytest.raises(ThemeFileError, match="^" + message.replace("(", r"\(")):
        parse(text, "t.yaml")


def test_every_led_token_has_its_own_slot_clear_of_named_defaults():
    slots = [slot for slot, _ in LED_COLORS.values()]
    assert len(set(slots)) == len(slots) and min(slots) == FIRST_SLOT
    assert {"pt_root", "pt_in_scale", "pt_out_of_scale", "pt_held"} <= set(LED_COLORS)
    assert set(OPEN_COLOR) == set(TOKENS)


def test_the_view_carries_the_theme_to_the_screen(env, tmp_path):
    app, _ = env()
    path = tmp_path / "themes" / "oc.yaml"
    path.write_text("background: 102030\n")  # an edit, as the watcher would see it
    os.utime(path, (1, 1))
    app._theme_changed(app.themes.poll())
    view = app.view()
    assert view["theme"]["background"] == (0x10, 0x20, 0x30)
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, WIDTH, HEIGHT)
    draw_view(cairo.Context(surface), view)
    b, g, r = surface.get_data()[WIDTH * 4 * 80 + 4 * 940 : WIDTH * 4 * 80 + 4 * 940 + 3]
    assert (r, g, b) == (0x10, 0x20, 0x30)  # a bare patch of background


def test_a_missing_theme_falls_back_with_a_toast(env, tmp_path):
    (tmp_path / "profiles").mkdir()
    app, _ = env("name: P\ntheme: nope\n")
    assert app.theme == DEFAULT_THEME
    assert "Theme error" in app.view()["toast"]


# Leaving Mix and Browse


def test_mix_button_closes_mix(env):
    app, _ = env()
    app.button_pressed(c.BUTTON_DEVICE)
    app.button_pressed(c.BUTTON_MIX)
    app.button_pressed(c.BUTTON_MIX)
    assert app.mode is app.knobs


def test_back_button_leaves_extras_and_names_where_it_goes(env):
    app, _ = env()
    app.button_pressed(c.BUTTON_MIX)
    assert app.view()["lower"][7]["label"] == "‹ Play"
    assert app.button_colors()["Lower Row 8"] == "white"
    app.button_pressed(c.BUTTON_BROWSE)  # Browse from Mix still returns to a core mode
    assert app.view()["lower"][7]["label"] == "‹ Play"
    app.button_pressed("Lower Row 8")
    assert app.mode is app.play
    assert app.view()["lower"][7] is None
