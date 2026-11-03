"""Tests for Module F: Web UI (standard library http.server)."""

import random
import re
import threading
import unittest
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from interview_rotator.core.cards import CardService
from interview_rotator.sample_cards import SAMPLE_CARDS
from interview_rotator.web.server import WebApp, create_server

from .helpers import InMemoryStorage


def make_app(*cards, warning=None):
    service = CardService(InMemoryStorage())
    for question, topic, confidence in cards:
        service.add_card(question, f"Answer to {question}", topic, confidence)
    return WebApp(service, rng=random.Random(3), storage_warning=warning), service


def follow(app, response, max_hops=5):
    """Follow 303 redirects like a browser does (with GET)."""
    for _ in range(max_hops):
        if response.status != 303:
            return response
        response = app.handle("GET", response.headers["Location"])
    raise AssertionError("too many redirects")


def card_id_from(location):
    return urlsplit(location).path.split("/")[2]


class TestPages(unittest.TestCase):
    def test_root_redirects_to_practice(self):
        app, _ = make_app()
        response = app.handle("GET", "/")
        self.assertEqual((response.status, response.headers["Location"]), (303, "/practice"))

    def test_empty_app_offers_sample_questions(self):
        app, _ = make_app()
        for path in ("/practice", "/cards", "/progress"):
            with self.subTest(path=path):
                page = app.handle("GET", path)
                self.assertEqual(page.status, 200)
                self.assertIn("Load sample questions", page.text)

    def test_load_samples(self):
        app, service = make_app()
        page = follow(app, app.handle("POST", "/samples"))
        self.assertIn(f"Added {len(SAMPLE_CARDS)} sample question(s).", page.text)
        self.assertEqual(len(service.list_cards()), len(SAMPLE_CARDS))
        page = follow(app, app.handle("POST", "/samples"))
        self.assertIn("already loaded", page.text)

    def test_static_css_and_unknown_pages(self):
        app, _ = make_app()
        css = app.handle("GET", "/static/style.css")
        self.assertEqual(css.status, 200)
        self.assertEqual(css.headers["Content-Type"], "text/css; charset=utf-8")
        self.assertEqual(app.handle("GET", "/nope").status, 404)
        self.assertEqual(app.handle("GET", "/practice/unknown-id").status, 404)
        self.assertEqual(app.handle("DELETE", "/cards").status, 405)

    def test_storage_warning_is_shown_once(self):
        app, _ = make_app(warning="Data file problem: test")
        self.assertIn("Data file problem: test", app.handle("GET", "/cards").text)
        self.assertNotIn("Data file problem: test", app.handle("GET", "/cards").text)


class TestPractice(unittest.TestCase):
    def test_practice_shows_question_with_hidden_answer_and_rating_buttons(self):
        app, _ = make_app(("What is REST?", "Web", 1))
        redirect = app.handle("GET", "/practice")
        self.assertEqual(redirect.status, 303)
        page = follow(app, redirect).text
        self.assertIn("What is REST?", page)
        self.assertIn("<details>", page)  # answer hidden until "Show answer"
        self.assertIn("Show answer", page)
        for n in range(1, 6):
            self.assertIn(f'name="confidence" value="{n}"', page)

    def test_rating_saves_and_moves_to_a_different_card(self):
        app, service = make_app(("Q1", "", 1), ("Q2", "", 1))
        card_id = card_id_from(app.handle("GET", "/practice").headers["Location"])

        response = app.handle("POST", f"/practice/{card_id}/rate", {"confidence": "4"})
        self.assertEqual(response.headers["Location"], f"/practice?last={card_id}")
        card = service.get_card(card_id)
        self.assertEqual((card.confidence, card.times_practiced), (4, 1))

        next_redirect = app.handle("GET", response.headers["Location"])
        self.assertNotEqual(card_id_from(next_redirect.headers["Location"]), card_id)
        self.assertIn("Saved: confidence 1 → 4", follow(app, next_redirect).text)

    def test_invalid_rating_is_rejected(self):
        app, service = make_app(("Q1", "", 2))
        card = service.list_cards()[0]
        page = follow(app, app.handle("POST", f"/practice/{card.id}/rate", {"confidence": "9"}))
        self.assertIn("Confidence must be a whole number from 1 to 5.", page.text)
        self.assertEqual((card.confidence, card.times_practiced), (2, 0))

    def test_topic_filter_is_kept_during_practice(self):
        app, service = make_app(("SQL question", "SQL", 1), ("Java question", "Java", 1))
        for _ in range(10):
            location = app.handle("GET", "/practice?topic=SQL").headers["Location"]
            self.assertTrue(location.endswith("?topic=SQL"))
            self.assertEqual(service.get_card(card_id_from(location)).topic, "SQL")

    def test_unknown_topic_shows_message(self):
        app, _ = make_app(("Q1", "SQL", 1))
        page = follow(app, app.handle("GET", "/practice?topic=Python"))
        self.assertIn("No cards in topic", page.text)


