"""Wires Push input to modes, the MIDI router and the renderer."""

import logging
import time

from push2_python import constants as c

from pushtoo.hw.push import PushController
from pushtoo.midi.router import MidiRouter
from pushtoo.modes.play import PlayMode
from pushtoo.render.process import Renderer

TOAST_SECONDS = 1.5
UNTIL_CLEARED = 24 * 3600.0
ENCODERS = {f"Track{i + 1} Encoder": i for i in range(8)}
SHIFT_ACTIONS = ["Stop: Panic (all notes off)", "Turn an encoder: fine adjust"]
# Modes that arrive in later milestones (PRD Core experience).
LATER_MODES = {
    c.BUTTON_DEVICE: "Knobs",
    c.BUTTON_MIX: "Mix",
    c.BUTTON_SESSION: "Launch",
    c.BUTTON_SETUP: "Setup",
}

log = logging.getLogger(__name__)


class App:
    def __init__(self, renderer: Renderer | None = None) -> None:
        self.router = MidiRouter()
        self.renderer = renderer or Renderer()
        self.play = PlayMode(self.router)
        self.shift = False
        self.shift_used = False  # turning an encoder while Shift is held hides the overlay
        self.peek: int | None = None
        self._toast = ("", 0.0)
        self._lost_push = False
        # Push events can arrive while PushController is still being constructed.
        self.push: PushController | None = None
        self.renderer.start()
        self.push = PushController(self)
        self.push.setup_hardware()
        self.refresh()

    # PushListener. Pad handlers send MIDI first; refresh() runs after.

    def pad_pressed(self, row: int, col: int, velocity: int) -> None:
        self.play.pad_pressed(row, col, velocity)
        self.refresh()

    def pad_released(self, row: int, col: int) -> None:
        self.play.pad_released(row, col)
        self.refresh()

    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None:
        self.play.pad_aftertouch(row, col, pressure)

    def touchstrip(self, value: int) -> None:
        self.play.touchstrip(value)

    def button_pressed(self, name: str) -> None:
        if name == c.BUTTON_SHIFT:
            self.shift, self.shift_used = True, False
        elif name == c.BUTTON_STOP and self.shift:
            self.router.panic()
            self.toast("Panic: all notes off")
        elif name in LATER_MODES:
            self.toast(f"{LATER_MODES[name]} mode is coming soon")
        else:
            self.play.button_pressed(name)
        self.refresh()

    def button_released(self, name: str) -> None:
        if name == c.BUTTON_SHIFT:
            self.shift = False
            self.refresh()

    def encoder_rotated(self, name: str, increment: int) -> None:
        index = ENCODERS.get(name)
        if index is None:
            return
        if self.shift:
            self.shift_used = True
        if self.play.encoder_turned(index, increment, fine=self.shift) or self.shift:
            self.refresh()

    def encoder_touched(self, name: str) -> None:
        index = ENCODERS.get(name)
        if index is not None and self.play.control_at(index) is not None:
            self.peek = index
            self.refresh()

    def encoder_released(self, name: str) -> None:
        if ENCODERS.get(name) == self.peek:
            self.peek = None
            self.refresh()

    def push_connected(self) -> None:
        log.info("Push connected")
        if self._lost_push:
            self._lost_push = False
            self.toast("Push connected")
        self.refresh()

    def push_disconnected(self) -> None:
        log.warning("Push disconnected; releasing held notes")
        self._lost_push = True
        self.router.panic()
        self.toast("Reconnecting to Push…", UNTIL_CLEARED)
        self.refresh()

    # Output

    def toast(self, text: str, seconds: float = TOAST_SECONDS) -> None:
        self._toast = (text, time.monotonic() + seconds)

    def view(self) -> dict:
        view = self.play.view()
        if self.peek is not None and (control := self.play.control_at(self.peek)):
            view["peek"] = control.view()
        elif self.shift and not self.shift_used:
            view["shift"] = SHIFT_ACTIONS
        view["toast"], view["toast_until"] = self._toast
        return view

    def refresh(self) -> None:
        self.renderer.update(self.view())
        if self.push is not None:
            self.push.set_pad_colors(self.play.pad_colors())
            buttons = self.play.button_colors()
            buttons[c.BUTTON_SHIFT] = "white" if self.shift else "dark_gray"
            buttons[c.BUTTON_STOP] = "white" if self.shift else "black"
            self.push.set_button_colors(buttons)
            self.push.apply_settings(self.play.hardware_settings())

    def close(self) -> None:
        self.router.close()
        if self.push is not None:
            self.push.close()
        self.renderer.stop()
