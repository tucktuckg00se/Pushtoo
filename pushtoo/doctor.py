"""`pushtoo doctor`: what's working, and the one-line fix for what isn't.

Read-only: it looks, it never changes anything, and it doesn't open the Push, so it's
safe to run while Pushtoo is playing.
"""

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pushtoo import __version__, instance
from pushtoo.fonts import FONT_DIR

PUSH_VENDOR, PUSH_PRODUCT = "2982", "1967"
USB_DEVICES = Path("/sys/bus/usb/devices")
UDEV_HINT = "install the udev rule: re-run the installer, or see README › Install"


@dataclass
class Check:
    name: str
    state: str  # "ok", "warn" (playable, with a limit) or "fail" (can't play)
    detail: str


def _python() -> Check:
    ok = sys.version_info >= (3, 12)
    return Check(
        "Python",
        "ok" if ok else "fail",
        f"{sys.version.split()[0]}" + ("" if ok else ", needs 3.12+"),
    )


def _font(font_dir: Path = FONT_DIR) -> Check:
    found = sorted(p.name for p in font_dir.glob("*.ttf"))
    if len(found) == 2:
        return Check("Screen font", "ok", "IBM Plex Sans Condensed (bundled)")
    return Check("Screen font", "warn", "bundled font missing; the screen uses a fallback")


def _sequencer(path: str = "/dev/snd/seq") -> Check:
    if os.access(path, os.R_OK | os.W_OK):
        return Check("MIDI (ALSA sequencer)", "ok", path)
    return Check(
        "MIDI (ALSA sequencer)",
        "fail",
        f"can't open {path}: is snd-seq loaded? (sudo modprobe snd-seq)",
    )


def _push_usb(devices: Path = USB_DEVICES) -> Check:
    """The Push's USB device, and whether this user may open it (the display needs it)."""
    for device in devices.glob("*"):
        try:
            vendor = (device / "idVendor").read_text().strip()
            product = (device / "idProduct").read_text().strip()
        except OSError:
            continue
        if (vendor, product) != (PUSH_VENDOR, PUSH_PRODUCT):
            continue
        bus = int((device / "busnum").read_text())
        dev = int((device / "devnum").read_text())
        node = f"/dev/bus/usb/{bus:03d}/{dev:03d}"
        if os.access(node, os.R_OK | os.W_OK):
            return Check("Push 2", "ok", f"plugged in, display accessible ({node})")
        return Check("Push 2", "fail", f"plugged in, but the display isn't accessible: {UDEV_HINT}")
    return Check("Push 2", "warn", "not plugged in (Pushtoo waits for it)")


def _uinput(path: str = "/dev/uinput") -> Check:
    if os.access(path, os.W_OK):
        return Check("Undo keystrokes", "ok", path)
    return Check("Undo keystrokes", "warn", f"{path} not writable, so Undo can't type: {UDEV_HINT}")


def _systemctl(*args: str) -> str:
    if shutil.which("systemctl") is None:
        return ""
    result = subprocess.run(
        ["systemctl", "--user", *args, "pushtoo"], capture_output=True, text=True
    )
    return result.stdout.strip()


def _service(query: Callable[..., str] = _systemctl) -> Check:
    enabled, active = query("is-enabled"), query("is-active")
    if not enabled or enabled == "not-found":
        return Check("Background service", "ok", "not installed (start Pushtoo by hand)")
    return Check("Background service", "ok", f"{enabled}, {active}")


def _running(lock_path: Path | None = None) -> Check:
    lock = instance.acquire(lock_path)
    if lock is None:
        return Check("Pushtoo", "ok", "running")
    lock.close()
    return Check("Pushtoo", "ok", "not running")


def checks() -> list[Check]:
    return [_python(), _font(), _sequencer(), _push_usb(), _uinput(), _service(), _running()]


def report(results: list[Check]) -> str:
    marks = {"ok": "✓", "warn": "!", "fail": "✗"}
    lines = [f"Pushtoo {__version__}"]
    lines += [f"  {marks[c.state]} {c.name}: {c.detail}" for c in results]
    return "\n".join(lines)


def main() -> int:
    results = checks()
    print(report(results))
    return 1 if any(c.state == "fail" for c in results) else 0
