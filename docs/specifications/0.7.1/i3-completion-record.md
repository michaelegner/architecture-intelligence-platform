# AIP v0.7.1 I3 — Completion Record

**Status:** COMPLETE on merge of the I3.2 PR (the closure SHA is added in a follow-up only if the owner asks).
**Outcome:** `READY_FOR_I4`, recorded by the owner on merging the I3.2 PR.

This record covers the I3 specification [`i3-destination-consumer-public-answer.md`](i3-destination-consumer-public-answer.md) under the [I2 → I3 handoff](i2-i3-handoff.md). I3 exposes one destination-first question through the semantic service, REST and a sixth negotiated MCP tool: for Kafka Topic D in environment E, which Services can AIP evidence-qualify as consumers. It adds no new consumer relationship and reinterprets no broker or mapping evidence. Qualification, the RabbitMQ contrast and the product-value check are I4.

## Run identity

| Slice | Deliverables | PR | Merge commit | Merged (UTC) |
|---|---|---|---|---|
| I3 spec | [`i3-destination-consumer-public-answer.md`](i3-destination-consumer-public-answer.md) | #590 | `0dcc6da6791a44faf988af82220f6d48ca6a0e8f` | 2026-10-18T15:32:01Z |
| I3.1 | query contract and schemas, query projection, service method, `kafka_topic_brokers_v1` | #592 | `fa91adb67e4842c13e91698d8a7fdeb18df27fc6` | 2026-10-18T17:26:35Z |
| I3.2 | evidence mode, REST routes, the sixth MCP tool, tool-list updates, this record, [`i3-i4-handoff.md`](i3-i4-handoff.md) | this PR | read from `gh pr view --json mergeCommit` after merge | |

The merge commits above were read from `gh pr view --json mergeCommit,mergedAt`.

## Decisions and deviations

