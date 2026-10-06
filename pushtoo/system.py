"""Facts about the machine Pushtoo runs on."""

from pathlib import Path

MODEL_FILE = Path("/proc/device-tree/model")
DEFAULT_FPS, LOW_POWER_FPS = 60, 30


def is_raspberry_pi(model_file: Path = MODEL_FILE) -> bool:
    try:
        return "Raspberry Pi" in model_file.read_text(errors="ignore")
    except OSError:
        return False


def default_fps(model_file: Path = MODEL_FILE) -> int:
    """30 frames a second on a Raspberry Pi (PRD N5: reduced frame rate), 60 elsewhere."""
    return LOW_POWER_FPS if is_raspberry_pi(model_file) else DEFAULT_FPS
