"""Session state: where you left off, per profile (PRD principle 5, "Never lose your place").

Kept apart from profiles so Pushtoo never rewrites a file the user edits. Saving is
debounced on a background thread, so pad callbacks never touch the disk (ADR 0001).
"""

import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path

import yaml

SAVE_DELAY = 1.0  # seconds after the last change

log = logging.getLogger(__name__)


def default_state_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "pushtoo" / "state.yaml"


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict = {}
        try:
            loaded = yaml.safe_load(path.read_text())
            self.data = loaded if isinstance(loaded, dict) else {}
        except FileNotFoundError:
            pass
        except (OSError, yaml.YAMLError):
            log.warning("Ignoring unreadable state file %s", path, exc_info=True)

    def for_profile(self, name: str) -> dict:
        return self.data.get("profiles", {}).get(name, {})

    @property
    def last_profile(self) -> str | None:
        return self.data.get("last_profile")

    def update(self, profile_file: str, profile_name: str, snapshot: dict) -> None:
        self.data["last_profile"] = profile_file
        self.data.setdefault("profiles", {})[profile_name] = snapshot

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(yaml.safe_dump(self.data, sort_keys=False))
        tmp.replace(self.path)  # atomic, so a crash never leaves half a file


class StateSaver:
    """Saves a snapshot SAVE_DELAY seconds after the last mark_dirty()."""

    def __init__(self, store: StateStore, snapshot: Callable[[], tuple[str, str, dict]]) -> None:
        self.store = store
        self._snapshot = snapshot
        self._dirty = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="pushtoo-state", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def mark_dirty(self) -> None:
        self._dirty.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._dirty.wait()
            # Debounce: wait until changes stop for SAVE_DELAY.
            while self._dirty.is_set() and not self._stop.is_set():
                self._dirty.clear()
                self._stop.wait(SAVE_DELAY)
            self.flush()

    def flush(self) -> None:
        try:
            self.store.update(*self._snapshot())
            self.store.save()
        except Exception:
            log.warning("Could not save session state", exc_info=True)

    def stop(self) -> None:
        self._stop.set()
        self._dirty.set()
        self._thread.join(2)
        self.flush()
