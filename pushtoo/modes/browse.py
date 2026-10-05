"""Profile browser on the Browse button (PRD button map): encoder 1 picks a profile,
upper button 1 loads it. Pads keep playing."""

from collections.abc import Callable
from pathlib import Path

from pushtoo.midi.router import MidiRouter
from pushtoo.modes.base import Mode
from pushtoo.modes.play import PlayMode
from pushtoo.ui.controls import Control, Option, Page


class BrowseMode(Mode):
    name = "browse"

    def __init__(
        self,
        router: MidiRouter,
        play: PlayMode,
        list_profiles: Callable[[], list[Path]],
        active: Callable[[], Path],
        load: Callable[[Path], None],
    ) -> None:
        super().__init__(router)
        self.play = play
        self._list = list_profiles
        self._active = active
        self._load = load
        self.paths: list[Path] = []
        self.selected = 0
        self._pages = [
            Page(
                "Profiles",
                controls=[
                    Control(
                        "Profile",
                        lambda: self.selected,
                        lambda v: setattr(self, "selected", v),
                        choices=lambda: [p.stem for p in self.paths],
                    )
                ],
                options=[Option("Load", self.load_selected)],
            )
        ]

    def refresh(self) -> None:
        """Re-read the profile folder; called when the browser opens."""
        self.paths = self._list()
        active = self._active()
        self.selected = self.paths.index(active) if active in self.paths else 0

    def load_selected(self) -> None:
        if self.paths:
            self._load(self.paths[self.selected])

    def pad_pressed(self, row: int, col: int, velocity: int) -> None:
        self.play.pad_pressed(row, col, velocity)

    def pad_released(self, row: int, col: int) -> None:
        self.play.pad_released(row, col)

    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None:
        self.play.pad_aftertouch(row, col, pressure)

    def pad_colors(self) -> list[list[str]]:
        return self.play.pad_colors()

    def panel(self) -> dict:
        return {
            "kind": "browse",
            "title": "Profiles",
            "names": [p.stem for p in self.paths],
            "selected": self.selected,
            "active": self._active().stem,
        }
