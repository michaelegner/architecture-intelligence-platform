# AIP v0.7.0 I2 — Completion Record

**Status:** **COMPLETE.** Closed by PR #536, merge `97d459227fa879322258195e1e866b52db8a2970` (2026-10-14T13:25:53Z). The closure SHA was written into this record after that merge (the two-step closure pattern, as for I1).

This record covers the I2 specification [`i2-consumer-attribution-and-configured-vs-observed-qualification.md`](i2-consumer-attribution-and-configured-vs-observed-qualification.md) (merged #520) under the accepted parent [`specification.md`](specification.md). I2 implements runtime measurement, reconciliation and the configured-vs-observed qualification as internal state; it implements no public answer (I3).

## Run identity

| Slice | Deliverables | PR | Merge commit | Merged (UTC) |
|---|---|---|---|---|
| spec | I2 specification | #520 | `9930a1511cf2e6b8f209a1148346fff1df5b60d8` | 2026-10-13T16:43:31Z |
| I2.1 | [`i2-measurement-contract.md`](i2-measurement-contract.md), [`i2-vectors/`](i2-vectors/) | #522 | `55cd5d5263d709cff827bda5abf8e795311eda59` | 2026-10-13T18:17:58Z |
| I2.2a | measurement contract module, capture tool | #524 | `f3c2369311121c72f7808dba355c09a7e8bc6e5c` | 2026-10-13T19:40:10Z |
| I2.2a (fix) | first-in-window series read as starting at 0; stable-seconds evidence | #525 | `135d148471ac02738fc839395e59367ae98d48fd` | 2026-10-13T20:37:15Z |
| I2.2b | measurement source, discoverer, adapter | #526 | `9d6a53c6b682f98626430fc91a5e74f10013a85a` | 2026-10-13T22:09:14Z |
| I2.2c | persistence, lifecycle, `api_usage_v1` | #531 | `2b1ec0e596dbb5c71a149e02d8d8561453da1c39` | 2026-10-14T07:34:44Z |
| I2.3 | reconciliation | #535 | `7820408267bf148621147d71bb8d16dda502c017` | 2026-10-14T12:05:06Z |
| I2.4 | qualification, this record, the handoff | #536 | `97d459227fa879322258195e1e866b52db8a2970` | 2026-10-14T13:25:53Z |

The merge commits above were read from `gh pr view --json mergeCommit`. Each slice PR carries its own planning-start marker.

## Owner decisions taken during I2

| # | Decision | Where |
|---|---|---|
| D1 | Coverage is route-wide: a decreased, one-boundary or unattributed upstream series downgrades the whole Route | contract §7 |
| D2 | A first-in-window series is read as starting at 0 under stated preconditions (amendment, review of #524); the start boundary must be recorded stable for ≥ 20 s (review of #525) | I2 spec §5, contract §3 |
| D3 | Reconciliation and qualification are derived in the snapshot projection from stored facts, not persisted (v0.5.0 I3 precedent) | contract §10.2, I2.3/I2.4 plans |

## Definition of Done (I2 §13)

| DoD | Status | Evidence |
|---|---|---|
| Capture/replay deterministic and secret-safe | Met | I2.2 unit + real APISIX tests |
| Window/counter/coverage semantics match the I0 freeze incl. one-boundary/missing/decreasing | Met | vectors W, F, Q15–Q17, Q25–Q30 through production code |
| Consumer and Route attribution scoped to gateway and environment | Met | J03–J06; `test_v070_i2_qualification.py` cross-scope test |
| Route → Operation and target → Service obey §7; outcomes explicit; no similarity | Met | I2.3 vectors K, T |
| Qualification uses the bounded union, not a Cartesian product | Met | `test_the_universe_is_the_bounded_union_not_a_cartesian_product`, Q24 |
| P1, P2, N1–N4 pass against independently authored results incl. zero-delta coverage | Met | Q01–Q30 via `qualify`; integration `test_the_frozen_spec_cases_p1_p2_n1_to_n4_through_a_real_request` |
| Rejected and unattributed traffic cannot become usage; zero only under `SUFFICIENT_FOR_ZERO` | Met | Q09–Q13, Q27 |
| Snapshot/replay/removal deterministic | Met | replay no-op, replace, rejected-import and drop-registration integration tests |
| I1 configuration behavior green | Met | full unit and integration suites |
| No I3 public API/schema decision | Met | no new endpoint, tool, `SourceType` or `:Evidence` node |
| Handoff identifies the exact internal state | Met | [`i2-i3-handoff.md`](i2-i3-handoff.md) |

## Deviations from the retained plans

- The I2.1 contract's "source-series carrier" became the `MeasurementSeries` / `MeasurementLimitation` carriers in I2.2b (review of #526) so the I2.4 row universe survives.
- The first-in-window reading and the stable-seconds evidence were added after real-APISIX probing (reviews of #524, #525).
- Source identity was bound into the snapshot as a first-class window field in I2.2c (review of #531).
- Interactions, coverage and qualification rows are derived, not carriers; their M06/M09 ids are computed by the pure function.

## Remaining limitations

- The recorded stable seconds are the capture tool's attestation; replay cannot re-derive them.
- Neo4j omits null properties, so rows omit counts and deltas that do not exist.
- No public exposure of any of this (I3), no Tyk cross-check (I4), no restart/reset inference.
