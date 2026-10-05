"""Command-line entry point. The app itself lands in M0 week 2."""

import sys

from pushtoo import __version__


def main() -> int:
    print(f"pushtoo {__version__}: not yet runnable; see docs/PRD.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
