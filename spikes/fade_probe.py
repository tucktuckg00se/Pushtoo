"""Throwaway probe: do Push 2's one-shot LED transitions cross-fade smoothly?

Stop the Pushtoo service first (systemctl --user stop pushtoo), then:

    uv run python spikes/fade_probe.py

The bottom-left 2x2 pads go black → amber → blue → black, twice: first with the
Push's own half-note one-shot transitions (a 1 s fade each, at the default 120 BPM),
then stepped, each color set at once. Watch whether the first round glides.
"""

import time

import push2_python
from push2_python.constants import ANIMATION_ONESHOT_HALF, ANIMATION_STATIC

COLORS = {"probe_amber": (240, 140, 0), "probe_blue": (54, 79, 199)}
PADS = [(7, 0), (7, 1), (6, 0), (6, 1)]  # push2-python counts rows from the top


def show(push, color: str, previous: str, fade: bool) -> None:
    for pad in PADS:
        if fade:
            push.pads.set_pad_color(
                pad, color, animation=ANIMATION_ONESHOT_HALF, animation_end_color=previous
            )
        else:
            push.pads.set_pad_color(pad, color, animation=ANIMATION_STATIC)


def main() -> None:
    push = push2_python.Push2()
    for i, (name, rgb) in enumerate(COLORS.items()):
        # 121 and the default palette's 125 (blue) are clear of Pushtoo's own slots.
        push.set_color_palette_entry((121, 125)[i], name, rgb=list(rgb), allow_overwrite=True)
    push.reapply_color_palette()
    push.pads.set_all_pads_to_color("black")
    try:
        for fade in (True, False):
            print("Hardware fades" if fade else "Stepped, no fade")
            previous = "black"
            for color in ("probe_amber", "probe_blue", "black"):
                show(push, color, previous, fade)
                previous = color
                time.sleep(2.5)
            time.sleep(1.5)
    finally:
        push.pads.set_all_pads_to_color("black")
        push.f_stop.set()


if __name__ == "__main__":
    main()
