"""Profile schema (PRD F3, F5, F16, F18). Channels are 1–16 in YAML, as musicians count.

Every section is optional: anything left out falls back to the PRD's default MIDI map.
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pushtoo.chords import (
    CHORD_SETS,
    DEFAULT_VOICING_BUTTONS,
    FAVORITE_SLOTS,
    ROW_CHORD_KINDS,
    SET_ROWS,
    VOICINGS,
)
from pushtoo.midi.router import OUT_PORT
from pushtoo.music import VELOCITY_CURVES
from pushtoo.rhythm.repeat import RATE_NAMES
from pushtoo.theme import CONTROL_COLOR_NAMES

Channel = Annotated[int, Field(ge=1, le=16)]
CC = Annotated[int, Field(ge=0, le=127)]
ColorName = Literal[CONTROL_COLOR_NAMES]  # type: ignore[valid-type]

# Default MIDI map: MIDI's undefined and general-purpose CCs, so nothing triggers
# sustain, modulation or volume on a synth before the user maps it.
FREE_CCS = (*range(14, 30), *range(102, 118))  # 32 per channel
COLUMN_COLORS = ("red", "orange", "amber", "yellow", "green", "teal", "blue", "violet")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KnobControl(Strict):
    name: str = Field(min_length=1, max_length=32)
    cc: CC
    channel: Channel
    min: int = Field(0, ge=0, le=127)
    max: int = Field(127, ge=0, le=127)
    default: int | None = Field(None, ge=0, le=127)
    color: ColorName = "amber"
    bipolar: bool = False

    @model_validator(mode="after")
    def _range(self) -> Self:
        if self.min >= self.max:
            raise ValueError(f"min ({self.min}) must be below max ({self.max})")
        if self.default is not None and not self.min <= self.default <= self.max:
            raise ValueError(f"default ({self.default}) must be between min and max")
        return self

    @property
    def start_value(self) -> int:
        if self.default is not None:
            return self.default
        return (self.min + self.max + 1) // 2 if self.bipolar else self.min


class KnobPage(Strict):
    name: str = Field(min_length=1, max_length=24)
    controls: list[KnobControl | None] = Field(default_factory=list, max_length=8)


def default_knob_pages() -> list[KnobPage]:
    """8 pages x 8 knobs: pages 1–4 on channel 15, 5–8 on channel 16."""
    pages = []
    for page in range(8):
        controls = []
        for column in range(8):
            index = (page % 4) * 8 + column
            controls.append(
                KnobControl(
                    name=f"Knob {page * 8 + column + 1}",
                    cc=FREE_CCS[index],
                    channel=15 if page < 4 else 16,
                    color=COLUMN_COLORS[column],
                )
            )
        pages.append(KnobPage(name=f"Page {page + 1}", controls=controls))
    return pages


class Knobs(Strict):
    pages: list[KnobPage] = Field(default_factory=default_knob_pages, min_length=1, max_length=8)


def _eight_ccs(first: int):
    """A field of 8 CC numbers, one per column, defaulting to first..first+7."""
    return Field(default_factory=lambda: list(range(first, first + 8)), min_length=8, max_length=8)


class Mix(Strict):
    channel: Channel = 14
    names: list[str] = Field(
        default_factory=lambda: [f"Track {i}" for i in range(1, 9)], min_length=8, max_length=8
    )
    faders: list[CC] = _eight_ccs(102)
    master: CC = 110
    mute: list[CC] = _eight_ccs(14)
    solo: list[CC] = _eight_ccs(22)
    fader_start: CC = 100  # value faders start from until state is saved


class PlayLayout(Strict):
    channel: Channel
    output: str = OUT_PORT


ChordKind = Literal[ROW_CHORD_KINDS]  # type: ignore[valid-type]
ChordRows = Annotated[list[ChordKind], Field(min_length=SET_ROWS, max_length=SET_ROWS)]


VoicingName = Literal[VOICINGS]  # type: ignore[valid-type]


class ChordLayoutSettings(PlayLayout):
    bass_channel: Channel = 3
    # The seven voicings on the side buttons, top to bottom (Latch is the eighth).
    voicing_buttons: Annotated[list[VoicingName], Field(min_length=7, max_length=7)] = Field(
        default_factory=lambda: list(DEFAULT_VOICING_BUTTONS)
    )
    # Your own chord sets: seven row kinds each, bottom to top, above the bass row.
    sets: dict[Annotated[str, Field(min_length=1, max_length=24)], ChordRows] = Field(
        default_factory=dict
    )
    # Up to 7 sets for the Chord page's upper buttons; built-in or from `sets`.
    favorite_sets: list[str] | None = Field(None, max_length=FAVORITE_SLOTS)

    @model_validator(mode="after")
    def _favorites_exist(self) -> Self:
        known = set(CHORD_SETS) | set(self.sets)
        unknown = [name for name in self.favorite_sets or [] if name not in known]
        if unknown:
            raise ValueError(f"no chord set called {unknown[0]!r}")
        return self


class Play(Strict):
    keyboard: PlayLayout = Field(default_factory=lambda: PlayLayout(channel=1))
    drums: PlayLayout = Field(default_factory=lambda: PlayLayout(channel=10))
    chord: ChordLayoutSettings = Field(default_factory=lambda: ChordLayoutSettings(channel=2))
    velocity_curve: Literal[VELOCITY_CURVES] = "Linear"  # type: ignore[valid-type]
    strip: Literal["Pitch bend", "Mod wheel"] = "Pitch bend"


class MidiAction(Strict):
    cc: CC
    channel: Channel
    value: CC = 127


class Action(Strict):
    """A DAW action: a keystroke such as "ctrl+z", or a MIDI CC."""

    keys: str | None = None
    midi: MidiAction | None = None

    @model_validator(mode="after")
    def _one(self) -> Self:
        if (self.keys is None) == (self.midi is None):
            raise ValueError("give exactly one of 'keys' or 'midi'")
        return self


class Undo(Strict):
    undo: Action = Field(default_factory=lambda: Action(keys="ctrl+z"))
    redo: Action = Field(default_factory=lambda: Action(keys="ctrl+shift+z"))


class Rhythm(Strict):
    """Tempo and note repeat defaults (PRD: Rhythm). Sending and following MIDI
    clock are device settings, in Setup."""

    tempo: float = Field(120.0, ge=40, le=240)
    swing: int = Field(50, ge=50, le=75)
    rate: Literal[RATE_NAMES] = "1/16"  # type: ignore[valid-type]


class Profile(Strict):
    name: str = Field("Default", min_length=1, max_length=40)
    output: str = OUT_PORT  # where Knobs, Mix and Undo MIDI go
    theme: str = Field("oc", min_length=1)  # a file name in the themes folder, without .yaml
    play: Play = Field(default_factory=Play)
    knobs: Knobs = Field(default_factory=Knobs)
    mix: Mix = Field(default_factory=Mix)
    undo: Undo = Field(default_factory=Undo)
    rhythm: Rhythm = Field(default_factory=Rhythm)
