import importlib.util
from pathlib import Path

import pytest

TOOL = Path(__file__).parent.parent / "tools" / "docs_graphics.py"


@pytest.fixture(scope="module")
def graphics():
    spec = importlib.util.spec_from_file_location("docs_graphics", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_drawing_and_screen_is_written(graphics, tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["docs_graphics", str(tmp_path)])
    graphics.main()
    for scene in graphics.SCENES:
        assert (tmp_path / "images" / "push" / f"{scene}.svg").stat().st_size > 0
    for name in graphics.SCREENS:
        assert (tmp_path / "images" / "screens" / f"{name}.png").stat().st_size > 0


def test_led_colors_resolve(graphics):
    assert graphics.led_rgb("black") is None
    assert graphics.led_rgb("pt_play") == pytest.approx((0x82 / 255, 0xC9 / 255, 0x1E / 255))
    with pytest.raises(ValueError):
        graphics.led_rgb("chartreuse")
