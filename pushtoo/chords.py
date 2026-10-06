"""Chord theory for the chord grid (PRD: Chord layout). Pure logic, no I/O.

Columns are the steps of the key (I to VII, then I an octave up); rows are chord
flavors built on those steps, so every pad is a complete chord that fits the key,
apart from the two "spice" rows at the top. A progression is a hand shape: I-V-vi-IV
is the same four pads in every key.
"""

from dataclasses import dataclass

from pushtoo.music import NOTE_NAMES, SCALES, KeyboardLayout, spelling

# Every kind of chord a row can hold, with its pad-map label. Rows are built on each
# column's step of the key; all but the borrowed and leading kinds stay in key.
KIND_LABELS = {
    "bass": "Bass",
    "triad": "Triad",
    "seventh": "7th",
    "add9": "add9",
    "sus": "sus",
    "ninth": "9th",
    "sus2": "sus2",
    "sus4": "sus4",
    "sixth": "6th",
    "six_nine": "6/9",
    "eleventh": "11th",
    "thirteenth": "13th",
    "add11": "add11",
    "power": "Power",
    "quartal": "Quartal",
    "borrowed": "Borrowed",
    "borrowed_dorian": "Dorian",
    "borrowed_mixolydian": "Mixolyd.",
    "borrowed_phrygian": "Phrygian",
    "borrowed_lydian": "Lydian",
    "dominant": "Dom 7",
    "augmented": "Aug",
    "secondary": "V7 of",
    "secondary_dim": "vii°7 of",
    "secondary_ii": "ii of",
    "tritone_sub": "Tri sub",
}
ROW_CHORD_KINDS = tuple(k for k in KIND_LABELS if k != "bass")
# The same step of another scale on the same root: "borrowed" means the parallel
# major or minor; the others name their mode.
BORROWED_KINDS = {
    "borrowed": None,
    "borrowed_dorian": "Dorian",
    "borrowed_mixolydian": "Mixolydian",
    "borrowed_phrygian": "Phrygian",
    "borrowed_lydian": "Lydian",
}
# Chords that pull to a column: V7 of it, the ii7 before that V7, the V7's tritone
# substitute, and the diminished 7th a half step below it.
LEADING_KINDS = ("secondary", "secondary_ii", "tritone_sub", "secondary_dim")
# Deliberately outside the key on every step: a blues dominant 7th, an augmented triad.
COLOR_KINDS = ("dominant", "augmented")

