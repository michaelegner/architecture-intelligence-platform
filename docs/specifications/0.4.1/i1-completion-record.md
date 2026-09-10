# I1 Completion Record — v0.4.1 Qualification Consistency

One concise record covering all three I1 slices, per this repository's established precedent
(`docs/specifications/0.4.0/i1-completion-record.md`). See
[`i1-qualification-consistency.md`](i1-qualification-consistency.md) for the full spec this record
qualifies against.

## Run identity

- **I1.1 (Shared Qualification Kernel):** merged to `main` as `27e1000` (PR #112, 2026-09-10).
- **I1.2 (Wire Both Existing Paths):** merged to `main` as `664857d` (PR #113, 2026-09-10) plus a
  same-PR review-round follow-up closing `_status_query`'s remaining hand-written OBSERVED
  predicate and a stale docstring reference (`4cc5a54`, squashed into `664857d` on merge).
- **I1.3 (Differential Qualification and Completion) candidate:**
  `385604b7c7098184b04193abf13727e90cd8b555` on branch
  `feature/v0.4.1-i1.3-differential-qualification` (PR #114) — the last code-changing commit (the
  first-round differential test and fix, `fc50cb0`, plus a review-round follow-up closing a real
  oracle blind spot in that same test and a docs clarification, `385604b`). This completion record
  is committed after it, changing no code the candidate's own CI needed to re-validate, per this
  repository's `v0.4.0` precedent (`i1-completion-record.md`'s own "Candidate identity" section).
- **CI, verified via the GitHub API against this exact SHA** (not `gh pr checks`, per this
  repository's standing rule that an unscoped/PR-view check query can silently miss what's actually
  attributed to the candidate commit —
  `gh api repos/michaelegner/architecture-intelligence-platform/commits/385604b.../check-runs`):
  `lint + test` ×2, `CodeQL`, `analyze (actions)`, `analyze (python)`,
  `dependency security scan (pip-audit, spec §29)` ×2 — all `completed`/`success`.
- **Environment / window used throughout the I1.3 differential fixture:** `qualification-test`,
  `2026-09-01T00:00:00Z`–`2026-09-02T00:00:00Z`.

## Regression suite (I1.3 candidate, full local run)

| Suite | Result |
|---|---|
| `uv run ruff check .` | clean |
| `uv run ruff format --check .` | clean |
| `uv run pytest tests/unit` | 867 passed |
| `uv run pytest tests/integration` | 248 passed |

867 unit tests is the same count I1.1 shipped with (I1.2 added zero new unit tests by design — both
existing suites passed unmodified, which was itself I1.2's regression-safety argument). 248
integration tests = the 244 pre-I1 baseline + 1 `environment=None` regression (I1.2) + 1 differential
test (I1.3) + 1 `until`-bound coverage regression (I1.3) + 1 open-ended-window (`until=None`)
regression (I1.3, spec §21.2).

## Differential test (spec §17-§22, §33, §38)

`tests/integration/test_qualification_consistency.py`, one hand-built graph fixture (deliberately
`PROVIDES`-free — see the module docstring), exercising the real production entry points on both
paths: `app.analysis.runtime.service_runtime_profile` and `ArchitectureIntelligenceService.
get_service_dependencies`.

18 relations covering the full Q1–Q15 matrix plus three coverage-driver relations (Q3/Q4/Q8, each
their own comparison key, per this repository's plan-review decision that drivers are first-class
fixture entries, not incidental scaffolding):

| Case | Relation | Evidence shape | Expected |
|---|---|---|---|
| Q1 | CALLS | declared + observed | `CONFIRMED` |
| Q2 | CALLS | observed only | `OBSERVED_ONLY` |
| Q3 (+ driver) | CALLS | declared-only + HTTP coverage driver | `NOT_OBSERVED_IN_WINDOW`/`SUFFICIENT` (+ driver `OBSERVED_ONLY`) |
| Q4 (+ driver) | CALLS | declared-only + messaging-only driver | `NOT_OBSERVED_IN_WINDOW`/`PARTIAL` (+ driver `OBSERVED_ONLY`) |
| Q5 | CALLS | declared-only, no other telemetry | `NOT_OBSERVED_IN_WINDOW`/`NONE` |
| Q6 | SENDS | declared + observed | `CONFIRMED` |
| Q7 | SENDS | observed only | `OBSERVED_ONLY` |
| Q8 (+ driver) | SENDS | declared-only + messaging driver | `NOT_OBSERVED_IN_WINDOW`/`SUFFICIENT` (+ driver `OBSERVED_ONLY`) |
| Q9 | CALLS | observed evidence in the wrong environment | `NOT_OBSERVED_IN_WINDOW`/`NONE` |
| Q10 | CALLS | observed before `window_start` | `NOT_OBSERVED_IN_WINDOW`/`NONE` |
| Q11 | CALLS | observed exactly at `window_start` (inclusive) | `CONFIRMED` |
| Q12 | CALLS | observed exactly at `window_end` (inclusive) | `CONFIRMED` |
| Q13 | CALLS | observed after `window_end` | `NOT_OBSERVED_IN_WINDOW`/`NONE` |
| Q14 | CALLS | dangling evidence reference | no supported claim (excluded from both outputs) |
| Q15 | SENDS | no evidence references at all | no supported claim (excluded from both outputs) |

**Required semantic completion statement (spec §38): qualification mismatches = 0, coverage
mismatches = 0, unexplained differential cases = 0.**

## Real pre-existing divergence found and fixed (spec §15)

The differential test's first run (before any fix) found exactly one mismatch — Q13, both paths
agreeing on qualification (`NOT_OBSERVED_IN_WINDOW`) but disagreeing on coverage (path A:
`SUFFICIENT`; path B: `NONE`, matching the hand-authored expected value). Per spec §15, this was
treated as a real pre-existing inconsistency rather than resolved silently:

- **Root cause:** `app/analysis/runtime.py`'s `declared_only_relations` (O4) called
  `telemetry_coverage(session, environment=environment, since=since, service_ids=subject_ids)`
  without passing `until` — so a service's O4 coverage annotation always used an open-ended upper
  bound regardless of what `until` `declared_only_relations` itself was given. This predates I1
  entirely (confirmed present in the original, pre-I1.1 file read at the start of this work).
- **Correct side, determined from governing semantics, not assumed:** the Python/MCP path's
  equivalent computation (`app/architecture_intelligence/repository.py`'s
  `read_service_dependency_rows`) already passed `until=window_end` explicitly — matching spec §12's
  normative "coverage... in this window/environment."
- **Fix:** `declared_only_relations`'s internal `telemetry_coverage` call now passes `until=until`.
  Only this one call site changed; nothing in path B was touched.
- **Regression test:** `tests/integration/test_runtime_analysis.py::
  test_o4_coverage_respects_an_explicit_until_bound` — confirmed to fail with the pre-fix code
  (`git stash`-verified during implementation) and pass with the fix, before being kept permanently.
- Full rationale also recorded in [ADR 0010](../../adr/0010-single-qualification-rule.md)'s
  "Implementation record" section.

## Scope preservation (spec §26-§27)

- `ArchitectureAnswer<T>` schema family: unchanged, `schema_version` still `"0.4"`.
- MCP surface: unchanged — `app/mcp/`, `app/architecture_intelligence/contracts.py`, and
  `schemas/architecture_intelligence/v0.4/` were not touched by any I1 commit.
- Canonical Model / Graph Schema: unchanged.
- `coverage_row_exists=False` (the shared kernel's "no coverage row" branch): supported and
  unit-tested, confirmed not reachable by either production caller today (both `telemetry_coverage`
  callers always synthesize exactly one coverage row per requested `service_id`) — deliberately not
  made reachable, since doing so would be a real behavior change to O5 outside I1's declared budget
  (repository-owner-confirmed decision, recorded in the I1.1 planning discussion).

## Documentation (spec §36)

`docs/analyses.md` and `docs/mcp.md` each state their surface's own window-default behavior and
carry the mandated cross-surface sentence verbatim: *"Equivalent effective observation contexts MUST
produce equivalent qualification semantics. Different effective observation windows MAY legitimately
produce different qualifications."*

## I1 exit statement (spec §40)

> GO — At `385604b7c7098184b04193abf13727e90cd8b555`, AIP's analysis/REST and
> ArchitectureIntelligenceService/MCP qualification paths are governed by one
> declared-versus-observed semantic owner
> (`app/qualification/declared_observed.py`). Against a shared deterministic real-Neo4j fixture,
> equivalent effective observation contexts produce qualification mismatches = 0 and coverage
> mismatches = 0 across CALLS and SENDS cases including declared-only, observed-only, confirmed,
> environment mismatch, window boundaries, and unsupported/dangling evidence. One real pre-existing
> coverage-window bug was found and fixed in the process, with its own permanent regression test.
> The shipped v0.4 public schemas and exactly three read-only MCP tools remain unchanged.

ADR 0010 moves from `Proposed` to `Accepted` on this record.
