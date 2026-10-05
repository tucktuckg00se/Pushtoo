"""Knobs mode (PRD F3): up to 8 pages of 8 named CC controls from the profile.

Pads keep playing the current Play layout, so you can play and tweak at once.
Values are Pushtoo's own until DAW feedback (F7) exists.
"""

from pushtoo.midi.router import MidiRouter, short_port_name
from pushtoo.modes.base import Mode, Row
from pushtoo.modes.play import PlayMode
from pushtoo.profiles.schema import KnobControl, Knobs
from pushtoo.ui.controls import COLUMNS, Control, Page

LEARN_REPEATS = 3


class KnobsMode(Mode):
    name = "knobs"

    def __init__(self, router: MidiRouter, play: PlayMode, settings: Knobs, output: str) -> None:
        super().__init__(router)
        self.play = play
        self.output = output
        self.values: dict[tuple[int, int], int] = {}
        self.specs: list[list[KnobControl | None]] = []
        self.apply_settings(settings, output)

    def apply_settings(self, settings: Knobs, output: str) -> None:
        """Rebuild pages from the profile, keeping values for controls that still exist."""
        self.output = output
        old_specs, old_values = self.specs, self.values
        self.specs = [
            [*page.controls, *[None] * (COLUMNS - len(page.controls))] for page in settings.pages
        ]
        self.values = {}
        pages = []
        for p, page in enumerate(settings.pages):
            controls: list[Control | None] = []
            for k, spec in enumerate(self.specs[p]):
                if spec is None:
                    controls.append(None)
                    continue
                # Keep a value only if this column still drives the same CC and channel;
                # a remapped control starts fresh rather than inheriting a stranger's value.
                old = old_specs[p][k] if p < len(old_specs) else None
                kept = old_values.get((p, k))
                same = old is not None and (old.cc, old.channel) == (spec.cc, spec.channel)
                in_range = kept is not None and spec.min <= kept <= spec.max
                self.values[(p, k)] = kept if same and in_range else spec.start_value
                controls.append(self._control(p, k, spec))
            pages.append(Page(page.name, controls=controls))
        self._pages = pages
        self._page_index = min(self._page_index, len(pages) - 1)

    def _control(self, p: int, k: int, spec: KnobControl) -> Control:
        center = (spec.min + spec.max + 1) // 2

        def fmt(value: int) -> str:
            return f"{value - center:+d}" if spec.bipolar else str(value)

        return Control(
            spec.name,
            lambda: self.values[(p, k)],
            lambda v: self._set(p, k, v),
            minimum=spec.min,
            maximum=spec.max,
            format=fmt,
            bipolar=spec.bipolar,
            color=spec.color,
        )

    def _set(self, p: int, k: int, value: int) -> None:
        self.values[(p, k)] = value
        self._send(self.specs[p][k], value)

    def _send(self, spec: KnobControl, value: int) -> None:
        self.router.control_change(self.output, spec.channel - 1, spec.cc, value)

    # Learn Assist and reset

    def learn(self, column: int) -> str | None:
        """Send this column's CC alone, a few times, so DAW MIDI learn catches it."""
        spec = self.specs[self.page_index][column]
        if spec is None:
            return None
        value = self.values[(self.page_index, column)]
        for _ in range(LEARN_REPEATS):
            self._send(spec, value)
        return f"Sent CC {spec.cc} on ch {spec.channel} for {spec.name}"

    def reset(self, column: int) -> bool:
        spec = self.specs[self.page_index][column]
        if spec is None:
            return False
        self._set(self.page_index, column, spec.start_value)
        return True

    # Pads play the current Play layout.

    def pad_pressed(self, row: int, col: int, velocity: int) -> None:
        self.play.pad_pressed(row, col, velocity)

    def pad_released(self, row: int, col: int) -> None:
        self.play.pad_released(row, col)

    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None:
        self.play.pad_aftertouch(row, col, pressure)

    def pad_colors(self) -> list[list[str]]:
        return self.play.pad_colors()

    # Output

    def button_rows(self) -> tuple[Row, Row]:
        _, lower = super().button_rows()
        # Upper buttons light in their column's color; Shift + one is Learn Assist.
        upper: Row = [
            {"label": "", "selected": False, "color": spec.color} if spec else None
            for spec in self.specs[self.page_index]
        ]
        return upper, lower

    def learn_labels(self) -> Row:
        return [
            {"label": "Learn", "selected": False, "color": spec.color} if spec else None
            for spec in self.specs[self.page_index]
        ]

    def panel(self) -> dict:
        return {
            "kind": "knobs",
            "title": f"Knobs · {self.page.name}",
            "destination": short_port_name(self.output),
        }

    def snapshot(self) -> dict:
        return super().snapshot() | {
            "values": {f"{p},{k}": v for (p, k), v in self.values.items()},
        }

    def restore(self, state: dict) -> None:
        super().restore(state)
        for key, value in (state.get("values") or {}).items():
            try:
                p, k = (int(part) for part in str(key).split(","))
            except ValueError:
                continue
            in_range = 0 <= p < len(self.specs) and 0 <= k < COLUMNS
            spec = self.specs[p][k] if in_range else None
            if spec is not None and isinstance(value, int) and spec.min <= value <= spec.max:
                self.values[(p, k)] = value
