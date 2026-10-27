"""
Input validation helpers shared by the service layer and the API.

They check *types and presence* (so bad input becomes a clean ``VALIDATION_ERROR``
instead of a TypeError/500). Business formats such as the phone pattern or the
gender list stay enforced by the database CHECK constraints on purpose - those are
part of what the project demonstrates.
"""
import math
from datetime import datetime
from typing import Any, Iterable, Optional

from errors import ValidationError

MAX_TEXT = 500


def _label(name: str) -> str:
    return name.replace('_', ' ')


def req_int(value: Any, name: str, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    """An integer (accepts ints and integer-looking strings; rejects bool, floats with fractions)."""
    if isinstance(value, bool) or value is None:
        raise ValidationError(f'{_label(name)} must be a whole number')
    if isinstance(value, float):
        if not value.is_integer():
            raise ValidationError(f'{_label(name)} must be a whole number')
        value = int(value)
    elif isinstance(value, str):
        try:
            value = int(value.strip())
        except ValueError:
            raise ValidationError(f'{_label(name)} must be a whole number')
    elif not isinstance(value, int):
        raise ValidationError(f'{_label(name)} must be a whole number')
    if minimum is not None and value < minimum:
        raise ValidationError(f'{_label(name)} must be at least {minimum}')
    if maximum is not None and value > maximum:
        raise ValidationError(f'{_label(name)} must be at most {maximum}')
    return value


def req_number(value: Any, name: str) -> float:
    """A finite number (accepts numeric strings)."""
    if isinstance(value, bool) or value is None:
        raise ValidationError(f'{_label(name)} must be a number')
    try:
        number = float(value.strip() if isinstance(value, str) else value)
    except (TypeError, ValueError):
        raise ValidationError(f'{_label(name)} must be a number')
    if not math.isfinite(number):
        raise ValidationError(f'{_label(name)} must be a finite number')
    return number


def req_str(value: Any, name: str, max_len: int = MAX_TEXT) -> str:
    """A non-empty string (stripped)."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f'Missing required field: {name}')
    value = value.strip()
    if len(value) > max_len:
        raise ValidationError(f'{_label(name)} is too long (max {max_len} characters)')
    return value


def opt_str(value: Any, name: str, max_len: int = MAX_TEXT) -> Optional[str]:
    """A string or None. Empty / whitespace-only becomes None (forms send '' for blank fields)."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str):
        raise ValidationError(f'{_label(name)} must be text')
    value = value.strip()
    if not value:
        return None
    if len(value) > max_len:
        raise ValidationError(f'{_label(name)} is too long (max {max_len} characters)')
    return value


def req_choice(value: Any, name: str, choices: Iterable[str]) -> str:
    choices = tuple(choices)
    if not isinstance(value, str) or value not in choices:
        raise ValidationError(f'Invalid {_label(name)}: {value!r} (allowed: {", ".join(choices)})')
    return value


def normalize_timestamp(value: Any, name: str = 'slot') -> str:
    """Accept 'YYYY-MM-DD HH:MM[:SS]' (or with a 'T') and return 'YYYY-MM-DD HH:MM:SS'."""
    if not isinstance(value, str):
        raise ValidationError(f'{_label(name)} must be a date and time like 2026-12-31 10:00:00')
    text = value.strip().replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(text, fmt).strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
    raise ValidationError(f'{_label(name)} must be a date and time like 2026-12-31 10:00:00')


def clamp_limit(value: Any, default: int = 100, maximum: int = 1000) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(n, maximum))
