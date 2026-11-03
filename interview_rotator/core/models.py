"""Card data model (Module A)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

MIN_CONFIDENCE = 1
MAX_CONFIDENCE = 5
LOW_CONFIDENCE_THRESHOLD = 2  # scores <= this count as "weak" cards


def new_card_id() -> str:
    """Return a short, unique card id."""
    return uuid4().hex[:8]


@dataclass
class Card:
    """A single interview question with its answer and practice state."""

    question: str
    answer: str
    topic: str = ""
    confidence: int = MIN_CONFIDENCE
    times_practiced: int = 0
    last_practiced: str | None = None  # ISO-8601 UTC timestamp
    id: str = field(default_factory=new_card_id)

    @property
    def is_weak(self) -> bool:
        return self.confidence <= LOW_CONFIDENCE_THRESHOLD

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Card:
        """Build a card from a dict, ignoring unknown keys."""
        known = {name for name in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

