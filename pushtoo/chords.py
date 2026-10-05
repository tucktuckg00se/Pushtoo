"""Chord theory for the Chord layout (PRD: Chord layout). Pure logic, no I/O.

Roots are placed relative to the key: the bottom row walks the scale from the home
note, and the row above holds the out-of-key notes in the gaps, like black keys. The
six rows above that are chord type (across) by voicing (up): each row up raises the
lowest chord tone an octave, so higher rows sound brighter.
"""

from dataclasses import dataclass

from pushtoo.music import NOTE_NAMES, KeyboardLayout

CHORD_TYPES = ("Auto", "Maj", "Min", "7", "Maj7", "m7", "Sus4", "Dim")
INTERVALS: dict[str, tuple[int, ...]] = {
    "Maj": (0, 4, 7),
    "Min": (0, 3, 7),
    "7": (0, 4, 7, 10),
    "Maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "Sus4": (0, 5, 7),
    "Dim": (0, 3, 6),
}
# How a chord's intervals are written after the root name.
SUFFIXES: dict[tuple[int, ...], str] = {
    (0, 4, 7): "",
    (0, 3, 7): "m",
    (0, 4, 7, 10): "7",
    (0, 4, 7, 11): "maj7",
    (0, 3, 7, 10): "m7",
    (0, 5, 7): "sus4",
    (0, 3, 6): "dim",
    (0, 4, 8): "aug",
    (0, 2, 7): "sus2",
}
# Side buttons, top four: (label, semitones above the root).
EXTENSIONS = (("+6", 9), ("+9", 14), ("+11", 17), ("+13", 21))
INVERSION_NAMES = ("Root position", "1st inversion", "2nd inversion", "3rd inversion")
ROOT_ROWS = 2  # rows 0 (in-key) and 1 (out-of-key)
VOICING_ROWS = 6


def auto_intervals(root_pc: int, key: KeyboardLayout) -> tuple[int, ...]:
    """The chord that fits the key on this root: the scale's triad built on it
    (scale steps 1-3-5 from there), or major for roots outside the scale."""
    scale = key.intervals
    relative = (root_pc - key.root) % 12
    if relative not in scale:
        return INTERVALS["Maj"]
    degree = scale.index(relative)
    tones = []
    for step in (0, 2, 4):
        octaves, index = divmod(degree + step, len(scale))
        tones.append(scale[index] + 12 * octaves - relative)
    return tuple(tones)


def intervals_for(chord_type: str, root_pc: int, key: KeyboardLayout) -> tuple[int, ...]:
    return auto_intervals(root_pc, key) if chord_type == "Auto" else INTERVALS[chord_type]


def fits_key(root_pc: int, intervals: tuple[int, ...], key: KeyboardLayout) -> bool:
    return all((root_pc + i - key.root) % 12 in key.intervals for i in intervals)


def voice(
    root_note: int, intervals: tuple[int, ...], inversion: int, extensions: tuple[int, ...] = ()
) -> list[int]:
    """MIDI notes, lowest first. Each inversion step lifts the lowest tone an octave."""
    notes = sorted(root_note + i for i in intervals)
    for _ in range(inversion):
        notes = sorted([*notes[1:], notes[0] + 12])
    notes += [root_note + semitones for semitones in extensions]
    return sorted(n for n in set(notes) if 0 <= n <= 127)


def chord_name(root_pc: int, intervals: tuple[int, ...], extension_labels=()) -> str:
    suffix = SUFFIXES.get(tuple(sorted(i % 12 for i in intervals)), "")
    name = f"{NOTE_NAMES[root_pc]}{suffix}"
    if extension_labels:
        name += " (" + ", ".join(label.lstrip("+") for label in extension_labels) + ")"
    return name


def inversion_name(inversion: int) -> str:
    if inversion < len(INVERSION_NAMES):
        return INVERSION_NAMES[inversion]
    return f"Voicing {inversion + 1}"


@dataclass(frozen=True)
class RootPad:
    note: int  # MIDI note of the root, in the layout's octave
    in_key: bool
    home: bool


def root_at(row: int, col: int, key: KeyboardLayout, octave: int) -> RootPad | None:
    """Row 0: home note, then the scale upward for 8 pads (one octave for 7-note
    scales). Row 1: above each in-key root of the first octave, the out-of-key note a
    semitone up, if any; past the octave it would only repeat, so those pads stay dark."""
    base = 12 * (octave + 1) + key.root
    scale = key.intervals
    octaves, index = divmod(col, len(scale))
    in_key_note = base + 12 * octaves + scale[index]
    if row == 0:
        return RootPad(in_key_note, in_key=True, home=scale[index] == 0)
    if row == 1 and octaves == 0:
        sharp = in_key_note + 1
        if (sharp - base) % 12 not in scale:
            return RootPad(sharp, in_key=False, home=False)
    return None


def grid_at(row: int, col: int) -> tuple[str, int] | None:
    """(chord type, inversion) for a pad in the six rows above the roots."""
    if ROOT_ROWS <= row < ROOT_ROWS + VOICING_ROWS:
        return CHORD_TYPES[col], row - ROOT_ROWS
    return None
