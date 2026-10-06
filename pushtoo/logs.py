"""Logging for a program that may run for days as a background service.

Some conditions repeat while they last: with no Push plugged in, push2-python reports
the missing display every time it retries. Each distinct message goes to the log once,
and again only after it has been quiet for a while, so the journal records changes
rather than a heartbeat.
"""

import logging
import time

QUIET_SECONDS = 600.0


class RepeatFilter(logging.Filter):
    def __init__(self, quiet: float = QUIET_SECONDS, clock=time.monotonic) -> None:
        super().__init__()
        self.quiet = quiet
        self._clock = clock
        self._last: dict[tuple[str, int, str], float] = {}

    def filter(self, record: logging.LogRecord) -> bool:
        key = (record.name, record.levelno, record.getMessage())
        now = self._clock()
        last = self._last.get(key)
        self._last[key] = now  # a message that keeps repeating stays quiet
        return last is None or now - last >= self.quiet


class PushMissingFilter(logging.Filter):
    """push2-python reports a Push that isn't plugged in as a bare ERROR ("Could not
    initialize Push 2 Display: "). That's an expected state, so it's said plainly."""

    PARTS = {"MIDI in": "MIDI", "MIDI out": "MIDI", "Display": "display"}

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        prefix = "Could not initialize Push 2 "
        if record.levelno == logging.ERROR and message.startswith(prefix):
            part = message[len(prefix) :].split(":")[0]
            record.levelno, record.levelname = logging.INFO, "INFO"
            record.msg, record.args = f"Push 2 {self.PARTS.get(part, part)} not found yet", None
        return True


def setup(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    quiet_repeats()


def quiet_repeats() -> None:
    """Add the repeat filter to the root handlers (safe to call again, as the renderer
    process does after it starts)."""
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, RepeatFilter) for f in handler.filters):
            handler.addFilter(PushMissingFilter())  # first, so repeats compare the new text
            handler.addFilter(RepeatFilter())
