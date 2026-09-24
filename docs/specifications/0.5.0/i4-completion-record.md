# AIP v0.5.0 I4 — Completion Record

**Status:** COMPLETE (`GO`) — once the Slice 6 PR carrying this record merges. I4 completion is not
release qualification. I5 and I6 are still required (spec §17).

This record covers the governing specification
[`i4-source-independent-pubsub-semantics.md`](i4-source-independent-pubsub-semantics.md). Draft 0.3
(#226, #227 → `f98e48b`) is what was implemented. Draft 0.4 is amended by this record's own PR. Its
§20 records the nine decisions settled during implementation and changes no already-merged behavior.
The decision is recorded in [`i4-decision-evidence.md`](i4-decision-evidence.md) and in
[ADR 0017](../../adr/0017-source-independent-pubsub-semantics.md), which is Accepted by this PR.

I4 answered §1's question with `GO`:
- AIP now carries source-independent `Topic` and `Subscription` entities with deterministic,
  broker/namespace-scoped, type-distinct identities, qualified against Azure Service Bus and Google
  Cloud Pub/Sub.
- Both ADR 0013 guards are retained: the destination-semantics guard and the service-identity guard.
- The Kafka consumer-group boundary holds.
- Queue behavior is unchanged.
- No broker-specific production exception was needed (§4.2, §16 #11).

## Run identity

| Item | Scope | Merge commit | PR # |
|---|---|---|---|
| Spec Draft 0.2 | I4 specification | `48552d2` | #226 |
| Spec Draft 0.3 | Post-merge review residuals | `f98e48b` | #227 |
| Slice 1 | Decision evidence, ADR 0017 (Proposed), GO, canonical foundation, public contract skeleton | `47873e8` | #228 |
| Slice 2a | `topicMappings`/`subscriptionMappings` in the shared-identity artifact, always-present digest keys | `c5dd51e` | #229 |
| Slice 2b | AsyncAPI Topic/Subscription mapping, persistence, carriers, canonicalization v3 | `f31cf4b` | #230 |
| Slice 3 | Runtime Topic/Subscription qualification (`decide_messaging_destination`) | `5958b4d` | #231 |
| Slice 4 | Architecture Intelligence dependency/drift/evidence projection, claim-id `subscription_id`, widened coverage | `af45004` | #232 |
| Slice 5 | Broker-semantic fixtures and deterministic qualification | `a72b292` | #233 |
| Slice 6 | Docs, spec Draft 0.4, ADR 0017 Accepted, this record | (this PR's own merge commit) | this PR |

**Rule identity at the candidate:**
- **Snapshot and schema:** `_CANONICALIZATION_VERSION = 3`, with dedicated Topic/Subscription node
  queries (`app/architecture_intelligence/repository.py`). Public `schema_version = "0.5"`.
- **Adapter:** `asyncapi-adapter@1` with `mapping_rule_version = "v1"`. Its behavior is widened
  within the unreleased v0.5 line.
- **Claim id:** `aip:claim:v1:` over the five-field payload, plus an optional `subscription_id`
  that is present only for a Subscription route.
- **Diagnostics:** exactly `TOPIC_IDENTITY_CONFLICT`, `SUBSCRIPTION_IDENTITY_CONFLICT` and
  `SUBSCRIPTION_IDENTITY_MISSING` (§8.4).
- **Identity formulas:** `topic:owned:` and `subscription:owned:`, as given in
  `app/sources/owner_ids.py`.

## Fixture identities

The three §13.3 fixtures live under [`tests/fixtures/pubsub/`](../../../tests/fixtures/pubsub/README.md).
Each one discloses its sources, retrieval date (2026-09-23), authored data, expected facts,
forbidden facts and unsupported constructs in its own `PROVENANCE.md`.

| Fixture | Role | Qualifies |
|---|---|---|
| `azure-service-bus/` | positive | Queue competing consumers (no fan-out); Topic fan-out via 2 Subscriptions; instance collapse; per-subscription DLQ token scoped to one carrier |
| `google-pubsub/` | positive | Topic with 2 Subscriptions; 3 subscriber instances → 1 consumer; dead-letter topic token scoped; unobserved publisher → drift; `ghost` Subscription never minted |
| `kafka/` | negative | Topic modeled; consumer-group subscriber → `SUBSCRIPTION_IDENTITY_MISSING`; group-only spans unresolved; zero Subscriptions |

The `SHA256SUMS` manifest has sha256 `873b206b37d66e6f9eb460df6d91c0439c6162d6b0c4ce608156152b86f8f5e1`
and git blob `bd003e5` at the candidate. It pins every fixture file (per-file sha256):

| File | sha256 |
|---|---|
| `README.md` | `f9154f628386a94a880363f68c957a908dec3b3294d2341dd5891e937eb153c8` |
| `azure-service-bus/PROVENANCE.md` | `833adb95a6d2c933107fa82379bb806d46ed865f46bb83096e70663f81c80dda` |
| `azure-service-bus/declarations/audit/asyncapi.yaml` | `eb20fbe877b7f2485703a6bd66f63533e26869e64fdef6be5ab121b09da8b008` |
| `azure-service-bus/declarations/billing/asyncapi.yaml` | `aee34c7ddea89db3b55f61d2f333fd53982ba06438a9b3b56bf0265dd59e2010` |
| `azure-service-bus/declarations/orders/asyncapi.yaml` | `a6fbfbeaff10682b4ea6a0204902359e160e26336b11a1b8098626982919ace7` |
| `azure-service-bus/declarations/payment-worker-a/asyncapi.yaml` | `1923065984317e09c77b8ca48acdd998374758ecef0322a59c4198de5fd5df2b` |
| `azure-service-bus/declarations/payment-worker-b/asyncapi.yaml` | `dd8b19af053f54e861734d8bf14837a22555c9beff512a9989d4b5ac6c8658f1` |
| `azure-service-bus/expected.yaml` | `e0889c55cbf1e56c0d4f0154d47693cb150cfa6fd19ba0ac25923acb640fdf22` |
| `azure-service-bus/spans.yaml` | `f502fc6bae94bb76764e8b696a73d42b1896483fa0abb996ec860916231368ef` |
| `google-pubsub/PROVENANCE.md` | `3e9e28d950934aadeb1af45259d16754af0829a5768a425a48713887d9d83487` |
| `google-pubsub/declarations/analytics/asyncapi.yaml` | `cee06467dca41c07f757d4f72b084f0f693c185a97946386004b0010f6736d5b` |
| `google-pubsub/declarations/checkout/asyncapi.yaml` | `ee2bfe2104f652787f1adaad3b24bca43e004b289a0c25ab7ad5c00bd1c28714` |
| `google-pubsub/declarations/fulfillment/asyncapi.yaml` | `ff362d10e8a9efd3ba329bb9ef31796becbcbca3f69d8c03074785a4a12df23a` |
| `google-pubsub/expected.yaml` | `582eca47431ae4aa340f75fafd63a15d9b25ce5047632c6c35b8a0dc10f9c2c1` |
| `google-pubsub/spans.yaml` | `06e82fb01d559dfa73dae035a28d3c070aa77ff7b29053160bce0879dffc6103` |
| `kafka/PROVENANCE.md` | `a0f4781147cbf1ef7227da14419d09dd5ecb47043d42a0288f4b9bca4a22bbd3` |
| `kafka/declarations/stock-projector/asyncapi.yaml` | `54817705bd4ef30a2c4d87d31f911a70707593769406a67a542f231c9fffb135` |
| `kafka/declarations/warehouse/asyncapi.yaml` | `4d1248f812678f289fa1e5ba3fdb7911d2af5c881594a79155640d2ec93b5630` |
| `kafka/expected.yaml` | `c0f9b0dd324821fc5edab88ca6b960ea9d047fecba38addec0d380a409acb573` |
| `kafka/spans.yaml` | `df84c4a4cd79db87f02b3a615093fd1152e4c5843b7993e79a3851db5cf23693` |

`tests/unit/test_pubsub_fixture_digests.py` enforces this manifest.

## Immutable qualification identity

This section is record-only. It cites an already-merged, CI- and CodeQL-verified SHA, so the record
never has to cite its own merge commit. The Slice 6 PR adds no code, test or fixture change.

| Artifact | Revision |
|---|---|
| Implementation candidate | `a72b29287b85d6ceabc3c537d3b66bd0480b494a` (#233, Slice 5, the last content-bearing I4 PR) |
| Governing spec as implemented (Draft 0.3) | git blob `5b896583fd86eb2645464fcc887c609e14788d8a`. It is identical at `f98e48b` and at the candidate. |
| Decision evidence | `i4-decision-evidence.md` blob `17423bf5d207b5f94561216ab6b935e08fc2fb5f` |
| ADR 0017 at the candidate (Proposed; Accepted by this PR) | blob `24a26957922e8195c235a6364523242ed2393572` |
| `app/canonical/pubsub.py` | blob `99ce788da4630f9df4d8b63b8e1e782be6e3be18` |
| `app/sources/owner_ids.py` | blob `36e20564d2d1abd65f636f49f89d418cba84f4e7` |
| `app/sources/migration_mappings.py` | blob `ae20aea20820f941ac803d621c2499c0a803edfb` |
| `app/ingestion/asyncapi_adapter.py` | blob `d3f3e1655bba12543168d590f1186701318134d5` |
| `app/telemetry/messaging_guards.py` | blob `a710a564f3a64e2eee617d8af54466708e7ed93c` |
| `app/telemetry/adapter.py` | blob `2540974ba8ca8277e66261e59e13b15fa2f5f0ac` |
| `app/architecture_intelligence/dependency_projection.py` | blob `3d119cc051fb88b208fc8854155b9319d5e64ce4` |
| `app/architecture_intelligence/repository.py` | blob `f7655d5bad1a8ccd971c0b1e049c84d7040b2653` |
| `app/architecture_intelligence/contracts.py` | blob `718b7b2946a7708aee336490cc31aebc401ebe5b` |
| `app/qualification/declared_observed.py` | blob `270b2a7f26a89a6ceabe36b13f50e145485d167f` |
| `app/analysis/runtime.py` | blob `c27b7879e6c67a79a4b704d00fe59b166efe50f3` |
| Report | Local full run at the candidate (below), plus GitHub Actions [run 35966051528](https://github.com/michaelegner/architecture-intelligence-platform/actions/runs/35966051528) at `a72b292`. Its jobs `lint + test`, `integration-core`, `demo-e2e`, `quality` and `dependency security scan (pip-audit, spec §29)` all have `conclusion: success`. Check-run attribution was verified via the Checks API against the exact SHA. |
| Evidence | CodeQL [run 35966051501](https://github.com/michaelegner/architecture-intelligence-platform/actions/runs/35966051501) at `a72b292`: `analyze (python)` and `analyze (actions)`, both `conclusion: success` |

**Byte-identity evidence.** `test_two_clean_full_qualification_runs_are_byte_identical` wipes the
graph and runs all three fixtures twice, then compares the canonical JSON bytes of the complete
output. That output includes:
- snapshot ids and claim ids;
- evidence records;
- diagnostics;
- fact sets.

The output hash is not cited as an identity, because it depends on the checkout path (see
Limitations). The pinned identities are the fixture digests above and the test result.

## Regression suite (full local run at the pinned candidate revision, `a72b292`)

| Suite | Result |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 353 files already formatted |
| `uv run pytest tests/unit` | 2138 passed |
| `uv run pytest tests/integration` | 427 passed, 12 deselected |

The 12 deselected tests are `test_mcp_demo_script`. They could not run locally because the
maintainer's demo compose stack holds their ports. The same SHA's CI `demo-e2e` and
`integration-core` jobs ran them and succeeded.

**Comparison with I3.** I3's completion baseline was 1815 unit and 405 integration tests. I3's 405
included the demo-script tests, so the like-for-like I4 integration collection is 439 (427 run plus 12
deselected). I4 therefore adds 323 unit and 34 integration tests.

**Pre-existing suites.** Every pre-existing suite passes. 14 pre-existing test files were modified
during I4. Each change only widened them for the new I4 vocabulary and row keys, or added I4 cases
(for example `test_architecture_intelligence_contracts.py`, `test_orchestrator.py`,
`test_sources_migration_mappings.py`, and the fake-row dictionaries in #232).

**Queue non-regression:**
- **Unmodified behavior suites:** `tests/unit/test_asyncapi_adapter.py`, `tests/unit/test_adapter.py`
  C1-C17 and `tests/integration/test_qualification_consistency.py` were not modified.
- **Answer scenarios:** all 23 `evaluation/architecture_answers` scenarios pass, including
  `async-confirmed`, `unresolved-queue-destination` and `multiple-delivery-paths`.
  - Their only I4 change was regenerating each expected `snapshot_id`/`model_revision` for
    canonicalization v3 in #230. `git diff 571220b a72b292 -- evaluation/architecture_answers/scenarios`
    touches only those lines.
  - Every claim, claim id, qualification and evidence ref is byte-identical to I3.

## §17 GO-exit Definition of Done — evidence by area

| §17 item | Evidence |
|---|---|
| ADR 0017 is accepted | [`docs/adr/0017-source-independent-pubsub-semantics.md`](../../adr/0017-source-independent-pubsub-semantics.md) Status line (this PR) |
| Topic/Subscription semantics are source-independent | No broker-specific entity or branch: `test_i4_pubsub_qualification.py::test_fixture_matches_its_hand_authored_expectations` passes for ASB and GCP through one unmodified production path. `git diff af45004 a72b292 -- app/` is empty (Slice 5 changed no production code). |
| Queue/Topic/Subscription identities are deterministic and collision-safe | `tests/unit/test_sources_owner_ids.py` (Queue/Topic never alias; the same Subscription name under different Topics is distinct; no consumer-group input); `test_asyncapi_adapter_pubsub.py::test_same_topic_name_under_different_brokers_or_namespaces_is_distinct` |
| Queue non-regression passes | The regression suite above; `test_i4_pubsub_qualification.py::test_queue_claims_keep_their_pre_i4_claim_ids`; `test_architecture_intelligence_dependency_projection_pubsub.py::test_http_and_queue_claim_ids_are_the_unchanged_five_field_payload` |
| AsyncAPI Channel is never automatically a destination | `test_asyncapi_adapter_pubsub.py::test_protocol_or_vendor_alone_never_establishes_topic`, `::test_publish_or_subscribe_operation_alone_never_establishes_topic`, `::test_unrecognized_kind_alone_preserves_i1_omission_and_aggregation` |
| Topic kind requires positive evidence | `::test_pre_i4_topic_kind_without_identity_is_still_omitted_and_rejected_unsupported`, `::test_amqp_routing_key_alone_is_never_topic_evidence`, `::test_queue_and_topic_kind_evidence_conflict_rejects_atomically` |
| Subscription requires explicit stable identity | `::test_missing_subscription_identity_never_guesses_one`; Kafka fixture |
| Consumer group is never automatically a Subscription | `test_asyncapi_adapter_pubsub.py::test_consumer_group_extension_never_becomes_subscription_identity`; `test_adapter_pubsub.py::test_consumer_group_equal_to_subscription_name_is_still_not_an_implicit_match`; Kafka fixture |
| Runtime cannot mint Topic/Subscription | `test_messaging_guards_pubsub.py::test_topic_kind_without_a_declared_topic_is_never_minted`; `test_adapter_pubsub.py::test_observed_only_entity_label_structurally_excludes_topic_and_subscription`; `test_pubsub_runtime.py::test_unmatched_pubsub_spans_never_reach_the_graph_or_the_snapshot` |
| Competing-consumer and fan-out cases stay distinguishable | The ASB fixture: 2 Queue claims with no route, and 2 routed Subscription claims. `test_architecture_intelligence_dependency_projection_pubsub.py::test_distinct_services_on_one_subscription_are_competing_consumers_sharing_the_route`, `::test_two_subscriptions_are_two_distinct_routed_claims` |
| Subscription dead-letter stays scoped with no guessed generic target | `test_asyncapi_adapter_pubsub.py::test_subscription_dead_letter_is_retained_only_for_the_named_subscription`; the ASB and GCP fixtures' `dead_letter_carriers` and the absence of `DEAD_LETTERS_TO` |
| Azure and Google positive fixtures pass; Kafka produces the negative result | `test_i4_pubsub_qualification.py::test_fixture_matches_its_hand_authored_expectations[azure-service-bus \| google-pubsub \| kafka]` |
| Evidence/provenance drill-down is complete | `test_pubsub_architecture_intelligence.py::test_every_pubsub_evidence_ref_resolves_at_the_answer_snapshot`; every fixture's `missing_evidence_refs == []`; `test_pubsub_persistence.py::test_evidence_supports_include_pubsub_relations` |
| Snapshot identity binds new public state | `test_pubsub_persistence.py::test_topic_state_moves_the_snapshot_but_internal_carriers_do_not`; `test_canonical_pubsub_foundation.py::test_pubsub_persistence_path_is_open_and_bound_to_canonicalization_v3` |
| Public v0.5 schemas validate old and new cases | `test_architecture_intelligence_contracts.py::test_delivery_ref_cross_product_agrees_between_pydantic_and_frozen_schema`, `::test_i4_public_vocabulary_additions_are_exact`; `test_architecture_intelligence_schema_frozen.py`; every fixture answer is schema-validated |
| Service/REST/MCP semantics agree | `test_i4_pubsub_qualification.py::test_service_rest_and_mcp_agree_with_zero_graph_writes` (per fixture); `test_pubsub_architecture_intelligence.py::test_service_rest_and_mcp_agree_and_reads_cause_zero_graph_writes` |
| MCP tool count stays exactly three | The same qualification test (real `tools/list`); `tests/unit/test_mcp_discovery.py::test_mcp_protocol_and_discovery` |
| Public reads cause zero graph writes | The same two parity tests (revision fence, node and relation counts unchanged) |
| Two clean qualification runs are byte-identical | `test_i4_pubsub_qualification.py::test_two_clean_full_qualification_runs_are_byte_identical`, `::test_qualification_is_independent_of_span_order` |
| All pre-I4 regressions stay green | The regression suite above; CI run 35966051528 |
| Limitations and unsupported constructs are documented | Below; each fixture's `PROVENANCE.md`; spec §3.2 |

#233's PR description maps every §13.1 and §13.2 matrix bullet to its test.

## Limitations and unsupported constructs (explicitly disclosed, not silently omitted)

- **Stop conditions:** none of §16's twenty was crossed. In particular:
  - no fourth MCP tool, live broker API, AsyncAPI 3.x, generic `Destination`, or broker-specific
    entity or branch;
  - no consumer-group equivalence, runtime minting, or fuzzy identity;
  - no Queue claim-id change, and no schema version beyond `0.5`.
- **§3.2 out of scope**, unchanged: live broker discovery, Kafka Connect, partitions, lag, offsets and
  transactions, delivery guarantees, filters and routing rules, ACLs, schema-registry lifecycle,
  choreography inference, messaging Intent, and AsyncAPI 3.x.
- **Per-broker unsupported constructs:** listed in each fixture's `PROVENANCE.md`. They cover ASB
  filters and rules, auto-forwarding, transfer DLQ and JMS; GCP filters, ordering, push/pull and
  retry policy; and Kafka partitions, offsets, rebalancing and share groups.
- **Decisions settled during implementation:** spec §20 items 1-9 (Draft 0.4). Two consequences are
  worth restating here:
  - publisher-only qualification means one observed publish CONFIRMS every declared Subscription
    route of that Topic;
  - O5 and REST `messagingObserved` now also reflect Pub/Sub-only telemetry.
- **Checkout-path-dependent snapshot identity (pre-existing, spec §20 item 9).** Declared
  `Evidence.source_file` is absolute, so identical inputs at another path give a different
  `snapshot_id`. Everything else is identical, as proven by
  `test_relocated_checkout_changes_only_the_snapshot_identity`. Making declared provenance
  root-relative is out of I4 scope.
- **Subscription-fallback claim:** covered at unit level only. AsyncAPI cannot produce a
  Subscription without its declaring consumer.
- **Queue-only analyses:** A1-A5, `async_flow_to` and O1-O4 do not traverse Pub/Sub. Pub/Sub is
  answered only by the Architecture Intelligence tools.
- **`evaluation/architecture_answers`:**
  - its committed evaluation report still dates from v0.4.0 (`candidate_sha: a906a58`);
  - its authoring-time `reference/snapshot.py` still computes canonicalization v1;
  - the 23 scenario fixtures were regenerated for v3 in #230, and the reference `claim_id` was
    widened in #232.

  Refreshing the report belongs with release qualification (I6).

## Handoff to I5 (§18)

- **Stable Queue/Topic/Subscription semantics and deterministic identities:**
  - `app/canonical/pubsub.py` and `app/sources/owner_ids.py`;
  - [`canonical-model.md`](../../canonical-model.md) and [`graph-model.md`](../../graph-model.md#pubsub-v050-i4).
- **Positive competing-consumer and fan-out fixtures, and the negative consumer-group boundary:**
  `tests/fixtures/pubsub/`, pinned by `SHA256SUMS`.
- **Runtime no-minting guards:** `app/telemetry/messaging_guards.py::decide_messaging_destination`,
  documented in [`opentelemetry.md`](../../opentelemetry.md#pubsub-observations-v050-i4).
- **Public Pub/Sub dependency projection and same-snapshot evidence drill-down:**
  `app/architecture_intelligence/dependency_projection.py`, documented in
  [`mcp.md`](../../mcp.md#pubsub-in-dependency-and-drift-answers-v050-i4).
- **Exact rule, schema and canonicalization revisions:** the Run identity and Immutable
  qualification identity sections above.

I5 may harden any of these only when independent cross-system evidence shows a general model defect.
Target-specific aliases, product-name branches, fixture exceptions and broker-specific canonical
semantics remain prohibited (§18).

## I4 exit statement

> **COMPLETE (`GO`).** The pinned implementation candidate `a72b292` contains:
> - Slices 1-5 (#228-#233): the canonical Topic/Subscription model, AsyncAPI mapping and persistence
>   (canonicalization v3), runtime qualification, public dependency, drift and evidence projection,
>   and deterministic broker-semantic qualification;
> - 2138 unit and 427 integration tests passing, with green CI and CodeQL at that exact SHA.
>
> The Slice 6 PR carrying this record adds no further code, test or fixture changes. It contains
> only living documentation, the spec's Draft 0.4 amendment (§20), ADR 0017's move to Accepted, ADR
> index corrections, and this record. **I4 itself is COMPLETE only once that PR merges.** I5 and I6
> remain required before v0.5.0 release qualification.
