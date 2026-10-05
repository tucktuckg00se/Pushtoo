import pytest

import pushtoo
from pushtoo.__main__ import main


def test_version_is_set():
    assert pushtoo.__version__


def test_version_flag(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["pushtoo", "--version"])
    with pytest.raises(SystemExit) as exit_info:
        main()
    assert exit_info.value.code == 0
    assert pushtoo.__version__ in capsys.readouterr().out
