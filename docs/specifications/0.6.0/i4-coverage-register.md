# AIP v0.6.0 I4 — Coverage and Expectation Register

**Status:** I4.1 deliverable (I4 spec §3, §8). It freezes the mapping from every parent §20 scenario to independent truth and an executable check. It claims no executed I4 run.
**Governing:** [I4 specification](i4-deterministic-semantic-qualification.md) revision 0.2, parent [§20](specification.md), the [I4 decision record](i4-decision-record.md).
**Independent truth:** frozen I1 oracle (`L01`–`L37`), I3 oracle (`X01`–`X28`, `P01`–`P09`, `Q01`–`Q08`), and the I4-only bridge vectors `B01a`, `B01b`, `B02`–`B06` in [`i4-vectors/expected-i4.json`](i4-vectors/expected-i4.json), authored by [`author_i4_expected.py`](i4-vectors/author_i4_expected.py) before any run.

**Keys.** `S20-NN` is the NN-th row of the parent §20 table, in table order (D1). Statuses:
- `COVERED`: an independent expected outcome exists and an executable check asserts it.
- `PARTIAL`: an anchor proves a narrower property; the Note names the gap and the `B` case or decision closing it in I4.2.
- `NEW_I4`: no earlier anchor; the cited `B` case is the independent expectation, executed in I4.2.
- `NOT_COVERED`: a documented blocker (none at freeze).

## 1. §20 register

| Key | Group | §20 scenario | Independent anchors | Executable check | Status | Note |
|---|---|---|---|---|---|---|
| S20-01 | 1 | Two caller Workloads, two dependencies | `X01`, `X02`, `X04`, `X18`, `X19`, `L04` | `tests/integration/test_locality_oracle.py::test_the_rehearsal_answer_matches_the_oracle` | COVERED | |
| S20-02 | 2 | v1 bucket plus separate Pod identity | `L05`, `L26` | `tests/unit/test_local_assessment.py::test_without_eligible_v2_the_answer_abstains` | PARTIAL | L05b is NOT_REACHABLE in v0.6 (I2 matrix, D8). The no-retroactive-`CALLS` property is checked at answer level by `B02`. |
| S20-03 | 2 | Concurrent v1/v2, replay/order/cross-batch | `L08`, `L12`, `L28`, `P07` | `tests/integration/test_v060_i2_conformance_gaps.py::test_l12a_one_interaction_has_exactly_one_v1_and_one_v2_representation` | COVERED | |
| S20-04 | 4 | Bounded enumeration, inventory over bound | `P01`, `P02`, `P03`, `X10`, `X25` | `tests/integration/test_locality_oracle.py::test_p02_the_i2_page_boundary_is_walked_on_one_snapshot` | COVERED | |
| S20-05 | 2 | Declaration plus scoped call: `CONFIRMED` | `L21`, `X01` | `tests/integration/test_locality_oracle.py::test_the_rehearsal_answer_matches_the_oracle` | COVERED | |
| S20-06 | 2 | Scoped observation, no declaration: `OBSERVED_ONLY` | `L22`, `X01` | `tests/integration/test_locality_oracle.py::test_the_rehearsal_answer_matches_the_oracle` | COVERED | |
| S20-07 | 2 | Service-level coverage, no local evidence | `L05`, `L23`, `X07` | `tests/integration/test_locality_oracle.py::test_the_answer_matches_the_oracle` | COVERED | |
| S20-08 | 4 | Full UTC day versus partial-day window | `L25`, `X08`, `X23` | `tests/integration/test_locality_oracle.py::test_the_answer_matches_the_oracle` | COVERED | |
| S20-09 | 1 | Two localities, different targets | `X02`, `X15`, `X16`, `X19` | `tests/integration/test_locality_oracle.py::test_the_rehearsal_answer_matches_the_oracle` | COVERED | |
| S20-10 | 7 | `DEPLOYED_AS` mapping, no admissible Pod UID | `L26`, `L06` | `tests/integration/test_snapshot_scoped_keys.py::test_every_answer_carries_the_same_one_snapshot` | PARTIAL | The shared-snapshot pin exists; no answer-level check that a mapping alone yields no local `CALLS`. Closed by `B02`. |
| S20-11 | 3 | Pod UID plus time-compatible owner capture | `L15`, `X01`, `X11` | `tests/integration/test_locality_oracle.py::test_the_rehearsal_answer_matches_the_oracle` | COVERED | |
| S20-12 | 3 | Same-day canary P1 → P3, captures before/after | `B01a`, `B01b`, `X03`, `P08`, `L18`, `L27` | `tests/integration/test_locality_oracle.py::test_p08_a_c1_snapshot_is_refused_after_c2` | NEW_I4 | `X03`/`P08` show P1's disappearance but never a replacement Pod P3 (I4 §3). `B01a` (Workload UID unchanged) and `B01b` (new Workload UID) are the mandatory bridge. |
| S20-13 | 7 | No v2 versus eligible v2 | `L13`, `L14` | `tests/integration/test_snapshot_scoped_keys.py::test_without_v2_neither_key_exists_and_the_v0_5_keys_are_unchanged` | COVERED | |
| S20-14 | 6 | Name/namespace/label/co-location only | `L26`, `L33`, `L34` | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row` | COVERED | |
| S20-15 | 6 | Declaration without explicit regional binding | `L24`, `X20`, `X21` | `tests/integration/test_locality_oracle.py::test_the_answer_matches_the_oracle` | NEW_I4 | `X20`/`X21` prove only the refusal of a region/tenant request. `B03` checks that no per-region declared assertion exists. |
| S20-16 | 1 | Known localities, different target edges | `L04`, `X02`, `X19` | `tests/integration/test_locality_oracle.py::test_the_rehearsal_answer_matches_the_oracle` | COVERED | |
| S20-17 | 5 | Contradictory identity paths in one locality | `L19`, `L37`, `X14` | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row` | COVERED | |
| S20-18 | 4 | Missing cluster UID, unsupported region/tenant, wrong namespace, stale capture | `L06`, `L10`, `L16`, `L34`, `X09`, `X12`, `X20`, `X21` | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle` | COVERED | |
| S20-19 | 4 | No eligible scoped call, declared-only relation | `L23`, `X07`, `X13` | `tests/integration/test_locality_oracle.py::test_the_answer_matches_the_oracle` | COVERED | |
| S20-20 | 5 | Snapshot changes between result and drill-down | `X24`, `X28`, `P04`, `P08` | `tests/integration/test_locality_oracle.py::test_every_case_is_executed` | COVERED | |
| S20-21 | 4 | Reimport, reorder, disappearance, authorized removal | `L29`, `P07` | `tests/integration/test_v060_i2_conformance_gaps.py::test_l29a_an_incomplete_capture_is_rejected_and_the_committed_one_stays_selected` | COVERED | |
| S20-22 | 6 | Caller locality evidenced, target locality missing | `L20`, `B04` | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row` | PARTIAL | `L20` is single-capture; `B04` asserts `target_runtime_scope` is `UNKNOWN` in a full answer. |
| S20-23 | 6 | Two one-hop edges, no causal path | `B04` | `tests/integration/test_locality_oracle.py::test_every_case_is_executed` | NEW_I4 | No earlier anchor. |
| S20-24 | 6 | Intent-like document or narrative added | `L30`, `B05` | `tests/unit/test_local_assessment.py::test_l30_no_narrative_or_intent_input_exists` | PARTIAL | `L30` shows no such input exists in the assessment path; `B05` checks bytes and snapshot are unchanged when one is ingested. |
| S20-25 | 7 | v0.5.1 Quarkus replay plus AsyncAPI overlay | `B06` | `tests/unit/test_quarkus_v05_dossier.py::test_derived_manifest_regenerates_byte_for_byte_and_only_adds_namespace_lines` | PARTIAL | The v0.5.1 pins are frozen; `B06` runs them with scoped evidence enabled and expects no new locality or Kafka observation. |

