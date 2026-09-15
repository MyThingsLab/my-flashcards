# Changelog

## [Unreleased]
### Added/Changed
- MyFlashcards v0: build (1 Engine call: corpus->front/back cards) + review (Engine-free, ordered by mastery.due) + grade (Engine-free, records flashcard recall). Deck=local TOML; recalls->local mastery ledger; per-topic (no 2nd state format). 13 tests, 94% cov.
- Mechanical migration to mythings.testing: inline ScriptedEngine replaced by the shared one (drop-in).
