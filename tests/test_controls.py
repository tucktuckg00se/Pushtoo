from pushtoo.ui.controls import (
    INCREMENTS_PER_STEP,
    Control,
    Option,
    Page,
    middle_ellipsis,
    pages_view,
)


class Box:
    def __init__(self, value: int = 0) -> None:
        self.value = value

    def get(self) -> int:
        return self.value

    def set(self, value: int) -> None:
        self.value = value


def make_control(box: Box, **kwargs) -> Control:
    return Control("Test", box.get, box.set, **kwargs)


def test_small_increments_accumulate_into_one_step():
    box = Box(5)
    control = make_control(box)
    for _ in range(INCREMENTS_PER_STEP - 1):
        assert not control.turn(1)
    assert control.turn(1)
    assert box.value == 6


def test_turning_back_cancels_accumulated_increments():
    box = Box(5)
    control = make_control(box)
    control.turn(INCREMENTS_PER_STEP - 1)
    control.turn(-(INCREMENTS_PER_STEP - 1))
    assert box.value == 5


def test_negative_turns_step_down():
    box = Box(5)
    make_control(box).turn(-2 * INCREMENTS_PER_STEP)
    assert box.value == 3


def test_fine_needs_four_times_the_turn():
    box = Box(5)
    control = make_control(box)
    assert not control.turn(INCREMENTS_PER_STEP, fine=True)
    control.turn(3 * INCREMENTS_PER_STEP, fine=True)
    assert box.value == 6


def test_value_clamps_to_range_and_reports_no_change_at_edge():
    box = Box(3)
    control = make_control(box, minimum=0, maximum=3)
    assert not control.turn(INCREMENTS_PER_STEP)
    assert box.value == 3


def test_choices_bound_the_range_and_label_the_value():
    box = Box(0)
    control = make_control(box, choices=["Linear", "Soft", "Hard"])
    control.turn(10 * INCREMENTS_PER_STEP)
    assert box.value == 2
    assert control.text() == "Hard"
    assert control.fraction() == 1.0


def test_callable_choices_are_read_at_turn_time():
    ports = ["Pushtoo Out"]
    box = Box(0)
    control = make_control(box, choices=lambda: ports)
    assert not control.turn(INCREMENTS_PER_STEP)
    ports.append("USB MIDI")
    assert control.turn(INCREMENTS_PER_STEP)
    assert control.text() == "USB MIDI"


def test_format_and_view():
    box = Box(3)
    control = make_control(box, minimum=-1, maximum=7, format=lambda v: f"Oct {v}")
    assert control.view() == {
        "name": "Test",
        "text": "Oct 3",
        "fraction": 0.5,
        "bipolar": False,
        "color": None,
    }


def test_page_options_and_views():
    pressed = []
    page = Page(
        "Strip",
        controls=[None, make_control(Box(1))],
        options=[Option("Bend", lambda: pressed.append("bend"), lambda: True)],
    )
    assert page.press_option(0)
    assert not page.press_option(5)
    assert pressed == ["bend"]
    assert page.options_view()[0] == {"label": "Bend", "selected": True}
    assert page.controls_view()[0] is None
    assert page.controls_view()[1]["text"] == "1"
    assert len(page.controls_view()) == 8


def test_pages_view_marks_current():
    view = pages_view([Page("Play"), Page("Strip")], current=1)
    assert view[0] == {"label": "Play", "selected": False}
    assert view[1] == {"label": "Strip", "selected": True}
    assert view[2:] == [None] * 6


def test_middle_ellipsis():
    assert middle_ellipsis("Cutoff", 10) == "Cutoff"
    assert middle_ellipsis("FilterCutoff", 8) == "Filt…off"
    assert len(middle_ellipsis("A very long control name", 9)) == 9


def test_step_scales_each_encoder_step():
    box = Box(36)
    control = make_control(box, minimum=0, maximum=64, step=16)
    control.turn(INCREMENTS_PER_STEP)
    assert box.value == 52
    control.turn(INCREMENTS_PER_STEP)
    assert box.value == 64  # clamped


def test_wrap_continues_from_the_other_end():
    box = Box(0)
    control = make_control(box, choices=["C", "C#", "D"], wrap=True)
    control.turn(-INCREMENTS_PER_STEP)
    assert box.value == 2
    control.turn(INCREMENTS_PER_STEP)
    assert box.value == 0
