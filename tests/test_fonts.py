"""The screen font ships with Pushtoo and needs nothing installed."""

import os
import shutil
import subprocess

import pytest

from pushtoo.fonts import FAMILY, FONT_DIR, config_text, use_bundled_fonts


def test_both_weights_ship_with_the_package():
    names = {p.name for p in FONT_DIR.glob("*.ttf")}
    assert names == {"IBMPlexSansCondensed-Regular.ttf", "IBMPlexSansCondensed-Bold.ttf"}


@pytest.mark.skipif(shutil.which("fc-match") is None, reason="fontconfig tools missing")
@pytest.mark.parametrize("weight", ["regular", "bold"])
def test_fontconfig_finds_the_bundled_font_with_no_system_fonts(tmp_path, weight):
    conf = tmp_path / "fonts.conf"
    conf.write_text(config_text(include_system=False))
    env = os.environ | {"FONTCONFIG_FILE": str(conf), "XDG_CACHE_HOME": str(tmp_path)}
    found = subprocess.run(
        ["fc-match", "-f", "%{file}", f"{FAMILY}:{weight}"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert found.startswith(str(FONT_DIR))
    assert ("Bold" in found) == (weight == "bold")


def test_the_config_is_written_once_and_inherited(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.delenv("FONTCONFIG_FILE", raising=False)
    path = use_bundled_fonts()
    assert os.environ["FONTCONFIG_FILE"] == str(path)
    assert str(FONT_DIR) in path.read_text() and "/etc/fonts/fonts.conf" in path.read_text()
    assert use_bundled_fonts() == path  # idempotent
