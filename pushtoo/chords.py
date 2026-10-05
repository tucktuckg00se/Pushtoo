"""Chord theory for the chord grid (PRD: Chord layout). Pure logic, no I/O.

Columns are the steps of the key (I to VII, then I an octave up); rows are chord
flavors built on those steps, so every pad is a complete chord that fits the key,
apart from the two "spice" rows at the top. A progression is a hand shape: I-V-vi-IV
is the same four pads in every key.
"""

from dataclasses import dataclass

from pushtoo.music import NOTE_NAMES, SCALES, KeyboardLayout, spelling

# Rows, bottom to top. Row 0 is single bass notes rather than chords.
ROW_KINDS = ("bass", "triad", "seventh", "add9", "sus", "ninth", "borrowed", "secondary")
# Scale steps stacked in thirds for each diatonic kind (0 = the column's step). The
# add9 and ninth rows take their color tone from color_step(): the 9th, or the 11th
# where the scale's 9th is a harsh flat 9th.
STEPS = {
    "triad": (0, 2, 4),
    "seventh": (0, 2, 4, 6),
}
# Harmony needs a 7-note scale; these borrow their parent's.
PARENT_SCALES = {"Major Pentatonic": "Major", "Minor Pentatonic": "Minor", "Blues": "Minor"}
ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII")

# Chord names by pitch-class set above the root. Anything else is shown as its notes.
SUFFIXES: dict[tuple[int, ...], str] = {
    (0, 4, 7): "",
    (0, 3, 7): "m",
    (0, 3, 6): "dim",
    (0, 4, 8): "aug",
    (0, 5, 7): "sus4",
    (0, 2, 7): "sus2",
    (0, 4, 7, 10): "7",
    (0, 4, 7, 11): "maj7",
    (0, 3, 7, 10): "m7",
    (0, 3, 7, 11): "m(maj7)",
    (0, 3, 6, 10): "m7b5",
    (0, 3, 6, 9): "dim7",
    (0, 4, 8, 11): "maj7#5",
    (0, 4, 8, 10): "7#5",
    (0, 2, 4, 7): "add9",
    (0, 2, 3, 7): "m(add9)",
    (0, 1, 3, 6): "dim(addb9)",
    (0, 1, 3, 7): "m(addb9)",
    (0, 2, 4, 8): "aug(add9)",
    (0, 2, 4, 7, 11): "maj9",
    (0, 2, 3, 7, 10): "m9",
    (0, 2, 4, 7, 10): "9",
    (0, 2, 3, 7, 11): "m(maj9)",
    (0, 1, 3, 7, 10): "m7(b9)",
    (0, 2, 3, 6, 10): "m9b5",
    (0, 1, 3, 6, 10): "m7b5(b9)",
    (0, 1, 4, 7, 10): "7(b9)",
    (0, 2, 4, 8, 11): "maj9#5",
    (0, 3, 5, 7): "m(add11)",
    (0, 3, 5, 6): "dim(add11)",
    (0, 4, 5, 7): "add11",
    (0, 3, 5, 7, 10): "m11",
    (0, 3, 5, 6, 10): "m11b5",
    (0, 3, 5, 6, 9): "dim7(add11)",
    (0, 4, 5, 7, 10): "7(add11)",
    (0, 5, 6): "sus4b5",
}


def parent_scale(key: KeyboardLayout) -> tuple[int, ...]:
    """The scale chords are built from: the key's own, or its 7-note parent."""
    return SCALES[PARENT_SCALES.get(key.scale, key.scale)]


def uses_parent(key: KeyboardLayout) -> bool:
    return key.scale in PARENT_SCALES


