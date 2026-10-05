import importlib.util
from pathlib import Path

import pytest

from pushtoo.render.screens import HEIGHT, WIDTH

TOOL = Path(__file__).parent.parent / "tools" / "render_preview.py"


@pytest.fixture(scope="module")
def preview():
    spec = importlib.util.spec_from_file_location("render_preview", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_sample_view_renders(preview):
    views = preview.sample_views()
    assert {"keyboard_first_run", "drums", "scale_selector", "peek_velocity"} <= set(views)
    for view in views.values():
        surface = preview.render(view)
        assert (surface.get_width(), surface.get_height()) == (WIDTH, HEIGHT)


def test_contact_sheet_is_written(preview, tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["render_preview", str(tmp_path)])
    preview.main()
    assert (tmp_path / "contact_sheet.png").stat().st_size > 0
