import pytest
from hypothesis import given
from hypothesis import strategies as st

from planner.domain.models import Horizon
from planner.domain.uniform import allocate_uniformly


@pytest.mark.parametrize(
    ("budget", "horizon", "channels", "expected"),
    [
        (5, Horizon(0, 2), ["b", "a"], [2, 1, 1, 1]),
        (0, Horizon(4, 6), ["a"], [0, 0]),
        (1, Horizon(0, 2), ["b", "a"], [1, 0, 0, 0]),
    ],
)
def test_uniform_examples(
    budget: int, horizon: Horizon, channels: list[str], expected: list[int]
) -> None:
    values = allocate_uniformly(budget, horizon, channels)
    assert [item.budget_micros for item in values] == expected


@given(
    budget=st.integers(min_value=0, max_value=2**63 - 1),
    from_hour=st.integers(min_value=0, max_value=20),
    duration=st.integers(min_value=1, max_value=30),
    channels=st.lists(
        st.from_regex(r"^[a-z][a-z0-9_]{0,5}$", fullmatch=True),
        min_size=1,
        max_size=10,
        unique=True,
    ),
)
def test_uniform_allocation_properties(
    budget: int, from_hour: int, duration: int, channels: list[str]
) -> None:
    horizon = Horizon(from_hour, from_hour + duration)
    first = allocate_uniformly(budget, horizon, channels)
    second = allocate_uniformly(budget, horizon, list(reversed(channels)))
    assert first == second
    assert len(first) == duration * len(channels)
    assert sum(item.budget_micros for item in first) == budget
    assert (
        max(item.budget_micros for item in first) - min(item.budget_micros for item in first) <= 1
    )
    assert [(item.hour, item.channel_id) for item in first] == sorted(
        (item.hour, item.channel_id) for item in first
    )
    assert len({(item.hour, item.channel_id) for item in first}) == len(first)


@pytest.mark.parametrize(
    ("horizon", "channels"), [(Horizon(0, 0), ["a"]), (Horizon(1, 0), ["a"]), (Horizon(0, 1), [])]
)
def test_uniform_rejects_empty_dimensions(horizon: Horizon, channels: list[str]) -> None:
    with pytest.raises(ValueError):
        allocate_uniformly(0, horizon, channels)
