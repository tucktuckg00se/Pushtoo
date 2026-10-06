"""Command-line entry point: `pushtoo` or `python -m pushtoo`."""

import argparse
import logging
import signal
import sys
import threading

from pushtoo import __version__


def main() -> int:
    parser = argparse.ArgumentParser(prog="pushtoo")
    parser.add_argument("--version", action="version", version=f"pushtoo {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    from pushtoo import instance, logs

    logs.setup(args.verbose)
    lock = instance.acquire()
    if lock is None:
        print(
            "Pushtoo is already running. If it's the background service, stop it with:\n"
            "  systemctl --user stop pushtoo"
        )
        return 0

    from pushtoo.app import App  # imported late so --version works without hardware libs

    # A thread holding the GIL keeps it for up to this long. 1 ms lets the rhythm
    # scheduler in well within its 20 ms lookahead (tools/clock/jitter.py).
    sys.setswitchinterval(0.001)

    app = App()
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    logging.getLogger("pushtoo").info("Running. Ctrl+C to quit.")
    stop.wait()
    app.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
