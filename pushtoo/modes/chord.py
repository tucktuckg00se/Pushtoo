"""The chord grid's player (PRD: Chord layout).

Every pad above the bottom row is one complete chord: press it and it plays. The last
chord pressed is the one sounding, and every change re-triggers. The bottom row plays
single bass notes. The side buttons choose the voicing: tap one to keep it, hold one
to use it only while held.

With Strum on, a chord pad plays only its bass note and the touch strip strums the
chord across a few octaves, one note per tone crossed, like an Omnichord.
"""

import time
from collections.abc import Callable

from pushtoo.chords import (
    ROW_KINDS,
    VOICING_NAMES,
    VOICINGS,
    Chord,
    apply_voicing,
    chord_at,
    chord_name,
    close,
    key_spelling,
    parent_scale,
    role,
    uses_parent,
)
from pushtoo.midi.router import MidiRouter
from pushtoo.music import ROWS, SCALES, KeyboardLayout, note_name
from pushtoo.theme import led
from pushtoo.ui.controls import COLUMNS

Pad = tuple[int, int]
BASS_ROW = 0
MAX_TONES = 8
NEW_TOUCH_GAP = 0.08  # seconds without strip messages that count as lifting the finger
HOLD_SECONDS = 0.3  # a voicing button held this long acts only while held
MIN_OCTAVE, MAX_OCTAVE = 1, 6
# Side buttons, top to bottom: the voicings, then one spare.
SCENE_BUTTONS = ("1/4", "1/4t", "1/8", "1/8t", "1/16", "1/16t", "1/32", "1/32t")
ROLE_COLORS = {"home": "pt_root", "away": led("blue"), "tension": led("amber")}


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
        self._output = output  # (destination, chord channel) of the Chord layout
        self._clock = clock
        self.bass_channel = 2
        self.octave = 3
        self.strum = False
        self.strum_octaves = 2
        self.mute_chords = False
        self.mute_bass = False
        self.voicing = "Smooth"  # latched
        self.momentary: str | None = None  # held voicing button, overriding the latch
        self._voicing_pressed: dict[str, float] = {}
        self.current: Pad | None = None  # the chord pad sounding
        self.velocity = 100
        self.notes: list[int] = []  # what the sounding (or last) chord played
        self.last_chord: Chord | None = None
        self.bass_pads: set[Pad] = set()
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
        if row == BASS_ROW or not 0 <= row < len(ROW_KINDS):
            return None
        return chord_at(self.key, ROW_KINDS[row], col)

    def _voiced(self, chord: Chord) -> list[int]:
        root_note = self.register() + chord.root
        previous = self.notes or None
        return apply_voicing(
            self.active_voicing, close(root_note, chord.intervals), previous, root_note
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
        if not self.strum and not self.mute_chords:
            for i, note in enumerate(notes):
                self.router.note_on(("chord", i), destination, channel, note, velocity)
        if not self.mute_bass:
            bass = self.register() - 12 + chord.root
            if bass >= 0:
                self.router.note_on(("bass",), destination, self.bass_channel, bass, velocity)
        self.current, self.velocity = pad, velocity
        self.notes, self.last_chord = notes, chord

    def _silence(self) -> None:
        for i in range(MAX_TONES):
            self.router.note_off(("chord", i))
        self.router.note_off(("bass",))
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
            self.router.note_on(("bass row", col), destination, self.bass_channel, note, velocity)
            self.bass_pads.add(pad)
            return
        if self.chord_for(pad) is None:
            return
        self._silence()  # the last chord pressed wins; changes re-trigger
        self._sound(pad, velocity)

    def pad_released(self, row: int, col: int) -> None:
        pad = (row, col)
        if row == BASS_ROW:
            self.router.note_off(("bass row", col))
            self.bass_pads.discard(pad)
        elif pad == self.current:
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

    def voicing_pressed(self, index: int) -> None:
        if index >= len(VOICINGS):
            return
        name = VOICINGS[index]
        self._voicing_pressed[name] = self._clock()
        self.momentary = name
        self._retrigger()  # hear the new voicing on the chord you're holding

    def voicing_released(self, index: int) -> None:
        if index >= len(VOICINGS):
            return
        name = VOICINGS[index]
        pressed = self._voicing_pressed.pop(name, None)
        if pressed is not None and self._clock() - pressed < HOLD_SECONDS:
            self.voicing = name  # a tap keeps the voicing
        if self.momentary == name:
            self.momentary = None

    def release_all(self) -> None:
        """Leaving the layout: nothing played here may keep sounding."""
        self._silence()
        self.current = None
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
            self.router.note_on(("strum", i), destination, channel, tones[i], self.velocity)
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
        if chord.kind == "borrowed":
            return led("violet")
        if chord.kind == "secondary":
            return led("pink")
        return ROLE_COLORS[role(chord, self.key)]

    def scene_colors(self) -> dict[str, str]:
        colors = {name: "black" for name in SCENE_BUTTONS}
        for i, voicing in enumerate(VOICINGS):
            colors[SCENE_BUTTONS[i]] = "white" if voicing == self.active_voicing else "dark_gray"
        return colors

    def panel(self) -> dict:
        chord = self.last_chord
        info: dict = {
            "strum": self.strum,
            "voicing": VOICING_NAMES[self.active_voicing],
            "sounding": self.current is not None,
            "parent": None,
        }
        if uses_parent(self.key):
            parent = next(n for n, s in SCALES.items() if s == parent_scale(self.key))
            info["parent"] = f"Chords from {parent}"
        if chord is None:
            return info | {"chord_name": None, "notes": [], "role": None}
        names = key_spelling(self.key)
        return info | {
            "chord_name": chord_name(chord.pitch_class(self.key), chord.intervals, names),
            "notes": [note_name(n, names) for n in self.notes],
            "role": role(chord, self.key),
        }

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
        for flag in ("strum", "mute_chords", "mute_bass"):
            if isinstance(state.get(flag), bool):
                setattr(self, flag, state[flag])
