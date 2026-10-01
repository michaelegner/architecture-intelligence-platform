# AIP v0.6.0 I2 — Conformance Matrix (I1 dossier L01–L37, 65 variants)

**Status:** I2.6b deliverable (I2 spec §15 I2.6 row, §16 DoD 8). It maps every variant of the independently authored I1 oracle ([`i1-vectors/conformance-expected.json`](i1-vectors/conformance-expected.json), 37 cases, 65 variants) to the executable tests that assert its expectation. Where I2 cannot reach a variant, the row says why and cites the decision or specification section. The oracle is read-only: no expected value was changed to match an implementation.
**Machine check:** `tests/unit/test_v060_i2_conformance_matrix.py` parses this table and requires three things. Every oracle variant appears exactly once. Every cited `path::test` exists; the check reads each file's AST, and class methods are written `path::Class::method`. Every `PARTIAL` or `NOT_REACHABLE` row cites a decision (`D…`) or a specification section (`§…`).

## How to read it
- **Kind:** which part of the expectation the variant fixes:
  - `ingestion`: I1 matrix §15.1, before anything is persisted;
  - `query`: a retained v2 candidate evaluated against a selected capture, phases 1–4;
  - `answer`: the answer when no v2 candidate exists;
  - `request`: the phase-1 check of the request itself;
  - `import`: a Kubernetes envelope the importer rejects;
  - `identity`: v1/v2 identifiers;
  - `snapshot`, `qualification`, `assessment`, `representation`, `cardinality`, `window`, `projection` and `structural`: as named.
- **Evidence:**
  - Oracle-driven suites parametrise directly over the oracle JSON:
    - `test_ingestion_outcome_matches_the_independent_oracle` covers every ingestion variant;
    - `test_every_single_capture_oracle_row` / `…_end_to_end` cover every single-capture query row, in pure form and against real imports;
    - `test_without_eligible_v2_the_answer_abstains` covers the answer rows.
  - The other cited tests assert the variant's remaining fields: v2/v1 IDs, timestamps, lineage, counts.
  - The rehearsal replay tests (`test_locality_rehearsal_replay.py`) assert the same outcomes on the real `kind` recording of I2.6a. That recording is labelled REHEARSAL – NOT I5.
- **Status:**
  - `COVERED`: every expected field is asserted.
  - `PARTIAL`: the I2-scoped fields are asserted and the rest belongs to a later increment, as cited.
  - `NOT_REACHABLE`: I2 cannot produce the variant, as cited.

## Matrix

