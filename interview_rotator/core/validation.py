"""Input validation rules shared by every interface (Module E)."""

from __future__ import annotations

from typing import Any

from .models import MAX_CONFIDENCE, MIN_CONFIDENCE

MAX_QUESTION_LENGTH = 500
MAX_ANSWER_LENGTH = 2000
MAX_TOPIC_LENGTH = 40


class ValidationError(ValueError):
    """Raised when user input breaks a validation rule."""


def validate_text(value: Any, field_name: str, max_length: int) -> str:
    """Return the stripped text, or raise if it is empty or too long."""
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be text.")
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(f"{field_name} cannot be empty.")
    if len(cleaned) > max_length:
        raise ValidationError(f"{field_name} must be at most {max_length} characters.")
    return cleaned


def validate_question(value: Any) -> str:
    return validate_text(value, "Question", MAX_QUESTION_LENGTH)


def validate_answer(value: Any) -> str:
    return validate_text(value, "Answer", MAX_ANSWER_LENGTH)


def validate_topic(value: Any) -> str:
    """Topic is optional: None/blank becomes an empty string."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError("Topic must be text.")
    cleaned = value.strip()
    if len(cleaned) > MAX_TOPIC_LENGTH:
        raise ValidationError(f"Topic must be at most {MAX_TOPIC_LENGTH} characters.")
    return cleaned


def validate_confidence(value: Any) -> int:
    """Accept an int or a numeric string (e.g. from a form) in the range 1-5."""
    message = f"Confidence must be a whole number from {MIN_CONFIDENCE} to {MAX_CONFIDENCE}."
    if isinstance(value, bool):  # bool is a subclass of int - reject it explicitly
        raise ValidationError(message)
    if isinstance(value, str):
        value = value.strip()
        if not value.lstrip("-").isdigit():
            raise ValidationError(message)
        value = int(value)
    if not isinstance(value, int):
        raise ValidationError(message)
    if not MIN_CONFIDENCE <= value <= MAX_CONFIDENCE:
        raise ValidationError(message)
    return value

