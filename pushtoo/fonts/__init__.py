"""The screen font, IBM Plex Sans Condensed (SIL Open Font License, LICENSES/OFL-IBM-Plex.txt),
shipped with Pushtoo so the screen looks the same on every machine.

Nothing is installed: fontconfig is pointed at a small config that adds this folder to
the system's fonts, before cairo first draws text.
"""

import os
from pathlib import Path
from xml.sax.saxutils import escape

FONT_DIR = Path(__file__).parent
FAMILY = "IBM Plex Sans Condensed"
SYSTEM_CONFIG = "/etc/fonts/fonts.conf"


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "pushtoo"


def config_text(include_system: bool = True, system: str = SYSTEM_CONFIG) -> str:
    cache = _cache_dir() / "fontconfig"
    include = f'<include ignore_missing="yes">{escape(system)}</include>' if include_system else ""
    return (
        '<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n'
        f"<fontconfig>{include}<dir>{escape(str(FONT_DIR))}</dir>"
        f"<cachedir>{escape(str(cache))}</cachedir></fontconfig>\n"
    )


def use_bundled_fonts() -> Path:
    """Write the config (if it changed) and point FONTCONFIG_FILE at it. Call before any
    text is drawn; child processes inherit it."""
    current = os.environ.get("FONTCONFIG_FILE")
    path = _cache_dir() / "fonts.conf"
    if current == str(path):
        return path
    text = config_text(system=current or SYSTEM_CONFIG)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text() != text:
        path.write_text(text)
    os.environ["FONTCONFIG_FILE"] = str(path)
    return path
