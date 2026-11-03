"""Card management service: CRUD, practice recording and statistics (Module A)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from .models import Card
from .rotation import pick_next_card
from .validation import (
    validate_answer,
    validate_confidence,
    validate_question,
    validate_topic,
)

GENERAL_TOPIC = "General"  # label used for cards without a topic


class CardNotFoundError(LookupError):
    """Raised when no card exists with the given id."""


class CardStorage(Protocol):
    """Anything that can load and save the full list of cards (see Module C)."""

    def load(self) -> list[Card]: ...

    def save(self, cards: list[Card]) -> None: ...


@dataclass
class ProgressStats:
    total_cards: int = 0
    average_confidence: float = 0.0
    low_confidence_count: int = 0
    total_practice_attempts: int = 0
    topic_averages: dict[str, float] = field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CardService:
    """Single entry point for card operations, used by both the CLI and the web UI."""

    def __init__(self, storage: CardStorage) -> None:
        self._storage = storage
        self._cards: list[Card] = storage.load()

    # --- queries -------------------------------------------------------
    def list_cards(self, topic: str | None = None) -> list[Card]:
        """Return all cards, optionally filtered by topic (case-insensitive)."""
        if not topic:
            return list(self._cards)
        wanted = topic.strip().lower()
        return [c for c in self._cards if c.topic.lower() == wanted]

    def get_card(self, card_id: str) -> Card:
        for card in self._cards:
            if card.id == card_id:
                return card
        raise CardNotFoundError(f"No card with id '{card_id}'.")

    def next_card(
        self,
        last_card_id: str | None = None,
        topic: str | None = None,
        rng: random.Random | None = None,
    ) -> Card | None:
        """Adaptive choice of the next card to practice (Module B), optionally within one topic."""
        return pick_next_card(self.list_cards(topic), last_card_id, rng)

    def topics(self) -> list[str]:
        """Sorted distinct topics; "SQL" and "sql" count as one (first spelling wins)."""
        return sorted(self._topic_labels().values(), key=str.lower)

    def _topic_labels(self) -> dict[str, str]:
        """Map lower-cased topic -> display label (first spelling seen)."""
        labels: dict[str, str] = {}
        for card in self._cards:
            if card.topic:
                labels.setdefault(card.topic.lower(), card.topic)
        return labels

    # --- commands ------------------------------------------------------
    def add_card(
        self, question: Any, answer: Any, topic: Any = "", confidence: Any = 1
    ) -> Card:
        card = Card(
            question=validate_question(question),
            answer=validate_answer(answer),
            topic=validate_topic(topic),
            confidence=validate_confidence(confidence),
        )
        self._cards.append(card)
        self._save()
        return card

    def update_card(
        self,
        card_id: str,
        *,
        question: Any = None,
        answer: Any = None,
        topic: Any = None,
        confidence: Any = None,
    ) -> Card:
        """Update only the fields that are given (not None)."""
        card = self.get_card(card_id)
        # Validate everything first so a bad field leaves the card unchanged.
        changes: dict[str, Any] = {}
        if question is not None:
            changes["question"] = validate_question(question)
        if answer is not None:
            changes["answer"] = validate_answer(answer)
        if topic is not None:
            changes["topic"] = validate_topic(topic)
        if confidence is not None:
            changes["confidence"] = validate_confidence(confidence)
        for name, value in changes.items():
            setattr(card, name, value)
        self._save()
        return card

    def delete_card(self, card_id: str) -> None:
        card = self.get_card(card_id)
        self._cards.remove(card)
        self._save()

    def record_practice(self, card_id: str, confidence: Any) -> Card:
        """Store the user's new confidence rating after practicing a card."""
        card = self.get_card(card_id)
        card.confidence = validate_confidence(confidence)
        card.times_practiced += 1
        card.last_practiced = _now_iso()
        self._save()
        return card

    # --- statistics ----------------------------------------------------
    def stats(self) -> ProgressStats:
        if not self._cards:
            return ProgressStats()
        labels = self._topic_labels()
        by_topic: dict[str, list[int]] = {}
        for card in self._cards:
            label = labels[card.topic.lower()] if card.topic else GENERAL_TOPIC
            by_topic.setdefault(label, []).append(card.confidence)
        return ProgressStats(
            total_cards=len(self._cards),
            average_confidence=round(
                sum(c.confidence for c in self._cards) / len(self._cards), 2
            ),
            low_confidence_count=sum(1 for c in self._cards if c.is_weak),
            total_practice_attempts=sum(c.times_practiced for c in self._cards),
            topic_averages={
                name: round(sum(scores) / len(scores), 2)
                for name, scores in sorted(by_topic.items(), key=lambda kv: kv[0].lower())
            },
        )

    def _save(self) -> None:
        self._storage.save(self._cards)