# Chord sets: the seven rows above the bass row, bottom to top. Scales choose the
# notes you have; a set chooses which flavors fill the grid.
# Grouped by style: pop and rock, blues and jazz, soul, then the atmospheric ones.
CHORD_SETS: dict[str, tuple[str, ...]] = {
    "Classic": ("triad", "seventh", "add9", "sus", "ninth", "borrowed", "secondary"),
    "Pop": ("triad", "sus2", "sus4", "add9", "sixth", "borrowed", "secondary"),
    "Anthem": ("triad", "power", "sus4", "add9", "sus2", "borrowed", "secondary"),
    "Rock": ("power", "triad", "sus4", "add9", "seventh", "borrowed", "secondary"),
    "Blues": ("power", "triad", "dominant", "ninth", "thirteenth", "borrowed", "secondary"),
    "Jazz": ("seventh", "six_nine", "ninth", "eleventh", "thirteenth", "secondary_ii",
             "tritone_sub"),
    "Bossa": ("seventh", "ninth", "six_nine", "thirteenth", "secondary_ii", "secondary",
              "tritone_sub"),
    "Gospel": ("seventh", "ninth", "six_nine", "secondary_dim", "secondary", "tritone_sub",
               "borrowed"),
    "Neo-soul": ("seventh", "ninth", "eleventh", "add9", "quartal", "borrowed", "secondary"),
    "Lo-fi": ("seventh", "ninth", "add9", "eleventh", "sus2", "borrowed", "secondary"),
    "Cinematic": ("triad", "power", "sus2", "add9", "quartal", "borrowed",
                  "borrowed_phrygian"),
    "Ambient": ("sus2", "add9", "add11", "quartal", "power", "borrowed_lydian", "borrowed"),
    "Dark": ("triad", "seventh", "borrowed_phrygian", "secondary_dim", "augmented", "power",
             "secondary"),
    "Modal": ("triad", "quartal", "sus2", "sus4", "borrowed_dorian", "borrowed_mixolydian",
              "borrowed_phrygian"),
}  # fmt: skip
# The Chord page's upper buttons, unless a profile picks its own: seven, since the
# eighth column belongs to the side buttons' rail.
FAVORITE_SLOTS = 7
DEFAULT_FAVORITE_SETS = ("Classic", "Pop", "Rock", "Jazz", "Neo-soul", "Lo-fi", "Cinematic")
SET_ROWS = 7
# Rows, bottom to top, of the default set. Row 0 is single bass notes, not chords.
ROW_KINDS = ("bass", *CHORD_SETS["Classic"])
# Scale steps stacked above the column's step (0) for the stacked kinds: thirds for
# triads and sevenths, the 6th for sixths, upper extensions without the notes that
# crowd them, and fourths for quartal chords. add9 and ninth take their color tone
# from color_step(): the 9th, or the 11th where the scale's 9th is a harsh flat 9th.
STEPS = {
    "triad": (0, 2, 4),
    "seventh": (0, 2, 4, 6),
    "sixth": (0, 2, 4, 5),
    "six_nine": (0, 2, 4, 5, 8),
    "eleventh": (0, 2, 4, 6, 10),
    "thirteenth": (0, 2, 4, 6, 12),
    "add11": (0, 2, 4, 10),
    "quartal": (0, 3, 6, 9),
}
# Harmony needs a 7-note scale; the others borrow the 7-note scale that contains them.
PARENT_SCALES = {
    "Major Pentatonic": "Major",
    "Minor Pentatonic": "Minor",
    "Egyptian": "Minor",
    "Hirajoshi": "Minor",
    "In-Sen": "Phrygian",
    "Iwato": "Locrian",
    "Pelog": "Phrygian",
    # These hold a passing or blue note no 7-note scale shares, or are symmetric;
    # their chords come from the nearest one, and the screen says which.
    "Blues": "Minor",
    "Major Blues": "Major",
    "Bebop Dominant": "Mixolydian",
    "Bebop Major": "Major",
    "Whole Tone": "Lydian Dominant",
    "Diminished HW": "Altered",
    "Diminished WH": "Harmonic Minor",
}
APPROXIMATE_PARENTS = {
    "Blues", "Major Blues", "Bebop Dominant", "Bebop Major",
    "Whole Tone", "Diminished HW", "Diminished WH",
}  # fmt: skip
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
    (0, 4, 7, 9): "6",
    (0, 3, 7, 9): "m6",
    (0, 2, 4, 7, 9): "6/9",
    (0, 2, 3, 7, 9): "m6/9",
    (0, 7): "5",
    (0, 4, 5, 7, 11): "maj7(add11)",
    (0, 4, 7, 9, 10): "13",
    (0, 3, 7, 9, 10): "m13",
    (0, 4, 7, 9, 11): "maj13",
    (0, 2, 5, 7, 10): "9sus4",
    (0, 2, 5, 7, 11): "maj9sus4",
    (0, 4, 6, 7): "add#11",
    (0, 4, 6, 7, 11): "maj7#11",
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


def _sus(scale: tuple[int, ...], degree: int, prefer: tuple[int, ...]) -> tuple[int, ...]:
    """A sus chord that stays in key: the preferred shape (sus4 (0, 5, 7) or sus2
    (0, 2, 7)), else the other, else the scale's own 2nd or 4th and 5th."""
    pcs = {s % 12 for s in scale}
    rel = scale[degree % len(scale)]
    other = (0, 2, 7) if prefer == (0, 5, 7) else (0, 5, 7)
    for shape in (prefer, other):
        if all((rel + i) % 12 in pcs for i in shape):
            return shape
    return _stack(scale, degree, (0, 3, 4))  # the scale's own 4th and 5th


def _extended_steps(scale: tuple[int, ...], degree: int, kind: str) -> tuple[int, ...]:
    """Sixths and upper extensions, swapping a tone that would rub for the one players
    use instead: a minor 6th becomes the 7th (Em7, not E G B C), a natural 11 over a
    major third becomes the pop 11 (9sus4: G C D F A), a minor 13th becomes the 11th."""

    def interval(step: int) -> int:
        return _stack(scale, degree, (0, step))[1] % 12

    major_third = interval(2) == 4
    if kind in ("sixth", "six_nine"):
        sixth = 5 if interval(5) == 9 else 6
        return (0, 2, 4, sixth) if kind == "sixth" else (0, 2, 4, sixth, color_step(scale, degree))
    if kind == "eleventh":
        return (0, 3, 4, 6, 8) if major_third and interval(10) == 5 else STEPS["eleventh"]
    return STEPS["eleventh"] if interval(12) == 8 else STEPS["thirteenth"]  # thirteenth


