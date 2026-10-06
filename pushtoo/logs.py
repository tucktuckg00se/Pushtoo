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
            handler.addFilter(RepeatFilter())
