from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from mythings.corpus import chunk, ingest
from mythings.engine import EngineRequest, EngineResult, NoopEngine
from mythings.mastery import now_iso

from myflashcards.flashcards import (
    build,
    load_deck,
    parse_cards,
    review_order,
    to_attempt,
    to_toml,
)

_TEXT = (
    "The EM algorithm alternates an E-step and an M-step. The E-step computes "
    "responsibilities; the M-step maximizes the expected complete-data log-likelihood. "
    "It never decreases the likelihood.\n\n"
    "PCA projects data onto the leading eigenvectors of the covariance matrix."
)
_NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


class ScriptedEngine:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[EngineRequest] = []

    def run(self, request: EngineRequest) -> EngineResult:
        self.calls.append(request)
        return EngineResult(text=self.reply, data={})


def _corpus():
    docs = ingest([Path("notes.txt")], extractor=lambda _p: _TEXT)
    return docs, [c for d in docs for c in chunk(d, target_chars=300)]


def test_build_parses_cards_and_ids_by_topic() -> None:
    docs, chunks = _corpus()
    engine = ScriptedEngine(
        '{"cards": [{"front": "What does the E-step compute?", "back": "responsibilities"}, '
        '{"front": "Does EM decrease the likelihood?", "back": "No."}]}'
    )
    cards = build("EM algorithm", docs, chunks, engine, count=5)
    assert len(engine.calls) == 1
    assert [c.slug for c in cards] == ["em-algorithm-1", "em-algorithm-2"]
    assert all(c.topic == "em-algorithm" for c in cards)
    assert cards[0].back == "responsibilities"


def test_build_strips_fences_and_caps_count() -> None:
    docs, chunks = _corpus()
    reply = (
        '```json\n{"cards": [{"front":"a","back":"1"},'
        '{"front":"b","back":"2"},{"front":"c","back":"3"}]}\n```'
    )
    cards = build("EM algorithm", docs, chunks, ScriptedEngine(reply), count=2)
    assert [c.front for c in cards] == ["a", "b"]


def test_build_noop_yields_no_cards() -> None:
    docs, chunks = _corpus()
    assert build("EM algorithm", docs, chunks, NoopEngine()) == []


def test_cards_missing_a_side_are_dropped() -> None:
    reply = '{"cards": [{"front": "q", "back": ""}, {"front": "q2", "back": "a2"}]}'
    cards = parse_cards("t", reply, count=5)
    assert [c.front for c in cards] == ["q2"]


def test_deck_toml_round_trips(tmp_path: Path) -> None:
    docs, chunks = _corpus()
    engine = ScriptedEngine('{"cards": [{"front": "q", "back": "a"}]}')
    cards = build("EM algorithm", docs, chunks, engine)
    deck = tmp_path / "deck.toml"
    deck.write_text(to_toml(cards), encoding="utf-8")
    assert load_deck(deck) == cards


def _cards():
    docs, chunks = _corpus()
    reply = '{"cards": [{"front": "q", "back": "a"}]}'
    em = build("EM algorithm", docs, chunks, ScriptedEngine(reply))
    pca = build("PCA", docs, chunks, ScriptedEngine(reply))
    return em + pca


def test_review_orders_never_seen_first_then_weakest() -> None:
    cards = _cards()  # topics: em-algorithm, pca
    # pca has a strong recent attempt; em-algorithm has never been reviewed.
    attempts = [to_attempt("PCA", 1.0, now=now_iso(_NOW - timedelta(days=1)))]
    ordered = review_order(cards, attempts, now=_NOW)
    topics = list(dict.fromkeys(c.topic for c in ordered))
    assert topics[0] == "em-algorithm"  # unseen surfaces before a strong, not-yet-due topic
    assert "pca" not in topics  # strong + recently seen -> not due


def test_review_all_shows_every_card() -> None:
    cards = _cards()
    attempts = [to_attempt("PCA", 1.0, now=now_iso(_NOW - timedelta(days=1)))]
    ordered = review_order(cards, attempts, now=_NOW, show_all=True)
    assert {c.topic for c in ordered} == {"em-algorithm", "pca"}
