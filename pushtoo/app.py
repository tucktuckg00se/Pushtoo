"""Wires Push input to modes, profiles, the MIDI router and the renderer.

Every input handler and the profile watcher run under one lock, so a profile reload
on the watcher thread never races a pad callback on the MIDI input thread. The lock
is uncontended almost always, so it costs nanoseconds on the pad path.
"""

import functools
import logging
import threading
import time
from pathlib import Path

from push2_python import constants as c

from pushtoo.hw.push import PushController
from pushtoo.keys import KeySender, describe
from pushtoo.midi.router import MidiRouter
from pushtoo.modes.base import Mode, row_index
from pushtoo.modes.browse import BrowseMode
from pushtoo.modes.chord import SCENE_BUTTONS
from pushtoo.modes.knobs import KnobsMode
from pushtoo.modes.mix import MixMode
from pushtoo.modes.play import PlayMode
from pushtoo.profiles.loader import ProfileError, ProfileStore, default_config_dir
from pushtoo.profiles.schema import Action, Profile
from pushtoo.profiles.state import StateSaver, StateStore, default_state_path
from pushtoo.render.process import Renderer
from pushtoo.theme import DEFAULT_THEME, Theme
from pushtoo.themes.loader import ThemeFileError, ThemeStore

TOAST_SECONDS = 1.5
ERROR_TOAST_SECONDS = 6.0
UNTIL_CLEARED = 24 * 3600.0
ENCODERS = {f"Track{i + 1} Encoder": i for i in range(8)}
MASTER = "master"
MODE_BUTTONS = {
    c.BUTTON_NOTE: "play",
    c.BUTTON_DEVICE: "knobs",
    c.BUTTON_MIX: "mix",
}
BACK_BUTTON = "Lower Row 8"  # leaves Mix and Browse
LATER_MODES = {c.BUTTON_SETUP: "Setup"}
# Play's own buttons act on Play from any mode, since pads keep playing there.
PLAY_BUTTONS = {
    c.BUTTON_LAYOUT,
    c.BUTTON_ACCENT,
    c.BUTTON_OCTAVE_UP,
    c.BUTTON_OCTAVE_DOWN,
    *SCENE_BUTTONS,  # Chord layout voicings
}

log = logging.getLogger(__name__)


