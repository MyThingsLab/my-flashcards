# my-flashcards

[![CI](https://github.com/MyThingsLab/my-flashcards/actions/workflows/ci.yml/badge.svg)](https://github.com/MyThingsLab/my-flashcards/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/MyThingsLab/my-flashcards/branch/main/graph/badge.svg)](https://codecov.io/gh/MyThingsLab/my-flashcards) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

The learn-loop's **spaced-recall drilling** step. Build a deck of flashcards from
a document corpus, then drill the cards that are due — weakest topic first.

Unlike [`my-professor`](../my-professor), only `build` calls the Engine; `review`
and `grade` are instant and free, so a whole deck can be crammed rapidly. Cards
roll up to their topic's mastery via the shared [`mythings.mastery`](../my-things-core)
seam, so the whole study cluster agrees on what "due" means.

## Usage

```bash
# Build a deck for a topic from the corpus (the one Engine call)
myflashcards build "EM algorithm" --corpus ~/Desktop/unsupervised_learning.pdf \
  --engine claude --deck .mythings/em.toml --count 8

# Drill the cards that are due (front then back, weakest topic first) — no Engine call
myflashcards review --deck .mythings/em.toml --ledger .mythings/mastery.jsonl

# Record how a recall went (0.0 forgot .. 1.0 easy) — no Engine call
myflashcards grade "EM algorithm" --score 0.3 --ledger .mythings/mastery.jsonl
```

`--engine noop` (default) makes zero Engine calls and writes an empty deck (a soft
failure). `review --all` shows every card regardless of schedule; `--fronts-only`
hides the answers for self-testing.

## How it works

- **`build`** shortlists the corpus for the topic and makes one Engine call to
  write N front/back cards, grounded strictly in the shown excerpts. The deck is a
  human-editable local TOML file.
- **`review`** orders the deck for a session: topics never reviewed first, then
  topics that are due (from `mythings.mastery.due`), weakest first.
- **`grade`** appends a self-scored recall `Attempt` to the local mastery ledger —
  never a PR. A card's schedule is its topic's mastery; no second state format.

## Install (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ../my-things-core -e ".[dev]"
pytest
```

## License

MIT — see [`LICENSE`](LICENSE).
