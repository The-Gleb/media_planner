import pytest

from planner.config import Settings


def test_default_settings_are_immutable(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("PLANNER_ADDR", "PLANNER_PORT", "PLANNER_LOG_LEVEL", "PLANNER_VERSION"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert settings == Settings()
    with pytest.raises((AttributeError, TypeError)):
        settings.port = 1  # type: ignore[misc]


def test_settings_accept_valid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLANNER_ADDR", "127.0.0.1")
    monkeypatch.setenv("PLANNER_PORT", "9000")
    monkeypatch.setenv("PLANNER_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("PLANNER_VERSION", "1.2.3")
    assert Settings.from_env() == Settings("127.0.0.1", 9000, "debug", "1.2.3")


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("PLANNER_ADDR", ""),
        ("PLANNER_PORT", "abc"),
        ("PLANNER_PORT", "0"),
        ("PLANNER_PORT", "65536"),
        ("PLANNER_LOG_LEVEL", "verbose"),
        ("PLANNER_VERSION", ""),
    ],
)
def test_invalid_settings_fail_startup(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        Settings.from_env()