def chord_at(key: KeyboardLayout, kind: str, degree: int) -> Chord:
    scale = parent_scale(key)
    root = degree_root(key, degree)
    if kind in ("sixth", "six_nine", "eleventh", "thirteenth"):
        return Chord(
            root, _stack(scale, degree, _extended_steps(scale, degree, kind)), kind, degree
        )
    if kind in STEPS:
        return Chord(root, _stack(scale, degree, STEPS[kind]), kind, degree)
    if kind in ("add9", "ninth"):
        base = (0, 2, 4) if kind == "add9" else (0, 2, 4, 6)
        return Chord(root, _stack(scale, degree, (*base, color_step(scale, degree))), kind, degree)
    if kind in ("sus", "sus4"):
        # sus4 where the 4th and 5th are in key, else sus2; on steps without a perfect
        # 5th, the scale's own 4th and 5th, so the pad stays in key.
        return Chord(root, _sus(scale, degree, (0, 5, 7)), kind, degree)
    if kind == "sus2":
        return Chord(root, _sus(scale, degree, (0, 2, 7)), kind, degree)
    if kind == "power":
        fifth = _stack(scale, degree, (0, 4))[1]  # the key's own fifth on this step
        return Chord(root, (0, fifth, 12), kind, degree)
    if kind in BORROWED_KINDS:
        # The same step of another scale on the key's root: the parallel minor in a
        # major key (major in minor), or the named mode.
        mode = BORROWED_KINDS[kind]
        if mode is None:
            other = SCALES["Minor"] if 4 in scale else SCALES["Major"]
        else:
            other = SCALES[mode]
        prel = other[degree % 7] + 12 * (degree // 7)
        return Chord(prel, _stack(other, degree, STEPS["triad"]), kind, degree)
    if kind == "secondary":
        # V7 of this column's chord: a dominant 7th a fifth above it.
        return Chord(root + 7, (0, 4, 7, 10), kind, degree, target=degree)
    if kind == "secondary_ii":
        # The ii7 that leads into that V7: minor 7th a step above the column, or
        # half-diminished when the column's chord is minor (ii-V-i).
        minor = _stack(scale, degree, STEPS["triad"])[1] == 3
        shape = (0, 3, 6, 10) if minor else (0, 3, 7, 10)
        return Chord(root + 2, shape, kind, degree, target=degree)
    if kind == "secondary_dim":
        # vii°7 of this column: a diminished 7th a half step below it, leading in.
        return Chord(root - 1, (0, 3, 6, 9), kind, degree, target=degree)
    if kind == "dominant":
        # A dominant 7th on every step, the blues way, whatever the key says.
        return Chord(root, (0, 4, 7, 10), kind, degree)
    if kind == "augmented":
        return Chord(root, (0, 4, 8), kind, degree)
    if kind == "tritone_sub":
        # The V7 a tritone away from V7/x: a dominant 7th a half step above the column.
        return Chord(root + 1, (0, 4, 7, 10), kind, degree, target=degree)
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


def _quality_numeral(base: str, intervals: tuple[int, ...]) -> str:
    """Upper case for major, lower for minor, ° for diminished, + for augmented."""
    third = min((i for i in intervals if i in (3, 4)), default=4)
    fifth = 6 if 6 in intervals and 7 not in intervals else 8 if 8 in intervals else 7
    numeral_text = base.lower() if third == 3 else base
    return numeral_text + {6: "°", 8: "+"}.get(fifth, "")


def numeral_label(chord: Chord, key: KeyboardLayout) -> str:
    """Roman numeral for the screen: "V7", "ii", "bVII", "V7/vi"."""
    if chord.kind in LEADING_KINDS:
        target = chord.target or 0
        prefix = {
            "secondary": "V7",
            "secondary_ii": _ii_label(chord),
            "tritone_sub": "subV7",
            "secondary_dim": "vii°7",
        }
        label = prefix[chord.kind]
        return label if target % 7 == 0 else f"{label}/{numeral(key, target)}"
    if chord.kind == "dominant":
        return ROMAN[chord.degree % 7] + "7"
    if chord.kind == "augmented":
        return ROMAN[chord.degree % 7] + "+"
    if chord.kind in BORROWED_KINDS:
        own_root = degree_root(key, chord.degree)
        accidental = {-1: "b", 1: "#"}.get(chord.root - own_root, "")
        return accidental + _quality_numeral(ROMAN[chord.degree % 7], chord.intervals)
    return _diatonic_label(numeral(key, chord.degree), chord)


def _ii_label(chord: Chord) -> str:
    return "iiø7" if 6 in chord.intervals else "ii7"


def _diatonic_label(base: str, chord: Chord) -> str:
    """Numeral plus the suffix theory books use: Imaj7, ii7, V7, viiø7, IVadd9, Vsus4."""
    pcs = {i % 12 for i in chord.intervals}
    plain = ROMAN[chord.degree % 7]  # for chords with no third: no major/minor case
    if chord.kind == "triad":
        return base
    if chord.kind in ("sus", "sus2", "sus4"):
        return plain + ("sus4" if 5 in pcs else "sus2" if 2 in pcs else "sus")
    if chord.kind == "add9":
        return base + ("add9" if 2 in pcs else "add11")
    if chord.kind == "add11":
        return base + ("add#11" if 6 in pcs and 5 not in pcs else "add11")
    if chord.kind == "power":
        return plain + "5"
    if chord.kind == "quartal":
        return plain + " quartal"
    if chord.kind in ("sixth", "six_nine") and 9 in pcs:
        return base.rstrip("°+") + ("6/9" if chord.kind == "six_nine" else "6")
    if chord.kind == "eleventh" and 4 not in pcs and 3 not in pcs:
        return plain + "11"  # the pop 11, 9sus4: no third to give it a case
    # The top of the stack, read from the notes the chord actually has, since rows
    # swap tones that would rub (a sixth row's iii is a iii7).
    if 9 in pcs and chord.kind == "thirteenth":
        top = "13"
    elif 6 in pcs and 4 in pcs and chord.kind in ("eleventh", "thirteenth"):
        top = "7#11"
    elif 5 in pcs and chord.kind in ("ninth", "eleventh", "thirteenth", "six_nine"):
        top = "11"
    elif 2 in pcs and chord.kind != "seventh":
        top = "9"
    else:
        top = "7"
    if 11 in pcs:
        return base.rstrip("°") + "maj" + top
    if base.endswith("°") and 10 in pcs:
        return base[:-1] + "ø" + top  # half-diminished
    return base + top


def role(chord: Chord, key: KeyboardLayout) -> str:
    """What a chord does, for colors and the screen: home, away, tension, borrowed, or
    the step a secondary dominant pulls toward."""
    if chord.kind in BORROWED_KINDS or chord.kind == "augmented":
        return "borrowed"
    if chord.kind in LEADING_KINDS:
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


def drop3(notes: list[int]) -> list[int]:
    """The third-highest note drops an octave; triads, with no third-highest worth
    dropping, take drop 2 instead."""
    notes = sorted(notes)
    if len(notes) < 4:
        return drop2(notes)
    return sorted([*notes[:-3], notes[-3] - 12, *notes[-2:]])


def shell(notes: list[int], root: int) -> list[int]:
    """Root, 3rd and 7th (or 6th): the jazz-piano left hand. Chords without a third or
    a 7th or 6th (triads, sus, power, quartal) stay as they are."""
    notes = sorted(notes)
    degree = {n: (n - root) % 12 for n in notes}
    third = next((n for n in notes if degree[n] in (3, 4)), None)
    top = next((n for n in notes if degree[n] in (10, 11, 9)), None)
    if third is None or top is None:
        return notes
    return sorted({min(notes), third, top})


def _movement(previous: list[int], candidate: list[int]) -> int:
    """How far the hand moves: each note to its nearest neighbor in the other chord."""
    there = sum(min(abs(n - p) for p in previous) for n in candidate)
    back = sum(min(abs(p - n) for n in candidate) for p in previous)
    return there + back


def smooth(previous: list[int] | None, notes: list[int], register: int) -> list[int]:
    """The inversion and octave of `notes` that moves least from `previous`, with its
    lowest note kept near `register` so progressions don't drift up or down."""
    notes = sorted(notes)
    candidates = []
    for times in range(len(notes)):
        voiced = invert(notes, times)
        for shift in (-12, 0, 12):
            candidate = [n + shift for n in voiced]
            if register - 7 <= candidate[0] <= register + 7:
                candidates.append(candidate)
    if not candidates:
        return notes
    if not previous:  # the first chord: the shape sitting nearest the register
        return min(candidates, key=lambda c: (abs(c[0] - register), c[0]))
    return min(candidates, key=lambda c: (_movement(previous, c), abs(c[0] - register)))


VOICINGS = ("Smooth", "Root", "1st", "2nd", "3rd", "Open", "Drop 3", "Wide", "Shell")
# The seven side buttons are shortcuts to these unless a profile picks its own; the
# Voicing encoder on the Chord page reaches every voicing.
DEFAULT_VOICING_BUTTONS = ("Smooth", "Root", "1st", "2nd", "Open", "Drop 3", "Shell")
VOICING_NAMES = {
    "Smooth": "Smooth",
    "Root": "Root position",
    "1st": "1st inversion",
    "2nd": "2nd inversion",
    "3rd": "3rd inversion",
    "Open": "Open (drop 2)",
    "Drop 3": "Drop 3",
    "Wide": "Wide",
    "Shell": "Shell",
}


def apply_voicing(
    voicing: str, notes: list[int], previous: list[int] | None, register: int
) -> list[int]:
    if voicing == "Smooth":
        voiced = smooth(previous, notes, register)
    elif voicing == "Open":
        voiced = drop2(notes)
    elif voicing == "Drop 3":
        voiced = drop3(notes)
    elif voicing == "Shell":
        voiced = shell(notes, register)
    elif voicing == "Wide":
        voiced = wide(notes)
    else:
        voiced = invert(notes, VOICINGS.index(voicing) - 1)
    return [n for n in voiced if 0 <= n <= 127]
