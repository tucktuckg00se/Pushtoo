"""Pages, encoder controls and button options (PRD F13). Pure logic, no I/O.

A Page fills the hardware's 8 columns: one encoder control and one upper-button
option per column. Controls read and write their model through get/set callables,
so the model stays the single source of truth.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

COLUMNS = 8
# Push encoders send about this many increments per detent-sized turn.
INCREMENTS_PER_STEP = 6
FINE_FACTOR = 4  # Shift + encoder moves values 4x finer


def middle_ellipsis(text: str, max_chars: int) -> str:
    """Shorten text from the middle, keeping both ends readable ("Filt…Cut")."""
    if len(text) <= max_chars:
        return text
    keep = max_chars - 1
    head = (keep + 1) // 2
    return text[:head] + "…" + text[len(text) - (keep - head) :]


@dataclass
class Control:
    name: str
    get: Callable[[], int]
    set: Callable[[int], None]
    minimum: int = 0
    maximum: int = 127
    step: int = 1  # value change per encoder step
    wrap: bool = False  # past either end, continue from the other (e.g. note names)
    # Labels for enumerated values; the value is then an index into them. A callable
    # lets the list change at runtime (for example, available MIDI ports).
    choices: Sequence[str] | Callable[[], Sequence[str]] | None = None
    format: Callable[[int], str] = str
    bipolar: bool = False
    _accumulated: int = field(default=0, repr=False)

    def _choices(self) -> Sequence[str] | None:
        return self.choices() if callable(self.choices) else self.choices

    def bounds(self) -> tuple[int, int]:
        choices = self._choices()
        if choices is not None:
            return 0, max(0, len(choices) - 1)
        return self.minimum, self.maximum

    def turn(self, increment: int, fine: bool = False) -> bool:
        """Apply a raw encoder increment. Returns True if the value changed."""
        per_step = INCREMENTS_PER_STEP * (FINE_FACTOR if fine else 1)
        total = self._accumulated + increment
        steps = int(total / per_step)  # truncates toward zero in both directions
        self._accumulated = total - steps * per_step
        if steps == 0:
            return False
        low, high = self.bounds()
        old = self.get()
        new = old + steps * self.step
        if self.wrap:
            new = low + (new - low) % (high - low + 1)
        else:
            new = max(low, min(high, new))
        if new != old:
            self.set(new)
        return new != old

    def text(self) -> str:
        value = self.get()
        choices = self._choices()
        if choices is not None:
            return choices[value] if 0 <= value < len(choices) else "—"
        return self.format(value)

    def fraction(self) -> float:
        low, high = self.bounds()
        if high == low:
            return 0.0
        return max(0.0, min(1.0, (self.get() - low) / (high - low)))

    def view(self) -> dict:
        return {
            "name": self.name,
            "text": self.text(),
            "fraction": self.fraction(),
            "bipolar": self.bipolar,
        }


@dataclass
class Option:
    """An upper-button action on a page, such as a mode toggle."""

    label: str
    action: Callable[[], None]
    selected: Callable[[], bool] = lambda: False

    def view(self) -> dict:
        return {"label": self.label, "selected": self.selected()}


@dataclass
class Page:
    name: str
    controls: list[Control | None] = field(default_factory=list)
    options: list[Option | None] = field(default_factory=list)

    def control(self, column: int) -> Control | None:
        return self.controls[column] if column < len(self.controls) else None

    def option(self, column: int) -> Option | None:
        return self.options[column] if column < len(self.options) else None

    def press_option(self, column: int) -> bool:
        option = self.option(column)
        if option is None:
            return False
        option.action()
        return True

    def controls_view(self) -> list[dict | None]:
        return [control.view() if (control := self.control(i)) else None for i in range(COLUMNS)]

    def options_view(self) -> list[dict | None]:
        return [option.view() if (option := self.option(i)) else None for i in range(COLUMNS)]


def pages_view(pages: Sequence[Page], current: int) -> list[dict | None]:
    """Lower-button labels: one page per button, current page selected."""
    return [
        {"label": pages[i].name, "selected": i == current} if i < len(pages) else None
        for i in range(COLUMNS)
    ]
