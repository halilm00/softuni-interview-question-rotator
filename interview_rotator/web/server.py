"""Web interface (Module F) built only on the Python standard library.

``WebApp.handle()`` turns (method, path, form) into a ``Response`` and holds all
page logic, so it can be tested without a network. ``create_server()`` wraps it
in ``http.server`` for real use:  python3 -m interview_rotator web
"""

from __future__ import annotations

import html
import random
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from ..core.cards import GENERAL_TOPIC, CardNotFoundError, CardService
from ..core.models import MAX_CONFIDENCE, MIN_CONFIDENCE, Card
from ..core.rotation import selection_probabilities
from ..core.validation import ValidationError
from ..sample_cards import SAMPLE_CARDS, load_sample_cards

WEB_DIR = Path(__file__).parent
MAX_BODY_BYTES = 100_000
RATING_LABELS = {1: "No idea", 2: "Shaky", 3: "Okay", 4: "Good", 5: "Nailed it"}
NAV = [("practice", "Practice"), ("cards", "Cards"), ("progress", "Progress")]


def esc(value: Any) -> str:
    """HTML-escape any value (also quotes, so it is safe inside attributes)."""
    return html.escape(str(value), quote=True)


@dataclass
class Response:
    status: int = 200
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")


def redirect(location: str) -> Response:
    # 303 See Other: after a form POST the browser loads the next page with GET,
    # so refreshing the page never submits the form twice (Post/Redirect/Get).
    return Response(303, b"", {"Location": location})


def practice_url(topic: str | None = None, last: str | None = None, card_id: str | None = None) -> str:
    path = f"/practice/{card_id}" if card_id else "/practice"
    params = {k: v for k, v in (("topic", topic), ("last", last)) if v}
    return f"{path}?{urlencode(params)}" if params else path


