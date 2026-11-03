"""JSON file storage for cards (Module C).

File format::

    {"version": 1, "cards": [ {card fields...}, ... ]}

Safety features:
* missing file   -> created automatically with no cards
* corrupted file -> backed up as ``<name>.corrupt-<timestamp>``, app continues
                    with the valid cards (or none) and exposes a ``warning``
* saving         -> written to a temporary file first and then renamed, so a
                    crash during saving can never leave a half-written file
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Card
from .validation import (
    ValidationError,
    validate_answer,
    validate_confidence,
    validate_question,
    validate_topic,
)

FORMAT_VERSION = 1
DATA_PATH_ENV_VAR = "INTERVIEW_ROTATOR_DATA"


def default_data_path() -> Path:
    """``$INTERVIEW_ROTATOR_DATA`` if set, otherwise ``./data/cards.json``."""
    return Path(os.environ.get(DATA_PATH_ENV_VAR, Path("data") / "cards.json"))


class JsonStorage:
    """Loads and saves the full list of cards as one JSON file."""

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path) if path is not None else default_data_path()
        self.warning: str | None = None  # set when load() had to recover from bad data

    # --- loading -------------------------------------------------------
    def load(self) -> list[Card]:
        self.warning = None
        if not self.path.exists():
            self.save([])
            return []

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._recover([], "the file is not valid JSON")

        raw_cards = data.get("cards") if isinstance(data, dict) else None
        if not isinstance(raw_cards, list):
            return self._recover([], "the file does not contain a list of cards")

        cards: list[Card] = []
        skipped = 0
        for entry in raw_cards:
            card = _parse_card(entry)
            if card is None:
                skipped += 1
            else:
                cards.append(card)
        if skipped:
            return self._recover(cards, f"{skipped} invalid card(s) were skipped")
        return cards

    def _recover(self, cards: list[Card], reason: str) -> list[Card]:
        """Back up the damaged file, rewrite a clean one and remember a warning."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = self.path.with_name(f"{self.path.name}.corrupt-{stamp}")
        counter = 1
        while backup.exists():  # never overwrite an earlier backup
            counter += 1
            backup = self.path.with_name(f"{self.path.name}.corrupt-{stamp}-{counter}")
        shutil.copy2(self.path, backup)
        self.save(cards)
        self.warning = (
            f"Data file problem: {reason}. A backup was saved as '{backup.name}'. "
            f"Loaded {len(cards)} card(s)."
        )
        return cards

    # --- saving --------------------------------------------------------
    def save(self, cards: list[Card]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": FORMAT_VERSION, "cards": [c.to_dict() for c in cards]}

        fd, tmp_name = tempfile.mkstemp(
            dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(payload, tmp, indent=2, ensure_ascii=False)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, self.path)  # atomic on the same file system
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise


def _parse_card(entry: Any) -> Card | None:
    """Convert one stored entry to a Card, or None if it is invalid."""
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
        return None
    try:
        card = Card.from_dict(entry)
        card.question = validate_question(card.question)
        card.answer = validate_answer(card.answer)
        card.topic = validate_topic(card.topic)
        card.confidence = validate_confidence(card.confidence)
    except (TypeError, ValidationError):
        return None
    if not isinstance(card.times_practiced, int) or card.times_practiced < 0:
        card.times_practiced = 0
    if card.last_practiced is not None and not isinstance(card.last_practiced, str):
        card.last_practiced = None
    return card


