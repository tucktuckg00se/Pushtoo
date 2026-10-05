"""Push 2 MIDI side: input events and LEDs. The display belongs to the renderer process.

push2-python calls only the first handler registered per action, so this module
registers exactly one handler for each and forwards to a single listener.
"""

from typing import Protocol

import push2_python

from pushtoo.hw.colors import LED_COLORS


class PushListener(Protocol):
    def pad_pressed(self, row: int, col: int, velocity: int) -> None: ...
    def pad_released(self, row: int, col: int) -> None: ...
    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None: ...
    def button_pressed(self, name: str) -> None: ...
    def button_released(self, name: str) -> None: ...
    def encoder_rotated(self, name: str, increment: int) -> None: ...
    def push_connected(self) -> None: ...
    def push_disconnected(self) -> None: ...


def pad_ij_to_row_col(pad_ij: tuple[int, int]) -> tuple[int, int]:
    """push2-python's (0, 0) is the top-left pad; Pushtoo's row 0 is the bottom row."""
    i, j = pad_ij
    return 7 - i, j


def row_col_to_pad_ij(row: int, col: int) -> tuple[int, int]:
    return 7 - row, col


class PushController:
    def __init__(self, listener: PushListener) -> None:
        self.listener = listener
        self._button_colors: dict[str, str] = {}  # push2-python resends unchanged buttons
        self._register_handlers()
        self.push = push2_python.Push2()

    def _register_handlers(self) -> None:
        listener = self.listener

        @push2_python.on_pad_pressed()
        def _pad_pressed(_, pad_n, pad_ij, velocity):
            listener.pad_pressed(*pad_ij_to_row_col(pad_ij), velocity)

        @push2_python.on_pad_released()
        def _pad_released(_, pad_n, pad_ij, velocity):
            listener.pad_released(*pad_ij_to_row_col(pad_ij))

        @push2_python.on_pad_aftertouch()
        def _pad_aftertouch(_, pad_n, pad_ij, pressure):
            if pad_ij is not None:  # None for channel aftertouch
                listener.pad_aftertouch(*pad_ij_to_row_col(pad_ij), pressure)

        @push2_python.on_button_pressed()
        def _button_pressed(_, name):
            listener.button_pressed(name)

        @push2_python.on_button_released()
        def _button_released(_, name):
            listener.button_released(name)

        @push2_python.on_encoder_rotated()
        def _encoder_rotated(_, name, increment):
            listener.encoder_rotated(name, increment)

        @push2_python.on_midi_connected()
        def _connected(_):
            if hasattr(self, "push"):  # may fire before __init__ finishes; App sets up then
                self.setup_hardware()
            listener.push_connected()

        @push2_python.on_midi_disconnected()
        def _disconnected(_):
            listener.push_disconnected()

    def setup_hardware(self) -> None:
        """Program the LED palette and pad mode; runs on every (re)connect."""
        for name, (index, rgb) in LED_COLORS.items():
            self.push.set_color_palette_entry(
                index, name, rgb=list(rgb), bw=max(rgb), allow_overwrite=True
            )
        self.push.reapply_color_palette()
        self.push.pads.set_polyphonic_aftertouch()
        self.push.pads.reset_current_pads_state()
        self.push.buttons.set_all_buttons_color("black")
        self._button_colors.clear()

    def set_pad_colors(self, colors: list[list[str]]) -> None:
        """colors[row][col] with row 0 at the bottom; only changed pads are sent."""
        self.push.pads.set_pads_color(list(reversed(colors)))

    def set_button_color(self, name: str, color: str) -> None:
        if self._button_colors.get(name) != color:
            self.push.buttons.set_button_color(name, color)
            self._button_colors[name] = color

    def close(self) -> None:
        self.push.pads.set_all_pads_to_color("black")
        self.push.buttons.set_all_buttons_color("black")
        self.push.stop_active_sensing_thread()
