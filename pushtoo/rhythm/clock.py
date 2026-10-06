"""The beat grid (PRD: Rhythm). Pure logic on monotonic seconds; no threads or I/O.

Pushtoo leads with its own tempo until MIDI clock arrives, then follows it, and goes
back to leading when the clock stops. Either way the grid is a line through time,
`origin + beats * seconds_per_beat`, so tempo changes keep the current beat in place
and steps never jump.
"""

import math
from dataclasses import dataclass, field

PPQN = 24  # MIDI clock ticks per beat
MIN_TEMPO, MAX_TEMPO = 40.0, 240.0
MIN_SWING, MAX_SWING = 50, 75  # percent: where the offbeat of each pair of steps falls
FOLLOW_TIMEOUT = 2.0  # seconds without ticks before Pushtoo leads again
TAP_RESET = 2.0  # a gap this long starts a new tap sequence
TAPS = 4
SMOOTHING = 24  # ticks averaged for a followed tempo: one beat


@dataclass
class Clock:
    tempo: float = 120.0
    swing: int = MIN_SWING
    running: bool = False  # the transport: Play, or the leader's Start
    origin: float = 0.0  # monotonic time of beat 0
    following: bool = False
    _taps: list[float] = field(default_factory=list)
    _ticks: list[float] = field(default_factory=list)  # recent external tick times
    _tick_count: int = 0  # external ticks since the leader's Start

    @property
    def beat_seconds(self) -> float:
        return 60.0 / self.tempo

    def beat_at(self, now: float) -> float:
        return (now - self.origin) / self.beat_seconds

    def time_of(self, beat: float) -> float:
        return self.origin + beat * self.beat_seconds

    def set_tempo(self, bpm: float, now: float) -> None:
        """Change tempo around `now`, so the beat playing stays where it is."""
        beat = self.beat_at(now)
        self.tempo = max(MIN_TEMPO, min(MAX_TEMPO, bpm))
        self.origin = now - beat * self.beat_seconds

    # Steps

    def steps(self, rate: float, start: float, end: float) -> list[tuple[int, float]]:
        """Grid steps `rate` beats apart in [start, end), as (index, time). Swing moves
        every odd step later: at 50% it's straight, at 75% it sits three quarters of
        the way through its pair."""
        first = int(self.beat_at(start) // rate) - 1
        found = []
        index = max(first, 0)
        while True:
            at = self.step_time(index, rate)
            if at >= end:
                return found
            if at >= start:
                found.append((index, at))
            index += 1

    def step_time(self, index: int, rate: float) -> float:
        beat = index * rate
        if index % 2:
            beat += (self.swing - 50) / 50 * rate  # 75% swing: half a step later
        return self.time_of(beat)

    def ticks(self, start: float, end: float) -> list[float]:
        """MIDI clock tick times in [start, end) while leading. Ticks never swing."""
        if self.following:
            return []
        index = max(0, math.ceil(self.beat_at(start) * PPQN - 1e-9))
        found = []
        while (at := self.time_of(index / PPQN)) < end:
            if at >= start:
                found.append(at)
            index += 1
        return found

    # Transport and tap tempo

    def start(self, now: float) -> None:
        """Play: beat 0 is now."""
        self.running = True
        self.origin = now

    def stop(self) -> None:
        self.running = False

    def tap(self, now: float) -> bool:
        """Tap Tempo. Returns True when the taps set a new tempo."""
        if self._taps and now - self._taps[-1] > TAP_RESET:
            self._taps.clear()
        self._taps = [*self._taps, now][-TAPS:]
        if len(self._taps) < 2:
            return False
        gaps = [b - a for a, b in zip(self._taps, self._taps[1:], strict=False)]
        self.set_tempo(60.0 / (sum(gaps) / len(gaps)), now)
        self.origin = now - round(self.beat_at(now)) * self.beat_seconds  # tap on the beat
        return True

    # Following a leader's MIDI clock

    def external_tick(self, now: float) -> None:
        self.following = True
        self._ticks = [*self._ticks, now][-(SMOOTHING + 1) :]
        self._tick_count += 1
        if len(self._ticks) >= 2:
            span = self._ticks[-1] - self._ticks[0]
            tempo = 60.0 / (span / (len(self._ticks) - 1) * PPQN)
            self.tempo = max(MIN_TEMPO, min(MAX_TEMPO, tempo))
        # The leader's ticks define the beats: tick n of the song is beat n / 24.
        self.origin = now - (self._tick_count - 1) / PPQN * self.beat_seconds

    def external_start(self, now: float) -> None:
        self.following = True
        self.running = True
        self._tick_count = 0
        self.origin = now

    def external_stop(self) -> None:
        self.running = False

    def check_leader(self, now: float) -> bool:
        """Lead again once the clock has stopped arriving. Returns True if it did."""
        if self.following and (not self._ticks or now - self._ticks[-1] > FOLLOW_TIMEOUT):
            self.following = False
            self._ticks.clear()
            return True
        return False
