# AIP v0.7.0 I4 — Coverage and Expectation Register

**Status:** I4.1a deliverable (I4 spec §4.1, §10). It freezes the mapping from each of the twelve parent §22 requirements to independent truth and an executable check, and the positive-versus-abstaining counts of §10. It claims no executed I4 run.
**Governing:** the [I4 specification](i4-deterministic-real-system-and-product-value-qualification.md) revision 0.2, parent [§22](specification.md), the [I4 decision record](i4-decision-record.md).
**Independent truth:** the frozen I3 oracle ([`i3-vectors/expected-answers.json`](i3-vectors/expected-answers.json): answer cases `A01`–`A20`, `E01a`–`E02c`, property cases `A14c`, `A15`, `C01`, request cases `V01`–`V22`), the I2 reconciliation vectors [`i2-vectors/reconciliation.json`](i2-vectors/reconciliation.json) (`K06`, `K08`) and the I4-only bridge vector `B07a`–`B07c` in [`i4-vectors/expected-i4.json`](i4-vectors/expected-i4.json), authored by [`i4-vectors/author_i4_expected.py`](i4-vectors/author_i4_expected.py) (stdlib only, no `app` import).

**Keys.** `S22-NN` is the NN-th item of the parent §22 list, in order. Statuses:
- `COVERED`: an independent expected outcome exists and an executable check asserts it today.
- `PARTIAL`: an anchor proves a narrower property; the Note names the gap and what closes it.
- `NEW_I4`: no earlier anchor; the cited `B` case is the independent expectation, executed in I4.2.
- `DOSSIER_ONLY`: qualified by the Tyk dossier alone; the frozen pipeline cannot express the condition, and no case is invented (I4 spec §4.1 row 6).
- `NOT_COVERED`: a documented blocker (none at freeze).

The executable-check column cites only checks that exist at this freeze. The real APISIX replay anchors (the replay test of I4.1c) are added to the rows that name a replay case, by I4.1c, before any candidate is chosen.

## 1. Parent §22 register

| Key | §22 requirement | Independent anchors | Executable check | Status | Note |
|---|---|---|---|---|---|
| S22-01 | configured plus observed | `A01`, `A15a` | `tests/unit/test_v070_i3_projection_oracle.py::test_the_projection_equals_the_expected_answer`, `tests/unit/test_v070_i3_adapter_oracle.py::test_rest_returns_the_expected_answer` | COVERED | Real replay case `P1` (allow-listed consumer with an upstream series) is added by I4.1c |
| S22-02 | configured plus no applicable measurement | `A03`, `A11`, `A13`, `A20` | `tests/unit/test_v070_i3_projection_oracle.py::test_the_projection_equals_the_expected_answer` | COVERED | `A13` is the typed no-window refusal. Real replay case `N1` (route with the Prometheus plugin disabled) is added by I4.1c |
| S22-03 | configured plus explicit measured zero | `A02` | `tests/unit/test_v070_i3_projection_oracle.py::test_the_projection_equals_the_expected_answer` | COVERED | Real replay case `P2` (closed coverage, no series) is added by I4.1c; metric absence alone is never zero |
| S22-04 | observed plus no matching configured access | `A04`, `A05` | `tests/unit/test_v070_i3_projection_oracle.py::test_the_projection_equals_the_expected_answer` | COVERED | `A05` is the rejected attempt that invents neither access nor usage. The replay plan has no observed-only row, so I4.1c adds a real case `OBS` |
| S22-05 | unattributed request | `A10` | `tests/unit/test_v070_i3_projection_oracle.py::test_the_projection_equals_the_expected_answer` | COVERED | Real replay case `N3` (`consumer=""` series) is added by I4.1c |
| S22-06 | ambiguous consumer identity | Tyk spike F6 (`i0-spike/README.md`, `i0-spike/tyk/dup-alias-output.txt`) | — | DOSSIER_ONLY | The frozen APISIX/I2 pipeline has no `AMBIGUOUS` consumer outcome and no Tyk adapter exists, so I4 invents no case. The Tyk dossier (I4.3) decides `REPRESENTABLE_WITH_SOURCE_SPECIFIC_DISTINCTION` or `MODEL_GAP`. An unresolvable label already yields the `A10` behaviour; that is not new ambiguity evidence |
| S22-07 | ambiguous Route to Operation mapping | `B07a`, `B07b`, `B07c`, I2 `K06`, `K08` | `tests/unit/test_v070_i4_register.py::test_the_bridge_world_equals_the_i2_rules_applied_to_its_raw_facts` | NEW_I4 | The I3 oracle has no public `AMBIGUOUS` answer. `B07` is the exact frozen handoff state; the check above verifies its *input* against `reconcile` and `qualify`. The answers are executed for the first time by the I4.2 runner on the candidate |
| S22-08 | gateway object distinct from application Service | `A06`, `A07`, `A08`, `A09`, `A19` | `tests/unit/test_v070_i3_projection_oracle.py::test_the_projection_equals_the_expected_answer` | COVERED | The Operation chain and the Service chain are independent in `B07a` as well |
| S22-09 | source revision removal or update | I2 lifecycle vectors | `tests/integration/test_v070_i2_qualification.py::test_a_replay_is_a_no_op_and_a_later_window_replaces_the_rows`, `tests/integration/test_v070_i2_measurement_source.py::test_dropping_the_registration_removes_its_carriers_and_the_snapshot_key` | PARTIAL | These prove replacement and removal on synthetic captures. The two real APISIX revisions R1 → R2 (a consumer removed from an allow-list, a Route removed, a Route added) and the stale cursor and ref refusal are added by I4.1c |
| S22-10 | same-snapshot evidence resolution | `E01a`, `E01b`, `E01c`, `E02a`, `E02b`, `E02c`, `A16`, `A17` | `tests/unit/test_v070_i3_adapter_oracle.py::test_mcp_returns_the_expected_answers_and_rejects_the_invalid_requests`, `tests/integration/test_api_usage_surface_parity.py::test_every_emitted_ref_resolves_on_every_surface_and_a_forged_one_does_not` | COVERED | Evidence resolution on the real replay is added by I4.1c |
| S22-11 | deterministic ordering and replay | `A14c`, `A15`, `A15a`, `A15b`, `A15d` | `tests/integration/test_api_usage_repeatability.py::test_two_clean_states_give_identical_answers_on_every_surface`, `tests/unit/test_api_usage_projection.py::test_the_answer_does_not_depend_on_the_order_of_the_input_rows` | COVERED | The A/B byte equality of I4.2 is gate G-03 below |
| S22-12 | v0.5/v0.6 dependency, locality, messaging and evidence regression | the frozen v0.5/v0.6 expectations and goldens | `tests/integration/test_architecture_intelligence_service.py::test_order_service_dependencies_resolve_confirmed_not_observed_and_unresolved`, `tests/integration/test_locality_surface_parity.py::test_service_rest_and_mcp_return_the_same_answer`, `tests/integration/test_broker_qualification.py::test_public_answers_carry_the_broker_claims_with_resolvable_evidence`, `tests/integration/test_i4_pubsub_qualification.py::test_service_rest_and_mcp_agree_with_zero_graph_writes`, `tests/integration/test_mcp_independent_client_golden_path.py::test_independent_client_completes_the_real_dependency_to_evidence_golden_path`, `tests/integration/test_snapshot_scoped_keys.py::test_without_v2_neither_key_exists_and_the_v0_5_keys_are_unchanged` | COVERED | The full unit and integration tiers run once on the candidate (I4 spec §4.3); these anchors are the named representatives per family |

