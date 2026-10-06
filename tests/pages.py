"""Open a page by its name, the way a hand would: the button below its label."""


def open_page(target, name: str) -> None:
    """`target` is a PlayMode (or any Mode) or an App, whose current mode is used."""
    mode = getattr(target, "mode", target)
    index = [page.name for page in mode.pages].index(name)
    target.button_pressed(f"Lower Row {index + 1}")


def tap_layout(target) -> None:
    """Press and release Layout: the next layout, which switches on release."""
    from push2_python import constants as c

    target.button_pressed(c.BUTTON_LAYOUT)
    target.button_released(c.BUTTON_LAYOUT)
