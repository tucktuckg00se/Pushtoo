"""Push 2 MIDI side: input events, LEDs and hardware settings. The display belongs to
the renderer process.

push2-python calls only the first handler registered per action, so this module
registers exactly one handler for each and forwards to a single listener.
"""

import logging
import threading
from typing import Protocol

import push2_python
from push2_python.exceptions import Push2MIDIeviceNotFound

from pushtoo.hw.colors import LED_COLORS
from pushtoo.music import velocity_curve

RECONNECT_INTERVAL = 1.0  # seconds between attempts to reopen Push's MIDI ports

log = logging.getLogger(__name__)


class PushListener(Protocol):
    def pad_pressed(self, row: int, col: int, velocity: int) -> None: ...
    def pad_released(self, row: int, col: int) -> None: ...
    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None: ...
    def button_pressed(self, name: str) -> None: ...
    def button_released(self, name: str) -> None: ...
    def encoder_rotated(self, name: str, increment: int) -> None: ...
    def encoder_touched(self, name: str) -> None: ...
    def encoder_released(self, name: str) -> None: ...
    def touchstrip(self, value: int) -> None: ...
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
        self.connected = False
        self._button_colors: dict[str, str] = {}  # push2-python resends unchanged buttons
        self._settings: dict = {}
        self._applied: dict = {}
        self._stop = threading.Event()
        self._reconnect_thread: threading.Thread | None = None
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

        @push2_python.on_encoder_touched()
        def _encoder_touched(_, name):
            listener.encoder_touched(name)

        @push2_python.on_encoder_released()
        def _encoder_released(_, name):
            listener.encoder_released(name)

        @push2_python.on_touchstrip()
        def _touchstrip(_, value):
            listener.touchstrip(value)

        @push2_python.on_midi_connected()
        def _connected(_):
            self.connected = True
            if hasattr(self, "push"):  # may fire before __init__ finishes; App sets up then
                self.setup_hardware()
            listener.push_connected()

        @push2_python.on_midi_disconnected()
        def _disconnected(_):
            self.connected = False
            listener.push_disconnected()
            self._start_reconnecting()

    # Hot-plug (PRD N3). After an unplug, push2-python keeps its input port bound to the
    # vanished ALSA client and never reopens it, so close both ports and retry here.

    def _start_reconnecting(self) -> None:
        if self._reconnect_thread is not None and self._reconnect_thread.is_alive():
            return
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop, name="pushtoo-reconnect", daemon=True
        )
        self._reconnect_thread.start()

    def _reconnect_loop(self) -> None:
        log.info("Push MIDI lost; trying to reconnect")
        while not self._stop.wait(RECONNECT_INTERVAL):
            if self.push.last_active_sensing_received is not None:
                return  # active sensing is back; push2-python fires the connected action
            self._close_push_ports()
            try:
                self.push.configure_midi_in()
                self.push.configure_midi_out()
            except Push2MIDIeviceNotFound:
                continue
            log.info("Push MIDI ports reopened; waiting for Push")

    def _close_push_ports(self) -> None:
        for attribute in ("midi_in_port", "midi_out_port"):
            port = getattr(self.push, attribute)
            if port is not None:
                try:
                    port.close()
                except Exception:  # the device is already gone; nothing left to close
                    log.debug("closing stale %s failed", attribute, exc_info=True)
                setattr(self.push, attribute, None)

    # Hardware state

    def setup_hardware(self) -> None:
        """Program palette, pad mode and settings; runs on every (re)connect because a
        replugged Push forgets everything."""
        for name, (index, rgb) in LED_COLORS.items():
            self.push.set_color_palette_entry(
                index, name, rgb=list(rgb), bw=max(rgb), allow_overwrite=True
            )
        self.push.reapply_color_palette()
        self.push.pads.set_polyphonic_aftertouch()
        self.push.pads.reset_current_pads_state()
        self.push.buttons.set_all_buttons_color("black")
        self._button_colors.clear()
        self._applied = {}
        self.apply_settings(self._settings)

    def apply_settings(self, settings: dict) -> None:
        """Send velocity curve and touch strip mode, skipping what is already applied."""
        self._settings = dict(settings)
        if not self.connected:
            return
        curve = settings.get("velocity_curve")
        if curve is not None and self._applied.get("velocity_curve") != curve:
            self.push.pads.set_velocity_curve(velocity_curve(curve))
            self._applied["velocity_curve"] = curve
        strip = settings.get("strip_mode")
        if strip is not None and self._applied.get("strip_mode") != strip:
            if strip == "Mod wheel":
                self.push.touchstrip.set_modulation_wheel_mode()
            else:
                self.push.touchstrip.set_pitch_bend_mode()
            self._applied["strip_mode"] = strip

    def set_pad_colors(self, colors: list[list[str]]) -> None:
        """colors[row][col] with row 0 at the bottom; only changed pads are sent."""
        if self.connected:
            self.push.pads.set_pads_color(list(reversed(colors)))

    def set_button_colors(self, colors: dict[str, str]) -> None:
        if not self.connected:
            return
        for name, color in colors.items():
            if self._button_colors.get(name) != color:
                self.push.buttons.set_button_color(name, color)
                self._button_colors[name] = color

    def close(self) -> None:
        self._stop.set()
        if self.connected:
            self.push.pads.set_all_pads_to_color("black")
            self.push.buttons.set_all_buttons_color("black")
        self.push.stop_active_sensing_thread()
