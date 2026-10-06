"""Loading, validating and watching profiles (PRD F5).

Profiles are the user's files: Pushtoo reads and hot-reloads them but never writes
them. A broken edit produces one readable error and the last good profile stays in
use.
"""

import logging
import os
import shutil
import threading
from collections.abc import Callable
from importlib import resources
from pathlib import Path

import yaml
from pydantic import ValidationError

from pushtoo.profiles.schema import Profile

POLL_SECONDS = 1.0
SUFFIXES = (".yaml", ".yml")

log = logging.getLogger(__name__)


class ProfileError(Exception):
    """A profile that can't be used, with a message short enough for a toast."""


def default_config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "pushtoo" / "profiles"


def line_of(root: yaml.Node | None, loc: tuple) -> int | None:
    """1-based line of the YAML node at a pydantic error location, if it exists."""
    node = root
    for key in loc:
        if isinstance(node, yaml.MappingNode):
            node = next((v for k, v in node.value if k.value == key), None)
        elif isinstance(node, yaml.SequenceNode) and isinstance(key, int):
            node = node.value[key] if key < len(node.value) else None
        else:
            break
        if node is None:
            break
    return node.start_mark.line + 1 if node is not None else None


def _format_loc(loc: tuple) -> str:
    out = ""
    for key in loc:
        out += f"[{key}]" if isinstance(key, int) else (f".{key}" if out else str(key))
    return out


def parse(text: str, source: str = "profile") -> Profile:
    try:
        data = yaml.safe_load(text) or {}
        root = yaml.compose(text)
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f" line {mark.line + 1}" if mark else ""
        raise ProfileError(f"{source}{where}: not valid YAML") from error
    if not isinstance(data, dict):
        raise ProfileError(f"{source}: expected a mapping at the top level")
    try:
        return Profile.model_validate(data)
    except ValidationError as error:
        first = error.errors()[0]
        loc = tuple(k for k in first["loc"] if not isinstance(k, str) or not k[0].isupper())
        line = line_of(root, loc)
        where = f" line {line}" if line else ""
        count = error.error_count()
        more = f" (+{count - 1} more)" if count > 1 else ""
        message = first["msg"].removeprefix("Value error, ")
        raise ProfileError(f"{source}{where}: {_format_loc(loc)}: {message}{more}") from error


def load(path: Path) -> Profile:
    try:
        text = path.read_text()
    except OSError as error:
        raise ProfileError(f"{path.name}: {error.strerror}") from error
    return parse(text, path.name)


def ensure_default(config_dir: Path) -> Path:
    """Create the config folder and the commented default profile on first run."""
    config_dir.mkdir(parents=True, exist_ok=True)
    target = config_dir / "default.yaml"
    if not target.exists():
        with resources.as_file(resources.files("pushtoo.profiles") / "default.yaml") as src:
            shutil.copyfile(src, target)
    return target


class ProfileStore:
    """The profile folder, the active profile, and a watcher that reloads it on save."""

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        ensure_default(config_dir)
        self.path = config_dir / "default.yaml"
        self.profile = Profile()
        self._mtime: float | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def paths(self) -> list[Path]:
        return sorted(p for p in self.config_dir.iterdir() if p.suffix in SUFFIXES)

    def select(self, path: Path) -> Profile:
        """Load and activate a profile. Raises ProfileError and keeps the current one."""
        profile = load(path)
        self.path, self.profile = path, profile
        self._mtime = self._stat(path)
        return profile

    @staticmethod
    def _stat(path: Path) -> float | None:
        try:
            return path.stat().st_mtime
        except OSError:
            return None

    def poll(self) -> Profile | ProfileError | None:
        """Reload if the active file changed: the new profile, an error, or None."""
        mtime = self._stat(self.path)
        if mtime is None or mtime == self._mtime:
            return None
        self._mtime = mtime
        try:
            self.profile = load(self.path)
        except ProfileError as error:
            return error
        return self.profile

    def watch(self, on_change: Callable[[Profile | ProfileError], None]) -> None:
        def run() -> None:
            while not self._stop.wait(POLL_SECONDS):
                result = self.poll()
                if result is not None:
                    on_change(result)

        self._thread = threading.Thread(target=run, name="pushtoo-profiles", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
