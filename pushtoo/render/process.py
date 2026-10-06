"""The renderer process (ADR 0001). Owns the Push 2 display; never touches MIDI.

The MIDI process sends plain state dicts with `update()`, which only enqueues and
never waits. The renderer always draws the newest state and drops the rest.
"""

import multiprocessing as mp
import queue
import time

import cairo
import numpy
from push2_python.constants import FRAME_FORMAT_RGB565
from push2_python.display import Push2Display

from pushtoo import logs
from pushtoo.fonts import use_bundled_fonts
from pushtoo.render.screens import HEIGHT, WIDTH, draw_view

MAX_FPS = 60
DISPLAY_RETRY_SECONDS = 2.0  # how often to look for the display when it isn't there
# Push 2 blanks the display if no frame arrives for about 2 s.
KEEPALIVE_SECONDS = 0.5


class _DisplayOnlyPush:
    """The parts of push2_python.Push2 that Push2Display needs, without opening MIDI."""

    simulator_controller = None

    def trigger_action(self, *args, **kwargs) -> None:
        pass


def _run(states: "mp.Queue") -> None:
    use_bundled_fonts()  # before cairo first draws text
    logs.quiet_repeats()  # with no Push, push2-python reports the display on every retry
    owner = _DisplayOnlyPush()  # Push2Display keeps only a weak reference
    display = Push2Display(owner)
    display.function_call_interval_limit_overwrite = DISPLAY_RETRY_SECONDS
    surface = cairo.ImageSurface(cairo.FORMAT_RGB16_565, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)
    state: dict | None = None
    last_frame = 0.0
    while True:
        dirty = False
        timeout = KEEPALIVE_SECONDS
        toast_until = state.get("toast_until", 0) if state else 0
        if toast_until > time.monotonic():
            timeout = min(timeout, toast_until - time.monotonic() + 0.01)
        try:
            state = states.get(timeout=timeout)
            dirty = True
            while True:  # keep only the newest state
                state = states.get_nowait()
        except queue.Empty:
            pass
        if state is None:
            continue
        if state.get("quit"):
            return
        now = time.monotonic()
        toast_expired = 0 < toast_until <= now and last_frame < toast_until
        if not dirty and not toast_expired and now - last_frame < KEEPALIVE_SECONDS:
            continue
        wait = 1 / MAX_FPS - (now - last_frame)
        if wait > 0:
            time.sleep(wait)
        draw_view(ctx, state)
        surface.flush()
        frame = numpy.ndarray(shape=(HEIGHT, WIDTH), dtype=numpy.uint16, buffer=surface.get_data())
        display.display_frame(frame.transpose(), input_format=FRAME_FORMAT_RGB565)
        last_frame = time.monotonic()


class Renderer:
    def __init__(self) -> None:
        self._states: mp.Queue = mp.Queue()
        self._process = mp.Process(target=_run, args=(self._states,), name="pushtoo-render")

    def start(self) -> None:
        self._process.start()

    def update(self, state: dict) -> None:
        self._states.put(state)

    def stop(self) -> None:
        self._states.put({"quit": True})
        self._process.join(2)
        if self._process.is_alive():
            self._process.terminate()
