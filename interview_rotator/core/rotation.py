"""Adaptive rotation engine: weighted choice of the next card to practice (Module B).

Each card gets the weight ``6 - confidence``:

    confidence:  1  2  3  4  5
    weight:      5  4  3  2  1

so a card rated 1 is five times as likely to be picked as a card rated 5,
while well-known cards still come up from time to time. The card that was
just shown is skipped (unless it is the only card) to avoid repeats.

The functions are pure (no files, no UI), which makes them easy to test.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

from .models import MAX_CONFIDENCE, MIN_CONFIDENCE, Card

_default_rng = random.Random()


def card_weight(card: Card) -> int:
    """Selection weight of a card: lower confidence -> higher weight."""
    # Clamp in case stored data contains an out-of-range value.
    confidence = max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, card.confidence))
    return MAX_CONFIDENCE + 1 - confidence


def _candidates(cards: Sequence[Card], last_card_id: str | None) -> list[Card]:
    """All cards except the one just shown - unless that would leave nothing."""
    others = [c for c in cards if c.id != last_card_id]
    return others or list(cards)


def selection_probabilities(
    cards: Sequence[Card], last_card_id: str | None = None
) -> dict[str, float]:
    """Chance (0..1) of each card being picked next, keyed by card id."""
    candidates = _candidates(cards, last_card_id)
    total = sum(card_weight(c) for c in candidates)
    return {c.id: card_weight(c) / total for c in candidates}


def pick_next_card(
    cards: Sequence[Card],
    last_card_id: str | None = None,
    rng: random.Random | None = None,
) -> Card | None:
    """Pick the next card to practice, or ``None`` if there are no cards.

    ``rng`` can be a seeded ``random.Random`` to make results repeatable (tests).
    """
    if not cards:
        return None
    candidates = _candidates(cards, last_card_id)
    weights = [card_weight(c) for c in candidates]
    return (rng or _default_rng).choices(candidates, weights=weights, k=1)[0]

