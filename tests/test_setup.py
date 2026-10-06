"""Device settings: the velocity table, aftertouch range and saved values."""

import pytest

from pushtoo.setup import CURVE_DYNAMICS, DeviceSettings, aftertouch_range, velocity_table


def table(**changes):
    return velocity_table(DeviceSettings(**changes))


def test_defaults_are_the_old_linear_curve_within_a_step():
    old_linear = [max(1, step) for step in range(128)]
    assert all(abs(a - b) <= 1 for a, b in zip(table(), old_linear, strict=True))


@pytest.mark.parametrize("dynamics", [-10, -5, 0, 5, 10])
@pytest.mark.parametrize("sensitivity", [1, 5, 10])
def test_every_table_rises_and_stays_in_midi_range(sensitivity, dynamics):
    values = table(sensitivity=sensitivity, dynamics=dynamics)
    assert len(values) == 128
    assert all(1 <= v <= 127 for v in values)
    assert values == sorted(values)


def test_soft_and_hard_are_dynamics_five_either_way():
    soft, linear, hard = (table(dynamics=CURVE_DYNAMICS[n]) for n in ("Soft", "Linear", "Hard"))
    assert soft[32] > linear[32] > hard[32]
    assert soft[32] == round(1 + 126 * (32 / 127) ** 0.5)


def test_sensitivity_reaches_full_velocity_with_less_force():
    assert table(sensitivity=10)[64] == 127
    assert table(sensitivity=1)[64] < table()[64]


def test_min_and_max_bound_the_table():
    values = table(min_velocity=40, max_velocity=100)
    assert values[0] == 40 and values[-1] == 100


def test_aftertouch_range_maps_percentages_onto_push_pressure():
    assert aftertouch_range(DeviceSettings()) == (401, 2048)
    low, high = aftertouch_range(DeviceSettings(aftertouch_start=50, aftertouch_full=50))
    assert 401 < low < high


def test_restore_keeps_valid_values_and_falls_back_for_the_rest():
    saved = {
        "sensitivity": 8,
        "dynamics": 99,
        "response": "Low",
        "aftertouch": "Sideways",
        "send_clock": False,
        "min_velocity": 120,
        "max_velocity": 90,
    }
    settings = DeviceSettings.restore(saved, DeviceSettings(dynamics=-5))
    assert settings.sensitivity == 8 and settings.dynamics == -5
    assert settings.response == "Low" and settings.aftertouch == "Poly"
    assert settings.send_clock is False
    assert settings.min_velocity <= settings.max_velocity == 90
