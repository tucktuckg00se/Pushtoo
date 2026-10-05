"""Play mode (PRD F2, F15, F19, F22): Keyboard and Drums layouts, the scale selector,
velocity curves, Accent and the touch strip. Pure logic; the router does the I/O.

Pad callbacks run on the MIDI input thread, so they send first and do nothing else
expensive. Everything the screen needs is computed in view().
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from push2_python import constants as c

from pushtoo.hw.colors import PAD_ROLE_COLORS
from pushtoo.midi.router import OUT_PORT, MidiRouter, short_port_name
from pushtoo.music import (
    BANK_SIZE,
    DRUM_HIGHEST_START,
    DRUM_LOWEST_START,
    NOTE_NAMES,
    ROWS,
    SCALE_NAMES,
    VELOCITY_CURVES,
    DrumLayout,
    KeyboardLayout,
    drum_name,
    note_name,
)
from pushtoo.ui.controls import COLUMNS, Control, Option, Page, pages_view

# Scale selector roots, in circle-of-fifths order as on stock Push. Upper button 1
# toggles In key / Chromatic; F# and Gb both select pitch class 6.
UPPER_ROOTS = (None, 0, 7, 2, 9, 4, 11, 6)
UPPER_ROOT_LABELS = (None, "C", "G", "D", "A", "E", "B", "F#")
LOWER_ROOTS = (5, 10, 3, 8, 1, 6)
LOWER_ROOT_LABELS = ("F", "Bb", "Eb", "Ab", "Db", "Gb")

STRIP_MODES = ("Pitch bend", "Mod wheel")
MOD_WHEEL_CC = 1
ACCENT_VELOCITY = 127


def row_index(name: str, row: str) -> int | None:
    """'Upper Row 3' -> 2 for row='Upper'."""
    prefix = f"{row} Row "
    return int(name[len(prefix) :]) - 1 if name.startswith(prefix) else None


@dataclass
class Layout:
    """Per-layout settings. Each layout remembers its own page and output."""

    name: str
    channel: int
    destination: str = OUT_PORT
    page: int = 0
    pages: list[Page] = field(default_factory=list)


class PlayMode:
    def __init__(self, router: MidiRouter) -> None:
        self.router = router
        self.keyboard = KeyboardLayout()  # also holds the key and scale shared by layouts
        self.drums = DrumLayout()
        self.velocity_curve = 0  # index into VELOCITY_CURVES
        self.strip_mode = 0  # index into STRIP_MODES
        self.accent = False
        self.scale_open = False
        self.played_once = False
        self.last_drum: int | None = None

        self.layouts = [Layout("Keyboard", channel=0), Layout("Drums", channel=9)]
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

    def _build_pages(self, layout: Layout) -> list[Page]:
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
            Control(
                "Output",
                lambda: self._destination_index(layout),
                lambda v: setattr(layout, "destination", self.router.destinations()[v]),
                choices=lambda: [short_port_name(d) for d in self.router.destinations()],
            ),
            Control(
                "Channel",
                lambda: layout.channel,
                lambda v: setattr(layout, "channel", v),
                minimum=0,
                maximum=15,
                format=lambda v: str(v + 1),
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
    def page(self) -> Page:
        return self.layout.pages[self.layout.page]

    def _grid(self) -> KeyboardLayout | DrumLayout:
        return self.keyboard if self.layout.name == "Keyboard" else self.drums

    # Pads

    def pad_pressed(self, row: int, col: int, velocity: int) -> None:
        note = self._grid().note_at(row, col)
        if note is None:
            return
        layout = self.layout
        if self.accent:
            velocity = ACCENT_VELOCITY
        self.router.note_on((row, col), layout.destination, layout.channel, note, velocity)
        self.played_once = True
        if layout.name == "Drums":
            self.last_drum = note

    def pad_released(self, row: int, col: int) -> None:
        self.router.note_off((row, col))

    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None:
        self.router.poly_aftertouch((row, col), pressure)

    def touchstrip(self, value: int) -> None:
        layout = self.layout
        if STRIP_MODES[self.strip_mode] == "Pitch bend":
            self.router.pitch_bend(layout.destination, layout.channel, value)
        else:
            value = max(0, min(127, value))
            self.router.control_change(layout.destination, layout.channel, MOD_WHEEL_CC, value)

    # Buttons and encoders. Each returns True if anything the user sees changed.

    def button_pressed(self, name: str) -> bool:
        if name == c.BUTTON_SCALE:
            self.scale_open = not self.scale_open
            return True
        if name == c.BUTTON_LAYOUT:
            self.current = (self.current + 1) % len(self.layouts)
            return True
        if name == c.BUTTON_ACCENT:
            self.accent = not self.accent
            return True
        if name in (c.BUTTON_OCTAVE_UP, c.BUTTON_OCTAVE_DOWN):
            delta = 1 if name == c.BUTTON_OCTAVE_UP else -1
            if self.layout.name == "Keyboard":
                self.keyboard.shift_octave(delta)
            else:
                self.drums.shift_bank(delta)
            return True
        if (index := row_index(name, "Upper")) is not None:
            return self._upper_pressed(index)
        if (index := row_index(name, "Lower")) is not None:
            return self._lower_pressed(index)
        return False

    def _upper_pressed(self, index: int) -> bool:
        if self.scale_open:
            if index == 0:
                self.keyboard.in_key = not self.keyboard.in_key
            else:
                self.keyboard.root = UPPER_ROOTS[index]
            return True
        return self.page.press_option(index)

    def _lower_pressed(self, index: int) -> bool:
        if self.scale_open:
            if index < len(LOWER_ROOTS):
                self.keyboard.root = LOWER_ROOTS[index]
                return True
            return False
        if index >= len(self.layout.pages) or index == self.layout.page:
            return False
        self.layout.page = index
        if self.page.name == "Output":
            self.router.refresh_destinations()
        return True

    def control_at(self, index: int) -> Control | None:
        if self.scale_open:
            return self._scale_controls[index] if index < len(self._scale_controls) else None
        return self.page.control(index)

    def encoder_turned(self, index: int, increment: int, fine: bool = False) -> bool:
        control = self.control_at(index)
        return control is not None and control.turn(increment, fine)

    # Output for the hardware, LEDs and renderer

    def hardware_settings(self) -> dict:
        return {
            "velocity_curve": VELOCITY_CURVES[self.velocity_curve],
            "strip_mode": STRIP_MODES[self.strip_mode],
        }

    def pad_colors(self) -> list[list[str]]:
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
        colors = {
            c.BUTTON_NOTE: lit,
            c.BUTTON_LAYOUT: lit,
            c.BUTTON_SCALE: lit if self.scale_open else "dark_gray",
            c.BUTTON_ACCENT: lit if self.accent else "dark_gray",
            c.BUTTON_OCTAVE_UP: lit,
            c.BUTTON_OCTAVE_DOWN: lit,
        }
        upper, lower = self._button_rows()
        for i in range(COLUMNS):
            colors[f"Upper Row {i + 1}"] = self._row_color(upper[i])
            colors[f"Lower Row {i + 1}"] = self._row_color(lower[i])
        return colors

    @staticmethod
    def _row_color(item: dict | None) -> str:
        if item is None:
            return "black"
        return "white" if item["selected"] else "dark_gray"

    def _button_rows(self) -> tuple[list[dict | None], list[dict | None]]:
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
        return self.page.options_view(), pages_view(self.layout.pages, self.layout.page)

    def view(self) -> dict:
        upper, lower = self._button_rows()
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
            controls: list[dict | None] = [None] * COLUMNS
        else:
            held = sorted(self.router.notes_on(destination, layout.channel))
            if layout.name == "Keyboard":
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
            controls = self.page.controls_view()
        return {
            "accent": "play",
            "upper": upper,
            "lower": lower,
            "controls": controls,
            "panel": panel,
        }
