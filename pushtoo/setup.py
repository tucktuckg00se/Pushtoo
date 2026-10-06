"""Device-wide settings from Setup mode: pad feel, aftertouch, brightness, clock.

They belong to the Push and the person playing it, not to a profile, so they're saved
once in the session state rather than per profile. Pure logic; PushController sends
the hardware parts and the App applies the rest.
"""

from dataclasses import asdict, dataclass, fields

RESPONSES = ("Regular", "Reduced", "Low")  # Push's own pad sensitivity (sysex 0x28)
AFTERTOUCH_MODES = ("Poly", "Channel", "Off")
# The old profile curves, as Dynamics values, for a first run before Setup is used.
CURVE_DYNAMICS = {"Linear": 0, "Soft": -5, "Hard": 5}
AFTERTOUCH_LOW, AFTERTOUCH_HIGH = 401, 2048  # Push's aftertouch pressure range

# Field limits, inclusive; strings list their choices.
LIMITS: dict[str, tuple[int, int] | tuple[str, ...]] = {
    "sensitivity": (1, 10),
    "dynamics": (-10, 10),
    "min_velocity": (1, 127),
    "max_velocity": (1, 127),
    "response": RESPONSES,
    "aftertouch": AFTERTOUCH_MODES,
    "aftertouch_start": (0, 99),
    "aftertouch_full": (1, 100),
    "pad_brightness": (0, 100),
    "screen_brightness": (0, 100),
}


@dataclass
class DeviceSettings:
    sensitivity: int = 5  # higher reaches full velocity with less force
    dynamics: int = 0  # below 0 soft (light touches louder), above 0 hard
    min_velocity: int = 1
    max_velocity: int = 127
    response: str = "Regular"
    aftertouch: str = "Poly"
    aftertouch_start: int = 0  # percent of Push's pressure range where it starts
    aftertouch_full: int = 100  # percent where it reaches 127
    pad_brightness: int = 100  # percent
    screen_brightness: int = 100  # percent
    send_clock: bool = True  # MIDI clock on Pushtoo Out while leading
    follow_clock: bool = True  # follow clock arriving on Pushtoo In

    def snapshot(self) -> dict:
        return asdict(self)

    @classmethod
    def restore(cls, saved: object, fallback: "DeviceSettings") -> "DeviceSettings":
        """Saved values that are valid, the fallback's for the rest."""
        settings = DeviceSettings(**asdict(fallback))
        if not isinstance(saved, dict):
            return settings
        for f in fields(cls):
            value = saved.get(f.name)
            limit = LIMITS.get(f.name)
            if isinstance(getattr(settings, f.name), bool):
                if isinstance(value, bool):
                    setattr(settings, f.name, value)
            elif isinstance(limit, tuple) and limit and isinstance(limit[0], str):
                if value in limit:
                    setattr(settings, f.name, value)
            elif isinstance(value, int) and not isinstance(value, bool):
                low, high = limit  # type: ignore[misc]
                if low <= value <= high:
                    setattr(settings, f.name, value)
        settings.min_velocity = min(settings.min_velocity, settings.max_velocity)
        settings.aftertouch_start = min(settings.aftertouch_start, settings.aftertouch_full - 1)
        return settings


def velocity_table(settings: DeviceSettings) -> list[int]:
    """Push 2's velocity table: 128 force steps mapped to velocities.

    Push applies it in hardware, so feel costs nothing on the note path. Sensitivity
    scales force (5 is neutral), Dynamics bends the curve (0 is straight), and the
    result spans Min to Max velocity.
    """
    gain = 2 ** ((settings.sensitivity - 5) / 2.5)
    exponent = 2 ** (settings.dynamics / 5)
    low, high = settings.min_velocity, settings.max_velocity
    table = []
    for step in range(128):
        force = min(1.0, step / 127 * gain)
        table.append(max(1, min(127, round(low + (high - low) * force**exponent))))
    return table


def hardware(settings: DeviceSettings) -> dict:
    """What PushController sends to the Push for these settings."""
    return {
        "velocity_table": tuple(velocity_table(settings)),
        "response": settings.response,
        "aftertouch": settings.aftertouch,
        "aftertouch_range": aftertouch_range(settings),
        "led_brightness": round(127 * settings.pad_brightness / 100),
        "display_brightness": round(255 * settings.screen_brightness / 100),
    }


def aftertouch_range(settings: DeviceSettings) -> tuple[int, int]:
    """Push's pressure range for aftertouch, from the percentages."""
    span = AFTERTOUCH_HIGH - AFTERTOUCH_LOW

    def at(percent: int) -> int:
        return AFTERTOUCH_LOW + round(span * percent / 100)

    return at(settings.aftertouch_start), max(
        at(settings.aftertouch_full), at(settings.aftertouch_start) + 1
    )