def _stack(scale: tuple[int, ...], degree: int, steps: tuple[int, ...]) -> tuple[int, ...]:
    """Intervals above the degree's root of the given scale steps above it."""
    root = scale[degree % len(scale)] + 12 * (degree // len(scale))
    out = []
    for step in steps:
        octaves, index = divmod(degree + step, len(scale))
        out.append(scale[index] + 12 * octaves - root)
    return tuple(out)


def color_step(scale: tuple[int, ...], degree: int) -> int:
    """The scale step to add for color: the 9th (step 8), unless it is a flat 9th a
    semitone above the root's octave, which sounds harsh; then the 11th (step 10)."""
    ninth = _stack(scale, degree, (0, 8))[1]
    return 8 if ninth % 12 != 1 else 10


def degree_root(key: KeyboardLayout, degree: int) -> int:
    """Semitones from the key's root to this step's root (the octave column is +12)."""
    scale = parent_scale(key)
    return scale[degree % len(scale)] + 12 * (degree // len(scale))


@dataclass(frozen=True)
class Chord:
    root: int  # semitones above the key's root, may exceed 12
    intervals: tuple[int, ...]  # above the chord's root, lowest first
    kind: str
    degree: int
    target: int | None = None  # for secondary dominants: the degree it resolves to

    def pitch_class(self, key: KeyboardLayout) -> int:
        return (key.root + self.root) % 12


def chord_at(key: KeyboardLayout, kind: str, degree: int) -> Chord:
    scale = parent_scale(key)
    root = degree_root(key, degree)
    if kind in STEPS:
        return Chord(root, _stack(scale, degree, STEPS[kind]), kind, degree)
    if kind in ("add9", "ninth"):
        base = (0, 2, 4) if kind == "add9" else (0, 2, 4, 6)
        return Chord(root, _stack(scale, degree, (*base, color_step(scale, degree))), kind, degree)
    if kind == "sus":
        # sus4 where the 4th and 5th are in key, else sus2; on steps without a perfect
        # 5th, the scale's own 4th and 5th, so the pad stays in key.
        pcs = {s % 12 for s in scale}
        rel = scale[degree % len(scale)]
        if (rel + 5) % 12 in pcs and (rel + 7) % 12 in pcs:
            intervals: tuple[int, ...] = (0, 5, 7)
        elif (rel + 2) % 12 in pcs and (rel + 7) % 12 in pcs:
            intervals = (0, 2, 7)
        else:
            intervals = _stack(scale, degree, (0, 3, 4))
        return Chord(root, intervals, kind, degree)
    if kind == "borrowed":
        # The same step of the parallel scale: minor's in a major key, major's in minor.
        parallel = SCALES["Minor"] if 4 in scale else SCALES["Major"]
        prel = parallel[degree % 7] + 12 * (degree // 7)
        return Chord(prel, _stack(parallel, degree, STEPS["triad"]), kind, degree)
    if kind == "secondary":
        # V7 of this column's chord: a dominant 7th a fifth above it.
        return Chord(root + 7, (0, 4, 7, 10), kind, degree, target=degree)
    raise ValueError(f"no chord kind {kind!r}")


def numeral(key: KeyboardLayout, degree: int) -> str:
    """Roman numeral of the triad on this step: IV, vi, vii°."""
    third, fifth = _stack(parent_scale(key), degree, STEPS["triad"])[1:]
    base = ROMAN[degree % 7]
    if third == 3:
        base = base.lower()
    if fifth == 6:
        return base + "°"
    if fifth == 8:
        return base + "+"
    return base


def role(chord: Chord, key: KeyboardLayout) -> str:
    """What a chord does, for colors and the screen: home, away, tension, borrowed, or
    the step a secondary dominant pulls toward."""
    if chord.kind == "borrowed":
        return "borrowed"
    if chord.kind == "secondary":
        return f"→ {numeral(key, chord.target)}"
    return {0: "home", 2: "home", 5: "home", 1: "away", 3: "away"}.get(chord.degree % 7, "tension")


def chord_name(
    root_pc: int, intervals: tuple[int, ...], names: tuple[str, ...] = NOTE_NAMES
) -> str:
    """Plain name such as "Dm7"; chords without a common name show their notes, never a
    wrong name."""
    shape = tuple(sorted({i % 12 for i in intervals}))
    if shape in SUFFIXES:
        return f"{names[root_pc]}{SUFFIXES[shape]}"
    return " ".join(names[(root_pc + i) % 12] for i in intervals)


def key_spelling(key: KeyboardLayout) -> tuple[str, ...]:
    return spelling(key.root, parent_scale(key))


def fits_key(root_pc: int, intervals: tuple[int, ...], key: KeyboardLayout) -> bool:
    return all((root_pc + i - key.root) % 12 in parent_scale(key) for i in intervals)


# Voicings


def close(root_note: int, intervals: tuple[int, ...]) -> list[int]:
    return sorted(root_note + i for i in intervals)


def invert(notes: list[int], times: int) -> list[int]:
    """Lift the lowest note an octave, `times` times."""
    notes = sorted(notes)
    for _ in range(times):
        notes = sorted([*notes[1:], notes[0] + 12])
    return notes


def drop2(notes: list[int]) -> list[int]:
    """Open voicing: the second-highest note drops an octave."""
    notes = sorted(notes)
    if len(notes) < 3:
        return notes
    return sorted([*notes[:-2], notes[-2] - 12, notes[-1]])


def wide(notes: list[int]) -> list[int]:
    """Root an octave down, the third an octave up: root, fifth, tenth and beyond."""
    notes = sorted(notes)
    if len(notes) < 3:
        return notes
    return sorted([notes[0] - 12, *notes[2:], notes[1] + 12])


def _movement(previous: list[int], candidate: list[int]) -> int:
    """How far the hand moves: each note to its nearest neighbor in the other chord."""
    there = sum(min(abs(n - p) for p in previous) for n in candidate)
    back = sum(min(abs(p - n) for n in candidate) for p in previous)
    return there + back


def smooth(previous: list[int] | None, notes: list[int], register: int) -> list[int]:
    """The inversion and octave of `notes` that moves least from `previous`, with its
    lowest note kept near `register` so progressions don't drift up or down."""
    notes = sorted(notes)
    if not previous:
        return notes
    candidates = []
    for times in range(len(notes)):
        voiced = invert(notes, times)
        for shift in (-12, 0, 12):
            candidate = [n + shift for n in voiced]
            if register - 7 <= candidate[0] <= register + 7:
                candidates.append(candidate)
    if not candidates:
        return notes
    return min(candidates, key=lambda c: (_movement(previous, c), abs(c[0] - register)))


VOICINGS = ("Smooth", "Root", "1st", "2nd", "3rd", "Open", "Wide")
VOICING_NAMES = {
    "Smooth": "Smooth",
    "Root": "Root position",
    "1st": "1st inversion",
    "2nd": "2nd inversion",
    "3rd": "3rd inversion",
    "Open": "Open (drop 2)",
    "Wide": "Wide",
}


def apply_voicing(
    voicing: str, notes: list[int], previous: list[int] | None, register: int
) -> list[int]:
    if voicing == "Smooth":
        voiced = smooth(previous, notes, register)
    elif voicing == "Open":
        voiced = drop2(notes)
    elif voicing == "Wide":
        voiced = wide(notes)
    else:
        voiced = invert(notes, VOICINGS.index(voicing) - 1)
    return [n for n in voiced if 0 <= n <= 127]
