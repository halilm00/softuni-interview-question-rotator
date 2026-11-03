"""Tests for Module D: CLI Interface (scripted input, captured output)."""

import contextlib
import io
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from interview_rotator.cli import Cli, confidence_bar
from interview_rotator.core.cards import CardService
from interview_rotator.main import main
from interview_rotator.sample_cards import SAMPLE_CARDS

from .helpers import InMemoryStorage


def run_cli(inputs, service=None, warning=None):
    """Run the CLI with scripted answers. Returns (output text, service)."""
    service = service or CardService(InMemoryStorage())
    answers = iter(inputs)
    output: list[str] = []

    def fake_input(prompt: str) -> str:
        output.append(prompt)
        try:
            return next(answers)
        except StopIteration:
            raise EOFError from None  # like pressing Ctrl+D

    cli = Cli(service, input_fn=fake_input, print_fn=output.append,
              rng=random.Random(7), storage_warning=warning)
    cli.run()
    return "\n".join(output), service


def service_with(*cards):
    service = CardService(InMemoryStorage())
    for question, topic, confidence in cards:
        service.add_card(question, f"Answer to {question}", topic, confidence)
    return service


class TestMenu(unittest.TestCase):
    def test_exit_option(self):
        out, _ = run_cli(["0"])
        self.assertIn("Goodbye! Your progress is saved.", out)

    def test_end_of_input_exits_cleanly(self):
        out, _ = run_cli([])  # Ctrl+D at the first prompt
        self.assertIn("Goodbye!", out)

    def test_unknown_option_shows_error(self):
        out, _ = run_cli(["9", "0"])
        self.assertIn("Unknown option '9'", out)

    def test_empty_app_suggests_samples_and_storage_warning_is_shown(self):
        out, _ = run_cli(["0"], warning="Data file problem: test")
        self.assertIn("choose 7 to load sample questions", out)
        self.assertIn("⚠ Data file problem: test", out)


class TestAddListEditDelete(unittest.TestCase):
    def test_add_valid_card_and_list_it(self):
        out, service = run_cli(["2", "What is SOLID?", "Five design principles", "OOP", "2", "3", "0"])
        self.assertIn("✔ Card added", out)
        self.assertIn("What is SOLID?", out)
        self.assertEqual(service.list_cards()[0].confidence, 2)

    def test_add_uses_default_confidence(self):
        _, service = run_cli(["2", "Q", "A", "", "", "0"])
        self.assertEqual(service.list_cards()[0].confidence, 1)

    def test_add_invalid_card_shows_error_and_saves_nothing(self):
        out, service = run_cli(["2", "   ", "A", "", "", "0"])
        self.assertIn("Card not saved: Question cannot be empty.", out)
        self.assertEqual(service.list_cards(), [])

    def test_edit_keeps_values_on_enter(self):
        service = service_with(("Q1", "SQL", 2))
        card = service.list_cards()[0]
        out, _ = run_cli(["4", card.id, "", "Better answer", "", "", "0"], service)
        self.assertIn("✔ Card updated.", out)
        self.assertEqual((card.question, card.answer, card.topic, card.confidence),
                         ("Q1", "Better answer", "SQL", 2))

    def test_edit_invalid_value_changes_nothing(self):
        service = service_with(("Q1", "SQL", 2))
        card = service.list_cards()[0]
        out, _ = run_cli(["4", card.id, "", "New", "", "8", "0"], service)
        self.assertIn("Card not changed", out)
        self.assertEqual(card.answer, "Answer to Q1")

    def test_delete_requires_confirmation(self):
        service = service_with(("Q1", "", 1))
        card_id = service.list_cards()[0].id
        out, _ = run_cli(["5", card_id, "n", "5", card_id, "y", "0"], service)
        self.assertIn("Nothing deleted.", out)
        self.assertIn("✔ Card deleted.", out)
        self.assertEqual(service.list_cards(), [])

    def test_unknown_card_id(self):
        out, _ = run_cli(["5", "nope", "0"])
        self.assertIn("No card with id 'nope'", out)


class TestPractice(unittest.TestCase):
    def test_practice_flow_records_rating_and_handles_bad_input(self):
        service = service_with(("Q1", "SQL", 1), ("Q2", "SQL", 1))
        # practice, all topics, show answer, bad rating, good rating, show answer, stop
        out, service = run_cli(["1", "", "", "abc", "4", "", "q", "0"], service)

        self.assertIn("Answer: Answer to Q", out)
        self.assertIn("Confidence must be a whole number from 1 to 5.", out)
        self.assertIn("✔ Saved: confidence 1 → 4", out)
        self.assertIn("Session finished: 1 card(s) practiced, average rating 4.0/5.", out)
        self.assertEqual(service.stats().total_practice_attempts, 1)

    def test_practice_by_topic_only_shows_that_topic(self):
        service = service_with(("SQL question", "SQL", 1), ("Java question", "Java", 1))
        # topics are listed as [1] All [2] Java [3] SQL -> choose 3
        inputs = ["1", "3"] + ["", "2"] * 5 + ["q", "0"]
        out, _ = run_cli(inputs, service)
        self.assertIn("SQL question", out)
        self.assertNotIn("Java question", out.split("Topic (Enter = all):", 1)[1])

    def test_practice_never_repeats_same_card_twice_in_a_row(self):
        service = service_with(("Q1", "", 1), ("Q2", "", 5), ("Q3", "", 3))
        out, _ = run_cli(["1"] + ["", "3"] * 20 + ["q", "0"], service)
        shown = [line for line in out.splitlines() if line in {"Q1", "Q2", "Q3"}]
        self.assertEqual(len(shown), 21)
        for a, b in zip(shown, shown[1:]):
            self.assertNotEqual(a, b)

    def test_practice_without_cards(self):
        out, _ = run_cli(["1", "0"])
        self.assertIn("No cards to practice", out)


class TestProgressAndSamples(unittest.TestCase):
    def test_progress_shows_stats_bars_and_weakest_cards(self):
        service = service_with(("Weak one", "SQL", 1), ("Strong one", "Java", 5))
        out, _ = run_cli(["6", "0"], service)
        self.assertIn("Total cards:          2", out)
        self.assertIn("Average confidence:   " + confidence_bar(3.0) + " 3.00/5", out)
        self.assertIn("SQL", out)
        self.assertIn("Focus next on:\n  (1/5) Weak one", out)

    def test_load_samples_only_once(self):
        out, service = run_cli(["7", "7", "0"])
        self.assertIn(f"Added {len(SAMPLE_CARDS)} sample question(s).", out)
        self.assertIn("All sample questions are already loaded.", out)
        self.assertEqual(len(service.list_cards()), len(SAMPLE_CARDS))

    def test_confidence_bar(self):
        self.assertEqual(confidence_bar(5, width=10), "█" * 10)
        self.assertEqual(confidence_bar(2.5, width=10), "█" * 5 + "░" * 5)
        self.assertEqual(confidence_bar(0, width=10), "░" * 10)


class TestMainEndToEnd(unittest.TestCase):
    def test_main_saves_to_json_file_between_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "cards.json"
            with mock.patch("builtins.input", side_effect=["7", "0"]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--data", str(data)]), 0)

            out = io.StringIO()
            with mock.patch("builtins.input", side_effect=["6", "0"]), \
                    contextlib.redirect_stdout(out):
                main(["--data", str(data)])
            self.assertIn(f"Total cards:          {len(SAMPLE_CARDS)}", out.getvalue())


if __name__ == "__main__":
    unittest.main()


