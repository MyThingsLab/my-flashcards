from __future__ import annotations

import argparse
from pathlib import Path

from mythings.engine import ClaudeCLIEngine, Engine, NoopEngine
from mythings.mastery import load, record

from myflashcards.flashcards import (
    Card,
    build,
    load_corpus,
    load_deck,
    resolve_extractor,
    review_order,
    to_attempt,
    to_toml,
)

BACKLOG_LABEL = "my-flashcards"
DEFAULT_LEDGER = Path(".mythings/mastery.jsonl")


def _engine(name: str) -> Engine:
    return NoopEngine() if name == "noop" else ClaudeCLIEngine()


def _render_deck(cards: list[Card], *, reveal: bool) -> str:
    lines: list[str] = []
    for c in cards:
        lines.append(f"[{c.slug}]  {c.front}")
        if reveal:
            lines.append(f"    -> {c.back}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="myflashcards",
        description="Build spaced-repetition flashcards from a corpus and drill them by topic.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    build_p = sub.add_parser("build", help="generate a flashcard deck for a topic from the corpus")
    build_p.add_argument("topic")
    build_p.add_argument("--corpus", type=Path, action="append", required=True,
                         help="file or directory of source material (repeatable)")
    build_p.add_argument("--deck", type=Path, required=True, help="deck file to write (TOML)")
    build_p.add_argument("--count", type=int, default=8)
    build_p.add_argument("--top", type=int, default=8, help="excerpts to shortlist")
    build_p.add_argument("--engine", choices=("noop", "claude"), default="noop")
    build_p.add_argument("--cache", type=Path, help="cache extracted PDF text under this directory")

    review_p = sub.add_parser("review", help="print due cards, weakest topic first")
    review_p.add_argument("--deck", type=Path, required=True)
    review_p.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    review_p.add_argument("--all", action="store_true", help="show every card, not only those due")
    review_p.add_argument("--fronts-only", action="store_true", help="hide the answers")

    grade_p = sub.add_parser("grade", help="record a self-scored recall for a topic")
    grade_p.add_argument("topic")
    grade_p.add_argument("--score", type=float, required=True, help="0.0 (forgot) .. 1.0 (easy)")
    grade_p.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)

    args = parser.parse_args(argv)

    if args.cmd == "build":
        documents, chunks = load_corpus(args.corpus, extractor=resolve_extractor(args.cache))
        if not documents:
            print("no corpus files found")
            return 1
        cards = build(args.topic, documents, chunks, _engine(args.engine),
                      count=args.count, top=args.top)
        args.deck.parent.mkdir(parents=True, exist_ok=True)
        args.deck.write_text(to_toml(cards), encoding="utf-8")
        print(f"wrote {len(cards)} card(s) to {args.deck}")
        return 0 if cards else 1

    if args.cmd == "review":
        cards = load_deck(args.deck)
        ordered = review_order(cards, load(args.ledger), show_all=args.all)
        if not ordered:
            print("nothing due -- all caught up (use --all to see every card)")
            return 0
        print(_render_deck(ordered, reveal=not args.fronts_only))
        return 0

    record(args.ledger, to_attempt(args.topic, args.score))
    print(f"recorded flashcard recall for {args.topic!r} ({args.score:.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
