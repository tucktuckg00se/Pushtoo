"""What every mode shares: pages on the lower buttons, options on the upper buttons,
controls on the encoders (PRD F13), and the view the renderer draws."""

from pushtoo.midi.router import MidiRouter
from pushtoo.theme import OFF, led
from pushtoo.ui.controls import COLUMNS, Control, Page, pages_view

Row = list[dict | None]


def row_index(name: str, row: str) -> int | None:
    """'Upper Row 3' -> 2 for row='Upper'."""
    prefix = f"{row} Row "
    return int(name[len(prefix) :]) - 1 if name.startswith(prefix) else None


def empty_pad_colors() -> list[list[str]]:
    return [[OFF] * COLUMNS for _ in range(COLUMNS)]


class Mode:
    name = "mode"  # also the theme accent key

    def __init__(self, router: MidiRouter) -> None:
        self.router = router
        self._pages: list[Page] = []
        self._page_index = 0

    # Pages. Subclasses with several page sets (Play's layouts) override these two.

    @property
    def pages(self) -> list[Page]:
        return self._pages

    @property
    def page_index(self) -> int:
        return self._page_index

    @page_index.setter
    def page_index(self, index: int) -> None:
        self._page_index = index

    @property
    def page(self) -> Page:
        return self.pages[min(self.page_index, len(self.pages) - 1)]

    def select_page(self, index: int) -> bool:
        if index >= len(self.pages) or index == self.page_index:
            return False
        self.page_index = index
        self.on_page_selected()
        return True

    def on_page_selected(self) -> None:
        pass

    # Input. Each returns True if anything the user sees changed.

    def button_pressed(self, name: str) -> bool:
        if (index := row_index(name, "Upper")) is not None:
            return self.upper_pressed(index)
        if (index := row_index(name, "Lower")) is not None:
            return self.lower_pressed(index)
        return False

    def upper_pressed(self, index: int) -> bool:
        return self.page.press_option(index)

    def lower_pressed(self, index: int) -> bool:
        return self.select_page(index)

    def control_at(self, index: int) -> Control | None:
        return self.page.control(index)

    def encoder_turned(self, index: int, increment: int, fine: bool = False) -> bool:
        control = self.control_at(index)
        return control is not None and control.turn(increment, fine)

    def pad_pressed(self, row: int, col: int, velocity: int) -> None:
        pass

    def pad_released(self, row: int, col: int) -> None:
        pass

    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None:
        pass

    # Output

    def button_rows(self) -> tuple[Row, Row]:
        return self.page.options_view(), pages_view(self.pages, self.page_index)

    @staticmethod
    def row_color(item: dict | None) -> str:
        if item is None:
            return "black"
        if item.get("color"):
            return led(item["color"])
        return "white" if item["selected"] else "dark_gray"

    def button_colors(self) -> dict[str, str]:
        upper, lower = self.button_rows()
        colors = {}
        for i in range(COLUMNS):
            colors[f"Upper Row {i + 1}"] = self.row_color(upper[i])
            colors[f"Lower Row {i + 1}"] = self.row_color(lower[i])
        return colors

    def pad_colors(self) -> list[list[str]]:
        return empty_pad_colors()

    def panel(self) -> dict | None:
        return None

    def controls_view(self) -> list[dict | None]:
        return self.page.controls_view()

    def view(self) -> dict:
        upper, lower = self.button_rows()
        return {
            "accent": self.name,
            "upper": upper,
            "lower": lower,
            "controls": self.controls_view(),
            "panel": self.panel(),
        }

    # Session state

    def snapshot(self) -> dict:
        return {"page": self.page_index}

    def restore(self, state: dict) -> None:
        page = state.get("page", 0)
        if isinstance(page, int) and 0 <= page < len(self.pages):
            self.page_index = page