def locked(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapper


class App:
    def __init__(
        self,
        renderer: Renderer | None = None,
        config_dir: Path | None = None,
        state_path: Path | None = None,
        router: MidiRouter | None = None,
        keys: KeySender | None = None,
        connect: bool = True,
    ) -> None:
        self._lock = threading.RLock()
        # Push events can arrive while PushController is still being constructed.
        self.push: PushController | None = None
        self.router = router or MidiRouter()
        self.renderer = renderer or Renderer()
        self.profiles = ProfileStore(config_dir or default_config_dir())
        self.state = StateStore(state_path or default_state_path())
        self.shift = self.delete = False
        self.shift_used = False  # turning an encoder while Shift is held hides the overlay
        self.delete_used = False  # likewise touching an encoder while Delete is held
        self.peek: int | str | None = None
        self._toast = ("", 0.0)
        self._lost_push = False

        self.profile = self._initial_profile()
        # Themes live next to the profiles folder.
        self.themes = ThemeStore(self.profiles.config_dir.parent / "themes")
        self.theme: Theme = DEFAULT_THEME
        self._theme_name: str | None = None
        self._select_theme(self.profile.theme)
        self.play = PlayMode(self.router)
        self.play.apply_settings(self.profile.play)
        self.knobs = KnobsMode(self.router, self.play, self.profile.knobs, self.profile.output)
        self.mix = MixMode(self.router, self.play, self.profile.mix, self.profile.output)
        self.browse = BrowseMode(
            self.router,
            self.play,
            list_profiles=self.profiles.paths,
            active=lambda: self.profiles.path,
            load=self.load_profile,
        )
        self.modes: dict[str, Mode] = {
            "play": self.play,
            "knobs": self.knobs,
            "mix": self.mix,
            "browse": self.browse,
        }
        self.mode: Mode = self.play
        self._previous_mode: Mode = self.play
        self._restore_state()

        self.keys = keys or KeySender(on_error=self._key_error)
        self.saver = StateSaver(self.state, self._snapshot)
        self.saver.start()
        if connect:
            self.renderer.start()
            self.push = PushController(self)
            self.push.theme = self.theme
            self.push.setup_hardware()
        self.profiles.watch(self._profile_changed)
        self.themes.watch(self._theme_changed)
        self.refresh()

    # Profiles and state

    def _initial_profile(self) -> Profile:
        last = self.state.last_profile
        candidates = [self.profiles.config_dir / last] if last else []
        candidates.append(self.profiles.config_dir / "default.yaml")
        for path in (p for p in candidates if p.exists()):
            try:
                return self.profiles.select(path)
            except ProfileError as error:
                self.toast(f"Profile error: {error}", ERROR_TOAST_SECONDS)
        return Profile()

    def _select_theme(self, name: str) -> None:
        """Use a profile's theme; the built-in Open Color theme if it can't load."""
        if name == self._theme_name:
            return
        self._theme_name = name
        try:
            self._use_theme(self.themes.select(name))
        except ThemeFileError as error:
            self._use_theme(DEFAULT_THEME)
            self.toast(f"Theme error: {error}", ERROR_TOAST_SECONDS)

    def _use_theme(self, theme: Theme) -> None:
        self.theme = theme
        if self.push is not None:
            self.push.set_theme(theme)

    @locked
    def _theme_changed(self, result: Theme | ThemeFileError) -> None:
        if isinstance(result, ThemeFileError):
            self.toast(f"Theme error: {result}", ERROR_TOAST_SECONDS)
        else:
            self._use_theme(result)
        self.refresh()

    def _apply_profile(self, profile: Profile) -> None:
        self._select_theme(profile.theme)
        self.profile = profile
        self.play.apply_settings(profile.play)
        self.knobs.apply_settings(profile.knobs, profile.output)
        self.mix.apply_settings(profile.mix, profile.output)

    def _restore_state(self) -> None:
        saved = self.state.for_profile(self.profile.name)
        for name, mode in self.modes.items():
            if isinstance(saved.get(name), dict):
                mode.restore(saved[name])
        if saved.get("mode") in ("play", "knobs", "mix"):
            self.mode = self.modes[saved["mode"]]

    @locked
    def _snapshot(self) -> tuple[str, str, dict]:
        mode = self._previous_mode if self.mode is self.browse else self.mode
        snapshot: dict = {"mode": mode.name}
        for name in ("play", "knobs", "mix"):
            snapshot[name] = self.modes[name].snapshot()
        return self.profiles.path.name, self.profile.name, snapshot

    @locked
    def _profile_changed(self, result: Profile | ProfileError) -> None:
        if isinstance(result, ProfileError):
            self.toast(f"Profile error: {result}", ERROR_TOAST_SECONDS)
        else:
            self._apply_profile(result)
            self.toast(f"Profile reloaded: {result.name}")
        self.refresh()

    @locked
    def load_profile(self, path: Path) -> None:
        self.saver.flush()  # keep the outgoing profile's state
        try:
            profile = self.profiles.select(path)
        except ProfileError as error:
            self.toast(f"Profile error: {error}", ERROR_TOAST_SECONDS)
            self.refresh()
            return
        self.router.panic()
        self._apply_profile(profile)
        self._restore_state()
        if self.mode is self.browse:
            self.mode = self._previous_mode
        self.toast(f"Loaded {profile.name}")
        self.saver.mark_dirty()
        self.refresh()

    # PushListener. Pad handlers send MIDI first; refresh() runs after.

    @locked
    def pad_pressed(self, row: int, col: int, velocity: int) -> None:
        self.mode.pad_pressed(row, col, velocity)
        self.refresh()

    @locked
    def pad_released(self, row: int, col: int) -> None:
        self.mode.pad_released(row, col)
        self.refresh()

    @locked
    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None:
        self.mode.pad_aftertouch(row, col, pressure)

    @locked
    def touchstrip(self, value: int) -> None:
        self.play.touchstrip(value)

    @locked
    def button_pressed(self, name: str) -> None:
        if name == c.BUTTON_SHIFT:
            self.shift, self.shift_used = True, False
        elif name == c.BUTTON_DELETE:
            self.delete, self.delete_used = True, False
        elif name == c.BUTTON_STOP and self.shift:
            self.router.panic()
            self.toast("Panic: all notes off")
        elif name == c.BUTTON_UNDO:
            self._undo(redo=self.shift)
        elif name == BACK_BUTTON and self.mode in (self.mix, self.browse):
            self._switch(self._previous_mode)
        elif name in MODE_BUTTONS:
            mode = self.modes[MODE_BUTTONS[name]]
            if mode is self.mix and self.mode is self.mix:
                mode = self._previous_mode  # Mix's own button closes it again, like Browse
            self._switch(mode)
        elif name == c.BUTTON_BROWSE:
            if self.mode is self.browse:
                self._switch(self._previous_mode)
            else:
                self.browse.refresh()
                self._switch(self.browse)
        elif name in LATER_MODES:
            self.toast(f"{LATER_MODES[name]} mode is coming soon")
        elif name == c.BUTTON_SCALE:
            self._switch(self.play)
            self.play.button_pressed(name)
        elif self.play.layout_held and (index := row_index(name, "Upper")) is not None:
            self.play.select_layout(index)
        elif name in PLAY_BUTTONS:
            self.play.button_pressed(name)
            self._describe_side_button(name)
        elif self.shift and isinstance(self.mode, KnobsMode) and name.startswith("Upper Row "):
            self.shift_used = True
            if sent := self.mode.learn(int(name.removeprefix("Upper Row ")) - 1):
                self.toast(sent)
        else:
            self.mode.button_pressed(name)
        self.refresh()

    @locked
    def button_released(self, name: str) -> None:
        if name == c.BUTTON_LAYOUT:
            self.play.button_released(name)
            self.refresh()
        elif name in SCENE_BUTTONS:
            if self.play.button_released(name):
                self._describe_side_button(name)
                self.refresh()
        elif name == c.BUTTON_SHIFT:
            self.shift = False
            self.refresh()
        elif name == c.BUTTON_DELETE:
            self.delete = False
            self.refresh()

    def _describe_side_button(self, name: str) -> None:
        """The voicing rail is on the Chord screen only; elsewhere a toast says what a
        side button did."""
        if name in SCENE_BUTTONS and self.play.in_chord and self.mode is not self.play:
            self.toast(self.play.chord.describe_side_button(SCENE_BUTTONS.index(name)))

    def _switch(self, mode: Mode) -> None:
        if mode is self.mode:
            return
        if self.mode in (self.play, self.knobs):
            self._previous_mode = self.mode  # extras return to the core mode below them
        self.mode = mode
        self.peek = None

    def _undo(self, redo: bool) -> None:
        label = "Redo" if redo else "Undo"
        action: Action = self.profile.undo.redo if redo else self.profile.undo.undo
        if action.keys is not None:
            if self.keys.send(action.keys):
                self.toast(f"{label} → {describe(action.keys)}")
        elif action.midi is not None:
            midi = action.midi
            self.router.control_change(self.profile.output, midi.channel - 1, midi.cc, midi.value)
            self.toast(f"{label} → CC {midi.cc} ch {midi.channel}")

    def _key_error(self, message: str) -> None:
        with self._lock:
            self.toast(message, ERROR_TOAST_SECONDS)
            self.refresh()

    @locked
    def encoder_rotated(self, name: str, increment: int) -> None:
        if self.shift:
            self.shift_used = True
        if name == c.ENCODER_MASTER_ENCODER:
            changed = self.mix.master.turn(increment, fine=self.shift)
        elif (index := ENCODERS.get(name)) is not None:
            changed = self.mode.encoder_turned(index, increment, fine=self.shift)
        else:
            return
        if changed or self.shift:
            self.refresh()

    @locked
    def encoder_touched(self, name: str) -> None:
        if name == c.ENCODER_MASTER_ENCODER:
            self.peek = MASTER
        elif (index := ENCODERS.get(name)) is not None and self.mode.control_at(index):
            if self.delete and hasattr(self.mode, "reset"):
                self.delete_used = True
                if self.mode.reset(index):
                    self.toast(f"Reset {self.mode.control_at(index).name}")
            self.peek = index
        else:
            return
        self.refresh()

    @locked
    def encoder_released(self, name: str) -> None:
        key = MASTER if name == c.ENCODER_MASTER_ENCODER else ENCODERS.get(name)
        if key == self.peek:
            self.peek = None
            self.refresh()

    @locked
    def push_connected(self) -> None:
        log.info("Push connected")
        if self._lost_push:
            self._lost_push = False
            self.toast("Push connected")
        self.refresh()

    @locked
    def push_disconnected(self) -> None:
        log.warning("Push disconnected; releasing held notes")
        self._lost_push = True
        self.router.panic()
        self.toast("Reconnecting to Push…", UNTIL_CLEARED)
        self.refresh()

    # Output

    def toast(self, text: str, seconds: float = TOAST_SECONDS) -> None:
        self._toast = (text, time.monotonic() + seconds)

    def _shift_actions(self) -> list[str]:
        actions = ["Stop: Panic (all notes off)", "Undo: Redo", "Turn an encoder: fine adjust"]
        if isinstance(self.mode, KnobsMode):
            actions.insert(0, "Upper button: Learn Assist (sends that CC alone)")
        return actions

    def view(self) -> dict:
        view = self.mode.view()
        if self.peek == MASTER:
            view["peek"] = self.mix.master.view()
        elif self.peek is not None and (control := self.mode.control_at(self.peek)):
            view["peek"] = control.view()
        elif self.play.layout_held:
            lines = ["Button above a layout: switch to it", "Tap Layout: the next layout"]
            view["overlay"] = {"title": "Layout", "lines": lines}
        elif self.shift and not self.shift_used:
            view["overlay"] = {"title": "Shift", "lines": self._shift_actions()}
        elif self.delete and not self.delete_used and hasattr(self.mode, "reset"):
            lines = ["Touch a knob: reset it to its default"]
            view["overlay"] = {"title": "Delete", "lines": lines}
        if self.shift and isinstance(self.mode, KnobsMode):
            view["upper"] = self.mode.learn_labels()
        if self.play.layout_held:
            view["upper"] = self.play.layout_choices()
        if self.mode in (self.mix, self.browse):
            # Extras sit on top of a core mode; say how to get back, next to the button.
            label = f"‹ {self._previous_mode.name.capitalize()}"
            view["lower"] = [*view["lower"][:7], {"label": label, "selected": False}]
        view["theme"] = dict(self.theme)
        view["toast"], view["toast_until"] = self._toast
        return view

    def button_colors(self) -> dict[str, str]:
        colors = self.mode.button_colors()
        for button, mode_name in MODE_BUTTONS.items():
            colors[button] = "white" if self.mode.name == mode_name else "dark_gray"
        colors[c.BUTTON_BROWSE] = "white" if self.mode is self.browse else "dark_gray"
        for button in LATER_MODES:
            colors[button] = "black"
        for button in (PLAY_BUTTONS - set(SCENE_BUTTONS)) | {c.BUTTON_SCALE}:
            colors.setdefault(button, "dark_gray")
        colors |= self.play.scene_colors()  # the voicing stays visible from any mode
        colors[c.BUTTON_SESSION] = "black"  # unassigned: Pushtoo has no clip launching
        colors[c.BUTTON_SHIFT] = "white" if self.shift else "dark_gray"
        colors[c.BUTTON_STOP] = "white" if self.shift else "black"
        colors[c.BUTTON_UNDO] = "dark_gray"
        colors[c.BUTTON_DELETE] = "white" if self.delete else "dark_gray"
        if self.mode in (self.mix, self.browse):
            colors[BACK_BUTTON] = "white"
        if self.play.layout_held:
            for i, item in enumerate(self.play.layout_choices()):
                colors[f"Upper Row {i + 1}"] = Mode.row_color(item)
        return colors

    def refresh(self) -> None:
        self.renderer.update(self.view())
        self.saver.mark_dirty()
        if self.push is not None:
            self.push.set_pad_colors(self.mode.pad_colors())
            self.push.set_button_colors(self.button_colors())
            self.push.apply_settings(self.play.hardware_settings())

    def close(self) -> None:
        self.profiles.stop()
        self.themes.stop()
        self.saver.stop()
        self.keys.close()
        self.router.close()
        if self.push is not None:
            self.push.close()
        self.renderer.stop()
