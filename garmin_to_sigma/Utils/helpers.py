"""Small shared helpers."""

import math


def is_finite_number(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def format_duration(seconds: float) -> str:
    hours = int(seconds // 3600)
    remainder = seconds % 3600
    minutes = int(remainder // 60)
    seconds = int(remainder % 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"
