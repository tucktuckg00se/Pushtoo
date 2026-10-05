"""Wires Push input to modes, the MIDI router and the renderer."""

import logging
import time

from push2_python import constants as c

from pushtoo.hw.push import PushController
from pushtoo.midi.router import MidiRouter
from pushtoo.modes.play import PlayMode
from pushtoo.render.process import Renderer

TOAST_SECONDS = 1.5

log = logging.getLogger(__name__)


class App:
    def __init__(self) -> None:
        self.router = MidiRouter()
        self.renderer = Renderer()
        self.play = PlayMode(self.router)
        self.shift = False
        self._toast = ("", 0.0)
        # Push events can arrive while PushController is still being constructed.
        self.push: PushController | None = None
        self.renderer.start()
        self.push = PushController(self)
        self.push.setup_hardware()
        self.refresh()

    # PushListener

    def pad_pressed(self, row: int, col: int, velocity: int) -> None:
        self.play.pad_pressed(row, col, velocity)
        self.refresh()

    def pad_released(self, row: int, col: int) -> None:
        self.play.pad_released(row, col)
        self.refresh()

    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None:
        self.play.pad_aftertouch(row, col, pressure)

    def button_pressed(self, name: str) -> None:
        if name == c.BUTTON_SHIFT:
            self.shift = True
        elif name == c.BUTTON_STOP and self.shift:
            self.router.panic()
            self.toast("Panic: all notes off")
        else:
            self.play.button_pressed(name)
        self.refresh()

    def button_released(self, name: str) -> None:
        if name == c.BUTTON_SHIFT:
            self.shift = False

    def encoder_rotated(self, name: str, increment: int) -> None:
        if self.play.encoder_rotated(name, increment):
            self.refresh()

    def push_connected(self) -> None:
        log.info("Push connected")
        self.refresh()

    def push_disconnected(self) -> None:
        log.warning("Push disconnected; releasing held notes")
        self.router.panic()
        self.refresh()

    # Output

    def toast(self, text: str) -> None:
        self._toast = (text, time.monotonic() + TOAST_SECONDS)

    def refresh(self) -> None:
        state = self.play.state()
        state["toast"], state["toast_until"] = self._toast
        self.renderer.update(state)
        if self.push is not None:
            self.push.set_pad_colors(self.play.pad_colors())
            self._update_buttons()

    def _update_buttons(self) -> None:
        for name in (c.BUTTON_NOTE, c.BUTTON_SCALE, c.BUTTON_OCTAVE_UP, c.BUTTON_OCTAVE_DOWN):
            self.push.set_button_color(name, "white")
        upper_1 = "white" if self.play.scale_open else "black"
        self.push.set_button_color(c.BUTTON_UPPER_ROW_1, upper_1)

    def close(self) -> None:
        self.router.close()
        if self.push is not None:
            self.push.close()
        self.renderer.stop()
