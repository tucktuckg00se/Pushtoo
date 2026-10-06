"""Push 2 MIDI side: input events, LEDs and hardware settings. The display belongs to
the renderer process.

push2-python calls only the first handler registered per action, so this module
registers exactly one handler for each and forwards to a single listener.
"""

import logging
import threading
from typing import Protocol

import mido
import push2_python
from push2_python.constants import PUSH2_SYSEX_END_BYTES, PUSH2_SYSEX_PREFACE_BYTES
from push2_python.exceptions import Push2MIDIeviceNotFound

from pushtoo.setup import RESPONSES
from pushtoo.theme import DEFAULT_THEME, Theme, led_palette

RECONNECT_INTERVAL = 1.0  # seconds between attempts to reopen Push's MIDI ports

log = logging.getLogger(__name__)


class PushListener(Protocol):
    def pad_pressed(self, row: int, col: int, velocity: int) -> None: ...
    def pad_released(self, row: int, col: int) -> None: ...
    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None: ...
    def channel_pressure(self, pressure: int) -> None: ...
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
        self.theme: Theme = DEFAULT_THEME
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
            if pad_ij is None:  # channel aftertouch: the whole pad surface
                listener.channel_pressure(pressure)
            else:
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
        self._program_palette()
        self.push.pads.set_polyphonic_aftertouch()
        self.push.pads.reset_current_pads_state()
        self.push.buttons.set_all_buttons_color("black")
        self._button_colors.clear()
        self._applied = {}
        self.apply_settings(self._settings)

    def _program_palette(self) -> None:
        for name, (index, rgb) in led_palette(self.theme).items():
            self.push.set_color_palette_entry(
                index, name, rgb=list(rgb), bw=max(rgb), allow_overwrite=True
            )
        self.push.reapply_color_palette()

    def set_theme(self, theme: Theme) -> None:
        """New LED colors; the caller's next refresh re-sends every pad and button."""
        self.theme = theme
        if self.connected:
            self._program_palette()
            self.push.pads.reset_current_pads_state()
            self._button_colors.clear()

    def apply_settings(self, settings: dict) -> None:
        """Send the pad feel, aftertouch, brightness and touch strip settings that
        changed since they were last sent. A replug resends everything (setup_hardware
        clears what was applied)."""
        self._settings = dict(settings)
        if not self.connected:
            return
        for key, value in settings.items():
            if self._applied.get(key) == value:
                continue
            send = self._SENDERS.get(key)
            if send is not None:
                send(self, value)
            self._applied[key] = value

    def _sysex(self, *data: int) -> None:
        message = PUSH2_SYSEX_PREFACE_BYTES + list(data) + PUSH2_SYSEX_END_BYTES
        self.push.send_midi_to_push(mido.Message.from_bytes(message))

    def _send_velocity_table(self, table: tuple[int, ...]) -> None:
        self.push.pads.set_velocity_curve(list(table))

    def _send_response(self, response: str) -> None:
        self._sysex(0x28, 0, 0, RESPONSES.index(response))  # scene 0, track 0: every pad

    def _send_aftertouch(self, mode: str) -> None:
        if mode == "Channel":
            self.push.pads.set_channel_aftertouch()
        else:  # "Off" keeps poly mode; Pushtoo just stops forwarding it
            self.push.pads.set_polyphonic_aftertouch()

    def _send_aftertouch_range(self, bounds: tuple[int, int]) -> None:
        self.push.pads.set_channel_aftertouch_range(*bounds)

    def _send_led_brightness(self, value: int) -> None:
        self._sysex(0x06, value)

    def _send_display_brightness(self, value: int) -> None:
        self._sysex(0x08, value & 0x7F, value >> 7)

    def _send_strip_mode(self, strip: str) -> None:
        if strip == "Mod wheel":
            self.push.touchstrip.set_modulation_wheel_mode()
        else:
            self.push.touchstrip.set_pitch_bend_mode()

    _SENDERS = {
        "velocity_table": _send_velocity_table,
        "response": _send_response,
        "aftertouch": _send_aftertouch,
        "aftertouch_range": _send_aftertouch_range,
        "led_brightness": _send_led_brightness,
        "display_brightness": _send_display_brightness,
        "strip_mode": _send_strip_mode,
    }

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
