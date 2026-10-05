"""The Chord layout's player (PRD F12, Strum from F14).

A root pad alone plays its Auto chord. A chord-type pad applies only while held:
press it before a root to choose that root's chord, or while roots are held to
re-trigger them as that type. Letting go of the type pad leaves the chord sounding
until the next press. Changes re-trigger: old notes stop, the whole new chord starts.

With Strum on, a root plays only its bass note and the touch strip strums the chord
across a few octaves, one note per tone crossed, like an Omnichord.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from pushtoo.chords import (
    EXTENSIONS,
    ROOT_ROWS,
    auto_intervals,
    chord_name,
    fits_key,
    grid_at,
    intervals_for,
    inversion_name,
    root_at,
    voice,
)
from pushtoo.midi.router import MidiRouter
from pushtoo.music import ROWS, KeyboardLayout, note_name
from pushtoo.theme import led
from pushtoo.ui.controls import COLUMNS

Pad = tuple[int, int]
MAX_TONES = 4 + len(EXTENSIONS)  # a 7th chord plus every extension
NEW_TOUCH_GAP = 0.08  # seconds without strip messages that count as lifting the finger
MIN_OCTAVE, MAX_OCTAVE = 0, 6
# Side buttons, top to bottom; the top four toggle extensions, the rest stay dark.
SCENE_BUTTONS = ("1/4", "1/4t", "1/8", "1/8t", "1/16", "1/16t", "1/32", "1/32t")


@dataclass
class Sounding:
    """What the screen shows: the chord most recently played."""

    root_pc: int
    intervals: tuple[int, ...]
    inversion: int
    extension_labels: tuple[str, ...]
    notes: list[int]


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
        self.extensions: set[int] = set()  # indices into EXTENSIONS
        self.held: dict[Pad, int] = {}  # root pad -> velocity, in press order
        self.grid_pad: Pad | None = None
        self.last: Sounding | None = None
        self._strum_index: int | None = None
        self._strum_time = 0.0
        self._strumming: set[int] = set()

    # Chord construction

    def _root(self, pad: Pad):
        return root_at(*pad, self.key, self.octave)

    def _chord(self, pad: Pad) -> Sounding | None:
        root = self._root(pad)
        if root is None:
            return None
        chord_type, inversion = grid_at(*self.grid_pad) if self.grid_pad else ("Auto", 0)
        root_pc = root.note % 12
        intervals = intervals_for(chord_type, root_pc, self.key)
        chosen = sorted(self.extensions)
        notes = voice(root.note, intervals, inversion, tuple(EXTENSIONS[i][1] for i in chosen))
        labels = tuple(EXTENSIONS[i][0] for i in chosen)
        return Sounding(root_pc, intervals, inversion, labels, notes)

    def notes_for(self, pad: Pad) -> list[int]:
        """The notes a root pad would play right now (empty for non-root pads)."""
        chord = self._chord(pad) if pad[0] < ROOT_ROWS else None
        return chord.notes if chord else []

    # Sounding and silencing a root's chord

    def _sound(self, pad: Pad) -> None:
        chord = self._chord(pad)
        if chord is None:
            return
        destination, channel = self._output()
        velocity = self.held[pad]
        if not self.strum and not self.mute_chords:
            for i, note in enumerate(chord.notes):
                self.router.note_on(("chord", pad, i), destination, channel, note, velocity)
        if not self.mute_bass:
            bass = self._root(pad).note - 12
            if bass >= 0:
                self.router.note_on(("bass", pad), destination, self.bass_channel, bass, velocity)
        self.last = chord

    def _silence(self, pad: Pad) -> None:
        for i in range(MAX_TONES):
            self.router.note_off(("chord", pad, i))
        self.router.note_off(("bass", pad))

    def _retrigger_all(self) -> None:
        self._release_strum()
        for pad in self.held:
            self._silence(pad)
        for pad in self.held:
            self._sound(pad)

    # Pads

    def pad_pressed(self, row: int, col: int, velocity: int) -> None:
        pad = (row, col)
        if row < ROOT_ROWS:
            if self._root(pad) is None:
                return
            self._release_strum()  # a new chord ends the old strum
            self.held[pad] = velocity
            self._sound(pad)
        elif grid_at(row, col):
            self.grid_pad = pad
            if self.held:
                self._retrigger_all()

    def pad_released(self, row: int, col: int) -> None:
        pad = (row, col)
        if pad in self.held:
            self._silence(pad)
            del self.held[pad]
            if not self.held:
                self._release_strum()
        elif pad == self.grid_pad:
            self.grid_pad = None  # the chord keeps sounding until the next press

    # Changes that re-voice held chords

    def revoice(self) -> None:
        """Key, scale, octave or extensions changed: re-trigger what's held."""
        if self.held:
            self._retrigger_all()

    def shift_octave(self, delta: int) -> None:
        self.octave = max(MIN_OCTAVE, min(MAX_OCTAVE, self.octave + delta))
        self.revoice()

    def toggle_extension(self, index: int) -> None:
        self.extensions ^= {index}
        self.revoice()

    def release_all(self) -> None:
        """Leaving the layout: nothing held here may keep sounding."""
        for pad in list(self.held):
            self._silence(pad)
        self.held.clear()
        self.grid_pad = None
        self._release_strum()

    # Strum

    def strum_tones(self) -> list[int]:
        if not self.held:
            return []
        chord = self._chord(next(reversed(self.held)))
        if chord is None:
            return []
        base = voice(self._root(next(reversed(self.held))).note, chord.intervals, 0)
        base += [n for n in chord.notes if n not in base]  # extensions
        tones = {n + 12 * o for o in range(self.strum_octaves) for n in base}
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
        destination, channel = self._output()
        velocity = self.held[next(reversed(self.held))]
        for i in crossed:
            if not self.mute_chords:
                self.router.note_on(("strum", i), destination, channel, tones[i], velocity)
                self._strumming.add(i)

    def _release_strum(self) -> None:
        for i in self._strumming:
            self.router.note_off(("strum", i))
        self._strumming.clear()
        self._strum_index = None

    # Output

    def current_root_pc(self) -> int:
        if self.held:
            return self._root(next(reversed(self.held))).note % 12
        return self.last.root_pc if self.last else self.key.root

    def pad_colors(self) -> list[list[str]]:
        root_pc = self.current_root_pc()

        def color(row: int, col: int) -> str:
            if row < ROOT_ROWS:
                return self._root_color((row, col))
            return self._grid_color((row, col), root_pc)

        return [[color(row, col) for col in range(COLUMNS)] for row in range(ROWS)]

    def _root_color(self, pad: Pad) -> str:
        root = self._root(pad)
        if root is None:
            return "pt_off"
        if pad in self.held:
            return "pt_held"
        if root.home:
            return "pt_root"
        # Chromatic turns off key hints and out-of-key dimming.
        return "pt_in_scale" if root.in_key or not self.key.in_key else "pt_out_of_scale"

    def _grid_color(self, pad: Pad, root_pc: int) -> str:
        chord_type, _ = grid_at(*pad)
        if pad == self.grid_pad:
            return "pt_held"
        if chord_type == "Auto":
            return "pt_in_scale"
        intervals = intervals_for(chord_type, root_pc, self.key)
        if self.key.in_key and fits_key(root_pc, intervals, self.key):
            return led("hint")
        return "pt_out_of_scale"

    def scene_colors(self) -> dict[str, str]:
        colors = {name: "black" for name in SCENE_BUTTONS}
        for i in range(len(EXTENSIONS)):
            colors[SCENE_BUTTONS[i]] = led("hint") if i in self.extensions else "dark_gray"
        return colors

    def panel(self) -> dict:
        chord = self.last
        if self.held:
            chord = self._chord(next(reversed(self.held)))
        info: dict = {
            "strum": self.strum,
            "extensions": [EXTENSIONS[i][0] for i in sorted(self.extensions)],
            "octave": self.octave,
            "sounding": bool(self.held),
        }
        if chord is None:
            return info | {"chord_name": None, "notes": [], "inversion": None}
        return info | {
            "chord_name": chord_name(chord.root_pc, chord.intervals, chord.extension_labels),
            "notes": [note_name(n) for n in chord.notes],
            "inversion": inversion_name(chord.inversion),
            "auto": chord.intervals == auto_intervals(chord.root_pc, self.key),
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
        }

    def restore(self, state: dict) -> None:
        if state.get("octave") in range(MIN_OCTAVE, MAX_OCTAVE + 1):
            self.octave = state["octave"]
        if state.get("strum_octaves") in range(1, 4):
            self.strum_octaves = state["strum_octaves"]
        if state.get("bass_channel") in range(1, 17):
            self.bass_channel = state["bass_channel"] - 1
        for flag in ("strum", "mute_chords", "mute_bass"):
            if isinstance(state.get(flag), bool):
                setattr(self, flag, state[flag])
