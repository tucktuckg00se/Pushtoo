"""Loading and watching color themes (PRD: Visual design system).

Themes are YAML files of `token: RRGGBB` in the themes folder, next to profiles.
Values are read as plain strings, so a color like 212529 never becomes a number.
Like profiles, a broken edit produces one readable error and the last good theme
stays in use.
"""

import os
import shutil
import threading
from collections.abc import Callable
from importlib import resources
from pathlib import Path

import yaml

from pushtoo.profiles.loader import line_of
from pushtoo.theme import Theme, ThemeError, resolve

POLL_SECONDS = 1.0
DEFAULT_NAME = "oc"


class ThemeFileError(Exception):
    """A theme that can't be used, with a message short enough for a toast."""


def default_themes_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "pushtoo" / "themes"


def parse(text: str, source: str = "theme") -> Theme:
    try:
        data = yaml.load(text, Loader=yaml.BaseLoader) or {}
        root = yaml.compose(text)
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f" line {mark.line + 1}" if mark else ""
        raise ThemeFileError(f"{source}{where}: not valid YAML") from error
    if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
        raise ThemeFileError(f"{source}: expected lines of `color: RRGGBB`")
    data.pop("name", None)
    try:
        return resolve(data)
    except ThemeError as error:
        line = line_of(root, (error.key,)) if error.key in data else None
        where = f" line {line}" if line else ""
        raise ThemeFileError(f"{source}{where}: {error}") from error


def ensure_default(themes_dir: Path) -> None:
    """Create the themes folder and the commented Open Color theme on first run."""
    themes_dir.mkdir(parents=True, exist_ok=True)
    target = themes_dir / f"{DEFAULT_NAME}.yaml"
    if not target.exists():
        with resources.as_file(resources.files("pushtoo.themes") / "oc.yaml") as src:
            shutil.copyfile(src, target)


class ThemeStore:
    """The themes folder, the active theme's file, and a watcher that reloads it."""

    def __init__(self, themes_dir: Path) -> None:
        self.themes_dir = themes_dir
        ensure_default(themes_dir)
        self.path: Path | None = None
        self._mtime: float | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def select(self, name: str) -> Theme:
        """Load and watch a theme by file name. Raises ThemeFileError, after which
        the caller falls back to the built-in theme."""
        path = self.themes_dir / f"{name}.yaml"
        self.path, self._mtime = path, self._stat(path)
        if self._mtime is None:
            raise ThemeFileError(f"theme {name!r} not found in {self.themes_dir}")
        return parse(path.read_text(), path.name)

    @staticmethod
    def _stat(path: Path) -> float | None:
        try:
            return path.stat().st_mtime
        except OSError:
            return None

    def poll(self) -> Theme | ThemeFileError | None:
        """Reload if the active file changed: the new theme, an error, or None."""
        if self.path is None:
            return None
        mtime = self._stat(self.path)
        if mtime is None or mtime == self._mtime:
            return None
        self._mtime = mtime
        try:
            return parse(self.path.read_text(), self.path.name)
        except ThemeFileError as error:
            return error
        except OSError as error:
            return ThemeFileError(f"{self.path.name}: {error.strerror}")

    def watch(self, on_change: Callable[[Theme | ThemeFileError], None]) -> None:
        def run() -> None:
            while not self._stop.wait(POLL_SECONDS):
                result = self.poll()
                if result is not None:
                    on_change(result)

        self._thread = threading.Thread(target=run, name="pushtoo-themes", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
