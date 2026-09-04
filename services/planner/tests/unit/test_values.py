import pytest
from hypothesis import given
from hypothesis import strategies as st

from planner.domain.values import (
    MAX_INT64,
    MAX_MICROS,
    MIN_INT64,
    count_to_int,
    micros_to_money,
    money_to_micros,
    validate_count,
    validate_int64_text,
)


@pytest.mark.parametrize(
    ("text", "micros", "canonical"),
    [
        ("0", 0, "0.000000"),
        ("12.3", 12_300_000, "12.300000"),
        ("0.000001", 1, "0.000001"),
        ("9223372036854.775807", MAX_MICROS, "9223372036854.775807"),
    ],
)
def test_money_exact_examples(text: str, micros: int, canonical: str) -> None:
    assert money_to_micros(text) == micros
    assert micros_to_money(micros) == canonical


@pytest.mark.parametrize(
    "value",
    ["", "-1", "+1", "01", ".1", "1.", "1.0000001", "nan", "1e2", " 1"],
)
def test_invalid_money(value: str) -> None:
    with pytest.raises(ValueError):
        money_to_micros(value)


def test_money_overflow_is_rejected() -> None:
    with pytest.raises(ValueError):
        money_to_micros("9223372036854.775808")
    with pytest.raises(ValueError):
        micros_to_money(MAX_MICROS + 1)


@given(st.integers(min_value=0, max_value=MAX_MICROS))
def test_money_roundtrip_property(micros: int) -> None:
    assert money_to_micros(micros_to_money(micros)) == micros


@pytest.mark.parametrize("value", ["0", "1", "999999999999999999999999999999999"])
def test_count_supports_arbitrary_precision(value: str) -> None:
    assert validate_count(value) == value
    assert count_to_int(value) == int(value)


@pytest.mark.parametrize("value", ["", "-1", "+1", "01", "1.0", " 1"])
def test_count_must_be_canonical(value: str) -> None:
    with pytest.raises(ValueError):
        validate_count(value)


def test_positive_count_rejects_zero() -> None:
    with pytest.raises(ValueError):
        count_to_int("0", positive=True)


@pytest.mark.parametrize("value", [str(MIN_INT64), "0", str(MAX_INT64)])
def test_int64_text_boundaries(value: str) -> None:
    assert validate_int64_text(value) == value


@pytest.mark.parametrize("value", [str(MIN_INT64 - 1), str(MAX_INT64 + 1), "01", "+1"])
def test_int64_text_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        validate_int64_text(value)