## 2. Adapter-level and method gates (not §20 rows)

| Key | Requirement (I4 spec) | Independent expectation | Status |
|---|---|---|---|
| G-01 | §5: execute `Q01`–`Q08` through the real REST routes (HTTP 422) | `Q01`–`Q08` (`expected.validation_error`) | NEW_I4 |
| G-02 | §5: execute `Q01`–`Q08` through negotiated MCP (`isError: true`) | `Q01`–`Q08` | NEW_I4 |
| G-03 | §4.4: raw canonical-byte A/B equality per case and surface | [ledger design](i4-ledger-and-comparator-design.md) §3 | NEW_I4 |
| G-04 | §4.4/§5: exact-byte service = REST = MCP, wrapper removed | [ledger design](i4-ledger-and-comparator-design.md) §3 | COVERED by `X01`–`X28` parity at the I3 level; byte-level comparison is NEW_I4 |

## 3. Disclosures

- The rehearsal worlds are `REHEARSAL – NOT I5`. I3's P08 predecessor-copy and X25 synthetic capture-clone deviations remain disclosed.
- `B01`–`B06` use synthetic generated envelopes. They are neither the I5 capture nor the rehearsal.
- `B02`–`B06` state a world and a delta, not a full answer. The runner builds them in I4.2 from the I3 K world; the expected and forbidden facts are frozen here and may not change after the first run (I4 §4).
- The `NOT_REACHABLE` and `PARTIAL` I2 variants (`L04a`, `L05b`, `L32a`, `L32b`) stay accounted for in [`i2-conformance-matrix.md`](i2-conformance-matrix.md); I4 does not edit them.
