"""Play mode, Keyboard layout (PRD F2). Minimal M0 version: in-key or chromatic
fourths, root, scale and octave, with a basic scale overlay on the Scale button."""

from push2_python import constants as c

from pushtoo.hw.colors import PAD_ROLE_COLORS
from pushtoo.midi.router import MidiRouter
from pushtoo.music import NOTE_NAMES, ROWS, SCALE_NAMES, KeyboardLayout, note_name

SCALE_ENCODER = c.ENCODER_TRACK1_ENCODER
ROOT_ENCODER = c.ENCODER_TRACK2_ENCODER
# Encoders send small increments per detent; this many make one step.
ENCODER_STEP = 6


class PlayMode:
    def __init__(self, router: MidiRouter, channel: int = 0) -> None:
        self.router = router
        self.channel = channel
        self.layout = KeyboardLayout()
        self.scale_open = False
        self.played_once = False
        self._encoder_accum: dict[str, int] = {}

    # Pads: these run on the MIDI input thread, so send first and keep the rest light.

    def pad_pressed(self, row: int, col: int, velocity: int) -> None:
        note = self.layout.note_at(row, col)
        if note is None:
            return
        self.router.note_on((row, col), self.channel, note, velocity)
        self.played_once = True

    def pad_released(self, row: int, col: int) -> None:
        self.router.note_off((row, col))

    def pad_aftertouch(self, row: int, col: int, pressure: int) -> None:
        self.router.poly_aftertouch((row, col), pressure)

    # Buttons and encoders

    def button_pressed(self, name: str) -> bool:
        """Returns True if the layout changed and pads need recoloring."""
        if name == c.BUTTON_OCTAVE_UP:
            self.layout.shift_octave(+1)
        elif name == c.BUTTON_OCTAVE_DOWN:
            self.layout.shift_octave(-1)
        elif name == c.BUTTON_SCALE:
            self.scale_open = not self.scale_open
            return False
        elif name == c.BUTTON_UPPER_ROW_1 and self.scale_open:
            self.layout.in_key = not self.layout.in_key
        else:
            return False
        return True

    def encoder_rotated(self, name: str, increment: int) -> bool:
        if not self.scale_open or name not in (SCALE_ENCODER, ROOT_ENCODER):
            return False
        total = self._encoder_accum.get(name, 0) + increment
        steps = int(total / ENCODER_STEP)  # truncates toward zero in both directions
        self._encoder_accum[name] = total - steps * ENCODER_STEP
        if steps == 0:
            return False
        if name == SCALE_ENCODER:
            self.layout.step_scale(steps)
        else:
            self.layout.step_root(steps)
        return True

    # Output for LEDs and the renderer

    def pad_colors(self) -> list[list[str]]:
        sounding = self.router.sounding_notes()
        colors = []
        for row in range(ROWS):
            line = []
            for col in range(8):
                note = self.layout.note_at(row, col)
                if note is None:
                    line.append("pt_off")
                elif note in sounding:
                    line.append("pt_held")
                else:
                    line.append(PAD_ROLE_COLORS[self.layout.role_of(note)])
            colors.append(line)
        return colors

    def state(self) -> dict:
        return {
            "mode": "play",
            "key_name": self.layout.key_name,
            "scale": self.layout.scale,
            "scale_names": list(SCALE_NAMES),
            "root_name": NOTE_NAMES[self.layout.root],
            "in_key": self.layout.in_key,
            "octave": self.layout.octave,
            "channel": self.channel,
            "scale_open": self.scale_open,
            "played_once": self.played_once,
            "held_names": [note_name(n) for n in sorted(self.router.sounding_notes())],
        }
