"""Play mode (PRD F2, F12, F15, F19, F22): Keyboard, Drums and Chord layouts, the scale
selector, velocity curves, Accent and the touch strip. Pure logic; the router does the I/O.

Pad callbacks run on the MIDI input thread, so they send first and do nothing else
expensive. Everything the screen needs is computed in view().
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from push2_python import constants as c

from pushtoo.chords import EXTENSIONS
from pushtoo.midi.router import OUT_PORT, MidiRouter, short_port_name
from pushtoo.modes.base import Mode, Row
from pushtoo.modes.chord import SCENE_BUTTONS, ChordPlayer
from pushtoo.music import (
    BANK_SIZE,
    DRUM_HIGHEST_START,
    DRUM_LOWEST_START,
    MAX_OCTAVE,
    MIN_OCTAVE,
    NOTE_NAMES,
    ROWS,
    SCALE_NAMES,
    VELOCITY_CURVES,
    DrumLayout,
    KeyboardLayout,
    drum_name,
    note_name,
)
from pushtoo.profiles.schema import Play as PlaySettings
from pushtoo.theme import PAD_ROLE_COLORS
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


@dataclass
class Layout:
    """Per-layout settings. Each layout remembers its own page and output."""

    name: str
    channel: int
    destination: str = OUT_PORT
    page: int = 0
    pages: list[Page] = field(default_factory=list)


class PlayMode(Mode):
    name = "play"

    def __init__(self, router: MidiRouter) -> None:
        super().__init__(router)
        self.keyboard = KeyboardLayout()  # also holds the key and scale shared by layouts
        self.drums = DrumLayout()
        self.velocity_curve = 0  # index into VELOCITY_CURVES
        self.strip_mode = 0  # index into STRIP_MODES
        self.accent = False
        self.scale_open = False
        self.played_once = False
        self.last_drum: int | None = None

        self.layouts = [
            Layout("Keyboard", channel=0),
            Layout("Drums", channel=9),
            Layout("Chord", channel=1),
        ]
        chord_layout = self.layouts[2]
        self.chord = ChordPlayer(
            router, self.keyboard, output=lambda: (chord_layout.destination, chord_layout.channel)
        )
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
            Option("Off", lambda: self._set_chord_flag("strum", False), lambda: not chord.strum),
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
            Page("Output", controls=output, options=mute_options),
        ]

    def _set_chord_flag(self, flag: str, value: bool) -> None:
        setattr(self.chord, flag, value)
        self.chord.revoice()  # held chords re-trigger in the new style or mix

    def _build_pages(self, layout: Layout) -> list[Page]:
        if layout.name == "Chord":
            return self._build_chord_pages(layout)
        velocity = Control(
            "Velocity",
            lambda: self.velocity_curve,
            lambda v: setattr(self, "velocity_curve", v),
            choices=VELOCITY_CURVES,
        )
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
        return [
            Page("Play", controls=[first, velocity]),
            Page("Strip", options=strip_options),
            Page("Output", controls=output),
        ]

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
        if self.accent:
            velocity = ACCENT_VELOCITY
        if self.in_chord:
            self.chord.pad_pressed(row, col, velocity)
            self.played_once = True
            return
        note = self._grid().note_at(row, col)
        if note is None:
            return
        layout = self.layout
        self.router.note_on((row, col), layout.destination, layout.channel, note, velocity)
        self.played_once = True
        if layout.name == "Drums":
            self.last_drum = note

    def pad_released(self, row: int, col: int) -> None:
        # Always release the plain pad source too: a note held while switching layouts
        # must not stick.
        self.router.note_off((row, col))
        if self.in_chord:
            self.chord.pad_released(row, col)

    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None:
        if not self.in_chord:
            self.router.poly_aftertouch((row, col), pressure)

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

    def _revoice_if_key_changed(self, before: tuple) -> None:
        # The PRD: changing key while holding a chord transposes or reharmonizes it live.
        if self.in_chord and self._key_state() != before:
            self.chord.revoice()

    def _button_pressed(self, name: str) -> bool:
        if name == c.BUTTON_SCALE:
            self.scale_open = not self.scale_open
            return True
        if name == c.BUTTON_LAYOUT:
            if self.in_chord:
                self.chord.release_all()
            self.current = (self.current + 1) % len(self.layouts)
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
        if name in SCENE_BUTTONS[: len(EXTENSIONS)] and self.in_chord:
            self.chord.toggle_extension(SCENE_BUTTONS.index(name))
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
        return {"velocity_curve": VELOCITY_CURVES[self.velocity_curve], "strip_mode": strip}

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
                    line.append("pt_off")
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

    def button_colors(self) -> dict[str, str]:
        lit = "white"
        return (
            super().button_colors()
            | {
                c.BUTTON_LAYOUT: lit,
                c.BUTTON_SCALE: lit if self.scale_open else "dark_gray",
                c.BUTTON_ACCENT: lit if self.accent else "dark_gray",
                c.BUTTON_OCTAVE_UP: lit,
                c.BUTTON_OCTAVE_DOWN: lit,
            }
            | self.scene_colors()
        )

    def scene_colors(self) -> dict[str, str]:
        """Side buttons: extension toggles in the Chord layout, dark otherwise."""
        if self.in_chord:
            return self.chord.scene_colors()
        return {name: "black" for name in SCENE_BUTTONS}

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
            "title": f"Play · {layout.name}",
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
                panel |= {
                    "key_name": self.keyboard.key_name,
                    "in_key": self.keyboard.in_key,
                    "held": [note_name(n) for n in held],
                    "first_run": not self.played_once,
                }
            else:
                panel |= {
                    "held": [drum_name(n) for n in held],
                    "last_hit": drum_name(self.last_drum) if self.last_drum is not None else None,
                    "first_run": not self.played_once,
                }
        return panel

    # Profiles and session state

    def apply_settings(self, settings: PlaySettings) -> None:
        """Profile defaults for channels, outputs, velocity curve and touch strip."""
        for layout, layout_settings in zip(
            self.layouts, (settings.keyboard, settings.drums, settings.chord), strict=True
        ):
            layout.channel = layout_settings.channel - 1
            layout.destination = layout_settings.output
        self.chord.bass_channel = settings.chord.bass_channel - 1
        self.velocity_curve = VELOCITY_CURVES.index(settings.velocity_curve)
        self.strip_mode = STRIP_MODES.index(settings.strip)

    def snapshot(self) -> dict:
        return {
            "layout": self.current,
            "root": self.keyboard.root,
            "scale": self.keyboard.scale,
            "in_key": self.keyboard.in_key,
            "octave": self.keyboard.octave,
            "drums_start": self.drums.start,
            "velocity_curve": VELOCITY_CURVES[self.velocity_curve],
            "strip": STRIP_MODES[self.strip_mode],
            "layouts": [
                {"channel": lo.channel + 1, "output": lo.destination, "page": lo.page}
                for lo in self.layouts
            ],
            "chord": self.chord.snapshot(),
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
        if state.get("velocity_curve") in VELOCITY_CURVES:
            self.velocity_curve = VELOCITY_CURVES.index(state["velocity_curve"])
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
        if state.get("layout") in range(len(self.layouts)):
            self.current = state["layout"]
