"""Tests for Module C: Data Persistence Layer (JSON file storage)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from interview_rotator.core.cards import CardService
from interview_rotator.core.models import Card
from interview_rotator.core.storage import JsonStorage


class StorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.path = self.dir / "data" / "cards.json"

    def write_raw(self, text: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, encoding="utf-8")

    def backups(self) -> list[Path]:
        return sorted(self.path.parent.glob("cards.json.corrupt-*"))


class TestMissingFile(StorageTestCase):
    def test_missing_file_is_created_with_no_cards(self):
        storage = JsonStorage(self.path)
        self.assertEqual(storage.load(), [])
        self.assertTrue(self.path.exists())  # parent folder created too
        self.assertEqual(json.loads(self.path.read_text()), {"version": 1, "cards": []})
        self.assertIsNone(storage.warning)


class TestRoundTrip(StorageTestCase):
    def test_save_and_load_keeps_all_fields_and_unicode(self):
        cards = [
            Card("Какво е JOIN?", "Свързва редове от таблици.", "SQL", 2,
                 times_practiced=3, last_practiced="2026-11-03T10:00:00+00:00"),
            Card("Explain OOP", "Objects, classes...", "", 5),
        ]
        JsonStorage(self.path).save(cards)

        loaded = JsonStorage(self.path).load()
        self.assertEqual([c.to_dict() for c in loaded], [c.to_dict() for c in cards])
        # Non-English text is stored readable, not as \u escapes.
        self.assertIn("Какво е JOIN?", self.path.read_text(encoding="utf-8"))

    def test_card_service_data_survives_restart(self):
        service = CardService(JsonStorage(self.path))
        card = service.add_card("What is REST?", "An architectural style.", "Web", 1)
        service.record_practice(card.id, 4)

        restarted = CardService(JsonStorage(self.path))  # simulates closing the app
        loaded = restarted.get_card(card.id)
        self.assertEqual(loaded.confidence, 4)
        self.assertEqual(loaded.times_practiced, 1)
        self.assertEqual(restarted.stats().total_practice_attempts, 1)


class TestCorruptedFile(StorageTestCase):
    def test_invalid_json_is_backed_up_and_app_continues(self):
        self.write_raw("{ this is not json")
        storage = JsonStorage(self.path)

        self.assertEqual(storage.load(), [])
        self.assertIn("not valid JSON", storage.warning)
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.backups()[0].read_text(), "{ this is not json")
        # The main file is valid again.
        self.assertEqual(json.loads(self.path.read_text())["cards"], [])

    def test_wrong_structure_is_treated_as_corrupted(self):
        for content in ['[1, 2, 3]', '{"cards": "oops"}', '"just a string"']:
            with self.subTest(content=content):
                self.write_raw(content)
                storage = JsonStorage(self.path)
                self.assertEqual(storage.load(), [])
                self.assertIn("list of cards", storage.warning)

    def test_invalid_cards_are_skipped_but_valid_ones_kept(self):
        good = Card("Q", "A", "SQL", 3).to_dict()
        bad_entries = [
            {"id": "x1", "answer": "missing question"},
            {"id": "x2", "question": "Q", "answer": "A", "confidence": 9},
            {"question": "no id", "answer": "A"},
            "not a dict",
        ]
        self.write_raw(json.dumps({"version": 1, "cards": [good, *bad_entries]}))
        storage = JsonStorage(self.path)

        loaded = storage.load()
        self.assertEqual([c.id for c in loaded], [good["id"]])
        self.assertIn("4 invalid card(s) were skipped", storage.warning)
        self.assertEqual(len(self.backups()), 1)  # original data kept for the user

    def test_repeated_recoveries_never_overwrite_backups(self):
        contents = ["{ broken 1", "{ broken 2", "{ broken 3"]
        for text in contents:
            self.write_raw(text)
            JsonStorage(self.path).load()  # all within the same second
        self.assertEqual(sorted(b.read_text() for b in self.backups()), contents)

    def test_damaged_counters_are_reset(self):
        entry = Card("Q", "A").to_dict() | {"times_practiced": "lots", "last_practiced": 5}
        self.write_raw(json.dumps({"version": 1, "cards": [entry]}))
        card = JsonStorage(self.path).load()[0]
        self.assertEqual(card.times_practiced, 0)
        self.assertIsNone(card.last_practiced)


class TestSafeSave(StorageTestCase):
    def test_failed_save_leaves_old_file_intact_and_no_temp_files(self):
        storage = JsonStorage(self.path)
        storage.save([Card("Original", "A")])
        before = self.path.read_text()

        with mock.patch("interview_rotator.core.storage.json.dump", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                storage.save([Card("New", "A")])

        self.assertEqual(self.path.read_text(), before)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()


