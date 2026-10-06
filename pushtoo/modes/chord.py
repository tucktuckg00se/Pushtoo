"""The chord grid's player (PRD: Chord layout).

Every pad above the bottom row is one complete chord: press it and it plays. The last
chord pressed is the one sounding, and every change re-triggers. The bottom row plays
single bass notes. The side buttons choose the voicing (tap one to keep it, hold one
to use it only while held); the bottom one is Latch, which keeps a chord sounding
after you let go.

With Strum on, a chord pad plays only its bass note and the touch strip strums the
chord across a few octaves, one note per tone crossed, like an Omnichord.
"""

import time
from collections.abc import Callable

from pushtoo.chords import (
    BORROWED_KINDS,
    CHORD_SETS,
    DEFAULT_FAVORITE_SETS,
    DEFAULT_VOICING_BUTTONS,
    KIND_LABELS,
    LEADING_KINDS,
    VOICING_NAMES,
    VOICINGS,
    Chord,
    apply_voicing,
    chord_at,
    chord_name,
    close,
    key_spelling,
    numeral,
    numeral_label,
    parent_scale,
    role,
    uses_parent,
)
from pushtoo.midi.router import MidiRouter
from pushtoo.music import ROWS, SCALES, KeyboardLayout, note_name
from pushtoo.rhythm.repeat import CHORD_TAG
from pushtoo.rhythm.timing import TimingSpread
from pushtoo.rhythm.velocity import VelocitySpread
from pushtoo.theme import accent_name, led
from pushtoo.ui.controls import COLUMNS

Pad = tuple[int, int]
BASS_ROW = 0
MAX_TONES = 8
NEW_TOUCH_GAP = 0.08  # seconds without strip messages that count as lifting the finger
HOLD_SECONDS = 0.3  # a voicing button held this long acts only while held
MIN_OCTAVE, MAX_OCTAVE = 1, 6
DEFAULT_OCTAVE = 3
# Side buttons, top to bottom: the voicings, then Latch. push2-python's map puts
# "1/32t" on CC 43, the top button, and "1/4" on CC 36, the bottom.
SCENE_BUTTONS = ("1/32t", "1/32", "1/16t", "1/16", "1/8t", "1/8", "1/4t", "1/4")
LATCH_BUTTON = 7  # the bottom side button; the seven above are voicing shortcuts
MIN_BRIGHTNESS, MAX_BRIGHTNESS = -6, 6  # semitones Smooth's register moves
OCTAVE_COLUMN = 7
ROLE_COLORS = {"home": led("home"), "away": led("away"), "tension": led("tension")}
# Side button states, shared by the screen's voicing rail and the button LEDs.
RAIL_LEDS = {
    "kept": led(accent_name("play")),
    "held": "white",
    "latch_on": led("latch"),
    "off": "dark_gray",
}