## 2. Positive and abstaining outcomes per scenario class (I4 spec §10)

A class cannot pass because every execution abstained: each class names at least one case that resolves a positive outcome and at least one expected-negative case, both independently frozen. The class of every case is also frozen, by hand, in [`i4-vectors/expected-i4.json`](i4-vectors/expected-i4.json) (`classifications`): the comparator requires each ledger record to carry exactly that label (decision record D3), and the two columns below are checked against it.

| Class | Parent §22 | Positive or resolved cases | Expected-negative or abstaining cases |
|---|---|---|---|
| Usage | S22-01, S22-03, S22-04 | `A01`, `A02`, `A04` | `A05`, `A03` |
| Coverage and window | S22-02 | `A02` | `A03`, `A11`, `A12`, `A13`, `A20` |
| Attribution | S22-05 | `A01`, `A04` | `A10` |
| Associations | S22-07, S22-08 | `A08`, `A09`, `A01` | `A06`, `A07`, `A19`, `B07a`, `B07b` |
| Evidence | S22-10 | `E01a`, `E01b`, `E01c`, `B07c` | `E02a`, `E02b`, `E02c` |
| Paging and snapshot | S22-09, S22-11 | `A15a`, `A15b`, `A15d` | `A16`, `A17`, `A15e` |
| Request validation | method | `A01` | `V01`, `V02`, `V10`, `V16`, `V17`, `V21` |

## 3. Method gates (not §22 rows)

| Key | Requirement (I4 spec) | Independent expectation | Status |
|---|---|---|---|
| G-01 | §7: run `V01`–`V22` through the real REST routes (422) | `V01`–`V22` (`expected.validation_error`) | COVERED at I3; executed through the I4.2 runner |
| G-02 | §7: run `V01`–`V22` through negotiated MCP (tool error) | `V01`–`V22` | COVERED at I3; executed through the I4.2 runner |
| G-03 | §3: raw canonical-byte A/B equality per case and surface | the comparator of I4.1b | NEW_I4 |
| G-04 | §3, §7: byte-exact service = REST = MCP | the comparator of I4.1b | COVERED by `tests/integration/test_api_usage_surface_parity.py`; the byte comparison on the candidate is NEW_I4 |
| G-05 | §7: independent HTTP client discovers five tools, queries, resolves evidence and reconnects | `tests/integration/test_mcp_independent_client_golden_path.py::test_independent_client_runs_an_api_usage_query_and_resolves_its_evidence` | COVERED; rerun on the candidate |
| G-06 | §3: every artifact binds the exact candidate and the CI check-runs of that SHA | the profile of I4.1b and the [decision record](i4-decision-record.md) D1 | NEW_I4 |

## 4. Disclosures

- The I3 oracle's worlds are synthetic handoff states with synthetic snapshot ids; refs and cursors are literal only under those ids. The I4.2 runner on a real import compares structure and rebinds refs; it never edits an expected literal.
- `B07` is a synthetic world in the exact frozen I2 handoff shape. It is neither a real capture nor the APISIX replay.
- The `B07` expectation is frozen here and may not change after the first execution (I4 spec §13). The I4.1a freeze projected nothing. The I4.1b runner smoke (development mode, never eligible to qualify) exercises the tooling on it and matched the expectation unchanged; the first qualifying execution is the I4.2 runner on the candidate.
- Parent §22 item 3 holds "if the selected source can establish complete bounded coverage". I4.1c records whether the pinned APISIX capture procedure establishes it.
