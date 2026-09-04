import re

MONEY_RE = re.compile(r"^(0|[1-9][0-9]*)(?:\.([0-9]{1,6}))?$")
COUNT_RE = re.compile(r"^(0|[1-9][0-9]*)$")
POSITIVE_COUNT_RE = re.compile(r"^[1-9][0-9]*$")
INT64_RE = re.compile(r"^-?(0|[1-9][0-9]*)$")
MAX_MICROS = 2**63 - 1
MIN_INT64 = -(2**63)
MAX_INT64 = 2**63 - 1
MICROS_PER_UNIT = 1_000_000


def money_to_micros(value: str) -> int:
    match = MONEY_RE.fullmatch(value)
    if match is None:
        raise ValueError("money must be a non-negative decimal string with at most 6 decimals")
    whole, _, fraction = value.partition(".")
    micros = int(whole) * MICROS_PER_UNIT + int(fraction.ljust(6, "0") or "0")
    if micros > MAX_MICROS:
        raise ValueError("money exceeds int64 micro-unit range")
    return micros


def micros_to_money(value: int) -> str:
    if not 0 <= value <= MAX_MICROS:
        raise ValueError("micro-unit value is outside range")
    return f"{value // MICROS_PER_UNIT}.{value % MICROS_PER_UNIT:06d}"


def validate_count(value: str, *, positive: bool = False) -> str:
    regex = POSITIVE_COUNT_RE if positive else COUNT_RE
    if regex.fullmatch(value) is None:
        qualifier = "positive " if positive else "non-negative "
        raise ValueError(f"count must be a canonical {qualifier}integer string")
    return value


def count_to_int(value: str, *, positive: bool = False) -> int:
    return int(validate_count(value, positive=positive))


def validate_int64_text(value: str) -> str:
    if INT64_RE.fullmatch(value) is None:
        raise ValueError("value must be a canonical signed integer string")
    parsed = int(value)
    if not MIN_INT64 <= parsed <= MAX_INT64:
        raise ValueError("value exceeds signed int64 range")
    return value