| # | What | Where |
|---|---|---|
| 1 | One new read-only tool `get_destination_consumers` with `query` and `evidence` modes, the service methods `get_destination_consumers` / `get_destination_consumer_evidence` and two POST routes; schema version `0.7.1` in `schemas/architecture_intelligence/v0.7.1/`, not a widening of an earlier envelope. | spec §5, #592, I3.2 |
| 2 | Broker check: the Topic node records no broker and its name is the channel name, so "declared on this broker" comes from the Topic declarations. The derived (`topic_id`, `broker_id`) pairs are bound into the snapshot as the conditional key `kafka_topic_brokers_v1`, present only beside `kafka_consumer_state_v1` (owner decision after CodeRabbit's review: first a revision-fenced read beside the state). A configured Topic id must equal its broker-derived id, so the only transition this closes is an explicit-id Topic losing its broker. | #592 |
| 3 | Kafka check: `DESTINATION_NOT_KAFKA_TOPIC` only for a Queue id or a Topic bound to another protocol. The AsyncAPI adapter takes `Topic.protocol` from channel bindings only, so the usual Kafka Topic has a null protocol and counts as Kafka through its declared broker plus an accepted capture. With no Kafka consumer state at all the answer is `NO_ACCEPTED_CAPTURE`. | owner, #592 |
| 4 | Every evaluated query is `PARTIAL` with `CAPTURE_SCOPE_LIMITED` (a capture covers only its configured groups at its own T); `ANSWERED` cannot occur for a query. | #592 |
| 5 | Rows come from `kafka_consumer_attribution_v1`, or, without a mapping carrier, from the same I2 `attribution_block` with empty mapping inputs; no reconciliation rule is reimplemented. | spec §3, #592 |
| 6 | Evidence refs are opaque, bound to the snapshot and the query context; the evidence mode rebuilds the ref map of that context with no ref history. Within one snapshot an attachment is visible in exactly one context, so the tested binding is the snapshot binding plus forged and cross-context refs that resolve to nothing. | #592, I3.2 |
| 7 | The snapshot ids of graphs with Kafka consumer state change (the new key); v0.7.1-only, unreleased state. The closed I1 and I2 records are not edited. | #592 |
| 8 | Release-facing material is left for the I5 re-freeze, not edited in I3: `examples/release-golden-path/` (`TOOLS`, `expected.json`, README), `README.md`'s tool table, `examples/mcp-clients/{cursor,vscode}.md` and `examples/runtime-demo/hero-demo.md`. The reference docs `docs/mcp.md` and `docs/architecture.md` describe the code and are updated, as are the tool-list tests that start AIP from this tree (MCP discovery and negotiated transport, the independent-client golden path, the in-process pub/sub qualification, the Pitstop and Quarkus demo smokes, whose Compose stacks `build: .`, and the v0.7.0 I4 runner `evaluation/i4/api_usage_runner.py`, whose live-app tool count is now six). | I3.2 |

## Done criteria (spec §7)

| Criterion | Status | Evidence |
|---|---|---|
| A caller queries one Topic and sees who is attributable, who is unresolved, why, and which evidence supports each reading | Met | integration `test_attached_and_mapped_group_resolves_with_both_paths_on_the_current_snapshot`, `test_without_a_mapping_source_the_attachment_is_unresolved_no_mapping`; unit `test_resolved_row_carries_both_evidence_paths_and_t`, `test_i2_outcomes_pass_through_unchanged_without_a_service` |
| Drill-down through REST or MCP | Met | integration `test_every_surface_answers_the_query_and_resolves_its_refs`; unit `test_every_emitted_ref_resolves_to_its_closed_payload` |
| Capture time and limited scope stay visible | Met | `captured_at` on every row, `capture_sources[]` with each T, `CAPTURE_SCOPE_LIMITED` on every evaluated query; unit `test_several_captures_keep_their_own_times`, `test_an_accepted_capture_without_attachment_is_empty_but_never_negative` |
| No positive or negative claim beyond I1/I2 evidence | Met | rows copy the I2 block; `service_id` only when RESOLVED (model and schema); unit `test_the_published_schema_and_the_model_reject_the_same_broken_answers` |
| One snapshot, one answer | Met | integration `test_a_changed_topic_broker_association_changes_the_snapshot_id`, `test_every_read_path_binds_the_same_configured_aliases` (includes this tool) |

## Spec §6 acceptance cases

| Case | Test |
|---|---|
| attachment + declared mapping → RESOLVED, both paths, T | unit `test_resolved_row_carries_both_evidence_paths_and_t`; integration `test_attached_and_mapped_group_resolves_with_both_paths_on_the_current_snapshot` |
| no mapping source → `NO_MAPPING` plus `NO_MAPPING_SOURCE`; source present, group unmapped → `NO_MAPPING` only | unit `test_no_mapping_source_uses_the_i2_rule_and_says_so`, `test_a_mapping_source_without_an_entry_is_no_mapping_without_the_source_limitation` |
| runtime-only, placeholder, ambiguous, conflicting, mixed → exact I2 outcomes | unit `test_i2_outcomes_pass_through_unchanged_without_a_service`, `test_a_resolved_row_names_its_non_resolving_entry_by_mapping_ref` |
| mapping without attachment; several members; one group on two Topics; same Topic in two environments | unit `test_only_the_requested_topic_and_environment_are_returned`; integration `test_one_topic_in_two_environments_returns_only_the_requested_one` |
| no accepted capture; empty or limited capture | unit `test_refusals`, `test_without_any_kafka_state_the_answer_is_no_accepted_capture`, `test_an_accepted_capture_without_attachment_is_empty_but_never_negative` |
| wrong broker, non-Kafka destination, unknown destination; declared Subscriptions excluded | unit `test_refusals`; integration `test_refusals_through_the_service`; the answer has no Subscription field |
| removal/replacement and alias changes → same-snapshot results | integration `test_a_configured_alias_decides_the_attribution`, `test_a_changed_topic_broker_association_changes_the_snapshot_id` |
| ordering, paging, stale cursor; valid vs forged or cross-snapshot ref | unit `test_paging_is_ordered_and_bound_to_snapshot_and_context`, `test_a_cursor_from_another_snapshot_is_stale`, `test_forged_cross_context_and_cross_snapshot_refs_are_not_resolved` |
| equivalent Service/REST/MCP payloads; no sensitive exposure; existing tools unchanged | integration `test_every_surface_answers_the_query_and_resolves_its_refs`, `test_refusals_are_identical_on_every_surface`; unit `test_mcp_protocol_and_discovery` (six tools, existing ones unchanged) |

Each new guard was proven by disabling it and seeing its test fail: the environment filter, the broker check, cursor-to-query binding, evidence-ref snapshot binding and the snapshot binding of the declared brokers (#592).

## Remaining limitations

- A namespaced Kafka Topic always gets `rows: []`: I1 attaches only to Topic ids computed with an empty namespace.
- The answer is never complete: each capture covers its configured allow-list at its own T.
- Real-system qualification, the RabbitMQ contrast, public-surface A/B and the product-value check are I4; the release re-freeze of golden path and release-facing docs is I5.