class WebApp:
    def __init__(
        self,
        service: CardService,
        rng: random.Random | None = None,
        storage_warning: str | None = None,
    ) -> None:
        self.service = service
        self.rng = rng
        self._flash: list[tuple[str, str]] = []  # (kind, message) shown on the next page
        if storage_warning:
            self._flash.append(("warning", storage_warning))
        self._base = Template((WEB_DIR / "templates" / "base.html").read_text(encoding="utf-8"))
        self._lock = threading.Lock()  # CardService is not thread-safe

    # --- entry point ---------------------------------------------------
    def handle(
        self,
        method: str,
        target: str,
        form: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        form = form or {}
        headers = headers or {}
        parts = urlsplit(target)
        segments = [s for s in parts.path.split("/") if s]
        query = {k: v[0] for k, v in parse_qs(parts.query).items()}
        with self._lock:
            try:
                if method in ("GET", "HEAD"):
                    return self._route_get(segments, query)
                if method == "POST":
                    if not self._same_origin(headers):
                        return self._error_page(403, "Forbidden", "Cross-site form submission blocked.")
                    return self._route_post(segments, form)
                return self._error_page(405, "Method not allowed", f"{method} is not supported.")
            except CardNotFoundError:
                return self._error_page(404, "Card not found", "This card does not exist (maybe it was deleted).")

    def _route_get(self, seg: list[str], query: dict[str, str]) -> Response:
        match seg:
            case []:
                return redirect("/practice")
            case ["practice"]:
                return self.practice_pick(query)
            case ["practice", card_id]:
                return self.practice_show(card_id, query)
            case ["cards"]:
                return self.cards_page(query.get("topic"))
            case ["cards", card_id, "edit"]:
                return self.edit_page(self.service.get_card(card_id))
            case ["progress"]:
                return self.progress_page()
            case ["static", "style.css"]:
                css = (WEB_DIR / "static" / "style.css").read_bytes()
                return Response(200, css, {"Content-Type": "text/css; charset=utf-8"})
        return self._error_page(404, "Page not found", "This page does not exist.")

    def _route_post(self, seg: list[str], form: Mapping[str, str]) -> Response:
        match seg:
            case ["cards"]:
                return self.add_card(form)
            case ["cards", card_id, "edit"]:
                return self.update_card(card_id, form)
            case ["cards", card_id, "delete"]:
                card = self.service.get_card(card_id)
                self.service.delete_card(card_id)
                self._flash.append(("success", f"Deleted: {card.question}"))
                return redirect("/cards")
            case ["samples"]:
                added = load_sample_cards(self.service)
                message = f"Added {added} sample question(s)." if added else "All sample questions are already loaded."
                self._flash.append(("success", message))
                return redirect("/cards")
            case ["practice", card_id, "rate"]:
                return self.rate(card_id, form)
        return self._error_page(404, "Page not found", "This page does not exist.")

    @staticmethod
    def _same_origin(headers: Mapping[str, str]) -> bool:
        """Block form posts coming from other websites (simple CSRF protection)."""
        origin = headers.get("Origin")
        if not origin:
            return True  # browsers always send Origin on cross-site POSTs
        return urlsplit(origin).netloc == headers.get("Host", "")

    # --- practice ------------------------------------------------------
    def practice_pick(self, query: dict[str, str]) -> Response:
        topic = query.get("topic") or None
        if not self.service.list_cards():
            return self._render("Practice", "practice", self._empty_state())
        card = self.service.next_card(query.get("last"), topic, self.rng)
        if card is None:
            self._flash.append(("error", f"No cards in topic '{topic}'."))
            return redirect("/practice")
        return redirect(practice_url(topic, card_id=card.id))

    def practice_show(self, card_id: str, query: dict[str, str]) -> Response:
        card = self.service.get_card(card_id)
        topic = query.get("topic") or None
        pool = self.service.list_cards(topic) or [card]
        chance = selection_probabilities(pool).get(card.id, 1.0)
        rating_buttons = "".join(
            f'<button class="rate r{n}" name="confidence" value="{n}"><b>{n}</b><span>{RATING_LABELS[n]}</span></button>'
            for n in range(MIN_CONFIDENCE, MAX_CONFIDENCE + 1)
        )
        content = f"""
        {self._topic_pills("/practice", topic)}
        <section class="panel practice">
          <div class="meta">
            <span class="badge tag">{esc(card.topic or GENERAL_TOPIC)}</span>
            {self._conf_badge(card.confidence)}
            <span>Practiced {card.times_practiced}×</span>
            <span>· Chance to come up: {chance:.0%}</span>
          </div>
          <h1 class="question">{esc(card.question)}</h1>
          <details>
            <summary class="btn big">Show answer</summary>
            <div class="answer">{esc(card.answer)}</div>
            <form method="post" action="/practice/{esc(card.id)}/rate">
              <input type="hidden" name="topic" value="{esc(topic or '')}">
              <p><strong>How confident are you now?</strong></p>
              <div class="rating">{rating_buttons}</div>
            </form>
          </details>
          <a class="skip" href="{esc(practice_url(topic, last=card.id))}">Skip this question →</a>
        </section>"""
        return self._render("Practice", "practice", content)

    def rate(self, card_id: str, form: Mapping[str, str]) -> Response:
        card = self.service.get_card(card_id)
        topic = form.get("topic") or None
        old = card.confidence
        try:
            self.service.record_practice(card_id, form.get("confidence"))
        except ValidationError as exc:
            self._flash.append(("error", str(exc)))
            return redirect(practice_url(topic, card_id=card_id))
        self._flash.append(("success", f"Saved: confidence {old} → {card.confidence}. Next question:"))
        return redirect(practice_url(topic, last=card_id))

    # --- cards ---------------------------------------------------------
    def cards_page(
        self,
        topic: str | None = None,
        error: str | None = None,
        values: Mapping[str, str] | None = None,
        status: int = 200,
    ) -> Response:
        cards = self.service.list_cards(topic)
        if self.service.list_cards():
            rows = "".join(self._card_row(c) for c in sorted(cards, key=lambda c: (c.topic.lower(), c.confidence)))
            listing = f"""
            {self._topic_pills("/cards", topic)}
            <table>
              <tr><th>Question</th><th>Topic</th><th>Confidence</th><th>Practiced</th><th></th></tr>
              {rows}
            </table>
            <p class="muted">{len(cards)} card(s).</p>"""
        else:
            listing = self._empty_state()
        content = f"""
        <section class="panel">
          <h2>Add a card</h2>
          {self._error_box(error)}
          {self._card_form("/cards", values or {}, "Add card")}
        </section>
        <section class="panel">
          <h2>Your cards</h2>
          {listing}
        </section>"""
        return self._render("Cards", "cards", content, status)

    def _card_row(self, card: Card) -> str:
        return f"""
        <tr>
          <td>{esc(card.question)}</td>
          <td><span class="badge tag">{esc(card.topic or GENERAL_TOPIC)}</span></td>
          <td>{self._conf_badge(card.confidence)}</td>
          <td>{card.times_practiced}×</td>
          <td class="actions">
            <a class="btn small secondary" href="/cards/{esc(card.id)}/edit">Edit</a>
            <form method="post" action="/cards/{esc(card.id)}/delete"
                  onsubmit="return confirm('Delete this card?')">
              <button class="btn danger small">Delete</button>
            </form>
          </td>
        </tr>"""

    def add_card(self, form: Mapping[str, str]) -> Response:
        try:
            card = self.service.add_card(
                form.get("question", ""), form.get("answer", ""),
                form.get("topic", ""), form.get("confidence", "1"),
            )
        except ValidationError as exc:
            return self.cards_page(error=str(exc), values=form, status=400)
        self._flash.append(("success", f"Card added: {card.question}"))
        return redirect("/cards")

    def edit_page(self, card: Card, error: str | None = None,
                  values: Mapping[str, str] | None = None, status: int = 200) -> Response:
        values = values or {
            "question": card.question, "answer": card.answer,
            "topic": card.topic, "confidence": str(card.confidence),
        }
        content = f"""
        <section class="panel">
          <h1>Edit card</h1>
          {self._error_box(error)}
          {self._card_form(f"/cards/{esc(card.id)}/edit", values, "Save changes")}
          <p><a href="/cards">← Back to cards</a></p>
        </section>"""
        return self._render("Edit card", "cards", content, status)

    def update_card(self, card_id: str, form: Mapping[str, str]) -> Response:
        card = self.service.get_card(card_id)
        try:
            self.service.update_card(
                card_id, question=form.get("question", ""), answer=form.get("answer", ""),
                topic=form.get("topic", ""), confidence=form.get("confidence", ""),
            )
        except ValidationError as exc:
            return self.edit_page(card, error=str(exc), values=form, status=400)
        self._flash.append(("success", "Card updated."))
        return redirect("/cards")

    def _card_form(self, action: str, values: Mapping[str, str], button: str) -> str:
        selected = values.get("confidence", "1")
        options = "".join(
            f'<option value="{n}"{" selected" if str(n) == selected else ""}>{n} – {RATING_LABELS[n]}</option>'
            for n in range(MIN_CONFIDENCE, MAX_CONFIDENCE + 1)
        )
        topics = "".join(f'<option value="{esc(t)}">' for t in self.service.topics())
        return f"""
        <form class="card-form" method="post" action="{action}">
          <label>Question <textarea name="question" required>{esc(values.get("question", ""))}</textarea></label>
          <label>Answer <textarea name="answer" required>{esc(values.get("answer", ""))}</textarea></label>
          <div class="row">
            <label>Topic (optional) <input name="topic" list="topics" value="{esc(values.get("topic", ""))}"></label>
            <label>Confidence <select name="confidence">{options}</select></label>
          </div>
          <datalist id="topics">{topics}</datalist>
          <div><button class="btn">{esc(button)}</button></div>
        </form>"""

    # --- progress ------------------------------------------------------
    def progress_page(self) -> Response:
        stats = self.service.stats()
        if stats.total_cards == 0:
            return self._render("Progress", "progress", f'<section class="panel">{self._empty_state()}</section>')

        tiles = "".join(
            f'<div class="tile"><div class="value">{value}</div><div class="label">{label}</div></div>'
            for value, label in [
                (stats.total_cards, "Cards"),
                (f"{stats.average_confidence:.2f}", f"Avg confidence (of {MAX_CONFIDENCE})"),
                (stats.low_confidence_count, "Weak cards (1–2)"),
                (stats.total_practice_attempts, "Practice attempts"),
            ]
        )
        topic_bars = "".join(
            self._bar_row(name, avg / MAX_CONFIDENCE, f"{avg:.2f}", round(avg))
            for name, avg in stats.topic_averages.items()
        )
        cards = self.service.list_cards()
        probs = selection_probabilities(cards)
        top = max(probs.values())
        chance_bars = "".join(
            self._bar_row(c.question, probs[c.id] / top, f"{probs[c.id]:.0%}", c.confidence)
            for c in sorted(cards, key=lambda c: -probs[c.id])
        )
        content = f"""
        <h1>Progress</h1>
        <div class="tiles">{tiles}</div>
        <section class="panel">
          <h2>Confidence by topic</h2>
          {topic_bars}
        </section>
        <section class="panel">
          <h2>Chance to come up next</h2>
          <p class="muted">Lower confidence = higher chance. This is the adaptive rotation at work.</p>
          {chance_bars}
        </section>"""
        return self._render("Progress", "progress", content)

    @staticmethod
    def _bar_row(label: str, fraction: float, value: str, confidence: int) -> str:
        width = max(2, round(fraction * 100))
        level = max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, confidence))
        return (
            f'<div class="bar-row"><span title="{esc(label)}">{esc(label[:40] + ("…" if len(label) > 40 else ""))}</span>'
            f'<div class="bar"><div class="conf-{level}" style="width:{width}%"></div></div>'
            f"<strong>{esc(value)}</strong></div>"
        )

    # --- shared pieces -------------------------------------------------
    def _render(self, title: str, active: str, content: str, status: int = 200) -> Response:
        nav = "".join(
            f'<a href="/{key}"{" class=active" if key == active else ""}>{label}</a>'
            for key, label in NAV
        )
        flash = "".join(f'<div class="flash {kind}">{esc(msg)}</div>' for kind, msg in self._flash)
        self._flash.clear()
        page = self._base.substitute(title=esc(title), nav=nav, flash=flash, content=content)
        return Response(status, page.encode("utf-8"), {"Content-Type": "text/html; charset=utf-8"})

    def _error_page(self, status: int, title: str, message: str) -> Response:
        content = f'<section class="panel empty"><h1>{esc(title)}</h1><p>{esc(message)}</p><a class="btn" href="/practice">Go to practice</a></section>'
        return self._render(title, "", content, status)

    def _topic_pills(self, base: str, current: str | None) -> str:
        topics = self.service.topics()
        if not topics:
            return ""
        current_key = (current or "").lower()
        pills = [f'<a class="pill{" active" if not current else ""}" href="{base}">All topics</a>']
        for t in topics:
            active = " active" if t.lower() == current_key else ""
            pills.append(f'<a class="pill{active}" href="{base}?{esc(urlencode({"topic": t}))}">{esc(t)}</a>')
        return f'<div class="pills">{"".join(pills)}</div>'

    @staticmethod
    def _conf_badge(confidence: int) -> str:
        level = max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, confidence))
        return f'<span class="badge conf-{level}">Confidence {confidence}/{MAX_CONFIDENCE}</span>'

    @staticmethod
    def _error_box(error: str | None) -> str:
        return f'<div class="flash error">{esc(error)}</div>' if error else ""

    @staticmethod
    def _empty_state() -> str:
        return f"""
        <div class="empty">
          <h2>No cards yet</h2>
          <p class="muted">Add your own questions or start with {len(SAMPLE_CARDS)} sample interview questions.</p>
          <form method="post" action="/samples"><button class="btn big">Load sample questions</button></form>
          <p><a href="/cards">or add your own cards →</a></p>
        </div>"""


# --- HTTP adapter ---------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    app: WebApp  # set by create_server()
    server_version = "InterviewRotator/1.0"

    def do_GET(self) -> None:
        self._send(self.app.handle("GET", self.path, headers=self.headers))

    def do_HEAD(self) -> None:
        self._send(self.app.handle("HEAD", self.path, headers=self.headers))

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if not 0 <= length <= MAX_BODY_BYTES:
            self._send(Response(413, b"Request body too large.", {"Content-Type": "text/plain"}))
            return
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        form = {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}
        self._send(self.app.handle("POST", self.path, form, self.headers))

    def _send(self, response: Response) -> None:
        self.send_response(response.status)
        for name, value in response.headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(response.body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(response.body)


def create_server(app: WebApp, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    handler = type("Handler", (_Handler,), {"app": app})
    return ThreadingHTTPServer((host, port), handler)


def run_server(
    service: CardService,
    host: str = "127.0.0.1",
    port: int = 8000,
    storage_warning: str | None = None,
) -> int:
    server = create_server(WebApp(service, storage_warning=storage_warning), host, port)
    print(f"Interview Prep Rotator is running at http://{host}:{server.server_port}/  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped. Your progress is saved.")
    finally:
        server.server_close()
    return 0


