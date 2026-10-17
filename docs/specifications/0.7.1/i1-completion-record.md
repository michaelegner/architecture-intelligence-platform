# AIP v0.7.1 I1 — Completion Record

**Status:** COMPLETE on merge of the I1.4 PR (the closure SHA is added in a follow-up only if the owner asks).
**Outcome:** `READY_FOR_I2`, recorded by the owner on merging the I1.4 PR.

This record covers the I1 specification [`i1-kafka-consumer-state-source.md`](i1-kafka-consumer-state-source.md) under the I0 [decisions](i0-semantic-decision.md) and the frozen [I1.1 contract](i1-kafka-source-contract.md). I1 implements the Kafka consumer-state source: consumer-group attachment to already-declared Topics. It implements no Service mapping, attribution or public answer (I2/I3).

## Run identity

| Slice | Deliverables | PR | Merge commit | Merged (UTC) |
|---|---|---|---|---|
| I1 spec | [`i1-kafka-consumer-state-source.md`](i1-kafka-consumer-state-source.md) | #579 | `d4174477c1491ed2da7f6e4409453f7b28cc7b0d` | 2026-10-16T11:57:14Z |
| I1.1 | [`i1-kafka-source-contract.md`](i1-kafka-source-contract.md), [`i1-vectors/`](i1-vectors/) | #580 | `bde3f7ff8cda05f034c78df0a3f3365c770520c8` | 2026-10-16T12:21:58Z |
| I1.2 | registration, ids, capture contract, loader, capture step | #581 | `18574c95c5f8a0fe053bc4baae6226cd8015f43e` | 2026-10-16T13:30:53Z |
| I1.3 | carriers, discoverer/adapter, import wiring, lifecycle, commit guard | #582 | `6d73d049fffb8ef5d876a9b472e3d560634606c7` | 2026-10-16T16:30:32Z |
| I1.4 | this record, [`i1-i2-handoff.md`](i1-i2-handoff.md), member-text retention fix (decision 7) | this PR | read from `gh pr view --json mergeCommit` after merge | |

The merge commits above were read from `gh pr view --json mergeCommit,mergedAt`.

## Decisions and deviations

| # | What | Where |
|---|---|---|
| 1 | Discovery/adapter wiring moved from I1.2 to I1.3; I1.2 shipped a registration-bound loader (a discoverer without persistence would have been a dead import path). | #581, #582 |
| 2 | The capture step is `app/kafka_capture` plus the operator CLI `harness/kafka-capture`; `confluent-kafka` is not a project dependency. `kafka_version` is `not-established`; the client version is in `tool_version`. | #581 review |
| 3 | The R09 value rule covers only values the caller knows (a secret is not recognizable by shape); no diagnostic carries a key name. | #581 review |
| 4 | Conditional snapshot key `kafka_consumer_state_v1`; additive `aip-import-report/1` run kind `kafka-consumer-state`; registering the adapter re-evaluates every source once after upgrade (no content change). | #582 |
| 5 | Graph-dependent rules are re-checked inside the commit transaction through a source-neutral `commit_guard`: R14/R15 under a per-source-instance `KafkaSourceLock` (uniquely constrained), declared Topics write-locked and re-verified. | #582 review, two rounds |
| 6 | A still-configured registration whose replacement run did not commit keeps its previous source (`configured_source_id` on the evidence carrier). | #582 CodeRabbit |
| 7 | AIP stores only the member count and each member's partitions per attachment; member id, client id and host never enter AIP state (they are client-supplied text no identity, mapping or attribution rule needs, I0 D3). The operator-side capture file still contains them as evidence for the operator. I1 §4, §8, §9 and §12 amended to say this. | #583 review |

## Exit criteria (I1 §12)

| Criterion | Status | Evidence |
|---|---|---|
| Structured capture replays deterministically | Met | unit `test_normalizer_reproduces_the_example_capture_byte_for_byte`, `test_identical_replay_has_an_identical_digest_l01`; integration `test_replay_is_a_semantic_no_op_l01` |
| Live assignments attach only to already-declared Topics | Met | unit `test_a06_undeclared_topic_is_a_diagnostic_and_never_minted`; integration `test_an_undeclared_topic_is_not_minted_and_attaches_once_it_is_declared`, `test_a_topic_removed_between_discovery_and_commit_blocks_the_attachment` |
| No Topic, Subscription or Service minted | Met | integration `test_a_live_assignment_to_a_declared_topic_persists_as_internal_carriers` |
| Consumer ids and source ownership match I0 | Met | ids: unit `test_known_answer_ids_match_the_vectors` (K01–K13), `test_a08_same_group_id_in_another_environment_is_a_distinct_identity`. Ownership (carriers written with `owner_source_ids` through the generic writer, removed only with their own source): integration `test_dropping_the_registration_retires_everything_l05`, `test_a_changed_allow_list_retires_the_old_source_and_never_infers_detachment_l06`, `test_a_rejected_capture_after_an_allow_list_change_keeps_the_previous_state` |
| Complete-capture replacement and failed/partial preservation tested | Met | integration `..._l03`, `..._l04`, `test_a_delayed_older_capture_cannot_overwrite_a_newer_one_committed_meanwhile`, `test_r14_holds_across_two_scopes_of_one_source_instance_under_real_concurrency`, `test_a_rejected_capture_after_an_allow_list_change_keeps_the_previous_state` |
| Secrets do not enter retained state | Met | Credential or security fields are rejected at import, and no diagnostic echoes a name or value: unit `test_rejection_vectors` (R09), `test_rejection_paths_never_carry_a_key_name`, `test_diagnostics_never_echo_a_name_or_value`. Client-supplied member text (member id, client id, host) is never stored, so a secret placed there cannot be retained: unit `test_client_supplied_member_text_never_enters_aip_state`, integration `test_client_supplied_member_text_never_reaches_the_graph` (every stored property, the snapshot and the import report). The capture CLI refuses to write its own secret client settings: unit `test_capture_utility_refuses_a_capture_holding_a_client_secret` |
| No-source behavior unchanged | Met | unit `test_no_kafka_registration_by_default`; integration `test_the_snapshot_gains_the_conditional_key_and_is_otherwise_unchanged`; full suites green on #582 |
| I1 → I2 handoff explicit | Met | [`i1-i2-handoff.md`](i1-i2-handoff.md) |

Each new guard was proven by disabling it and seeing its test fail (declared-Topic check, ordering, commit guard, source-instance lock, retirement protection), as reported in #581 and #582.

## I1 §9 cases

| Case | Vector | Test |
|---|---|---|
| live member, several members, several Topics | A01–A03 | unit `test_a01_…`, `test_a02_…`, `test_a03_…` |
| Empty / Dead | A04, A05 | unit `test_a04_a05_…` |
| rebalance and unknown states | R05–R07 | unit `test_rejection_vectors`; integration `..._l04[rebalance]` |
| undeclared Topic | A06 | unit `test_a06_…` |
| broker / environment / scope mismatch | R01–R03 | unit `test_rejection_vectors` |
| allow-list change | K03, K04, L06 | integration `..._l06`, `test_a_rejected_capture_after_an_allow_list_change_keeps_the_previous_state` |
| same group on another broker or environment | K06, K07, A08 | unit `test_known_answer_ids_match_the_vectors`, `test_a08_…` |
| replay, later T, removal, rejection, unconfigured | L01–L05 | integration `..._l01` to `..._l05` |
| member / client / host change | A07 | unit `test_a07_…` |
| secret canary | R09 | unit `test_canary_value_…`, `test_rejection_never_echoes_a_rejected_value` |
| duplicates, stale, conflict | R12–R15 | unit `test_r12_…`, `test_r14_…`, `test_r15_…`; integration `test_duplicate_registrations_are_both_rejected_through_the_request` |

## Remaining limitations

- No Service mapping or attribution (I2); no public answer (I3).
- No real-system replay fixture yet: the integration tests use the authored pubsub Kafka fixture, and the I0 capture is semantic evidence only (I0 D7). The live Admin API check in #581 was development evidence, not CI.
- A `KafkaSourceLock` node remains when a source is removed by scope enumeration rather than by retirement (internal metadata, never in the snapshot).
- A Topic removed in a later request detaches when that request's Kafka run re-resolves; every request runs all configured sources, so this is the next import.
