"""Play mode (PRD F2, F12, F15, F19, F22): Keyboard, Drums and Chord layouts, the scale
selector, velocity curves, Accent and the touch strip. Pure logic; the router does the I/O.

Pad callbacks run on the MIDI input thread, so they send first and do nothing else
expensive. Everything the screen needs is computed in view().
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from push2_python import constants as c

from pushtoo.midi.router import OUT_PORT, MidiRouter, short_port_name
from pushtoo.modes.base import Mode, Row
from pushtoo.modes.chord import HOLD_SECONDS, SCENE_BUTTONS, ChordPlayer
from pushtoo.modes.chord import MAX_OCTAVE as CHORD_MAX_OCTAVE
from pushtoo.modes.chord import MIN_OCTAVE as CHORD_MIN_OCTAVE
from pushtoo.music import (
    BANK_SIZE,
    DRUM_HIGHEST_START,
    DRUM_LOWEST_START,
    MAX_OCTAVE,
    MIN_OCTAVE,
    NOTE_NAMES,
    ROWS,
    SCALE_NAMES,
    DrumLayout,
    KeyboardLayout,
    drum_name,
    note_name,
    spelling,
)
from pushtoo.profiles.schema import Play as PlaySettings
from pushtoo.profiles.schema import Rhythm as RhythmSettings
from pushtoo.rhythm.arp import MAX_OCTAVES, PATTERNS
from pushtoo.rhythm.clock import Clock
from pushtoo.rhythm.repeat import MODES, RATE_NAMES, Rhythm, Scheduled
from pushtoo.rhythm.timing import DIRECTIONS, MAX_LOOSE, MAX_ROLL
from pushtoo.rhythm.velocity import MAX_SPREAD, MAX_TOP
from pushtoo.theme import OFF, PAD_ROLE_COLORS, led
from pushtoo.ui.controls import COLUMNS, Control, Option, Page

# Scale selector roots, in circle-of-fifths order as on stock Push. Upper button 1
# toggles In key / Chromatic; F# and Gb both select pitch class 6.
UPPER_ROOTS = (None, 0, 7, 2, 9, 4, 11, 6)
UPPER_ROOT_LABELS = (None, "C", "G", "D", "A", "E", "B", "F#")
LOWER_ROOTS = (5, 10, 3, 8, 1, 6)
LOWER_ROOT_LABELS = ("F", "Bb", "Eb", "Ab", "Db", "Gb")

STRIP_MODES = ("Pitch bend", "Mod wheel")
MOD_WHEEL_CC = 1
ACCENT_VELOCITY = 127
CHORD_SOURCE = ("chord",)  # the sounding chord, as one source for repeat and arp


@dataclass
class Layout:
    """Per-layout settings. Each layout remembers its own page and output."""

    name: str
    channel: int
    destination: str = OUT_PORT
    page: int = 0
    pages: list[Page] = field(default_factory=list)


@dataclass
class ChoicePage(Page):
    """A page whose first `always` encoders always apply, and the rest only while
    `more()` says so: the Arp's shape in Arp mode, the spread in Random velocity.
    Settings that do nothing stay off the screen."""

    always: int = 1
    more: Callable[[], bool] = lambda: False

    def control(self, column: int) -> Control | None:
        return super().control(column) if column < self.always or self.more() else None


class PlayMode(Mode):
    name = "play"

    def __init__(self, router: MidiRouter) -> None:
        super().__init__(router)
        self.keyboard = KeyboardLayout()  # also holds the key and scale shared by layouts
        self.drums = DrumLayout()
        self.strip_mode = 0  # index into STRIP_MODES
        self.accent = False
        self.scale_open = False
        self.layout_held = False  # while Layout is held, the upper buttons pick a layout
        self.played_once = False
        self.last_drum: int | None = None
        # Rhythm (PRD: Rhythm). Repeat toggles it; held, it's momentary, and in the
        # Chord layout the side buttons pick rates while it's held.
        self.clock = Clock()
        self.rhythm = Rhythm()
        self.time: Callable[[], float] = time.monotonic
        self.repeat_held = False
        self._repeat_pressed_at = 0.0
        self._repeat_was_on = False
        self._repeat_used = False  # a rate was picked while Repeat was held

        self.layouts = [
            Layout("Keyboard", channel=0),
            Layout("Drums", channel=9),
            Layout("Chord", channel=1),
        ]
        chord_layout = self.layouts[2]
        self.chord = ChordPlayer(
            router, self.keyboard, output=lambda: (chord_layout.destination, chord_layout.channel)
        )
        self.chord.hand_to_rhythm = self._chord_to_rhythm
        self.chord.take_from_rhythm = lambda: self._rhythm_release(CHORD_SOURCE)
        self.chord.accent = lambda: self.accent
        self.current = 0
        for layout in self.layouts:
            layout.pages = self._build_pages(layout)
        self._scale_controls = [
            Control("Scale", self._scale_index, self._set_scale_index, choices=SCALE_NAMES),
            Control(
                "Root", lambda: self.keyboard.root, self._set_root, choices=NOTE_NAMES, wrap=True
            ),
        ]

    # Pages

    def _output_control(self, layout: Layout) -> Control:
        return Control(
            "Output",
            lambda: self._destination_index(layout),
            lambda v: setattr(layout, "destination", self.router.destinations()[v]),
            choices=lambda: [short_port_name(d) for d in self.router.destinations()],
        )

    @staticmethod
    def _channel_control(name: str, get: Callable[[], int], set_: Callable[[int], None]):
        return Control(name, get, set_, minimum=0, maximum=15, format=lambda v: str(v + 1))

    def _build_chord_pages(self, layout: Layout) -> list[Page]:
        chord = self.chord
        strum_range = Control(
            "Strum range",
            lambda: chord.strum_octaves,
            lambda v: setattr(chord, "strum_octaves", v),
            minimum=1,
            maximum=3,
            format=lambda v: f"{v} oct",
        )
        style_options: list[Option | None] = [
            Option("Press", lambda: self._set_chord_flag("strum", False), lambda: not chord.strum),
            Option("Strum", lambda: self._set_chord_flag("strum", True), lambda: chord.strum),
        ]
        output = [
            self._output_control(layout),
            self._channel_control(
                "Chords ch", lambda: layout.channel, lambda v: setattr(layout, "channel", v)
            ),
            self._channel_control(
                "Bass ch", lambda: chord.bass_channel, lambda v: setattr(chord, "bass_channel", v)
            ),
        ]
        mute_options: list[Option | None] = [
            Option(
                "Mute chords",
                lambda: self._set_chord_flag("mute_chords", not chord.mute_chords),
                lambda: chord.mute_chords,
            ),
            Option(
                "Mute bass",
                lambda: self._set_chord_flag("mute_bass", not chord.mute_bass),
                lambda: chord.mute_bass,
            ),
        ]
        return [
            Page("Style", controls=[strum_range], options=style_options),
            self._velocity_page(),
            self._timing_page(),
            Page("Output", controls=output, options=mute_options),
            self._rhythm_page(),
        ]

    def _timing_page(self) -> Page:
        """When each chord note starts: Together, or Spread out by Roll and Loose."""
        timing = self.chord.timing
        controls: list[Control | None] = [
            Control(
                "Roll",
                lambda: timing.roll,
                lambda v: setattr(timing, "roll", v),
                maximum=MAX_ROLL,
                step=2,
                format=lambda v: f"{v} ms",
            ),
            Control(
                "Direction",
                lambda: DIRECTIONS.index(timing.direction),
                lambda v: setattr(timing, "direction", DIRECTIONS[v]),
                choices=DIRECTIONS,
            ),
            Control(
                "Loose",
                lambda: timing.loose,
                lambda v: setattr(timing, "loose", v),
                maximum=MAX_LOOSE,
                format=lambda v: f"{v} ms",
            ),
        ]
        options: list[Option | None] = [
            Option("Together", lambda: setattr(timing, "spread", False), lambda: not timing.spread),
            Option("Spread out", lambda: setattr(timing, "spread", True), lambda: timing.spread),
        ]
        return ChoicePage("Timing", controls, options, always=0, more=lambda: timing.spread)

    def _velocity_page(self) -> Page:
        """The chord grid's velocities: As played or Random above the display; the
        range always, and the spread and top-note lift only for Random."""
        spread = self.chord.spread
        controls: list[Control | None] = [
            Control("Min", lambda: spread.min, spread.set_min, minimum=1, maximum=127),
            Control("Max", lambda: spread.max, spread.set_max, minimum=1, maximum=127),
            Control(
                "Spread",
                lambda: spread.spread,
                lambda v: setattr(spread, "spread", v),
                maximum=MAX_SPREAD,
                format=lambda v: f"±{v}",
            ),
            Control(
                "Top note",
                lambda: spread.top,
                lambda v: setattr(spread, "top", v),
                minimum=-MAX_TOP,
                maximum=MAX_TOP,
                format=lambda v: f"{v:+d}",
                bipolar=True,
            ),
        ]
        options: list[Option | None] = [
            Option(
                "As played", lambda: setattr(spread, "random", False), lambda: not spread.random
            ),
            Option("Random", lambda: setattr(spread, "random", True), lambda: spread.random),
        ]
        return ChoicePage("Velocity", controls, options, always=2, more=lambda: spread.random)

    def _rhythm_page(self) -> Page:
        """Repeat or Arp above the display; the arp's shape on the encoders."""
        rhythm = self.rhythm
        controls: list[Control | None] = [
            Control(
                "Rate",
                lambda: RATE_NAMES.index(rhythm.rate),
                lambda v: setattr(rhythm, "rate", RATE_NAMES[v]),
                choices=RATE_NAMES,
            ),
            Control(
                "Pattern",
                lambda: PATTERNS.index(rhythm.pattern),
                lambda v: setattr(rhythm, "pattern", PATTERNS[v]),
                choices=PATTERNS,
            ),
            Control(
                "Octaves",
                lambda: rhythm.octaves,
                lambda v: setattr(rhythm, "octaves", v),
                minimum=1,
                maximum=MAX_OCTAVES,
            ),
            Control(
                "Gate",
                lambda: rhythm.gate,
                lambda v: setattr(rhythm, "gate", v),
                minimum=10,
                maximum=100,
                step=5,
                format=lambda v: f"{v}%",
            ),
        ]
        options: list[Option | None] = [
            Option(mode, self._mode_setter(mode), lambda m=mode: rhythm.mode == m) for mode in MODES
        ]
        return ChoicePage("Rhythm", controls, options, always=1, more=lambda: rhythm.arp)

    def _mode_setter(self, mode: str) -> Callable[[], None]:
        def choose() -> None:
            self._stop_rhythm_notes()  # held pads restart in the new mode
            self.rhythm.mode = mode
            self.rhythm.on = True  # picking a mode means you want to hear it

        return choose

    def _set_chord_flag(self, flag: str, value: bool) -> None:
        setattr(self.chord, flag, value)
        self.chord.revoice()  # held chords re-trigger in the new style or mix

    def _build_pages(self, layout: Layout) -> list[Page]:
        if layout.name == "Chord":
            return self._build_chord_pages(layout)
        if layout.name == "Keyboard":
            first = Control(
                "Octave",
                lambda: self.keyboard.octave,
                lambda v: setattr(self.keyboard, "octave", v),
                minimum=-1,
                maximum=7,
            )
        else:
            first = Control(
                "Notes",
                lambda: self.drums.start,
                lambda v: setattr(self.drums, "start", v),
                minimum=DRUM_LOWEST_START,
                maximum=DRUM_HIGHEST_START,
                step=BANK_SIZE,  # one bank per step, like the Octave buttons
                format=lambda v: f"{v}–{v + 4 * BANK_SIZE - 1}",
            )
        strip_options: list[Option | None] = [
            Option(label, self._strip_setter(i), lambda i=i: self.strip_mode == i)
            for i, label in enumerate(STRIP_MODES)
        ]
        output = [
            self._output_control(layout),
            self._channel_control(
                "Channel", lambda: layout.channel, lambda v: setattr(layout, "channel", v)
            ),
        ]
        pages = [
            Page("Play", controls=[first]),  # pad feel is in Setup
            Page("Strip", options=strip_options),
            Page("Output", controls=output),
        ]
        if layout.name == "Keyboard":  # Drums only repeat, with rates on the side buttons
            pages.append(self._rhythm_page())
        return pages

    def _strip_setter(self, index: int) -> Callable[[], None]:
        return lambda: setattr(self, "strip_mode", index)

    def _destination_index(self, layout: Layout) -> int:
        destinations = self.router.destinations()
        return destinations.index(layout.destination) if layout.destination in destinations else -1

    def _scale_index(self) -> int:
        return SCALE_NAMES.index(self.keyboard.scale)

    def _set_scale_index(self, index: int) -> None:
        self.keyboard.scale = SCALE_NAMES[index]

    def _set_root(self, root: int) -> None:
        self.keyboard.root = root

    @property
    def layout(self) -> Layout:
        return self.layouts[self.current]

    @property
    def pages(self) -> list[Page]:
        return self.layout.pages

    @property
    def page_index(self) -> int:
        return self.layout.page

    @page_index.setter
    def page_index(self, index: int) -> None:
        self.layout.page = index

    def on_page_selected(self) -> None:
        if self.page.name == "Output":
            self.router.refresh_destinations()

    @property
    def in_chord(self) -> bool:
        return self.layout.name == "Chord"

    def _grid(self) -> KeyboardLayout | DrumLayout:
        return self.keyboard if self.layout.name == "Keyboard" else self.drums

    def _key_state(self) -> tuple:
        return (self.keyboard.root, self.keyboard.scale, self.keyboard.in_key)

    # Pads

    def pad_pressed(self, row: int, col: int, velocity: int) -> None:
        if self.in_chord:  # the chord grid applies Accent itself, with its Velocity page
            self.chord.pad_pressed(row, col, velocity)
            self.played_once = True
            return
        if self.accent:
            velocity = ACCENT_VELOCITY
        note = self._grid().note_at(row, col)
        if note is None:
            return
        layout = self.layout
        self.played_once = True
        if layout.name == "Drums":
            self.last_drum = note
        if self.rhythm.on:
            hits = self.rhythm.press(
                (row, col),
                layout.destination,
                layout.channel,
                [note],
                velocity,
                self.clock,
                self.time(),
            )
            self.send_scheduled(hits)
            return
        self.router.note_on((row, col), layout.destination, layout.channel, note, velocity)

    def pad_released(self, row: int, col: int) -> None:
        # Always release the plain pad source too: a note held while switching layouts
        # must not stick.
        self.router.note_off((row, col))
        self._rhythm_release((row, col))
        if self.in_chord:
            self.chord.pad_released(row, col)

    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None:
        if self.rhythm.on:  # pressure sets the velocity of the repeats to come
            pad = (row, col)
            source = CHORD_SOURCE if self.in_chord and pad == self.chord.current else pad
            self.rhythm.pressure(source, pressure)
        elif not self.in_chord:
            self.router.poly_aftertouch((row, col), pressure)

    # Rhythm

    def send_scheduled(self, events: list[Scheduled]) -> None:
        for at, destination, message, tag in events:
            self.router.schedule(destination, message, at, tag)

    def _chord_to_rhythm(
        self, destination: str, channel: int, notes: list[int], velocity: int, vary, timing
    ) -> bool:
        if not self.rhythm.on:
            return False
        hits = self.rhythm.press(
            CHORD_SOURCE,
            destination,
            channel,
            notes,
            velocity,
            self.clock,
            self.time(),
            vary,
            timing,
        )
        self.send_scheduled(hits)
        return True

    def _rhythm_release(self, source) -> None:
        tag = self.rhythm.release(source)
        if tag is not None:
            self.router.cancel(tag)  # take back its queued notes; note-offs stay

    def _stop_rhythm_notes(self) -> None:
        for tag in self.rhythm.release_all():
            self.router.cancel(tag)

    def set_rhythm(self, on: bool) -> None:
        if on == self.rhythm.on:
            return
        self._stop_rhythm_notes()
        self.rhythm.on = on
        if self.in_chord and self.chord.current is not None:
            self.chord.revoice()  # a sounding chord switches between held and rhythmic

    @property
    def rates_on_side(self) -> bool:
        """Side buttons pick rates: in Keyboard and Drums while rhythm is on, and in
        the Chord layout (where they're voicings) while Repeat is held."""
        return self.repeat_held or (self.rhythm.on and not self.in_chord)

    def _repeat_pressed(self) -> None:
        self.repeat_held = True
        self._repeat_pressed_at = self.time()
        self._repeat_was_on = self.rhythm.on
        self._repeat_used = False
        self.set_rhythm(True)

    def _repeat_released(self) -> None:
        self.repeat_held = False
        held = self.time() - self._repeat_pressed_at >= HOLD_SECONDS
        if held or self._repeat_used:
            self.set_rhythm(self._repeat_was_on)  # momentary, or just picking a rate
        elif self._repeat_was_on:
            self.set_rhythm(False)  # a tap turns it off again

    def rhythm_text(self) -> str | None:
        if not self.rhythm.on:
            return None
        if self.rhythm.arp and not self.layout.name == "Drums":
            return f"Arp {self.rhythm.pattern} {self.rhythm.rate}"
        return f"Repeat {self.rhythm.rate}"

    def channel_pressure(self, pressure: int) -> None:
        layout = self.layout
        self.router.channel_pressure(layout.destination, layout.channel, pressure)

    def touchstrip(self, value: int) -> None:
        if self.in_chord and self.chord.strum:
            self.chord.strum_to(value)
            return
        layout = self.layout
        if STRIP_MODES[self.strip_mode] == "Pitch bend":
            self.router.pitch_bend(layout.destination, layout.channel, value)
        else:
            value = max(0, min(127, value))
            self.router.control_change(layout.destination, layout.channel, MOD_WHEEL_CC, value)

    # Buttons and encoders. Each returns True if anything the user sees changed.

    def button_pressed(self, name: str) -> bool:
        key = self._key_state()
        changed = self._button_pressed(name)
        self._revoice_if_key_changed(key)
        return changed

    def encoder_turned(self, index: int, increment: int, fine: bool = False) -> bool:
        key = self._key_state()
        changed = super().encoder_turned(index, increment, fine)
        self._revoice_if_key_changed(key)
        return changed

    def button_released(self, name: str) -> bool:
        """Side buttons need releases: a held voicing button only lasts while held.
        So does Layout, whose layout picker shows only while it's held."""
        if name == c.BUTTON_LAYOUT:
            self.layout_held = False
            return True
        if name == c.BUTTON_REPEAT:
            self._repeat_released()
            return True
        if name in SCENE_BUTTONS and self.in_chord:
            self.chord.voicing_released(SCENE_BUTTONS.index(name))
            return True
        return False

    def select_layout(self, index: int) -> bool:
        if index == self.current or not 0 <= index < len(self.layouts):
            return False
        if self.in_chord:
            self.chord.release_all()
        self._stop_rhythm_notes()
        self.current = index
        self.rhythm.allow_arp = self.layout.name != "Drums"
        return True

    def layout_choices(self) -> Row:
        """The upper-button labels while Layout is held."""
        choices: Row = [
            {"label": layout.name, "selected": i == self.current}
            for i, layout in enumerate(self.layouts)
        ]
        return choices + [None] * (COLUMNS - len(choices))

    def _revoice_if_key_changed(self, before: tuple) -> None:
        # The PRD: changing key while holding a chord transposes or reharmonizes it live.
        if self.in_chord and self._key_state() != before:
            self.chord.revoice()

    def _button_pressed(self, name: str) -> bool:
        if name == c.BUTTON_SCALE:
            self.scale_open = not self.scale_open
            return True
        if name == c.BUTTON_LAYOUT:
            # A tap moves to the next layout; held, the upper buttons also pick one.
            self.layout_held = True
            self.select_layout((self.current + 1) % len(self.layouts))
            return True
        if name == c.BUTTON_ACCENT:
            self.accent = not self.accent
            return True
        if name in (c.BUTTON_OCTAVE_UP, c.BUTTON_OCTAVE_DOWN):
            delta = 1 if name == c.BUTTON_OCTAVE_UP else -1
            if self.in_chord:
                self.chord.shift_octave(delta)
            elif self.layout.name == "Keyboard":
                self.keyboard.shift_octave(delta)
            else:
                self.drums.shift_bank(delta)
            return True
        if name == c.BUTTON_REPEAT:
            self._repeat_pressed()
            return True
        if name in SCENE_BUTTONS and self.rates_on_side:
            self.rhythm.rate = name  # the side buttons are labelled with their rates
            self._repeat_used = self.repeat_held
            return True
        if name in SCENE_BUTTONS and self.in_chord:
            self.chord.voicing_pressed(SCENE_BUTTONS.index(name))
            return True
        return super().button_pressed(name)

    def upper_pressed(self, index: int) -> bool:
        if self.scale_open:
            if index == 0:
                self.keyboard.in_key = not self.keyboard.in_key
            else:
                self.keyboard.root = UPPER_ROOTS[index]
            return True
        return super().upper_pressed(index)

    def lower_pressed(self, index: int) -> bool:
        if self.scale_open:
            if index < len(LOWER_ROOTS):
                self.keyboard.root = LOWER_ROOTS[index]
                return True
            return False
        return super().lower_pressed(index)

    def control_at(self, index: int) -> Control | None:
        if self.scale_open:
            return self._scale_controls[index] if index < len(self._scale_controls) else None
        return super().control_at(index)

    # Output for the hardware, LEDs and renderer

    def hardware_settings(self) -> dict:
        strip = STRIP_MODES[self.strip_mode]
        if self.in_chord and self.chord.strum:
            # Pitch-bend mode springs back to center, which would strum again on release.
            strip = "Mod wheel"
        return {"strip_mode": strip}

    def pad_colors(self) -> list[list[str]]:
        if self.in_chord:
            return self.chord.pad_colors()
        layout, grid = self.layout, self._grid()
        held = self.router.notes_on(layout.destination, layout.channel)
        colors = []
        for row in range(ROWS):
            line = []
            for col in range(COLUMNS):
                note = grid.note_at(row, col)
                if note is None:
                    line.append(OFF)
                elif note in held:
                    line.append("pt_held")
                elif isinstance(grid, DrumLayout):
                    # Checkerboard the four banks so their edges are visible.
                    bank = grid.bank_of(row, col)
                    line.append("pt_root" if bank in (0, 3) else "pt_in_scale")
                else:
                    line.append(PAD_ROLE_COLORS[grid.role_of(note)])
            colors.append(line)
        return colors

    def octave_room(self) -> tuple[bool, bool]:
        """Can the Octave buttons still move (down, up)? They go dark at the limit."""
        if self.in_chord:
            octave = self.chord.octave
            return octave > CHORD_MIN_OCTAVE, octave < CHORD_MAX_OCTAVE
        if self.layout.name == "Keyboard":
            octave = self.keyboard.octave
            return octave > MIN_OCTAVE, octave < MAX_OCTAVE
        start = self.drums.start
        return start > DRUM_LOWEST_START, start < DRUM_HIGHEST_START

    def button_colors(self) -> dict[str, str]:
        lit = "white"
        down, up = self.octave_room()
        return (
            super().button_colors()
            | {
                c.BUTTON_LAYOUT: lit,
                c.BUTTON_SCALE: lit if self.scale_open else "dark_gray",
                c.BUTTON_ACCENT: lit if self.accent else "dark_gray",
                c.BUTTON_OCTAVE_UP: lit if up else "dark_gray",
                c.BUTTON_OCTAVE_DOWN: lit if down else "dark_gray",
            }
            | self.scene_colors()
        )

    def scene_colors(self) -> dict[str, str]:
        """Side buttons: rates while they pick rates, voicings in the Chord layout,
        dark otherwise."""
        if self.rates_on_side:
            return {
                name: led("rate") if name == self.rhythm.rate else "dark_gray"
                for name in SCENE_BUTTONS
            }
        if self.in_chord:
            return self.chord.scene_colors()
        return {name: "black" for name in SCENE_BUTTONS}

    def rail(self) -> list[dict] | None:
        """The screen column beside the side buttons, naming what they do now."""
        if self.rates_on_side:
            return [
                {"label": name, "state": "rate" if name == self.rhythm.rate else "off"}
                for name in SCENE_BUTTONS
            ]
        return self.chord.rail() if self.in_chord else None

    def button_rows(self) -> tuple[Row, Row]:
        if self.scale_open:
            root = self.keyboard.root
            upper: list[dict | None] = [
                {"label": "In key" if self.keyboard.in_key else "Chromatic", "selected": True}
            ]
            upper += [
                {"label": label, "selected": UPPER_ROOTS[i] == root}
                for i, label in enumerate(UPPER_ROOT_LABELS)
                if label is not None
            ]
            lower: list[dict | None] = [
                {"label": label, "selected": LOWER_ROOTS[i] == root}
                for i, label in enumerate(LOWER_ROOT_LABELS)
            ]
            # F# and Gb are the same root; light only the upper one.
            if root == 6:
                lower[-1]["selected"] = False
            return upper, lower + [None] * (COLUMNS - len(lower))
        return super().button_rows()

    def controls_view(self) -> list[dict | None]:
        return [None] * COLUMNS if self.scale_open else super().controls_view()

    def panel(self) -> dict:
        layout = self.layout
        destination = layout.destination
        panel: dict = {
            "destination": short_port_name(destination),
            "kind": "scale_selector" if self.scale_open else layout.name.lower(),
            "layout": layout.name,
            "default_destination": destination == OUT_PORT,
            "channel": layout.channel,
            "accent": self.accent,
        }
        if self.scale_open:
            panel |= {
                "scale": self.keyboard.scale,
                "scale_names": list(SCALE_NAMES),
                "root_name": NOTE_NAMES[self.keyboard.root],
                "in_key": self.keyboard.in_key,
            }
        else:
            held = sorted(self.router.notes_on(destination, layout.channel))
            if self.in_chord:
                panel |= self.chord.panel() | {
                    "key_name": self.keyboard.key_name,
                    "in_key": self.keyboard.in_key,
                    "first_run": not self.played_once,
                }
            elif layout.name == "Keyboard":
                names = spelling(self.keyboard.root, self.keyboard.intervals)
                panel |= {
                    "key_name": self.keyboard.key_name,
                    "in_key": self.keyboard.in_key,
                    "held": [note_name(n, names) for n in held],
                    "first_run": not self.played_once,
                }
            else:
                panel |= {
                    "held": [drum_name(n) for n in held],
                    "last_hit": drum_name(self.last_drum) if self.last_drum is not None else None,
                    "first_run": not self.played_once,
                }
        if not self.scale_open:
            panel["rail"] = self.rail()
            panel["rhythm"] = self.rhythm_text()
            panel["tempo"] = self.tempo_text()
        return panel

    def tempo_text(self) -> str | None:
        """The tempo, while it matters: rhythm on, the transport running, or following."""
        clock = self.clock
        if clock.following:
            return f"Following clock · {clock.tempo:.0f}"
        if self.rhythm.on or clock.running:
            return f"{clock.tempo:.0f} BPM"
        return None

    # Profiles and session state

    def apply_rhythm(self, settings: RhythmSettings) -> None:
        """Profile defaults for tempo, swing and rate."""
        self.clock.set_tempo(settings.tempo, self.time())
        self.clock.swing = settings.swing
        self.rhythm.rate = settings.rate

    def apply_settings(self, settings: PlaySettings) -> None:
        """Profile defaults for channels, outputs and touch strip. (The profile's velocity
        curve only seeds Setup on a first run; see App.)"""
        for layout, layout_settings in zip(
            self.layouts, (settings.keyboard, settings.drums, settings.chord), strict=True
        ):
            layout.channel = layout_settings.channel - 1
            layout.destination = layout_settings.output
        self.chord.bass_channel = settings.chord.bass_channel - 1
        self.strip_mode = STRIP_MODES.index(settings.strip)

    def snapshot(self) -> dict:
        return {
            "layout": self.current,
            "root": self.keyboard.root,
            "scale": self.keyboard.scale,
            "in_key": self.keyboard.in_key,
            "octave": self.keyboard.octave,
            "drums_start": self.drums.start,
            "strip": STRIP_MODES[self.strip_mode],
            "layouts": [
                {"channel": lo.channel + 1, "output": lo.destination, "page": lo.page}
                for lo in self.layouts
            ],
            "chord": self.chord.snapshot(),
            "rhythm": {
                "tempo": round(self.clock.tempo, 1),
                "swing": self.clock.swing,
                "mode": self.rhythm.mode,
                "rate": self.rhythm.rate,
                "pattern": self.rhythm.pattern,
                "octaves": self.rhythm.octaves,
                "gate": self.rhythm.gate,
            },
        }

    def restore(self, state: dict) -> None:
        """Apply a snapshot, ignoring anything missing or out of range."""
        if state.get("scale") in SCALE_NAMES:
            self.keyboard.scale = state["scale"]
        if state.get("root") in range(12):
            self.keyboard.root = state["root"]
        if isinstance(state.get("in_key"), bool):
            self.keyboard.in_key = state["in_key"]
        if state.get("octave") in range(MIN_OCTAVE, MAX_OCTAVE + 1):
            self.keyboard.octave = state["octave"]
        if state.get("drums_start") in range(DRUM_LOWEST_START, DRUM_HIGHEST_START + 1):
            self.drums.start = state["drums_start"]
        if state.get("strip") in STRIP_MODES:
            self.strip_mode = STRIP_MODES.index(state["strip"])
        for layout, saved in zip(self.layouts, state.get("layouts", []), strict=False):
            if saved.get("channel") in range(1, 17):
                layout.channel = saved["channel"] - 1
            if isinstance(saved.get("output"), str):
                layout.destination = saved["output"]
            if saved.get("page") in range(len(layout.pages)):
                layout.page = saved["page"]
        if isinstance(state.get("chord"), dict):
            self.chord.restore(state["chord"])
        self._restore_rhythm(state.get("rhythm"))
        if state.get("layout") in range(len(self.layouts)):
            self.current = state["layout"]
            self.rhythm.allow_arp = self.layout.name != "Drums"

    def _restore_rhythm(self, saved) -> None:
        if not isinstance(saved, dict):
            return
        if isinstance(saved.get("tempo"), int | float) and 40 <= saved["tempo"] <= 240:
            self.clock.set_tempo(float(saved["tempo"]), self.time())
        if saved.get("swing") in range(50, 76):
            self.clock.swing = saved["swing"]
        if saved.get("mode") in MODES:
            self.rhythm.mode = saved["mode"]
        if saved.get("rate") in RATE_NAMES:
            self.rhythm.rate = saved["rate"]
        if saved.get("pattern") in PATTERNS:
            self.rhythm.pattern = saved["pattern"]
        if saved.get("octaves") in range(1, MAX_OCTAVES + 1):
            self.rhythm.octaves = saved["octaves"]
        if saved.get("gate") in range(10, 101):
            self.rhythm.gate = saved["gate"]
