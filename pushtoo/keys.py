"""Keystrokes to the focused window through Linux uinput (PRD F16).

uinput works under both X11 and Wayland. Keys are physical key positions, so on a
non-QWERTY layout "z" is the key where Z sits on QWERTY. Keystrokes are sent on a
worker thread so a slow uinput write can never delay pads.
"""

import logging
import queue
import threading
import time
from collections.abc import Callable

from evdev import ecodes

log = logging.getLogger(__name__)

MODIFIERS = {
    "ctrl": ecodes.KEY_LEFTCTRL,
    "control": ecodes.KEY_LEFTCTRL,
    "shift": ecodes.KEY_LEFTSHIFT,
    "alt": ecodes.KEY_LEFTALT,
    "super": ecodes.KEY_LEFTMETA,
    "meta": ecodes.KEY_LEFTMETA,
}
NAMED_KEYS = {
    "space": ecodes.KEY_SPACE,
    "enter": ecodes.KEY_ENTER,
    "return": ecodes.KEY_ENTER,
    "tab": ecodes.KEY_TAB,
    "esc": ecodes.KEY_ESC,
    "escape": ecodes.KEY_ESC,
    "backspace": ecodes.KEY_BACKSPACE,
    "delete": ecodes.KEY_DELETE,
    "home": ecodes.KEY_HOME,
    "end": ecodes.KEY_END,
    "left": ecodes.KEY_LEFT,
    "right": ecodes.KEY_RIGHT,
    "up": ecodes.KEY_UP,
    "down": ecodes.KEY_DOWN,
}
# Time for the compositor to notice a new virtual keyboard before its first keystroke.
DEVICE_SETTLE_SECONDS = 0.5
KEY_HOLD_SECONDS = 0.01


def parse_keys(spec: str) -> list[int]:
    """'ctrl+shift+z' -> [KEY_LEFTCTRL, KEY_LEFTSHIFT, KEY_Z]. Raises ValueError."""
    codes = []
    for part in (p.strip().lower() for p in spec.split("+")):
        if part in MODIFIERS:
            codes.append(MODIFIERS[part])
        elif part in NAMED_KEYS:
            codes.append(NAMED_KEYS[part])
        elif len(part) == 1 and part.isalnum():
            codes.append(getattr(ecodes, f"KEY_{part.upper()}"))
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 12:
            codes.append(getattr(ecodes, f"KEY_{part.upper()}"))
        else:
            raise ValueError(f"unknown key {part!r} in {spec!r}")
    if not codes or all(code in MODIFIERS.values() for code in codes):
        raise ValueError(f"{spec!r} needs a key besides modifiers")
    return codes


def describe(spec: str) -> str:
    """'ctrl+shift+z' -> 'Ctrl+Shift+Z' for toasts."""
    return "+".join(part.strip().capitalize() for part in spec.split("+"))


class KeySender:
    """Owns one virtual keyboard and types key combos on a worker thread."""

    def __init__(self, on_error: Callable[[str], None]) -> None:
        self._on_error = on_error
        self._queue: queue.Queue[list[int] | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="pushtoo-keys", daemon=True)
        self._thread.start()

    def send(self, spec: str) -> bool:
        try:
            codes = parse_keys(spec)
        except ValueError as error:
            self._on_error(str(error))
            return False
        self._queue.put(codes)
        return True

    def _run(self) -> None:
        try:
            from evdev import UInput

            device = UInput(name="Pushtoo keys")
            time.sleep(DEVICE_SETTLE_SECONDS)
        except Exception as error:  # usually no permission on /dev/uinput
            log.warning("Keystrokes unavailable: %s", error)
            device = None
        while (codes := self._queue.get()) is not None:
            if device is None:
                self._on_error("Keystrokes need /dev/uinput access: see packaging/udev")
                continue
            # Presses and releases in separate frames, or some compositors drop the combo.
            for code in codes:
                device.write(ecodes.EV_KEY, code, 1)
            device.syn()
            time.sleep(KEY_HOLD_SECONDS)
            for code in reversed(codes):
                device.write(ecodes.EV_KEY, code, 0)
            device.syn()
        if device is not None:
            device.close()

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join(2)
