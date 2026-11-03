"""Tests for Module A: Card Management (standard library unittest)."""

import unittest

from interview_rotator.core.cards import CardNotFoundError, CardService
from interview_rotator.core.models import Card
from interview_rotator.core.validation import ValidationError

from .helpers import InMemoryStorage


class CardServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = InMemoryStorage()
        self.service = CardService(self.storage)


class TestCreateCard(CardServiceTestCase):
    """FR1 - create cards."""

    def test_add_card_stores_cleaned_values_and_saves(self):
        card = self.service.add_card("  What is a JOIN?  ", " Combines rows. ", " SQL ", 3)

        self.assertEqual(card.question, "What is a JOIN?")
        self.assertEqual(card.answer, "Combines rows.")
        self.assertEqual(card.topic, "SQL")
        self.assertEqual(card.confidence, 3)
        self.assertEqual(card.times_practiced, 0)
        self.assertEqual(self.storage.save_count, 1)
        self.assertEqual(self.storage.saved[0]["id"], card.id)

    def test_add_card_defaults(self):
        card = self.service.add_card("Q", "A")
        self.assertEqual(card.topic, "")
        self.assertEqual(card.confidence, 1)

    def test_card_ids_are_unique(self):
        ids = {self.service.add_card(f"Q{i}", "A").id for i in range(50)}
        self.assertEqual(len(ids), 50)

    def test_add_card_rejects_empty_question_or_answer(self):
        for question, answer in [("", "A"), ("   ", "A"), ("Q", ""), ("Q", "\n\t"), (None, "A")]:
            with self.subTest(question=question, answer=answer):
                with self.assertRaises(ValidationError):
                    self.service.add_card(question, answer)
        self.assertEqual(self.service.list_cards(), [])
        self.assertEqual(self.storage.save_count, 0)

    def test_add_card_rejects_invalid_confidence(self):
        for confidence in [0, 6, -1, "abc", "", 3.5, True, None]:
            with self.subTest(confidence=confidence):
                with self.assertRaises(ValidationError):
                    self.service.add_card("Q", "A", confidence=confidence)

    def test_add_card_accepts_numeric_string_confidence(self):
        # Web forms send values as strings.
        self.assertEqual(self.service.add_card("Q", "A", confidence=" 4 ").confidence, 4)


class TestListAndFilter(CardServiceTestCase):
    """FR2 - list, filter, get."""

    def test_list_and_filter_by_topic_case_insensitive(self):
        self.service.add_card("Q1", "A", "SQL")
        self.service.add_card("Q2", "A", "Java")
        self.service.add_card("Q3", "A", "sql")

        self.assertEqual(len(self.service.list_cards()), 3)
        self.assertEqual({c.question for c in self.service.list_cards("SQL")}, {"Q1", "Q3"})
        self.assertEqual(self.service.list_cards("Python"), [])
        # "SQL" and "sql" are the same topic; the first spelling is used as the label.
        self.assertEqual(self.service.topics(), ["Java", "SQL"])

    def test_stats_group_topics_case_insensitively(self):
        self.service.add_card("Q1", "A", "SQL", 1)
        self.service.add_card("Q2", "A", "sql", 5)
        self.assertEqual(self.service.stats().topic_averages, {"SQL": 3.0})

    def test_get_unknown_card_raises(self):
        with self.assertRaises(CardNotFoundError):
            self.service.get_card("missing")


class TestEditAndDelete(CardServiceTestCase):
    """FR2 - edit and delete."""

    def test_update_card_changes_only_given_fields(self):
        card = self.service.add_card("Q", "A", "SQL", 2)
        self.service.update_card(card.id, answer="New answer", confidence=5)

        updated = self.service.get_card(card.id)
        self.assertEqual(updated.question, "Q")
        self.assertEqual(updated.answer, "New answer")
        self.assertEqual(updated.topic, "SQL")
        self.assertEqual(updated.confidence, 5)

    def test_update_with_invalid_field_leaves_card_unchanged(self):
        card = self.service.add_card("Q", "A", "SQL", 2)
        with self.assertRaises(ValidationError):
            self.service.update_card(card.id, answer="Changed", confidence=9)
        self.assertEqual(self.service.get_card(card.id).answer, "A")

    def test_delete_card(self):
        keep = self.service.add_card("Keep", "A")
        remove = self.service.add_card("Remove", "A")
        self.service.delete_card(remove.id)

        self.assertEqual([c.id for c in self.service.list_cards()], [keep.id])
        self.assertEqual([d["id"] for d in self.storage.saved], [keep.id])
        with self.assertRaises(CardNotFoundError):
            self.service.delete_card(remove.id)


class TestPracticeAndStats(CardServiceTestCase):
    """FR4 + FR5 - practice recording and progress statistics."""

    def test_record_practice_updates_confidence_and_counters(self):
        card = self.service.add_card("Q", "A", confidence=1)
        self.service.record_practice(card.id, 4)
        self.service.record_practice(card.id, "5")

        self.assertEqual(card.confidence, 5)
        self.assertEqual(card.times_practiced, 2)
        self.assertIsNotNone(card.last_practiced)

    def test_stats_empty(self):
        stats = self.service.stats()
        self.assertEqual(stats.total_cards, 0)
        self.assertEqual(stats.average_confidence, 0.0)
        self.assertEqual(stats.topic_averages, {})

    def test_stats_values(self):
        a = self.service.add_card("Q1", "A", "SQL", 1)
        self.service.add_card("Q2", "A", "SQL", 4)
        self.service.add_card("Q3", "A", "", 2)
        self.service.record_practice(a.id, 2)

        stats = self.service.stats()
        self.assertEqual(stats.total_cards, 3)
        self.assertEqual(stats.average_confidence, round((2 + 4 + 2) / 3, 2))
        self.assertEqual(stats.low_confidence_count, 2)
        self.assertEqual(stats.total_practice_attempts, 1)
        self.assertEqual(stats.topic_averages, {"General": 2.0, "SQL": 3.0})


class TestLoading(unittest.TestCase):
    def test_service_loads_existing_cards_from_storage(self):
        existing = Card(question="Saved Q", answer="Saved A", topic="HR", confidence=3)
        service = CardService(InMemoryStorage([existing]))

        loaded = service.get_card(existing.id)
        self.assertEqual(loaded.question, "Saved Q")
        self.assertEqual(loaded.confidence, 3)

    def test_card_from_dict_ignores_unknown_keys(self):
        card = Card.from_dict({"question": "Q", "answer": "A", "extra": "ignored"})
        self.assertEqual(card.question, "Q")


if __name__ == "__main__":
    unittest.main()


