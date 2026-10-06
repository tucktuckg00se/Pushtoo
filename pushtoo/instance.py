"""One Pushtoo at a time. Two would fight over the Push and the "Pushtoo" MIDI ports,
which happens easily when the background service is running and you also start it by
hand."""

import fcntl
import os
from pathlib import Path
from typing import IO


def lock_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return Path(runtime) / "pushtoo.lock"
    return Path("/tmp") / f"pushtoo-{os.getuid()}.lock"


def acquire(path: Path | None = None) -> IO | None:
    """The lock, held for as long as the returned file stays open, or None if another
    Pushtoo already holds it. The kernel drops it when the process ends, crash or not."""
    path = path or lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle
