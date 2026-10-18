# AIP v0.7.1 I2 — Completion Record

**Status:** COMPLETE on merge of the I2.3 PR (the closure SHA is added in a follow-up only if the owner asks).
**Outcome:** `READY_FOR_I3`, recorded by the owner on merging the I2.3 PR.

This record covers the I2 specification [`i2-service-mapping-and-attribution.md`](i2-service-mapping-and-attribution.md) under the I0 [decisions](i0-semantic-decision.md), the [I1 → I2 handoff](i1-i2-handoff.md) and the frozen [I2.1 contract](i2-kafka-service-mapping-contract.md). I2 implements an operator-supplied consumer-group → Service mapping source and the derived, snapshot-bound attribution of I1 attachments to declared Services. It implements no public answer (I3).

## Run identity

| Slice | Deliverables | PR | Merge commit | Merged (UTC) |
|---|---|---|---|---|
| I2 spec | [`i2-service-mapping-and-attribution.md`](i2-service-mapping-and-attribution.md) | #584 | `8a5446fd361fdc13615189d0d62682f29caabc7c` | 2026-10-17T19:41:19Z |
| I2.1 | [`i2-kafka-service-mapping-contract.md`](i2-kafka-service-mapping-contract.md), [`i2-vectors/`](i2-vectors/) | #585 | `f5121ffea6e0586507c0cd6ec314c509d2c9d04f` | 2026-10-18T11:05:44Z |
| I2.2 | mapping source, carriers, import wiring, lifecycle, pure group reconciliation | #586 | `b3f057704f7101e3f2d535361c16c55595017a65` | 2026-10-18T12:32:54Z |
| I2.3 | attribution rows, `kafka_consumer_attribution_v1`, alias binding, this record, [`i2-i3-handoff.md`](i2-i3-handoff.md) | this PR | read from `gh pr view --json mergeCommit` after merge | |

The merge commits above were read from `gh pr view --json mergeCommit,mergedAt`.

## Decisions and deviations

| # | What | Where |
|---|---|---|
| 1 | Declared candidates are the Service nodes with non-empty `owner_source_ids`; a runtime-only stub is never a candidate, so an `OBSERVED_ONLY` target reads `SERVICE_NOT_DECLARED` and its id never appears. | #585 contract §6 |
| 2 | Mixed unresolved reasons in one group: the group reason is the first of `SERVICE_NOT_DECLARED`, `SERVICE_IDENTITY_PLACEHOLDER`; each entry keeps its own reason. | #585 contract §7 |
| 3 | The snapshot block exists only when a mapping carrier exists, so Kafka without a mapping source keeps its exact I1 bytes. | #585 contract §9 |
| 4 | `aliases_applied` holds only the aliases whose key is a mapping `service_name`. An alias nobody uses cannot change the snapshot. | #584 review, #585 |
| 5 | An explicit `"service_namespace": null` is rejected (`KSM_ARTIFACT_INVALID`); an empty `mappings` list is a valid source with no entries. | #586 |
| 6 | Vector reading: `expected_groups` covers the vector's own broker and environment (C14's staging group is asserted separately); a case without `limitations` expects none. | #586 |
| 7 | The I1 consumer-state adapter's `supports()` now checks the schema string, as the I1.1 contract §1 says (it checked the source kind; the I1 record did not mention it). | #586, owner decision |
| 8 | Registering the mapping adapter re-evaluates every source once after upgrade (the adapter registry feeds the mapping-context digest); no content change. Same as I1 decision 4. | #586 |
| 9 | The configured `telemetry.service_aliases` are bound into the canonical snapshot state: every production snapshot reader passes them, so all tools report one `snapshot_id` for one graph and configuration. | I2.3 |
| 10 | No commit guard or source lock for the mapping source: it has no ordering rule and reads no graph state; two imports of one source instance share its discovery-scope lock. | #586 |

## Exit criteria (I2 §10)

| Criterion | Status | Evidence |
|---|---|---|
| Broker attachment and Service mapping remain independent evidence paths | Met | separate source kinds and carriers; integration `test_an_accepted_artifact_persists_only_internal_carriers`, `test_a_mapping_alone_is_a_group_row_without_an_attribution` |
| Only explicit mapping to a declared Service can resolve attribution | Met | unit `test_reconciliation_vectors[C04]`, `test_c04_a_runtime_stub_is_never_a_candidate_and_no_service_id_leaks`; integration `test_a_runtime_stub_service_is_not_declared` |
| Unresolved, ambiguous and conflicting mappings remain explicit | Met | unit `test_reconciliation_vectors` (C02, C04–C08, C10, C13, C14), `test_attribution_rows_match_the_vectors` |
| Mixed-source reconciliation follows the frozen rule | Met | unit `test_reconciliation_vectors` (C09–C13), `test_mixed_unresolved_reasons_pick_not_declared_first`, `test_ambiguous_wins_over_not_declared_when_nothing_resolves`, `test_a_placeholder_entry_is_a_limitation_of_a_resolved_group` |
| Every outcome retains the evidence needed to explain it | Met | unit `test_attribution_rows_match_the_vectors` (both evidence paths on every row), `test_no_mapping_row_keeps_the_attachment_evidence`, `test_entry_readings_and_limitations_are_kept_per_entry` |
| Resolved attribution carries both paths and T | Met | integration `test_attachment_plus_mapping_attributes_a_declared_service_with_both_paths` |
| Mapping alone creates no consumer claim or Kafka consumer identity | Met | integration `test_a_mapping_alone_is_a_group_row_without_an_attribution`, `test_an_accepted_artifact_persists_only_internal_carriers`; unit `test_c03_a_mapping_without_attachment_has_a_group_row_and_no_attribution` |
| No new canonical messaging relationship | Met | integration `test_attachment_plus_mapping_attributes_a_declared_service_with_both_paths` (relationship count and the rest of the state unchanged) |
| Required cases pass deterministically | Met | all I2 §7 cases below; unit `test_the_block_does_not_depend_on_input_order` |
| I1 and v0.7.0 behavior unchanged without a mapping source | Met | integration `test_l03_removing_the_last_mapping_source_restores_the_i1_bytes`, `test_l05_l06_no_mapping_source_means_no_block`; unit `test_registration_defaults_and_no_mapping_source_by_default`; full suites green |
| I2 → I3 handoff explicit | Met | [`i2-i3-handoff.md`](i2-i3-handoff.md) |

Each new guard was proven by disabling it and seeing its test fail: the retirement protection (#586), the runtime-stub filter and the alias binding on one service read path (I2.3).

## I2 §7 cases

| Case | Vector | Test |
|---|---|---|
| attachment + one mapping; + no mapping; mapping + no attachment | C01–C03 | unit `test_reconciliation_vectors`, `test_attribution_rows_match_the_vectors`, `test_c03_…`; integration `test_attachment_plus_mapping_…`, `test_a_mapping_alone_…` |
| OBSERVED_ONLY target; placeholder; ambiguous; conflicting | C04–C08 | unit as above; integration `test_a_runtime_stub_service_is_not_declared` |
| two sources same / different Service; one resolves, another does not | C09–C13 | unit as above |
| broker/environment mismatch; exact group id | C14, C15 | unit as above, `test_c14_the_other_environment_entry_is_its_own_group` |
| several members; one group on two Topics | C16, C17 | unit `test_c16_c17_one_row_per_attachment_one_service_per_group` |
| alias to a declared Service | C18 | unit as above; integration `test_every_read_path_binds_the_same_configured_aliases` |
| attachment disappears; mapping disappears; last source removed | L01–L03 | integration `test_l01_…`, `test_l02_…`, `test_l03_…` |
| rejected update; replay; replacement | L04, L07, L08 | integration `test_a_rejected_update_keeps_the_previous_entries_l04`, `test_replay_is_a_semantic_no_op_l07`, `test_a_later_valid_artifact_replaces_only_that_sources_entries_l08` |
| no mapping source; no Kafka and no mapping source | L05, L06 | integration `test_l05_l06_no_mapping_source_means_no_block` |
| artifact rejections; duplicate registrations | Q01–Q09 | unit `test_rejection_vectors`, `test_q07_…`, `test_q08_…`, `test_q09_…`; integration `test_q09_registrations_sharing_an_id_are_all_rejected_and_keep_prior_state` |
| identities | M01–M09 | unit `test_known_answer_ids_match_the_vectors` |

## Remaining limitations

- No public answer: the attribution is internal, snapshot-bound state (I3).
- The only mapping source kind is the operator-supplied artifact; no automatic mapping is inferred from group names, hosts or runtime identity.
- Attribution is as fresh as the last accepted capture (T) and the current mapping; the mapping itself has no observation time.
- Mapping evidence carriers are not `:Evidence` nodes; how they are exposed publicly is I3's decision, like the I1 capture evidence.
