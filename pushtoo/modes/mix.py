"""Mix mode (PRD F4): 8 fader CCs on the encoders, mute and solo toggles on the top
two pad rows, and the bottom six rows still playing the current Play layout.
Meters arrive with DAW feedback (F7).
"""

from pushtoo.midi.router import MidiRouter, short_port_name
from pushtoo.modes.base import Mode
from pushtoo.modes.play import PlayMode
from pushtoo.profiles.schema import Mix
from pushtoo.theme import led
from pushtoo.ui.controls import COLUMNS, Control, Page

MUTE_ROW, SOLO_ROW = 7, 6  # top row, second row (row 0 is the bottom)
ON, OFF = 127, 0
MUTE_COLOR, SOLO_COLOR = "mute", "solo"  # theme tokens


class MixMode(Mode):
    name = "mix"

    def __init__(self, router: MidiRouter, play: PlayMode, settings: Mix, output: str) -> None:
        super().__init__(router)
        self.play = play
        self.faders = [settings.fader_start] * COLUMNS
        self.master_value = settings.fader_start
        self.mute = [False] * COLUMNS
        self.solo = [False] * COLUMNS
        self.apply_settings(settings, output)

    def apply_settings(self, settings: Mix, output: str) -> None:
        self.settings, self.output = settings, output
        self.channel = settings.channel - 1
        self._pages = [Page("Mix", controls=[self._fader(i) for i in range(COLUMNS)])]
        self.master = Control(
            "Master",
            lambda: self.master_value,
            self._set_master,
            format=str,
            color="coral",
        )

    def _fader(self, i: int) -> Control:
        # Chips mirror this column's mute and solo pads, in the same colors.
        def badges() -> list[tuple[str, str | None]]:
            return [
                ("M", MUTE_COLOR if self.mute[i] else None),
                ("S", SOLO_COLOR if self.solo[i] else None),
            ]

        return Control(
            self.settings.names[i],
            lambda: self.faders[i],
            lambda v: self._set_fader(i, v),
            badges=badges,
        )

    def _set_fader(self, i: int, value: int) -> None:
        self.faders[i] = value
        self._cc(self.settings.faders[i], value)

    def _set_master(self, value: int) -> None:
        self.master_value = value
        self._cc(self.settings.master, value)

    def _cc(self, cc: int, value: int) -> None:
        self.router.control_change(self.output, self.channel, cc, value)

    # Pads: top two rows toggle, the rest play.

    def pad_pressed(self, row: int, col: int, velocity: int) -> None:
        if row == MUTE_ROW:
            self.mute[col] = not self.mute[col]
            self._cc(self.settings.mute[col], ON if self.mute[col] else OFF)
        elif row == SOLO_ROW:
            self.solo[col] = not self.solo[col]
            self._cc(self.settings.solo[col], ON if self.solo[col] else OFF)
        else:
            self.play.pad_pressed(row, col, velocity)

    def pad_released(self, row: int, col: int) -> None:
        if row < SOLO_ROW:
            self.play.pad_released(row, col)

    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None:
        if row < SOLO_ROW:
            self.play.pad_aftertouch(row, col, pressure)

    def pad_colors(self) -> list[list[str]]:
        colors = self.play.pad_colors()
        dim = "pt_out_of_scale"
        colors[MUTE_ROW] = [led(MUTE_COLOR) if on else dim for on in self.mute]
        colors[SOLO_ROW] = [led(SOLO_COLOR) if on else dim for on in self.solo]
        return colors

    def panel(self) -> dict:
        return {
            "kind": "mix",
            "title": "Mix",
            "destination": short_port_name(self.output),
            "channel": self.channel,
        }

    def snapshot(self) -> dict:
        return super().snapshot() | {
            "faders": list(self.faders),
            "master": self.master_value,
            "mute": list(self.mute),
            "solo": list(self.solo),
        }

    def restore(self, state: dict) -> None:
        super().restore(state)

        def valid(values, kind) -> bool:
            return (
                isinstance(values, list)
                and len(values) == COLUMNS
                and all(isinstance(v, kind) for v in values)
            )

        if valid(state.get("faders"), int):
            self.faders = [max(0, min(127, v)) for v in state["faders"]]
        if isinstance(state.get("master"), int):
            self.master_value = max(0, min(127, state["master"]))
        if valid(state.get("mute"), bool):
            self.mute = list(state["mute"])
        if valid(state.get("solo"), bool):
            self.solo = list(state["solo"])