| Variant | Kind | Executable evidence | Status | Note |
|---|---|---|---|---|
| L01a | identity | `tests/unit/test_scoped_observed_call_v2_id.py::test_the_implementation_reproduces_every_independent_vector`<br>`tests/unit/test_scoped_observed_call_v2_id.py::test_reordered_input_is_the_same_identity` | COVERED |  |
| L02a | identity | `tests/unit/test_scoped_observed_call_v2_id.py::test_the_implementation_reproduces_every_independent_vector`<br>`tests/unit/test_scoped_observed_call_v2_id.py::test_distinct_pod_cluster_operation_day_and_environment_are_distinct_identities`<br>`tests/unit/test_scoped_observed_call_v2_id.py::test_the_v1_evidence_id_is_unchanged_and_has_no_pod_or_cluster` | COVERED |  |
| L03a | identity | `tests/unit/test_scoped_observed_call_v2_id.py::test_the_implementation_reproduces_every_independent_vector`<br>`tests/unit/test_scoped_observed_call_v2_id.py::test_distinct_pod_cluster_operation_day_and_environment_are_distinct_identities` | COVERED |  |
| L04a | query, identity | `tests/unit/test_scoped_applicability.py::test_l27a_two_localities_coexist_for_one_caller_service`<br>`tests/integration/test_local_assessment.py::test_the_oracle_ids_reproduce_the_frozen_assertion_vectors`<br>`tests/unit/test_scoped_observed_call_v2_id.py::test_the_v1_evidence_id_is_unchanged_and_has_no_pod_or_cluster`<br>`tests/unit/test_local_assessment.py::test_the_assessment_carries_its_capture_lineage_and_source_limitations` | PARTIAL | `provider_services` (the Operation -> provider Service projection) is the I3 public roll-up, I1 §5.1; I2 qualifies per Operation only. |
| L05a | answer | `tests/unit/test_local_assessment.py::test_without_eligible_v2_the_answer_abstains` | COVERED |  |
| L05b | answer | — | NOT_REACHABLE | `LOCALITY_LEGACY_V1_UNSCOPED` is never emitted in v0.6 (D8); L05a's generic abstention is the valid I1 outcome. |
| L06a | ingestion | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle` | COVERED |  |
| L06b | ingestion | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle` | COVERED |  |
| L06c | ingestion | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle` | COVERED |  |
| L06d | answer | `tests/unit/test_local_assessment.py::test_without_eligible_v2_the_answer_abstains` | COVERED |  |
| L07a | ingestion, identity | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle`<br>`tests/unit/test_scoped_attribution.py::test_eligible_seed_hashes_to_the_i1_golden_v2_id`<br>`tests/unit/test_scoped_attribution.py::test_paired_seed_takes_its_day_and_time_from_the_accepted_fact_not_the_client`<br>`tests/unit/test_adapter.py::test_every_pairing_path_yields_the_same_seed_for_the_same_calls` | COVERED |  |
| L08a | ingestion, identity | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle`<br>`tests/unit/test_adapter.py::test_every_pairing_path_yields_the_same_seed_for_the_same_calls`<br>`tests/integration/test_locality_rehearsal_replay.py::test_attempt_1_keeps_client_identity_in_the_client_first_order` | COVERED |  |
| L08b | ingestion, identity | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle`<br>`tests/unit/test_adapter.py::test_every_pairing_path_yields_the_same_seed_for_the_same_calls`<br>`tests/integration/test_locality_rehearsal_replay.py::test_c1_yields_the_two_workload_answer_and_every_call_keeps_its_client_identity` | COVERED |  |
| L09a | ingestion, identity | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle`<br>`tests/unit/test_adapter.py::test_client_only_expiry_keeps_the_original_client_identity`<br>`tests/unit/test_scoped_attribution.py::test_client_only_seed_uses_the_shared_instant` | COVERED |  |
| L09b | ingestion | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle`<br>`tests/unit/test_adapter.py::test_server_only_is_recorded_as_a_refusal_and_never_a_seed` | COVERED |  |
| L10a | ingestion | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle`<br>`tests/unit/test_adapter.py::test_environment_and_day_mismatches_are_ingestion_refusals_with_v1_unchanged` | COVERED |  |
| L10b | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end`<br>`tests/unit/test_scoped_applicability.py::test_l10b_carries_the_internal_environment_limitation_and_no_locality_code`<br>`tests/integration/test_scoped_evidence_repository.py::test_environment_and_day_are_never_filters` | COVERED |  |
| L11a | ingestion | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle`<br>`tests/unit/test_scoped_attribution.py::test_cross_midnight_pair_is_refused_and_keeps_the_v1_day`<br>`tests/unit/test_adapter.py::test_a_cross_midnight_pair_keeps_its_v1_day_and_gets_no_seed` | COVERED |  |
| L12a | representation | `tests/integration/test_v060_i2_conformance_gaps.py::test_l12a_one_interaction_has_exactly_one_v1_and_one_v2_representation` | COVERED |  |
| L13a | snapshot | `tests/integration/test_snapshot_scoped_keys.py::test_without_v2_neither_key_exists_and_the_v0_5_keys_are_unchanged`<br>`tests/integration/test_mcp_demo_script.py::TestServeLifecycle::test_full_lifecycle` | COVERED | The demo lifecycle test classifies the golden demo `COMPLETE` against the pinned `0bfcbded…`. |
| L14a | snapshot | `tests/integration/test_snapshot_scoped_keys.py::test_the_d15_fixture_graph_yields_the_frozen_after_snapshot`<br>`tests/integration/test_snapshot_scoped_keys.py::test_every_answer_carries_the_same_one_snapshot` | COVERED |  |
| L15a | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end` | COVERED |  |
| L16a | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end` | COVERED |  |
| L17a | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end` | COVERED |  |
| L17b | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end` | COVERED |  |
| L17c | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end` | COVERED |  |
| L17d | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end`<br>`tests/integration/test_scoped_evidence_repository.py::test_environment_and_day_are_never_filters` | COVERED |  |
| L17e | import | `tests/integration/test_v060_i2_conformance_gaps.py::test_l17e_an_envelope_without_captured_at_is_rejected_invalid_and_never_selectable`<br>`tests/integration/test_scoped_applicability.py::test_a_rejected_envelope_writes_no_selectable_capture` | COVERED |  |
| L18a | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end`<br>`tests/unit/test_scoped_applicability.py::test_l18_the_replaced_pod_stays_attributed_to_its_own_record`<br>`tests/integration/test_scoped_applicability.py::test_c1_then_c2_changes_the_answer_and_keeps_the_record` | COVERED |  |
| L19a | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end` | COVERED | CAP-AMB realized per D13.1. |
| L19b | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end` | COVERED | CAP-CONF realized per D13.1. |
| L20a | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end`<br>`tests/unit/test_local_assessment.py::test_the_assessment_carries_its_capture_lineage_and_source_limitations` | COVERED |  |
| L21a | query, qualification | `tests/unit/test_local_assessment.py::test_l21_an_applicable_declaration_confirms_the_local_call`<br>`tests/integration/test_local_assessment.py::test_the_two_workload_demonstration_with_the_real_adapters` | COVERED |  |
| L22a | query, qualification | `tests/unit/test_local_assessment.py::test_l22_without_its_own_declaration_the_call_is_observed_only`<br>`tests/integration/test_local_assessment.py::test_the_two_workload_demonstration_with_the_real_adapters` | COVERED |  |
| L22b | qualification | `tests/unit/test_local_assessment.py::test_l22_without_its_own_declaration_the_call_is_observed_only` | COVERED |  |
| L23a | answer | `tests/unit/test_local_assessment.py::test_without_eligible_v2_the_answer_abstains`<br>`tests/integration/test_local_assessment.py::test_without_v2_the_answer_abstains` | COVERED |  |
| L24a | request | `tests/unit/test_scoped_applicability.py::test_phase_one_terminates_the_request` | COVERED |  |
| L24b | request | `tests/unit/test_scoped_applicability.py::test_phase_one_terminates_the_request` | COVERED |  |
| L25a | request | `tests/unit/test_scoped_applicability.py::test_phase_one_terminates_the_request` | COVERED |  |
| L25b | window | `tests/unit/test_scoped_applicability.py::test_every_membership_vector`<br>`tests/unit/test_scoped_attribution.py::test_utc_day` | COVERED |  |
| L26a | answer | `tests/unit/test_local_assessment.py::test_without_eligible_v2_the_answer_abstains` | COVERED |  |
| L27a | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end`<br>`tests/unit/test_scoped_applicability.py::test_l27a_two_localities_coexist_for_one_caller_service`<br>`tests/integration/test_locality_rehearsal_replay.py::test_c1_yields_the_two_workload_answer_and_every_call_keeps_its_client_identity` | COVERED |  |
| L27b | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end`<br>`tests/integration/test_scoped_applicability.py::test_c1_then_c2_changes_the_answer_and_keeps_the_record`<br>`tests/integration/test_locality_rehearsal_replay.py::test_c2_keeps_p1_s_record_and_unresolves_it` | COVERED |  |
| L28a | cardinality | `tests/integration/test_v060_i2_conformance_gaps.py::test_l28a_n_pods_of_one_workload_are_n_v2_records_and_one_v1_bucket` | COVERED | The cost obligation itself is measured in I2.6c (I2 §14). |
| L29a | import | `tests/integration/test_v060_i2_conformance_gaps.py::test_l29a_an_incomplete_capture_is_rejected_and_the_committed_one_stays_selected` | COVERED |  |
| L29b | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end` | COVERED |  |
| L30a | structural | `tests/unit/test_local_assessment.py::test_l30_no_narrative_or_intent_input_exists` | COVERED | Realized structurally: v0.6 has no Intent input (D14.6). |
| L31a | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end` | COVERED |  |
| L32a | qualification | `tests/unit/test_local_assessment.py::test_l32a_each_operation_is_qualified_on_its_own` | PARTIAL | `logical_provider`, `group_evidence` and `group_shape` are the I3 Service roll-up, I1 §5.1. |
| L32b | projection | — | NOT_REACHABLE | I2 mints no provider Service dependency at all; I3 owns the roll-up and its missing/ambiguous-owner rule, I1 §5.1. |
| L33a | assessment | `tests/unit/test_scoped_applicability.py::test_l33_two_replica_sets_of_one_deployment_are_one_workload`<br>`tests/unit/test_local_assessment.py::test_l33a_two_pods_of_one_workload_are_one_assertion` | COVERED |  |
| L33b | assessment | `tests/unit/test_local_assessment.py::test_l33b_two_workloads_are_two_assertions`<br>`tests/integration/test_locality_rehearsal_replay.py::test_c1_yields_the_two_workload_answer_and_every_call_keeps_its_client_identity` | COVERED |  |
| L34a | ingestion, query | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle`<br>`tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end` | COVERED |  |
| L34b | ingestion | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle` | COVERED |  |
| L35a | ingestion | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle` | COVERED |  |
| L35b | ingestion | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle` | COVERED |  |
| L35c | ingestion | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle` | COVERED |  |
| L35d | ingestion | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle` | COVERED |  |
| L35e | ingestion | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle` | COVERED |  |
| L35f | ingestion | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle` | COVERED |  |
| L35g | ingestion | `tests/unit/test_scoped_attribution.py::test_ingestion_outcome_matches_the_independent_oracle` | COVERED |  |
| L35h | answer | `tests/unit/test_local_assessment.py::test_without_eligible_v2_the_answer_abstains` | COVERED |  |
| L35i | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end` | COVERED |  |
| L36a | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end`<br>`tests/unit/test_scoped_applicability.py::test_later_phases_are_never_evaluated_after_a_terminating_one` | COVERED |  |
| L37a | query | `tests/unit/test_scoped_applicability.py::test_every_single_capture_oracle_row`<br>`tests/integration/test_scoped_applicability.py::test_every_single_capture_oracle_row_end_to_end`<br>`tests/unit/test_scoped_applicability.py::test_later_phases_are_never_evaluated_after_a_terminating_one` | COVERED |  |

## Summary

- **Covered:** 61 of the 65 variants have every expected field asserted by an executable test.
- **Partial (2):** L04a and L32a. Their per-Operation parts are asserted; the Operation → provider Service projection and the Service-level group are the I3 public roll-up (I1 §5.1).
- **Not reachable in I2 (2):**
  - L05b: `LOCALITY_LEGACY_V1_UNSCOPED` is never emitted in v0.6 (D8).
  - L32b: I2 mints no provider Service dependency at all (I1 §5.1).
- **Gap tests added in I2.6b:** `test_v060_i2_conformance_gaps.py` (L12a, L17e, L28a, L29a), plus L06d in the abstention parametrisation.
