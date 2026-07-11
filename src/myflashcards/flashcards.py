from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from mythings.corpus import (
    Chunk,
    Document,
    Extractor,
    cached_extractor,
    chunk,
    extract,
    ingest,
    shortlist,
)
from mythings.engine import Engine, EngineRequest
from mythings.mastery import Attempt, now_iso, rollup
from mythings.mastery import due as mastery_due

TOOL = "myflashcards"
SOURCE = "my-flashcards"

TEXT_SUFFIXES = frozenset({".md", ".txt", ".rst", ".tex"})
CORPUS_SUFFIXES = TEXT_SUFFIXES | {".pdf"}

_FENCE_RE = re.compile(r"^```[a-zA-Z0-9]*\n?|\n?```$")
_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def corpus_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(p for p in sorted(path.rglob("*")) if p.suffix.lower() in CORPUS_SUFFIXES)
        elif path.is_file():
            files.append(path)
    return files


def load_corpus(
    paths: Iterable[Path],
    *,
    target_chars: int = 1200,
    extractor: Extractor = extract,
) -> tuple[list[Document], list[Chunk]]:
    documents = ingest(corpus_files(paths), extractor=extractor)
    chunks = [c for doc in documents for c in chunk(doc, target_chars=target_chars)]
    return documents, chunks


def resolve_extractor(cache_dir: Path | None) -> Extractor:
    return extract if cache_dir is None else cached_extractor(cache_dir)


def format_excerpts(chunks: Iterable[Chunk], documents: Iterable[Document]) -> str:
    titles = {doc.id: doc.title for doc in documents}
    return "\n\n".join(
        f"[{c.doc_id}:{c.ordinal}] ({titles[c.doc_id]})\n{' '.join(c.text.split())}"
        for c in chunks
    )


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "topic"


def _load_json(text: str) -> dict | None:
    # Strip the ```json fences the ClaudeCLIEngine sometimes emits (known core bug),
    # then fall back to the first {...} block. Copied across the study tools; a
    # candidate for a core mythings.engine helper once the fence bug is fixed.
    stripped = _FENCE_RE.sub("", text.strip()).strip()
    if not stripped:
        return None
    candidates = [stripped]
    match = _OBJECT_RE.search(stripped)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


@dataclass(frozen=True)
class Card:
    slug: str  # unique card id, e.g. "em-algorithm-1"
    topic: str  # Topic.slug the card drills
    front: str
    back: str


SYSTEM = (
    "You write spaced-repetition flashcards for a student, using only the excerpts "
    "you are given. Each card is a short question (front) and its concise answer "
    "(back), both grounded strictly in the excerpts — never invent facts. Write "
    'exactly {n} cards. Reply as JSON: {{"cards": [{{"front": "...", "back": "..."}}]}} '
    "and nothing else. If the excerpts do not cover the topic, reply with exactly: "
    "INSUFFICIENT"
)


def build_prompt(topic: str, chunks: Iterable[Chunk], documents: Iterable[Document]) -> str:
    return (
        f"Topic: {topic}\n\n"
        f"Excerpts:\n\n{format_excerpts(chunks, documents)}\n\n"
        f"Flashcards on {topic!r}, as JSON:"
    )


def parse_cards(topic: str, text: str, *, count: int) -> list[Card]:
    parsed = _load_json(text)
    if not parsed:
        return []
    base = slug(topic)
    cards: list[Card] = []
    for item in parsed.get("cards", []):
        if not isinstance(item, dict):
            continue
        front = str(item.get("front", "")).strip()
        back = str(item.get("back", "")).strip()
        if not front or not back:
            continue
        cards.append(Card(slug=f"{base}-{len(cards) + 1}", topic=base, front=front, back=back))
        if len(cards) >= count:
            break
    return cards


def build(
    topic: str,
    documents: Iterable[Document],
    chunks: Iterable[Chunk],
    engine: Engine,
    *,
    count: int = 8,
    top: int = 8,
) -> list[Card]:
    documents = list(documents)
    selected = shortlist(chunks, topic, top=top)
    if not selected:
        return []
    system = SYSTEM.format(n=count)
    prompt = build_prompt(topic, selected, documents)
    reply = engine.run(EngineRequest(prompt=prompt, system=system))
    return parse_cards(topic, reply.text, count=count)


def _esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def to_toml(cards: Iterable[Card]) -> str:
    blocks = []
    for c in cards:
        blocks.append(
            "\n".join(
                [
                    "[[card]]",
                    f'slug = "{_esc(c.slug)}"',
                    f'topic = "{_esc(c.topic)}"',
                    f'front = "{_esc(c.front)}"',
                    f'back = "{_esc(c.back)}"',
                ]
            )
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def load_deck(path: str | Path) -> list[Card]:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    return [
        Card(slug=row["slug"], topic=row["topic"], front=row["front"], back=row["back"])
        for row in data.get("card", [])
    ]


def review_order(
    cards: list[Card],
    attempts: Iterable[Attempt],
    *,
    now: datetime | None = None,
    show_all: bool = False,
) -> list[Card]:
    # Order the deck for a study session: topics never reviewed come first, then
    # topics that are due, weakest first. A card's schedule rolls up to its topic's
    # mastery (the shared seam), so the whole cluster agrees on what "due" means.
    masteries = {m.topic: m for m in rollup(attempts, now=now)}
    due_slugs = {m.topic for m in mastery_due(list(masteries.values()), now=now)}
    topics = list(dict.fromkeys(c.topic for c in cards))

    def rank(topic: str) -> tuple[int, float]:
        m = masteries.get(topic)
        return (0, 0.0) if m is None else (1, m.score)

    selected = [
        t for t in topics if show_all or t not in masteries or t in due_slugs
    ]
    selected.sort(key=rank)
    return [c for t in selected for c in cards if c.topic == t]


def to_attempt(topic: str, score: float, *, now: str | None = None) -> Attempt:
    return Attempt(
        topic=slug(topic),
        at=now or now_iso(),
        score=max(0.0, min(1.0, score)),
        kind="flashcard",
        gaps=(),
        source=SOURCE,
    )
