# AIP v0.7.0 I0 — Completion Record

**Status:** **PROPOSED COMPLETE — pending merge of PR B.** Closure SHA: `PENDING_MERGE_SHA` (the two-step closure pattern: a small follow-up PR writes the real merge SHA from `gh pr view --json mergeCommit` after PR B merges).
**Terminal outcome (spec §18):** **`READY_FOR_I1`** — proposed by the agent, recorded by the owner on merging PR B.

This record covers the I0 specification [`i0-gateway-capability-survey-and-semantic-freeze.md`](i0-gateway-capability-survey-and-semantic-freeze.md) (merged #507, `9009ab9`) under the accepted parent [`specification.md`](specification.md). I0 is documentation and throwaway spike evidence only; it implements no adapter, schema, REST/MCP surface or runtime ingestion.

## Run identity

| Slice | Deliverables | PR | Merge commit | Merged (UTC) |
|---|---|---|---|---|
| I0.1 | [`i0-capability-survey-matrix.md`](i0-capability-survey-matrix.md), [`i0-spike/`](i0-spike/README.md) | #508 | `fbc8550b471886a09062f87433269ec6e50d8575` | 2026-10-12T08:02:26Z |
| I0.2 | decision, acquisition plan, dossier, handoff, this record | PENDING | `PENDING_MERGE_SHA` | PENDING |

Planning started at `2026-10-12T06:42:34Z` (recorded in each slice PR's hidden metadata marker). I0.1's merge commit was read from `gh pr view --json mergeCommit`.

## Owner decisions

| # | Decision | Where |
|---|---|---|
| D1 | Spike finalists: APISIX and Tyk | spike README |
| D2 | Select APISIX (O1) | decision §1 |
| D3 | Tyk is the I4 cross-check | decision §6 |
| D4 | Environment is operator-asserted capture context; coverage from capture metadata, never inferred from absence | decision §5 |

## I0 exit criteria (spec §18)

| Criterion | Status | Evidence |
|---|---|---|
| Four gateways have comparable evidence-backed rows | Met | Survey matrix §3, sources with retrieval date |
| Native configured-access semantics explicit for all four | Met | Matrix §2 |
| Vocabulary represents all four without calling the native relationship a generic subscription | Met | Decision §7; matrix §2 differences |
| One gateway selected by the §12 gates | Met | Decision §§1–2 |
| One differently shaped gateway retained for I4 | Met | Decision §6 |
| Selected consumer identity and secret boundary frozen | Met | Decision §§4.3, 8; dossier §1 |
| Configuration acquisition and replay path concrete | Met | Acquisition plan §2, §4; spike F13–F16 |
| Request-derived measurement acquisition and replay path concrete | Met | Acquisition plan §3; spike F1–F5 |
| Environment/window and coverage limits explicit | Met | Decision §5 |
| Identity mappings classified | Met | Dossier §2 |
| Proprietary-only dependencies explicit | Met | None on the selected path; Kong edition not established, recorded |
| I1 and I2 can start without inventing semantics | Met | Handoff §§1–4 |
| No adapter/schema/public API smuggled in | Met | Diff touches only `docs/` |

## Stop-condition check (spec §16)

None triggered; see decision §11.

## Deviations from the retained plan

- The plan's A3 step ("derive the eligible set from the matrix, then the owner chooses finalists") was not performed as a separate derivation in I0.1; the eligible set is derived in the decision record §2 (as the review of #508 requested).
- Extra APISIX Admin-API/etcd probe and a Tyk duplicate-alias probe were added after review of #508.

## Remaining limitations

- Kong and Gravitee were surveyed from documentation only; the Kong open-source status and Gravitee identifiers remain unestablished.
- Environment is operator-asserted; zero usage can only be stated under the manifest's closed-world assertion.
- Counter windows beyond a fresh-start fixture need a restart-detection mechanism that is not frozen.
- Evidence is from pinned images on one host (WSL2); no production gateway was inspected.
