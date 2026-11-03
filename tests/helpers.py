"""Shared test helpers (no external packages needed)."""

from __future__ import annotations

from interview_rotator.core.models import Card


class InMemoryStorage:
    """Fake storage that keeps a copy of the last saved data (no files)."""

    def __init__(self, cards: list[Card] | None = None) -> None:
        self.saved: list[dict] = [c.to_dict() for c in (cards or [])]
        self.save_count = 0

    def load(self) -> list[Card]:
        return [Card.from_dict(d) for d in self.saved]

    def save(self, cards: list[Card]) -> None:
        self.saved = [c.to_dict() for c in cards]
        self.save_count += 1

