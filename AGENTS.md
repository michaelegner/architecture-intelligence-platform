# AGENTS.md

Mandatory instructions for any coding agent (Codex, Claude Code, or otherwise) working in this
repository. This file is procedural — it governs *how* agents work, not *what* the system does.

## Governing sources, in authority order

1. [`docs/product-doctrine-and-strategic-direction.md`](docs/product-doctrine-and-strategic-direction.md)
   — product strategy, target wedge, and the semantic model (evidence, provenance, identity,
   qualification) the whole system is built on.
2. [`ROADMAP.md`](ROADMAP.md) — authoritative for release sequencing and what's shipped vs. planned.
3. The applicable release's governing specification: `docs/specifications/<release>/specification.md`
   (the parent spec for that release) and its `iN-<slug>.md` increment specs (the normative contract
   for that increment). See [`docs/specifications/README.md`](docs/specifications/README.md).

`docs/specifications/poc.md` and its siblings there (`h1-h3-hardening.md`, `h4-opentelemetry.md`,
`h5-open-source-readiness.md`, `11h-runtime-correctness-robustness.md`,
`12g-public-repository-activation.md`) are historical design input this project was originally
built from — not the current governing specification. The current release's own
`docs/specifications/<release>/` directory is.

**Specifications are authoritative over implementation plans, skills, and agent instructions —
including this file.** If anything below conflicts with a specification, the specification wins.

## Mandatory agent behavior

- Before planning substantial work, read the three governing layers above for the area you're
  touching — not just the increment spec in isolation.
- Identify the exact governing specification revision (e.g. "Draft 0.3, amended during PR3b") before
  writing a plan against it.
- Fetch and merge `origin/main` before starting implementation, not only before pushing: governing
  specifications are revised on `main` while an increment is in progress. Re-check the revision you
  planned against before opening the PR. (In v0.5 I1 a formula was implemented after the spec had
  already changed it.)
- Write a commit or merge SHA into a record, PR body or comment only from git output captured in
  the same step (`git rev-parse`, `gh pr view --json mergeCommit`), never from memory or
  expectation. Qualification evidence depends on exact SHAs.
- Inspect the current repository — existing code, tests, prior completion records — before
  proposing implementation details. Reuse existing functions/utilities/patterns; don't propose new
  ones where suitable ones already exist.
- For substantial increment work, produce a reviewed implementation plan **before** changing
  production code. See the [specification-driven-implementation skill](.agents/skills/specification-driven-implementation/SKILL.md)
  for the full procedure and templates.
- Persist the approved plan, verbatim, in the GitHub issue or the initial PR description. Retain the
  original plan — do not replace it with a retrospective summary once implementation is done.
- Add an implementation reconciliation (a diff against the retained plan, not a fresh retrospective)
  before considering the work complete.
- If implementation exposes a semantic ambiguity the specification doesn't resolve, **stop** and
  request a specification decision. Do not guess and do not silently pick a default. Tests you
  write are implementation evidence, not independent qualification — a passing test suite
  demonstrates the plan was implemented; it never resolves what the specification should mean.
- Never silently introduce new requirements, precedence rules, identity rules, conflict-resolution
  behavior, or unsupported-case behavior that the specification doesn't already state.
- Preserve AIP's evidence, provenance, identity, qualification, and unsupported-case guarantees in
  every change — these are load-bearing product invariants, not implementation details.
- Code in the packages `[tool.pyright]` covers (`pyproject.toml`) must pass `uv run pyright`. Never
  silence it with a bare `# type: ignore`/`# pyright: ignore`, by loosening `[tool.pyright]`, or by
  shrinking its `include`. A suppression must be rule-scoped (`# pyright: ignore[<rule>]`) with a
  comment naming the tool or stub limitation it works around. A type error that exposes a reachable
  `None`/union path is a correctness finding: fix it, don't suppress it.
- Before opening a pull request or pushing a commit meant to pass CI, run the full local gate in
  this order: `uv run ruff format .`, `uv run ruff check .`, `uv run pyright`, then
  `uv run pytest tests/unit` **and** `uv run pytest tests/integration`. Run both suites, not the
  one that seems relevant: contract changes that stay unit-green have broken integration tests
  here before. This applies to small changes too. The only exception is the documentation-only
  exemption in the specification-driven-implementation skill, which never covers specifications,
  completion records, release notes, schemas or fixtures.
- Never merge a pull request, force-push, or push directly to `main`; the owner merges. This rule is
  procedural. For Claude Code, `.claude/settings.json` adds best-effort deny rules for the common
  command forms (they override any local allow rule), but they match command text only and are not
  a security boundary.

## Minimum implementation-plan content

- Governing specification path and exact revision.
- Bounded scope and explicit non-goals.
- Affected components and expected change surface.
- Specification-requirement → implementation-task mapping.
- Acceptance-criterion → test/evidence mapping.
- Validation commands.
- Unresolved questions, assumptions, and stop conditions.

## Minimum reconciliation content

- Work completed as planned.
- Material deviations and their justification.
- Specification questions discovered during implementation.
- Deferred work.
- Test and qualification evidence.
- Remaining limitations.

## Small-change exemption

Maintenance changes that don't alter public contracts, identity rules, evidence/provenance
semantics, qualification behavior, reconciliation logic, or release semantics don't need the full
plan-then-implement-then-reconcile workflow. When in doubt about whether a change is "small,"
default to treating it as substantial.

## Where to go next

For the full procedure, phase-by-phase guidance, and copy-paste plan/reconciliation templates, see
the [specification-driven-implementation skill](.agents/skills/specification-driven-implementation/SKILL.md).
Don't duplicate that procedure here — this file states *what's* mandatory, the skill states *how*
to execute it.

For build/lint/test commands and local dev setup, see [`docs/development.md`](docs/development.md).
For general contribution mechanics (branching, PRs, commit style), see
[`CONTRIBUTING.md`](CONTRIBUTING.md) — that file is unaffected by this workflow and covers a
different concern.
