"""What running as a background service needs: one instance, quiet logs, a scheduler
that rests when idle, and finding a Push that's plugged in later."""

import logging
import threading

import pytest
from push2_python import constants as c

from pushtoo import instance
from pushtoo.app import CLOCK_TICK, IDLE_TICK, RHYTHM_TICK
from pushtoo.logs import RepeatFilter


def test_only_one_pushtoo_at_a_time(tmp_path):
    path = tmp_path / "pushtoo.lock"
    first = instance.acquire(path)
    assert first is not None
    assert instance.acquire(path) is None  # a second one is turned away
    first.close()  # the first quits (or crashes): the lock is free again
    again = instance.acquire(path)
    assert again is not None
    again.close()


def test_repeated_log_lines_are_written_once_until_they_go_quiet():
    now = [0.0]
    repeat = RepeatFilter(quiet=60, clock=lambda: now[0])

    def record(message):
        return logging.LogRecord("push2", logging.ERROR, __file__, 1, message, None, None)

    assert repeat.filter(record("Could not initialize Push 2 Display"))
    for _ in range(100):
        now[0] += 2  # a retry every two seconds
        assert not repeat.filter(record("Could not initialize Push 2 Display"))
    assert repeat.filter(record("something else"))
    now[0] += 61  # quiet for a minute: worth saying again
    assert repeat.filter(record("Could not initialize Push 2 Display"))


def test_the_scheduler_rests_when_nothing_is_timed(env):
    app, _ = env()
    app.device.send_clock = False
    assert app.rhythm_interval() == IDLE_TICK
    app.device.send_clock = True
    assert app.rhythm_interval() == CLOCK_TICK
    app.button_pressed(c.BUTTON_PLAY)
    assert app.rhythm_interval() == RHYTHM_TICK


def test_input_wakes_the_resting_scheduler(env):
    app, _ = env()
    app._rhythm_wake.clear()
    app.pad_pressed(0, 0, 100)
    assert app._rhythm_wake.is_set()


def test_a_push_plugged_in_later_is_still_found(monkeypatch):
    from pushtoo.hw import push as hw

    started = threading.Event()

    class NoPush:  # push2_python.Push2 with nothing plugged in
        last_active_sensing_received = None

    monkeypatch.setattr(hw.push2_python, "Push2", NoPush)
    monkeypatch.setattr(hw.PushController, "_start_reconnecting", lambda self: started.set())
    hw.PushController(listener=object())
    assert started.is_set()


@pytest.mark.parametrize("signal_name", ["SIGTERM"])
def test_stopping_the_service_sends_panic_first(env, signal_name):
    app, sent = env()
    app.pad_pressed(0, 0, 100)
    app.close()  # what __main__ calls on SIGTERM
    assert [0xB0, 123, 0] in sent  # All Notes Off on channel 1
    assert sent.index([0x80, 48, 0]) < sent.index([0xB0, 123, 0])


def test_a_missing_push_is_logged_as_information_not_an_error():
    from pushtoo.logs import PushMissingFilter

    record = logging.LogRecord(
        "root", logging.ERROR, __file__, 1, "Could not initialize Push 2 Display: ", None, None
    )
    PushMissingFilter().filter(record)
    assert record.levelno == logging.INFO
    assert record.getMessage() == "Push 2 display not found yet"