class ChordPlayer:
    def __init__(
        self,
        router: MidiRouter,
        key: KeyboardLayout,
        output: Callable[[], tuple[str, int]],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.router = router
        self.key = key
        # Set by PlayMode: while rhythm is on, a chord's notes go to the repeat or arp
        # engine instead of sounding held. hand_to_rhythm returns True if it took them.
        self.hand_to_rhythm: Callable[..., bool] = lambda *_: False
        self.take_from_rhythm: Callable[[], None] = lambda: None
        self.accent: Callable[[], bool] = lambda: False  # PlayMode's Accent button
        self.spread = VelocitySpread()  # the Velocity page
        self.sets: dict[str, tuple[str, ...]] = dict(CHORD_SETS)
        self.chord_set = "Classic"  # which flavors fill the rows
        self.voicing_buttons: tuple[str, ...] = DEFAULT_VOICING_BUTTONS
        self.favorite_sets: tuple[str, ...] = DEFAULT_FAVORITE_SETS  # the upper buttons
        self.brightness = 0  # semitones up or down for Smooth's register
        self.timing = TimingSpread()  # the Timing page
        self.last_velocities: list[int] = []  # what the sounding chord's notes got
        self._output = output  # (destination, chord channel) of the Chord layout
        self._clock = clock
        self.bass_channel = 2
        self.octave = DEFAULT_OCTAVE
        self.strum = False
        self.strum_octaves = 2
        self.mute_chords = False
        self.mute_bass = False
        self.voicing = "Smooth"  # latched
        self.momentary: str | None = None  # held voicing button, overriding the latch
        self._voicing_pressed: dict[str, float] = {}
        self.latch = False
        self.current: Pad | None = None  # the chord pad sounding
        self.current_held = False  # is that pad still pressed (vs latched)?
        self.velocity = 100
        self.notes: list[int] = []  # what the sounding (or last) chord played
        self.last_chord: Chord | None = None
        self.bass_pads: dict[Pad, int] = {}  # bass-row pads held, and their notes
        self._strum_index: int | None = None
        self._strum_time = 0.0
        self._strumming: set[int] = set()

    # Chords and voicing

    @property
    def active_voicing(self) -> str:
        return self.momentary or self.voicing

    def register(self) -> int:
        """MIDI note of the key's root in the chord octave."""
        return 12 * (self.octave + 1) + self.key.root

    def chord_for(self, pad: Pad) -> Chord | None:
        row, col = pad
        if row == BASS_ROW or not 0 <= row < len(self.rows):
            return None
        return chord_at(self.key, self.rows[row], col)

    @property
    def rows(self) -> tuple[str, ...]:
        """Bottom to top: the bass row, then the chord set's seven rows."""
        return ("bass", *self.sets[self.chord_set])

    def set_chord_set(self, name: str) -> None:
        """Choose a chord set; a sounding chord re-voices into it, like a key change."""
        if name in self.sets and name != self.chord_set:
            self.chord_set = name
            self.revoice()

    def apply_sets(self, custom: dict[str, tuple[str, ...]]) -> None:
        """The built-in sets, then a profile's own (which may reuse a built-in name)."""
        self.sets = dict(CHORD_SETS) | custom
        if self.chord_set not in self.sets:
            self.chord_set = "Classic"

    def _voiced(self, chord: Chord) -> list[int]:
        previous = self.notes or None
        if chord.degree == OCTAVE_COLUMN and self.active_voicing == "Smooth":
            # The right column is the "lift": the first column's chord as Smooth would
            # voice it now, an octave higher, so it never duplicates the left column.
            base = chord_at(self.key, chord.kind, 0)
            root_note = self.register() + base.root
            notes = apply_voicing(
                "Smooth", close(root_note, base.intervals), previous, root_note + self.brightness
            )
            return [n + 12 for n in notes if n + 12 <= 127]
        root_note = self.register() + chord.root
        # Brightness moves the register Smooth keeps to; the other voicings are fixed
        # shapes around the chord's root.
        register = root_note + (self.brightness if self.active_voicing == "Smooth" else 0)
        return apply_voicing(
            self.active_voicing, close(root_note, chord.intervals), previous, register
        )

    def notes_for(self, pad: Pad) -> list[int]:
        """The notes a pad would play right now, without playing them."""
        if pad[0] == BASS_ROW:
            return [self._bass_note(pad[1])]
        chord = self.chord_for(pad)
        return self._voiced(chord) if chord else []

    def _bass_note(self, col: int) -> int:
        return self.register() - 12 + chord_at(self.key, "triad", col).root

    # Sounding

    def _sound(self, pad: Pad, velocity: int) -> None:
        chord = self.chord_for(pad)
        if chord is None:
            return
        notes = self._voiced(chord)
        destination, channel = self._output()
        accent = self.accent()
        velocities = self.spread.velocities(notes, velocity, accent)
        self.last_velocities = velocities
        if not self.strum and not self.mute_chords:
            handed = self.hand_to_rhythm(
                destination, channel, notes, velocity, self._vary(notes), self.timing.offsets
            )
            if not handed:
                now = self._clock()
                offsets = self.timing.offsets(notes)
                for i, (note, v, offset) in enumerate(zip(notes, velocities, offsets, strict=True)):
                    if offset > 0:  # rolled in: queued, and taken back if released first
                        at = now + offset
                        self.router.note_on_at(
                            ("chord", i), destination, channel, note, v, at, CHORD_TAG
                        )
                    else:
                        self.router.note_on(("chord", i), destination, channel, note, v)
        if not self.mute_bass:
            bass = self.register() - 12 + chord.root
            if bass >= 0:  # the bass stays steady at the center, never randomized
                center = self.spread.center(velocity, accent)
                self.router.note_on(("bass",), destination, self.bass_channel, bass, center)
        self.current, self.velocity = pad, velocity
        self.notes, self.last_chord = notes, chord

    def sounding_name(self) -> str | None:
        """The name of the chord sounding now, for the Keyboard playing over it."""
        if self.current is None or self.last_chord is None:
            return None
        chord = self.last_chord
        return chord_name(chord.pitch_class(self.key), chord.intervals, key_spelling(self.key))

    def timing_text(self) -> str | None:
        """The status line's word for how chords roll in, while they do."""
        t = self.timing
        if not t.spread or (t.roll == 0 and t.loose == 0):
            return None
        if t.roll == 0:
            return f"Loose {t.loose} ms"
        arrows = {"Up": "↑", "Down": "↓", "Alternate": "↕", "Random": "?"}
        return f"Rolled {arrows[t.direction]} {t.roll} ms"

    def _vary(self, chord_notes: list[int]) -> Callable[[list[int], int], list[int]]:
        """Fresh velocities for each repeat or arp step. A note is the top note if it's
        the chord's highest (arp octaves above it aren't)."""
        top = max(chord_notes, default=None)

        def vary(notes: list[int], velocity: int) -> list[int]:
            accent = self.accent()
            return [self.spread.one(n == top, velocity, accent) for n in notes]

        return vary

    def _silence(self) -> None:
        if self.timing.spread:
            self.router.cancel(CHORD_TAG)  # rolled-in notes that haven't started yet
        for i in range(MAX_TONES):
            self.router.note_off(("chord", i))
        self.router.note_off(("bass",))
        self.take_from_rhythm()
        self._release_strum()

    def _retrigger(self) -> None:
        if self.current is not None:
            pad = self.current
            self._silence()
            self._sound(pad, self.velocity)

    # Pads

    def pad_pressed(self, row: int, col: int, velocity: int) -> None:
        pad = (row, col)
        if row == BASS_ROW:
            destination, _ = self._output()
            note = self._bass_note(col)
            velocity = self.spread.center(velocity, self.accent())
            self.router.note_on(("bass row", col), destination, self.bass_channel, note, velocity)
            self.bass_pads[pad] = note
            return
        if self.chord_for(pad) is None:
            return
        if self.latch and pad == self.current and not self.current_held:
            self._silence()  # tapping the latched chord again stops it
            self.current = None
            return
        self._silence()  # the last chord pressed wins; changes re-trigger
        self._sound(pad, velocity)
        self.current_held = True

    def pad_released(self, row: int, col: int) -> None:
        pad = (row, col)
        if row == BASS_ROW:
            self.router.note_off(("bass row", col))
            self.bass_pads.pop(pad, None)
        elif pad == self.current:
            if self.latch:
                self.current_held = False  # keeps sounding until the next chord
            else:
                self._silence()
                self.current = None

    # Changes that re-voice the sounding chord

    def revoice(self) -> None:
        """Key, scale or octave changed: re-trigger what's sounding."""
        self._retrigger()

    def shift_octave(self, delta: int) -> None:
        self.octave = max(MIN_OCTAVE, min(MAX_OCTAVE, self.octave + delta))
        self.notes = []  # Smooth starts fresh in the new register
        self.revoice()

    def toggle_latch(self) -> None:
        self.latch = not self.latch
        if not self.latch and self.current is not None and not self.current_held:
            self._silence()  # turning Latch off releases a latched chord
            self.current = None

    def voicing_pressed(self, index: int) -> None:
        if index == LATCH_BUTTON:
            self.toggle_latch()
            return
        if index >= len(self.voicing_buttons):
            return
        name = self.voicing_buttons[index]
        self._voicing_pressed[name] = self._clock()
        self.momentary = name
        self._retrigger()  # hear the new voicing on the chord you're holding

    def voicing_released(self, index: int) -> None:
        if index >= len(self.voicing_buttons):
            return
        name = self.voicing_buttons[index]
        pressed = self._voicing_pressed.pop(name, None)
        if pressed is not None and self._clock() - pressed < HOLD_SECONDS:
            self.voicing = name  # a tap keeps the voicing
        if self.momentary == name:
            self.momentary = None

    @property
    def latched(self) -> bool:
        """A chord Latch is holding, with no finger on its pad."""
        return self.latch and self.current is not None and not self.current_held

    def release_all(self, keep_latched: bool = False) -> None:
        """Leaving the layout: nothing played here keeps sounding, except a latched
        chord when asked, so a melody can be played over it on the Keyboard."""
        if not (keep_latched and self.latched):
            self._silence()
            self.current = None
            self.current_held = False
        for _, col in list(self.bass_pads):
            self.router.note_off(("bass row", col))
        self.bass_pads.clear()

    # Strum

    def strum_tones(self) -> list[int]:
        if self.current is None:
            return []
        tones = {n + 12 * o for o in range(self.strum_octaves) for n in self.notes}
        return sorted(n for n in tones if n <= 127)

    def strum_to(self, value: int) -> None:
        """Touch strip moved (0..127 in mod-wheel mode): sound every tone crossed."""
        now = self._clock()
        tones = self.strum_tones()
        if not tones:
            self._strum_index = None
            return
        index = min(len(tones) - 1, max(0, value) * len(tones) // 128)
        new_touch = self._strum_index is None or now - self._strum_time > NEW_TOUCH_GAP
        self._strum_time = now
        if new_touch:
            crossed = [index]
        elif index == self._strum_index:
            crossed = []
        else:
            step = 1 if index > self._strum_index else -1
            crossed = list(range(self._strum_index + step, index + step, step))
        self._strum_index = index
        if self.mute_chords:
            return
        destination, channel = self._output()
        for i in crossed:
            top = tones[i] == max(self.notes, default=None)
            velocity = self.spread.one(top, self.velocity, self.accent())
            self.router.note_on(("strum", i), destination, channel, tones[i], velocity)
            self._strumming.add(i)

    def _release_strum(self) -> None:
        for i in self._strumming:
            self.router.note_off(("strum", i))
        self._strumming.clear()
        self._strum_index = None

    # Output

    def pad_colors(self) -> list[list[str]]:
        colors = []
        for row in range(ROWS):
            line = []
            for col in range(COLUMNS):
                pad = (row, col)
                if pad == self.current or pad in self.bass_pads:
                    line.append("pt_held")
                elif row == BASS_ROW:
                    line.append("pt_root" if col in (0, COLUMNS - 1) else "pt_in_scale")
                else:
                    line.append(self._role_color(self.chord_for(pad)))
            colors.append(line)
        return colors

    def _role_color(self, chord: Chord) -> str:
        if chord.kind in BORROWED_KINDS or chord.kind == "augmented":
            return led("borrowed")  # deliberate color from outside the key
        if chord.kind in LEADING_KINDS:
            return led("secondary")
        return ROLE_COLORS[role(chord, self.key)]

    def rail(self) -> list[dict]:
        """The side buttons, top to bottom, as the screen's voicing rail shows them. A
        voicing chosen on the encoder that has no button lights none."""
        entries = []
        for voicing in self.voicing_buttons:
            if voicing == self.momentary:
                state = "held"
            elif voicing == self.voicing and self.momentary is None:
                state = "kept"
            else:
                state = "off"
            entries.append({"label": voicing, "state": state})
        latch = "latch_on" if self.latch else "off"
        entries.append({"label": "Latch", "state": latch, "apart": True})
        return entries

    def scene_colors(self) -> dict[str, str]:
        colors = {name: "black" for name in SCENE_BUTTONS}
        for button, entry in zip(SCENE_BUTTONS, self.rail(), strict=False):
            colors[button] = RAIL_LEDS[entry["state"]]
        return colors

    def describe_side_button(self, index: int) -> str:
        """What a side button just did, for when the rail isn't on screen."""
        if index == LATCH_BUTTON:
            return "Latch on" if self.latch else "Latch off"
        if self.momentary is not None:
            return f"Voicing: {self.momentary} (held)"
        return f"Voicing: {self.voicing}"

    def panel(self) -> dict:
        chord = self.last_chord
        # The lowest bass-row note held is the bass under the chord: G over B is "G/B".
        bass = min(self.bass_pads.values(), default=None)
        held_bass = bass is not None
        info: dict = {
            "strum": self.strum,
            "voicing": VOICING_NAMES[self.active_voicing],
            "sounding": self.current is not None,
            "latch": self.latch,
            "latched": self.latch and self.current is not None and not self.current_held,
            "parent": None,
            "octave": self.octave,
            "octave_moved": self.octave != DEFAULT_OCTAVE,
            "random_velocity": self.spread.random,
            "timing": self.timing_text(),
            "rail": self.rail(),
            "grid": self.pad_colors(),
            "row": self.current[0] if self.current else (BASS_ROW if held_bass else None),
            "row_names": [KIND_LABELS[kind] for kind in self.rows],
            "chord_set": self.chord_set,
            "bass_note": None,
            "bass_channel": self.bass_channel,
        }
        names = key_spelling(self.key)
        if held_bass:
            info["bass_note"] = note_name(bass, names)
        if uses_parent(self.key):
            parent = next(n for n, s in SCALES.items() if s == parent_scale(self.key))
            info["parent"] = f"Chords from {parent}"
        if chord is None:
            return info | {"chord_name": None, "notes": [], "role": None}
        name = chord_name(chord.pitch_class(self.key), chord.intervals, names)
        notes = [note_name(n, names) for n in self.notes]
        velocities: list[int | None] = list(self.last_velocities)
        if held_bass and self.current is not None:
            notes.insert(0, note_name(bass, names))
            velocities.insert(0, None)  # a hand-played bass note, not part of the roll
            if bass % 12 != chord.pitch_class(self.key):
                name = f"{name}/{names[bass % 12]}"
        return info | {
            "velocities": velocities if self.current is not None else [],
            "chord_name": name,
            "notes": notes,
            "role": role(chord, self.key),
            "role_line": self._role_line(chord),
        }

    def _role_line(self, chord: Chord) -> str:
        """Plain role first, numeral for those who want theory: "V7 · tension"."""
        label = numeral_label(chord, self.key)
        if chord.kind in LEADING_KINDS:
            line = f"{label} · leads to {numeral(self.key, chord.target or 0)}"
        else:
            line = f"{label} · {role(chord, self.key)}"
        # The right column repeats the first one higher; say so, or it looks like a copy.
        return f"{line} · octave up" if chord.degree == OCTAVE_COLUMN else line

    # Session state

    def snapshot(self) -> dict:
        return {
            "octave": self.octave,
            "strum": self.strum,
            "strum_octaves": self.strum_octaves,
            "mute_chords": self.mute_chords,
            "mute_bass": self.mute_bass,
            "bass_channel": self.bass_channel + 1,
            "voicing": self.voicing,
            "brightness": self.brightness,
            "latch": self.latch,
            "velocity": self.spread.snapshot(),
            "timing": self.timing.snapshot(),
            "set": self.chord_set,
        }

    def restore(self, state: dict) -> None:
        if state.get("octave") in range(MIN_OCTAVE, MAX_OCTAVE + 1):
            self.octave = state["octave"]
        if state.get("strum_octaves") in range(1, 4):
            self.strum_octaves = state["strum_octaves"]
        if state.get("bass_channel") in range(1, 17):
            self.bass_channel = state["bass_channel"] - 1
        if state.get("voicing") in VOICINGS:
            self.voicing = state["voicing"]
        if state.get("brightness") in range(MIN_BRIGHTNESS, MAX_BRIGHTNESS + 1):
            self.brightness = state["brightness"]
        for flag in ("strum", "mute_chords", "mute_bass", "latch"):
            if isinstance(state.get(flag), bool):
                setattr(self, flag, state[flag])
        self.spread.restore(state.get("velocity"))
        self.timing.restore(state.get("timing"))
        if state.get("set") in self.sets:
            self.chord_set = state["set"]
