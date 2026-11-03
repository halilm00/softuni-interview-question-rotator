"""Command-line interface (Module D) - a thin layer over CardService.

Run with:  python3 -m interview_rotator      (entry point: main.py)
"""

from __future__ import annotations

import random
from collections.abc import Callable

from .core.cards import GENERAL_TOPIC, CardNotFoundError, CardService
from .core.models import MAX_CONFIDENCE, Card
from .core.validation import ValidationError, validate_confidence
from .sample_cards import load_sample_cards

BAR_WIDTH = 20
QUIT_WORDS = {"q", "quit", "exit"}


class _Quit(Exception):
    """Raised when input ends (Ctrl+D) to leave the app cleanly."""


def confidence_bar(value: float, width: int = BAR_WIDTH) -> str:
    """Text bar for a 0-5 confidence value, e.g. ``████████░░░░``."""
    filled = max(0, min(width, round(value / MAX_CONFIDENCE * width)))
    return "█" * filled + "░" * (width - filled)


def shorten(text: str, limit: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


class Cli:
    MENU = [
        ("1", "Practice"),
        ("2", "Add a card"),
        ("3", "List cards"),
        ("4", "Edit a card"),
        ("5", "Delete a card"),
        ("6", "Progress"),
        ("7", "Load sample questions"),
        ("0", "Exit"),
    ]

    def __init__(
        self,
        service: CardService,
        input_fn: Callable[[str], str] | None = None,
        print_fn: Callable[[str], None] | None = None,
        color: bool = False,
        rng: random.Random | None = None,
        storage_warning: str | None = None,
    ) -> None:
        self.service = service
        # Resolve the builtins at call time (not as default arguments), so they
        # can be replaced in tests with unittest.mock.patch("builtins.input").
        self.input_fn = input_fn or (lambda prompt: input(prompt))
        self.print_fn = print_fn or (lambda text: print(text))
        self.color = color
        self.rng = rng
        self.storage_warning = storage_warning

    # --- output helpers ------------------------------------------------
    def _style(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.color else text

    def _say(self, text: str = "") -> None:
        self.print_fn(text)

    def _title(self, text: str) -> None:
        self._say()
        self._say(self._style(f"== {text} ==", "1;36"))

    def _ok(self, text: str) -> None:
        self._say(self._style(f"✔ {text}", "32"))

    def _error(self, text: str) -> None:
        self._say(self._style(f"✖ {text}", "31"))

    def _ask(self, prompt: str) -> str:
        try:
            return self.input_fn(prompt).strip()
        except EOFError:
            raise _Quit from None

    # --- main loop -----------------------------------------------------
    def run(self) -> int:
        self._say(self._style("Interview Prep Question Rotator", "1;36"))
        self._say("Adaptive practice: the less confident you are, the more often a question comes up.")
        if self.storage_warning:
            self._say(self._style(f"⚠ {self.storage_warning}", "33"))
        if not self.service.list_cards():
            self._say("You have no cards yet - choose 7 to load sample questions or 2 to add your own.")

        actions = {
            "1": self.practice,
            "2": self.add_card,
            "3": self.list_cards,
            "4": self.edit_card,
            "5": self.delete_card,
            "6": self.progress,
            "7": self.load_samples,
        }
        try:
            while True:
                self._say()
                for row in (self.MENU[:4], self.MENU[4:]):
                    self._say("  ".join(f"[{key}] {label:<14}" for key, label in row).rstrip())
                choice = self._ask("Choose an option: ")
                if choice == "0" or choice.lower() in QUIT_WORDS:
                    break
                action = actions.get(choice)
                if action is None:
                    self._error(f"Unknown option '{choice}'. Type a number from the menu.")
                    continue
                action()
        except (_Quit, KeyboardInterrupt):
            self._say()
        self._say("Goodbye! Your progress is saved.")
        return 0

    # --- practice ------------------------------------------------------
    def practice(self) -> None:
        self._title("Practice")
        if not self.service.list_cards():
            self._error("No cards to practice. Add cards or load the samples first.")
            return
        topic = self._choose_topic()

        last_id: str | None = None
        ratings: list[int] = []
        while True:
            card = self.service.next_card(last_id, topic, self.rng)
            if card is None:
                self._error("No cards in this topic.")
                break
            self._show_question(card, len(ratings) + 1)
            if self._ask("Press Enter to show the answer (q = stop): ").lower() in QUIT_WORDS:
                break
            self._say(self._style("Answer: ", "1;32") + card.answer)
            rating = self._ask_rating()
            if rating is None:
                break
            old = card.confidence
            self.service.record_practice(card.id, rating)
            self._ok(f"Saved: confidence {old} → {rating}")
            ratings.append(rating)
            last_id = card.id

        if ratings:
            average = sum(ratings) / len(ratings)
            self._say(
                f"Session finished: {len(ratings)} card(s) practiced, "
                f"average rating {average:.1f}/{MAX_CONFIDENCE}."
            )

    def _choose_topic(self) -> str | None:
        """Ask for a topic. Returns None for 'all topics'."""
        topics = self.service.topics()
        if not topics:
            return None
        options = ["All topics", *topics]
        self._say("  ".join(f"[{i}] {name}" for i, name in enumerate(options, start=1)))
        while True:
            raw = self._ask("Topic (Enter = all): ")
            if raw in ("", "1"):
                return None
            if raw.isdigit() and 2 <= int(raw) <= len(options):
                return options[int(raw) - 1]
            self._error(f"Type a number from 1 to {len(options)}.")

    def _show_question(self, card: Card, number: int) -> None:
        self._say()
        self._say(
            self._style(f"Question {number}", "1")
            + f"  [{card.topic or GENERAL_TOPIC}]  confidence {card.confidence}/{MAX_CONFIDENCE}"
        )
        self._say(self._style(card.question, "1;33"))

    def _ask_rating(self) -> int | None:
        while True:
            raw = self._ask(f"How confident are you now? 1-{MAX_CONFIDENCE} (q = stop): ")
            if raw.lower() in QUIT_WORDS:
                return None
            try:
                return validate_confidence(raw)
            except ValidationError as exc:
                self._error(str(exc))

    # --- card management -----------------------------------------------
    def add_card(self) -> None:
        self._title("Add a card")
        question = self._ask("Question: ")
        answer = self._ask("Answer: ")
        topic = self._ask("Topic (optional): ")
        confidence = self._ask(f"Confidence 1-{MAX_CONFIDENCE} (Enter = 1): ") or "1"
        try:
            card = self.service.add_card(question, answer, topic, confidence)
        except ValidationError as exc:
            self._error(f"Card not saved: {exc}")
            return
        self._ok(f"Card added (ID {card.id}).")

    def list_cards(self) -> None:
        self._title("Cards")
        cards = self.service.list_cards()
        if not cards:
            self._say("No cards yet.")
            return
        self._say(f"{'ID':<9} {'TOPIC':<12} {'CONF':<5} {'DONE':<5} QUESTION")
        for c in sorted(cards, key=lambda c: (c.topic.lower(), c.confidence)):
            self._say(
                f"{c.id:<9} {shorten(c.topic or GENERAL_TOPIC, 12):<12} "
                f"{c.confidence:<5} {c.times_practiced:<5} {shorten(c.question)}"
            )
        self._say(f"{len(cards)} card(s).")

    def _find_card(self) -> Card | None:
        card_id = self._ask("Card ID (see 'List cards'): ")
        try:
            return self.service.get_card(card_id)
        except CardNotFoundError as exc:
            self._error(str(exc))
            return None

    def edit_card(self) -> None:
        self._title("Edit a card")
        card = self._find_card()
        if card is None:
            return
        self._say("Press Enter to keep the current value.")
        question = self._ask(f"Question [{shorten(card.question, 40)}]: ") or None
        answer = self._ask(f"Answer [{shorten(card.answer, 40)}]: ") or None
        topic = self._ask(f"Topic [{card.topic or '-'}]: ") or None
        confidence = self._ask(f"Confidence [{card.confidence}]: ") or None
        try:
            self.service.update_card(
                card.id, question=question, answer=answer, topic=topic, confidence=confidence
            )
        except ValidationError as exc:
            self._error(f"Card not changed: {exc}")
            return
        self._ok("Card updated.")

    def delete_card(self) -> None:
        self._title("Delete a card")
        card = self._find_card()
        if card is None:
            return
        if self._ask(f"Delete '{shorten(card.question, 40)}'? (y/N): ").lower() != "y":
            self._say("Nothing deleted.")
            return
        self.service.delete_card(card.id)
        self._ok("Card deleted.")

    # --- progress ------------------------------------------------------
    def progress(self) -> None:
        self._title("Progress")
        stats = self.service.stats()
        if stats.total_cards == 0:
            self._say("No cards yet.")
            return
        self._say(f"Total cards:          {stats.total_cards}")
        self._say(
            f"Average confidence:   {confidence_bar(stats.average_confidence)} "
            f"{stats.average_confidence:.2f}/{MAX_CONFIDENCE}"
        )
        self._say(f"Weak cards (1-2):     {stats.low_confidence_count}")
        self._say(f"Practice attempts:    {stats.total_practice_attempts}")
        self._say()
        self._say("Confidence by topic:")
        for topic, average in stats.topic_averages.items():
            self._say(f"  {shorten(topic, 14):<14} {confidence_bar(average)} {average:.2f}")

        weakest = sorted(self.service.list_cards(), key=lambda c: c.confidence)[:3]
        self._say()
        self._say("Focus next on:")
        for card in weakest:
            self._say(f"  ({card.confidence}/{MAX_CONFIDENCE}) {shorten(card.question)}")

    def load_samples(self) -> None:
        added = load_sample_cards(self.service)
        if added:
            self._ok(f"Added {added} sample question(s).")
        else:
            self._say("All sample questions are already loaded.")




