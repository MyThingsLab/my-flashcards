# my-flashcards — agent instructions

You are developing **my-flashcards**, a MyThingsLab My[X] tool.

**Inherited rules:** obey [`./HARNESS.md`](./HARNESS.md) in full — the vendored
MyThingsLab build-harness rules. Do not restate or override them. Anything not
covered here defers to `HARNESS.md`, then `my-things-core/docs/CONVENTIONS.md`.

## This tool

- **Purpose:** the learn-loop's **spaced-recall drilling** step. `build` makes
  concise front/back flashcards for a topic from a document corpus (via
  `mythings.corpus`); `review` prints the cards due for study, weakest topic
  first (via `mythings.mastery`); `grade` records a self-scored recall. The
  distinguishing property vs `my-professor`: only `build` calls the Engine —
  `review` and `grade` are instant and free, so a whole deck can be drilled
  rapidly. Cards roll up to their topic's mastery, the shared per-topic seam.
- **The single Engine call:** one per invocation, and only in `build` — "using
  only these excerpts, write N front/back cards." `review` and `grade` make no
  Engine call. Against `NoopEngine`, `build` produces no cards (a soft failure),
  never invented ones.
- **Invariants / rules:** at most one Engine call per run (only `build`).
  Card content rests only on the shown excerpts; never fabricated. The deck is a
  local TOML file; recalls append to the append-only local mastery ledger — never
  a PR. No `Workspace`, no GitHub. A card's schedule is its topic's mastery: this
  tool never invents a second state format.
- **Backlog label:** `my-flashcards`
