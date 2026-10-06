"""Scales and the Play mode keyboard layout. Pure logic, no I/O."""

from dataclasses import dataclass
from enum import Enum

NOTE_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
FLAT_NAMES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
SHARP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# Ordered as shown in the scale list; intervals are semitones above the root.
# In the order the scale selector lists them: the modes, then the other 7-note scales,
# the 5- and 6-note scales, the 8-note bebop scales, and the symmetric scales.
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
    "Harmonic Major": (0, 2, 4, 5, 7, 8, 11),
    "Phrygian Dominant": (0, 1, 4, 5, 7, 8, 10),
    "Lydian Dominant": (0, 2, 4, 6, 7, 9, 10),
    "Altered": (0, 1, 3, 4, 6, 8, 10),
    "Hungarian Minor": (0, 2, 3, 6, 7, 8, 11),
    "Double Harmonic": (0, 1, 4, 5, 7, 8, 11),
    "Major Pentatonic": (0, 2, 4, 7, 9),
    "Minor Pentatonic": (0, 3, 5, 7, 10),
    "Blues": (0, 3, 5, 6, 7, 10),
    "Major Blues": (0, 2, 3, 4, 7, 9),
    "Egyptian": (0, 2, 5, 7, 10),
    "Hirajoshi": (0, 2, 3, 7, 8),
    "In-Sen": (0, 1, 5, 7, 10),
    "Iwato": (0, 1, 5, 6, 10),
    "Pelog": (0, 1, 3, 7, 8),
    "Bebop Dominant": (0, 2, 4, 5, 7, 9, 10, 11),
    "Bebop Major": (0, 2, 4, 5, 7, 8, 9, 11),
    "Whole Tone": (0, 2, 4, 6, 8, 10),
    "Diminished HW": (0, 1, 3, 4, 6, 7, 9, 10),  # half step, then whole
    "Diminished WH": (0, 2, 3, 5, 6, 8, 9, 11),  # whole step, then half
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


def note_name(midi_note: int, names: tuple[str, ...] = NOTE_NAMES) -> str:
    return f"{names[midi_note % 12]}{midi_note // 12 - 1}"


def spelling(root: int, intervals: tuple[int, ...]) -> tuple[str, ...]:
    """Note names that suit a key: flats in keys with Bb and no F#, sharps in keys
    with F# and no Bb, otherwise the common mix (C#, Eb, F#, Ab, Bb)."""
    pcs = {(root + i) % 12 for i in intervals}
    if 10 in pcs and 6 not in pcs:
        return FLAT_NAMES
    if 6 in pcs and 10 not in pcs:
        return SHARP_NAMES
    return NOTE_NAMES


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


# General MIDI percussion names (channel 10), shortened to fit a screen column.
GM_DRUM_NAMES: dict[int, str] = {
    35: "Kick 2", 36: "Kick", 37: "Side Stick", 38: "Snare", 39: "Clap", 40: "Snare 2",
    41: "Low Tom 2", 42: "Closed Hat", 43: "Low Tom", 44: "Pedal Hat", 45: "Mid Tom 2",
    46: "Open Hat", 47: "Mid Tom", 48: "High Tom 2", 49: "Crash", 50: "High Tom",
    51: "Ride", 52: "China", 53: "Ride Bell", 54: "Tambourine", 55: "Splash",
    56: "Cowbell", 57: "Crash 2", 58: "Vibraslap", 59: "Ride 2", 60: "Hi Bongo",
    61: "Low Bongo", 62: "Mute Conga", 63: "Open Conga", 64: "Low Conga",
    65: "High Timbale", 66: "Low Timbale", 67: "High Agogo", 68: "Low Agogo",
    69: "Cabasa", 70: "Maracas", 71: "Short Whistle", 72: "Long Whistle",
    73: "Short Guiro", 74: "Long Guiro", 75: "Claves", 76: "Hi Wood Block",
    77: "Low Wood Block", 78: "Mute Cuica", 79: "Open Cuica", 80: "Mute Triangle",
    81: "Open Triangle",
}  # fmt: skip

BANK_SIZE = 16
DRUM_LOWEST_START, DRUM_HIGHEST_START = 0, 127 - 4 * BANK_SIZE + 1


def drum_name(midi_note: int) -> str:
    return GM_DRUM_NAMES.get(midi_note, note_name(midi_note))


@dataclass
class DrumLayout:
    """Four 4x4 banks of 16 consecutive notes: bottom-left, bottom-right, top-left,
    top-right. With the default start of 36, the bottom-left bank is the GM kit."""

    start: int = 36

    @staticmethod
    def bank_of(row: int, col: int) -> int:
        return (row // 4) * 2 + col // 4

    def note_at(self, row: int, col: int) -> int | None:
        note = self.start + self.bank_of(row, col) * BANK_SIZE + (row % 4) * 4 + col % 4
        return note if 0 <= note <= 127 else None

    def shift_bank(self, delta: int) -> None:
        """Octave buttons move the grid one bank of 16 at a time."""
        self.start = max(DRUM_LOWEST_START, min(DRUM_HIGHEST_START, self.start + delta * BANK_SIZE))


# A profile's starting pad feel; Setup takes over once used (pushtoo/setup.py).
VELOCITY_CURVES = ("Linear", "Soft", "Hard")
