import pushtoo
from pushtoo.__main__ import main


def test_version_is_set():
    assert pushtoo.__version__


def test_main_runs():
    assert main() == 0
