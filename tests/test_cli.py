from __future__ import annotations

from pathlib import Path

import pytest

from myflashcards.cli import main

_TEXT = (
    "The EM algorithm alternates an E-step and an M-step. The E-step computes "
    "responsibilities; the M-step maximizes the expected log-likelihood."
)


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    p = tmp_path / "notes.txt"
    p.write_text(_TEXT, encoding="utf-8")
    return p


def _fake_build(monkeypatch) -> None:
    from mythings.testing import ScriptedEngine

    import myflashcards.cli as cli

    reply = '{"cards": [{"front": "E-step?", "back": "responsibilities"}]}'
    monkeypatch.setattr(cli, "_engine", lambda _name: ScriptedEngine(reply=reply))


def test_build_then_review_then_grade(corpus: Path, tmp_path: Path, monkeypatch,
                                      capsys: pytest.CaptureFixture[str]) -> None:
    _fake_build(monkeypatch)
    deck = tmp_path / "deck.toml"
    ledger = tmp_path / "mastery.jsonl"

    assert main(["build", "EM algorithm", "--corpus", str(corpus),
                 "--deck", str(deck), "--engine", "claude"]) == 0
    assert deck.exists()
    capsys.readouterr()

    # A fresh deck's topic has never been reviewed -> due.
    assert main(["review", "--deck", str(deck), "--ledger", str(ledger)]) == 0
    out = capsys.readouterr().out
    assert "E-step?" in out and "responsibilities" in out

    assert main(["grade", "EM algorithm", "--score", "0.3", "--ledger", str(ledger)]) == 0
    assert ledger.exists()
    assert "em-algorithm" in capsys.readouterr().out.lower() or ledger.read_text()


def test_build_noop_writes_empty_deck_and_soft_fails(corpus: Path, tmp_path: Path,
                                                     capsys: pytest.CaptureFixture[str]) -> None:
    deck = tmp_path / "deck.toml"
    rc = main(["build", "EM algorithm", "--corpus", str(corpus), "--deck", str(deck)])
    assert rc == 1  # noop -> no cards
    assert deck.read_text(encoding="utf-8") == ""


def test_review_fronts_only_hides_answers(corpus: Path, tmp_path: Path, monkeypatch,
                                          capsys: pytest.CaptureFixture[str]) -> None:
    _fake_build(monkeypatch)
    deck = tmp_path / "deck.toml"
    main(["build", "EM algorithm", "--corpus", str(corpus), "--deck", str(deck),
          "--engine", "claude"])
    capsys.readouterr()
    main(["review", "--deck", str(deck), "--ledger", str(tmp_path / "m.jsonl"),
          "--fronts-only"])
    out = capsys.readouterr().out
    assert "E-step?" in out and "responsibilities" not in out


def test_missing_corpus_is_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["build", "EM", "--corpus", str(tmp_path / "none"),
               "--deck", str(tmp_path / "d.toml")])
    assert rc == 1
    assert "no corpus files found" in capsys.readouterr().out
