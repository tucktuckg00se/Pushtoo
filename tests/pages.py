"""Open a page by its name, the way a hand would: the button below its label."""


def open_page(target, name: str) -> None:
    """`target` is a PlayMode (or any Mode) or an App, whose current mode is used."""
    mode = getattr(target, "mode", target)
    index = [page.name for page in mode.pages].index(name)
    target.button_pressed(f"Lower Row {index + 1}")
