"""Scales and the Play mode keyboard layout. Pure logic, no I/O."""

from dataclasses import dataclass
from enum import Enum

NOTE_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")

# Ordered as shown in the scale list; intervals are semitones above the root.
SCALES: dict[str, tuple[int, ...]] = {
    "Major": (0, 2, 4, 5, 7, 9, 11),
    "Minor": (0, 2, 3, 5, 7, 8, 10),
    "Dorian": (0, 2, 3, 5, 7, 9, 10),
    "Mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "Lydian": (0, 2, 4, 6, 7, 9, 11),
    "Phrygian": (0, 1, 3, 5, 7, 8, 10),
    "Locrian": (0, 1, 3, 5, 6, 8, 10),
    "Harmonic Minor": (0, 2, 3, 5, 7, 8, 11),
    "Melodic Minor": (0, 2, 3, 5, 7, 9, 11),
    "Major Pentatonic": (0, 2, 4, 7, 9),
    "Minor Pentatonic": (0, 3, 5, 7, 10),
    "Blues": (0, 3, 5, 6, 7, 10),
    "Whole Tone": (0, 2, 4, 6, 8, 10),
}
SCALE_NAMES = tuple(SCALES)

ROWS = COLS = 8
# Each row up is a fourth: 5 semitones chromatic, or the scale degree closest to a fourth.
CHROMATIC_ROW_STEP = 5
MIN_OCTAVE, MAX_OCTAVE = -1, 7


class PadRole(Enum):
    ROOT = "root"
    IN_SCALE = "in_scale"
    OUT_OF_SCALE = "out_of_scale"


def note_name(midi_note: int) -> str:
    return f"{NOTE_NAMES[midi_note % 12]}{midi_note // 12 - 1}"


@dataclass
class KeyboardLayout:
    """Maps pads to MIDI notes. Row 0 is the bottom row, column 0 the left."""

    root: int = 0  # pitch class, 0 = C
    scale: str = "Minor"
    octave: int = 3  # octave of the bottom-left pad; C3 = MIDI 48
    in_key: bool = True

    @property
    def intervals(self) -> tuple[int, ...]:
        return SCALES[self.scale]

    @property
    def base_note(self) -> int:
        return 12 * (self.octave + 1) + self.root

    def row_step_degrees(self) -> int:
        """Scale degrees per row: the degree count that spans a fourth (3 in a 7-note scale)."""
        for degree, interval in enumerate(self.intervals):
            if interval >= CHROMATIC_ROW_STEP:
                return degree
        return len(self.intervals) // 2

    def note_at(self, row: int, col: int) -> int | None:
        """MIDI note for a pad, or None if it falls outside 0..127."""
        if self.in_key:
            degree = row * self.row_step_degrees() + col
            octaves, index = divmod(degree, len(self.intervals))
            note = self.base_note + 12 * octaves + self.intervals[index]
        else:
            note = self.base_note + row * CHROMATIC_ROW_STEP + col
        return note if 0 <= note <= 127 else None

    def role_of(self, midi_note: int) -> PadRole:
        relative = (midi_note - self.root) % 12
        if relative == 0:
            return PadRole.ROOT
        if relative in self.intervals:
            return PadRole.IN_SCALE
        return PadRole.OUT_OF_SCALE

    def shift_octave(self, delta: int) -> None:
        self.octave = max(MIN_OCTAVE, min(MAX_OCTAVE, self.octave + delta))

    def step_scale(self, delta: int) -> None:
        index = SCALE_NAMES.index(self.scale)
        self.scale = SCALE_NAMES[max(0, min(len(SCALE_NAMES) - 1, index + delta))]

    def step_root(self, delta: int) -> None:
        self.root = (self.root + delta) % 12

    @property
    def key_name(self) -> str:
        return f"{NOTE_NAMES[self.root]} {self.scale}"
