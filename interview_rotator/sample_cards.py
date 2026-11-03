"""Built-in sample interview questions, so the app can be tried right away."""

from __future__ import annotations

from .core.cards import CardService

# (topic, question, answer)
SAMPLE_CARDS: list[tuple[str, str, str]] = [
    ("Python", "What is the difference between a list and a tuple?",
     "Lists are mutable and use []. Tuples are immutable, use (), and can be used as dict keys."),
    ("Python", "What does the GIL do in CPython?",
     "The Global Interpreter Lock lets only one thread run Python bytecode at a time; "
     "use multiprocessing or async I/O for parallel work."),
    ("Python", "What is a decorator?",
     "A function that takes a function and returns a new one that adds behavior, applied with @name."),
    ("SQL", "What is the difference between INNER JOIN and LEFT JOIN?",
     "INNER JOIN returns only matching rows. LEFT JOIN returns all rows from the left table, "
     "with NULLs where there is no match."),
    ("SQL", "What is an index and when should you use one?",
     "A data structure that speeds up lookups on a column. Use it on columns used often in "
     "WHERE/JOIN/ORDER BY; it slows down writes a little."),
    ("SQL", "What is the difference between WHERE and HAVING?",
     "WHERE filters rows before grouping; HAVING filters groups after GROUP BY."),
    ("Web", "What is REST?",
     "An architectural style for APIs: resources identified by URLs, standard HTTP methods, "
     "stateless requests."),
    ("Web", "What is the difference between PUT and PATCH?",
     "PUT replaces the whole resource; PATCH changes only the given fields."),
    ("Web", "What HTTP status code means 'Not Found' and which means 'Unauthorized'?",
     "404 = Not Found, 401 = Unauthorized (not logged in), 403 = Forbidden (no permission)."),
    ("Behavioral", "Tell me about a time you made a mistake at work.",
     "Use STAR: Situation, Task, Action, Result. Own the mistake, explain the fix and what you learned."),
    ("Behavioral", "Why do you want to work here?",
     "Connect the company's product/values to your skills and goals; be specific, not generic."),
    ("Behavioral", "Describe a conflict with a colleague and how you solved it.",
     "Stay factual, show you listened, describe the compromise and the positive result."),
]


def load_sample_cards(service: CardService) -> int:
    """Add the sample cards that are not present yet. Returns how many were added."""
    existing = {c.question.strip().lower() for c in service.list_cards()}
    added = 0
    for topic, question, answer in SAMPLE_CARDS:
        if question.lower() not in existing:
            service.add_card(question, answer, topic, 1)
            added += 1
    return added

