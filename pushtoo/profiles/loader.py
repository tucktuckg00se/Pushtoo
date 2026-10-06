"""Loading, validating and watching profiles (PRD F5).

Profiles are the user's files: Pushtoo reads and hot-reloads them but never writes
them. A broken edit produces one readable error and the last good profile stays in
use.

The profile editor (`pushtoo edit`) leaves your file alone too: what you change there
goes in `<name>-user.yaml` beside it, which overrides it key by key. Maps merge; a
list (knob pages, a page's controls) is replaced whole.
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
USER_SUFFIX = "-user"  # foo.yaml's edits from the profile editor: foo-user.yaml

log = logging.getLogger(__name__)


class ProfileError(Exception):
    """A profile that can't be used, with a message short enough for a toast."""


def default_config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "pushtoo" / "profiles"


def override_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}{USER_SUFFIX}{path.suffix}")


def is_override(path: Path) -> bool:
    return path.stem.endswith(USER_SUFFIX)


def merge(base: object, override: object) -> object:
    """`override` over `base`: maps merge key by key, anything else is replaced."""
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, value in override.items():
            merged[key] = merge(base.get(key), value) if key in base else value
        return merged
    return override


def _depth(root: yaml.Node | None, loc: tuple) -> int:
    """How many keys of a location a YAML document has."""
    node, depth = root, 0
    for key in loc:
        if isinstance(node, yaml.MappingNode):
            node = next((v for k, v in node.value if k.value == key), None)
        elif isinstance(node, yaml.SequenceNode) and isinstance(key, int):
            node = node.value[key] if key < len(node.value) else None
        else:
            node = None
        if node is None:
            break
        depth += 1
    return depth


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


def _yaml_loc(root: yaml.Node | None, loc: tuple) -> tuple:
    """The parts of a pydantic error location that are in the YAML: keys and indexes,
    without the type names pydantic adds for unions (but keeping a user's own key,
    such as a chord set called "Bad")."""
    kept: list = []
    node = root
    for key in loc:
        if isinstance(node, yaml.MappingNode):
            child = next((v for k, v in node.value if k.value == key), None)
        elif isinstance(node, yaml.SequenceNode) and isinstance(key, int):
            child = node.value[key] if key < len(node.value) else None
        else:
            child = None
        if child is not None:
            kept.append(key)
            node = child
        elif not (isinstance(key, str) and key[:1].isupper()):
            kept.append(key)  # not in the YAML (say, a missing field): still worth naming
    return tuple(kept)


def _format_loc(loc: tuple) -> str:
    out = ""
    for key in loc:
        out += f"[{key}]" if isinstance(key, int) else (f".{key}" if out else str(key))
    return out


def _read(text: str, source: str) -> tuple[dict, yaml.Node | None]:
    try:
        data = yaml.safe_load(text) or {}
        root = yaml.compose(text)
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f" line {mark.line + 1}" if mark else ""
        raise ProfileError(f"{source}{where}: not valid YAML") from error
    if not isinstance(data, dict):
        raise ProfileError(f"{source}: expected a mapping at the top level")
    return data, root


def parse(
    text: str,
    source: str = "profile",
    override: str | None = None,
    override_source: str = "edits",
) -> Profile:
    """A profile from YAML text, with the editor's override text over it if given.
    Errors name the file and line the bad value came from."""
    data, root = _read(text, source)
    if override is not None:
        edits, edits_root = _read(override, override_source)
        data = merge(data, edits)  # type: ignore[assignment]
    try:
        return Profile.model_validate(data)
    except ValidationError as error:
        first = error.errors()[0]
        if override is not None:
            # The edits win where they reach as deep as the file does.
            reach = _depth(edits_root, first["loc"])
            if reach and reach >= _depth(root, first["loc"]):
                source, root = override_source, edits_root
        loc = _yaml_loc(root, first["loc"])
        line = line_of(root, loc)
        where = f" line {line}" if line else ""
        count = error.error_count()
        more = f" (+{count - 1} more)" if count > 1 else ""
        message = first["msg"].removeprefix("Value error, ")
        raise ProfileError(f"{source}{where}: {_format_loc(loc)}: {message}{more}") from error


def _text(path: Path) -> str:
    try:
        return path.read_text()
    except OSError as error:
        raise ProfileError(f"{path.name}: {error.strerror}") from error


def load(path: Path) -> Profile:
    """A profile file, with its editor overrides (`<name>-user.yaml`) if there are any."""
    edits = override_path(path)
    if not edits.exists():
        return parse(_text(path), path.name)
    return parse(_text(path), path.name, _text(edits), edits.name)


def ensure_default(config_dir: Path) -> Path:
    """Create the config folder and the commented default profile on first run."""
    config_dir.mkdir(parents=True, exist_ok=True)
    target = config_dir / "default.yaml"
    if not target.exists():
        with resources.as_file(resources.files("pushtoo.profiles") / "default.yaml") as src:
            shutil.copyfile(src, target)
    return target


def profile_paths(config_dir: Path) -> list[Path]:
    """The profiles in a folder: YAML files, not counting editor overrides."""
    return sorted(p for p in config_dir.iterdir() if p.suffix in SUFFIXES and not is_override(p))


class ProfileStore:
    """The profile folder, the active profile, and a watcher that reloads it on save."""

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        ensure_default(config_dir)
        self.path = config_dir / "default.yaml"
        self.profile = Profile()
        self._mtime: tuple[float | None, float | None] | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def paths(self) -> list[Path]:
        return profile_paths(self.config_dir)

    def select(self, path: Path) -> Profile:
        """Load and activate a profile. Raises ProfileError and keeps the current one."""
        profile = load(path)
        self.path, self.profile = path, profile
        self._mtime = self._stat(path)
        return profile

    @staticmethod
    def _stat(path: Path) -> tuple[float | None, float | None] | None:
        """The profile's modification time and its overrides'; None if it's gone."""

        def mtime(p: Path) -> float | None:
            try:
                return p.stat().st_mtime
            except OSError:
                return None

        base = mtime(path)
        return None if base is None else (base, mtime(override_path(path)))

    def poll(self) -> Profile | ProfileError | None:
        """Reload if the active file or its overrides changed: the new profile, an
        error, or None."""
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