class TestCards(unittest.TestCase):
    def test_add_card(self):
        app, service = make_app()
        form = {"question": "What is CI/CD?", "answer": "Automated build and deploy.", "topic": "DevOps", "confidence": "2"}
        page = follow(app, app.handle("POST", "/cards", form))
        self.assertIn("Card added: What is CI/CD?", page.text)
        self.assertEqual(service.list_cards()[0].confidence, 2)

    def test_invalid_card_shows_error_and_keeps_input(self):
        app, service = make_app()
        response = app.handle("POST", "/cards", {"question": "Kept text", "answer": " ", "topic": "", "confidence": "1"})
        self.assertEqual(response.status, 400)
        self.assertIn("Answer cannot be empty.", response.text)
        self.assertIn("Kept text</textarea>", response.text)
        self.assertEqual(service.list_cards(), [])

    def test_user_text_is_html_escaped(self):
        app, _ = make_app(('<script>alert("x")</script>', "<b>", 1))
        page = app.handle("GET", "/cards").text
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;", page)

    def test_edit_and_delete(self):
        app, service = make_app(("Q1", "SQL", 1))
        card = service.list_cards()[0]
        self.assertIn("Q1</textarea>", app.handle("GET", f"/cards/{card.id}/edit").text)

        form = {"question": "Q1 edited", "answer": "New", "topic": "", "confidence": "3"}
        follow(app, app.handle("POST", f"/cards/{card.id}/edit", form))
        self.assertEqual((card.question, card.answer, card.topic, card.confidence), ("Q1 edited", "New", "", 3))

        bad = app.handle("POST", f"/cards/{card.id}/edit", form | {"confidence": "0"})
        self.assertEqual(bad.status, 400)
        self.assertEqual(card.confidence, 3)

        page = follow(app, app.handle("POST", f"/cards/{card.id}/delete"))
        self.assertIn("Deleted: Q1 edited", page.text)
        self.assertEqual(service.list_cards(), [])

    def test_cross_site_post_is_blocked(self):
        app, service = make_app()
        form = {"question": "Q", "answer": "A"}
        evil = app.handle("POST", "/cards", form, {"Origin": "http://evil.example", "Host": "127.0.0.1:8000"})
        self.assertEqual(evil.status, 403)
        same = app.handle("POST", "/cards", form, {"Origin": "http://127.0.0.1:8000", "Host": "127.0.0.1:8000"})
        self.assertEqual(same.status, 303)
        self.assertEqual(len(service.list_cards()), 1)


class TestProgress(unittest.TestCase):
    def test_progress_shows_stats_topics_and_chances(self):
        app, _ = make_app(("Weak", "SQL", 1), ("Strong", "Java", 5))
        page = app.handle("GET", "/progress").text
        self.assertIn("Confidence by topic", page)
        self.assertIn("SQL", page)
        # weights 5 and 1 -> 83% and 17%, weakest card listed first
        self.assertIn("83%", page)
        self.assertIn("17%", page)
        self.assertLess(page.index(">Weak<"), page.index(">Strong<"))


class TestRealServer(unittest.TestCase):
    def test_http_round_trip(self):
        app, service = make_app()
        server = create_server(app, "127.0.0.1", 0)  # port 0 = any free port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"

        with urlopen(f"{base}/cards", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/html", resp.headers["Content-Type"])

        body = urlencode({"question": "Über-Frage?", "answer": "Ja", "topic": "", "confidence": "2"}).encode()
        with urlopen(Request(f"{base}/cards", data=body), timeout=5) as resp:
            page = resp.read().decode("utf-8")
            self.assertEqual(urlsplit(resp.url).path, "/cards")  # followed the 303
        self.assertIn("Über-Frage?", page)
        self.assertEqual(service.list_cards()[0].confidence, 2)

        with urlopen(f"{base}/static/style.css", timeout=5) as resp:
            self.assertTrue(re.search(r"--primary:", resp.read().decode()))


if __name__ == "__main__":
    unittest.main()

