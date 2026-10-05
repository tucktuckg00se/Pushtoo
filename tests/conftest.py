"""Fixtures shared across test modules."""

import pytest

from pushtoo.app import App
from pushtoo.keys import parse_keys
from tests.test_router import make_router


class FakeRenderer:
    def __init__(self) -> None:
        self.views: list[dict] = []

    def start(self) -> None: ...

    def update(self, view: dict) -> None:
        self.views.append(view)

    def stop(self) -> None: ...


class FakeKeys:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, spec: str) -> bool:
        parse_keys(spec)
        self.sent.append(spec)
        return True

    def close(self) -> None: ...


@pytest.fixture
def env(tmp_path):
    """Builds Apps that share a config folder and state file, like restarts would."""
    apps = []

    def make(profile_text: str | None = None) -> tuple[App, list]:
        config = tmp_path / "profiles"
        if profile_text is not None:
            config.mkdir(exist_ok=True)
            (config / "default.yaml").write_text(profile_text)
        router, virtual, *_ = make_router()
        app = App(
            renderer=FakeRenderer(),
            config_dir=config,
            state_path=tmp_path / "state.yaml",
            router=router,
            keys=FakeKeys(),
            connect=False,
        )
        apps.append(app)
        return app, virtual.sent

    yield make
    for app in apps:
        app.close()
