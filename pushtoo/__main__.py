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
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from pushtoo.app import App  # imported late so --version works without hardware libs

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
