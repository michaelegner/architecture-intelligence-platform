# AIP v0.7.0 I1 — Completion Record

**Status:** **PROPOSED COMPLETE — pending merge of the I1.4 PR.** Closure SHA: `PENDING_MERGE_SHA` (two-step closure: a small follow-up PR writes the real merge SHA from `gh pr view --json mergeCommit`).

This record covers the I1 specification [`i1-selected-gateway-configuration-source.md`](i1-selected-gateway-configuration-source.md) (merged #511) under the accepted parent [`specification.md`](specification.md) and the I0 freeze. I1 implements the APISIX configuration source; it implements no runtime measurement, reconciliation or public answer (I2/I3).

## Run identity

| Slice | Deliverables | PR | Merge commit | Merged (UTC) |
|---|---|---|---|---|
| I1.1 | [`i1-gateway-source-contract.md`](i1-gateway-source-contract.md), [`i1-vectors/`](i1-vectors/) | #512 | `3521d9e05a1770bfe30e150162679f7519ea70b5` | 2026-10-12T17:51:50Z |
| I1.2 | conditional OpenAPI contract carriers | #514 | `8ad711bb6dd8fa1eef98c728656242649271700a` | 2026-10-12T19:43:58Z |
| I1.3 | capture tool, shared envelope, redaction | #515 | `4734249d17e0a05e243ebfc35e3705d7f7c617c5` | 2026-10-13T08:22:16Z |
| I1.4 | gateway source, state, ConfiguredAccess, lifecycle, docs, this record, the handoff | PENDING | `PENDING_MERGE_SHA` | PENDING |

The merge commits for I1.1-I1.3 were read from `gh pr view --json mergeCommit`. Planning started at `2026-10-12T09:55:36Z` (each slice PR's hidden metadata marker).

## Owner decisions taken during I1

| # | Decision | Where |
|---|---|---|
| D1 | Four slices (I1.1-I1.4) | plan |
| D2 | Contract carriers gated on the import request's configuration (each configured source is its own discovery run), not on a run's contents | I1.1 contract §6, I1.2 |
| D3 | Additive in-place amendment of the frozen `aip-import-report/1` schema for `apisix` runs and `GW_*` codes | contract §7, `schemas/import/v0.5/` |

Decisions the agent took inside the spec's freedom, reviewed in the slice PRs: gateway source evidence is a dedicated internal carrier, not a `Provenance` (contract §4, amended); the `GatewayLimitation` carrier; `created_index` / `modified_index` retained per object (I0 plan §2.3); `GW_CAPTURE_LIMIT_EXCEEDED` and `GW_CONFIGURATION_LIMITATIONS` codes.

## Definition of Done (I1 §8)

| DoD | Status | Evidence |
|---|---|---|
| Capture produces a complete, revision-consistent, normalized fixture; replay deterministic | Met | I1.3 tool + real APISIX/etcd tests; `test_an_accepted_capture_maps_and_replays_deterministically`; replay no-op integration test |
| Discovery uses the production discoverer; invalid sources take the normal rejected path | Met | `test_rejection_vectors_through_the_production_discoverer` (R01-R08) |
| Secret canaries, including the Admin API key, absent from retained and diagnostic outputs | Met | I1.3 canary tests; I1.4 unredacted-fixture rejection (code only, no value) |
| Gateway identities and configured-access semantics match the I0 freeze | Met | vectors V01-V07, V13, C01-C15 through the production mapping |
| New canonical identity assumptions have graph constraints | Met | six gateway constraints + three contract constraints in `app/graph/schema.py` |
| Updates/removals atomic and bounded to APISIX-owned state | Met | `test_a_later_complete_capture_authoritatively_removes_what_is_gone`; rejected-capture test |
| Contract associations explicit; `Operation` ids preserved; no-gateway snapshot unchanged | Met | I1.2 golden pin (`aip:snapshot:v1:e90e0868…00a1`, path-normalized) |
| Minimum qualification cases pass | Met | contract §8 map; unit + integration modules named in the PRs |
| Existing v0.5/v0.6 behavior green | Met | full unit and integration suites |
| Model/ingestion documentation updated | Met | `canonical-model.md`, `graph-model.md`, `ingestion.md`, `adapter-development.md`, `evidence.md` |
| Handoff identifies canonical / source-qualified / unresolved | Met | [`i1-i2-handoff.md`](i1-i2-handoff.md) |

## Deviations from the retained plan

- The plan listed `GatewayLimitation` and the source-evidence carrier implicitly under "gateway entities"; both are explicit carriers in the model.
- The import-report schema amendment (D3) was not anticipated by the plan; it was raised and decided during I1.4.
- Gateway evidence is a carrier, not a `Provenance` (contract §4 amended), to avoid widening the public evidence and natural-language guards.

## Remaining limitations

- No runtime usage, no Route↔Operation or upstream↔Service reconciliation (I2); no public exposure (I3).
- A configured but rejected gateway still leaves the OpenAPI-side contract carriers in place (the rejection only blocks the gateway run).
- A non-string `info.version` now yields no version rather than crashing the OpenAPI adapter (fixed in I1.2).
- The first import after upgrade re-evaluates every source once (the adapter registry is part of the mapping-context digest); no graph content or snapshot id changes.
