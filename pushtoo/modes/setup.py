"""Setup mode (the Setup button): pad feel, aftertouch, brightness and clock.

Pads keep playing the current layout, so every change can be felt as it's made, and
the screen shows where each hit landed on the velocity curve.
"""

from collections.abc import Callable

from pushtoo.midi.router import MidiRouter
from pushtoo.modes.base import Mode
from pushtoo.modes.play import PlayMode
from pushtoo.setup import AFTERTOUCH_MODES, LIMITS, RESPONSES, DeviceSettings, velocity_table
from pushtoo.standby import SCENES
from pushtoo.ui.controls import Control, Option, Page


class SetupMode(Mode):
    name = "setup"

    def __init__(
        self,
        router: MidiRouter,
        play: PlayMode,
        settings: DeviceSettings,
        on_change: Callable[[], None],
    ) -> None:
        super().__init__(router)
        self.play = play
        self.settings = settings
        self._on_change = on_change
        self.last_velocity: int | None = None
        self.last_pressure = 0
        s = settings
        self._pages = [
            Page(
                "Pads",
                controls=[
                    self._number("Sensitivity", "sensitivity"),
                    self._number("Dynamics", "dynamics", bipolar=True, signed=True),
                    self._number("Min velocity", "min_velocity"),
                    self._number("Max velocity", "max_velocity"),
                ],
                options=[self._choice("response", r) for r in RESPONSES],
            ),
            Page(
                "Aftertouch",
                controls=[
                    self._number("Starts at", "aftertouch_start", percent=True),
                    self._number("Full at", "aftertouch_full", percent=True),
                ],
                options=[self._choice("aftertouch", m) for m in AFTERTOUCH_MODES],
            ),
            Page(
                "Display",
                controls=[
                    self._number("Pads", "pad_brightness", percent=True),
                    self._number("Screen", "screen_brightness", percent=True),
                    self._number("Standby", "standby_minutes", minutes=True),
                ],
                # The standby scene; Shift+Session starts it at once.
                options=[self._choice("standby_scene", scene) for scene in SCENES],
            ),
            Page(
                "Clock",
                options=[
                    Option("Send clock", lambda: self._toggle("send_clock"), lambda: s.send_clock),
                    Option(
                        "Follow clock", lambda: self._toggle("follow_clock"), lambda: s.follow_clock
                    ),
                ],
            ),
        ]

    # Controls that write straight into the settings

    def _set(self, field: str, value) -> None:
        s = self.settings
        setattr(s, field, value)
        # Keep ranges the right way round, whichever end was moved.
        if field == "min_velocity":
            s.max_velocity = max(s.max_velocity, value)
        elif field == "max_velocity":
            s.min_velocity = min(s.min_velocity, value)
        elif field == "aftertouch_start":
            s.aftertouch_full = max(s.aftertouch_full, value + 1)
        elif field == "aftertouch_full":
            s.aftertouch_start = min(s.aftertouch_start, value - 1)
        self._on_change()

    def _number(
        self, name: str, field: str, bipolar=False, signed=False, percent=False, minutes=False
    ):
        low, high = LIMITS[field]

        def fmt(value: int) -> str:
            if minutes:
                return f"{value} min" if value else "Off"
            if percent:
                return f"{value}%"
            return f"{value:+d}" if signed and value else str(value)

        return Control(
            name,
            lambda: getattr(self.settings, field),
            lambda v: self._set(field, v),
            minimum=low,
            maximum=high,
            format=fmt,
            bipolar=bipolar,
        )

    def _choice(self, field: str, value: str) -> Option:
        return Option(
            value,
            lambda: self._set(field, value),
            lambda: getattr(self.settings, field) == value,
        )

    def _toggle(self, field: str) -> None:
        self._set(field, not getattr(self.settings, field))

    # Pads keep playing, and the screen shows what they sent.

    def pad_pressed(self, row: int, col: int, velocity: int) -> None:
        self.play.pad_pressed(row, col, velocity)
        self.last_velocity = velocity

    def pad_released(self, row: int, col: int) -> None:
        self.play.pad_released(row, col)

    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None:
        self.play.pad_aftertouch(row, col, pressure)
        self.last_pressure = pressure

    def pad_colors(self) -> list[list[str]]:
        return self.play.pad_colors()

    def panel(self) -> dict:
        clock = self.play.clock
        return {
            "kind": "setup",
            "page": self.page.name,
            "table": velocity_table(self.settings),
            "last_velocity": self.last_velocity,
            "last_pressure": self.last_pressure,
            "aftertouch": self.settings.aftertouch,
            "clock": self.play.tempo_text() or f"Leading at {clock.tempo:.0f} BPM",
            "following": clock.following,
        }
