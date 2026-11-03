"""Tests for Module B: Adaptive Rotation Engine."""

import random
import unittest
from collections import Counter

from interview_rotator.core.cards import CardService
from interview_rotator.core.models import Card
from interview_rotator.core.rotation import (
    card_weight,
    pick_next_card,
    selection_probabilities,
)

from .helpers import InMemoryStorage


def make_card(card_id: str, confidence: int, topic: str = "") -> Card:
    return Card(question=f"Q {card_id}", answer="A", topic=topic, confidence=confidence, id=card_id)


class TestWeights(unittest.TestCase):
    def test_weight_is_six_minus_confidence(self):
        weights = [card_weight(make_card("x", c)) for c in range(1, 6)]
        self.assertEqual(weights, [5, 4, 3, 2, 1])

    def test_out_of_range_confidence_is_clamped(self):
        # Defensive: damaged data must never give a zero/negative weight.
        self.assertEqual(card_weight(make_card("x", 0)), 5)
        self.assertEqual(card_weight(make_card("x", 9)), 1)

    def test_exact_probabilities(self):
        cards = [make_card("low", 1), make_card("mid", 3), make_card("high", 5)]
        probs = selection_probabilities(cards)
        self.assertAlmostEqual(probs["low"], 5 / 9)
        self.assertAlmostEqual(probs["mid"], 3 / 9)
        self.assertAlmostEqual(probs["high"], 1 / 9)
        self.assertAlmostEqual(sum(probs.values()), 1.0)

    def test_probabilities_exclude_last_card(self):
        cards = [make_card("a", 1), make_card("b", 1)]
        self.assertEqual(selection_probabilities(cards, last_card_id="a"), {"b": 1.0})


class TestPickNextCard(unittest.TestCase):
    def setUp(self) -> None:
        self.rng = random.Random(42)  # fixed seed -> repeatable results

    def test_empty_list_returns_none(self):
        self.assertIsNone(pick_next_card([], rng=self.rng))

    def test_single_card_is_returned_even_if_just_shown(self):
        only = make_card("only", 3)
        self.assertIs(pick_next_card([only], last_card_id="only", rng=self.rng), only)

    def test_low_confidence_cards_are_picked_more_often(self):
        """Simulation: 1000 picks should roughly match the 5:3:1 weights."""
        cards = [make_card("low", 1), make_card("mid", 3), make_card("high", 5)]
        counts = Counter(pick_next_card(cards, rng=self.rng).id for _ in range(1000))

        self.assertGreater(counts["low"], counts["mid"])
        self.assertGreater(counts["mid"], counts["high"])
        self.assertGreater(counts["high"], 0)  # strong cards still appear
        # Expected ~556 / ~333 / ~111; allow a generous margin for randomness.
        self.assertAlmostEqual(counts["low"] / 1000, 5 / 9, delta=0.06)
        self.assertAlmostEqual(counts["mid"] / 1000, 3 / 9, delta=0.06)
        self.assertAlmostEqual(counts["high"] / 1000, 1 / 9, delta=0.06)

    def test_equal_confidence_gives_roughly_equal_picks(self):
        cards = [make_card(str(i), 3) for i in range(3)]
        counts = Counter(pick_next_card(cards, rng=self.rng).id for _ in range(3000))
        for card in cards:
            self.assertAlmostEqual(counts[card.id] / 3000, 1 / 3, delta=0.05)

    def test_no_card_is_shown_twice_in_a_row(self):
        cards = [make_card("a", 1), make_card("b", 5), make_card("c", 2)]
        last_id = None
        for _ in range(500):
            card = pick_next_card(cards, last_card_id=last_id, rng=self.rng)
            self.assertNotEqual(card.id, last_id)
            last_id = card.id

    def test_rating_change_shifts_the_order(self):
        """After a card is rated higher, it is picked less often."""
        cards = [make_card("a", 1), make_card("b", 1)]
        before = selection_probabilities(cards)["a"]
        cards[0].confidence = 5
        after = selection_probabilities(cards)["a"]
        self.assertAlmostEqual(before, 0.5)
        self.assertAlmostEqual(after, 1 / 6)


class TestServiceNextCard(unittest.TestCase):
    def test_next_card_uses_rotation_and_topic_filter(self):
        service = CardService(InMemoryStorage())
        sql = service.add_card("SQL Q", "A", "SQL", 1)
        service.add_card("Java Q", "A", "Java", 1)
        rng = random.Random(1)

        for _ in range(50):
            self.assertIs(service.next_card(topic="sql", rng=rng), sql)
        self.assertIsNone(service.next_card(topic="Python", rng=rng))
        self.assertIsNone(CardService(InMemoryStorage()).next_card())


if __name__ == "__main__":
    unittest.main()

