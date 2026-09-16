# I1 Completion Record — v0.5.0 Source Ingestion Foundation

Governing spec: `docs/specifications/0.5.0/i1-source-ingestion-foundation.md` (Draft 0.3, amended
during PR3b to accept OpenAPI `3.1.2` — see its own §12 amendment note). Per §13: "The I1 completion
record SHALL identify the candidate revision, adapter/mapping-rule versions, fixture identities,
source inventory/replay evidence, regression results, and any limitations or unsupported
constructs. It SHALL state that I2 may rely on the seam and lifecycle contract without
reintroducing directory-based ownership or name-based identity."

## Run identity

I1 shipped as four sequential PRs, each independently reviewed and merged, per the user-approved
delivery plan:

| PR | Scope | Merge commit | PR # |
|---|---|---|---|
| 1 | Source/configuration contracts, identity/digest formulas, mapping-context fingerprint | `f3aa5e6` | #180 |
| 2 | Inventory lifecycle, atomic reconciliation, removal/tombstone safety | `87a5806` | #181 |
| 3a | Registry seam (ADR 0009); adapter migration to owner-scoped RFC 8785 Schema/Message/Queue identity | `7492bd2` | #185 |
| 3b | Bounded multi-file `$ref` resolution/containment (ADR 0015), `allOf`/`oneOf`/`anyOf` composition, exact OpenAPI/AsyncAPI version enforcement | `934de3f` | #186 |
| 4 | Explicit shared-identity/migration mapping mechanism, cross-source content-conflict detection, deterministic-qualification evidence, this record | *(this branch, pending merge)* | — |

**Adapter/mapping-rule identities and versions** (unchanged since PR3a, all `v1`):
`openapi-adapter@1`, `asyncapi-adapter@1`, `manifest-adapter@1`.

**Bundled-example fixture identities** (`examples/`, configured source id
`aip-bundled-examples-v0.5`, stable target identity `urn:aip:logical-root:bundled-examples`) — the
five root documents' `SourceInstanceId`s, independently reproducible via
`app.sources.identity.source_instance_id`, never hand-derived:

| Root document | SourceInstanceId |
|---|---|
| `order-service/openapi.yaml` | `urn:aip:source:filesystem:a302361f5e4b2b86839e1b2da03c9691ddba8a7bcc22a21c0270ef80ece247bf` |
| `order-service/asyncapi.yaml` | `urn:aip:source:filesystem:352ae2ff7922c69e0655b782cc90c1a6f21085cacf4cc4c0da60a073155816ad` |
| `product-service/openapi.yaml` | `urn:aip:source:filesystem:6e78c4f7625f06e968b1b409ded73b234bfc40382dc4b4566fc58e04ba7b1562` |
| `payment-service/asyncapi.yaml` | `urn:aip:source:filesystem:9c1c685fb93a9d7e687a6c0b9602a3534481decd270a94635b902870c5710299` |
| `invoice-service/asyncapi.yaml` | `urn:aip:source:filesystem:679f611e8055bd5869723affbe177e73f49454415c1e7808ed34eec5633fe659` |

**Migration artifact** (§5.1.1): `config/migrations/v0.5.0-bundled-example-identities.yaml`,
artifact id `aip-v0.5.0-bundled-example-identities-v1`, revision `v1` — exists and is proven correct
(see below) but is deliberately not referenced by `config.yaml`/`config.demo.yaml`'s own default
`sources.migrations` list, so the bundled examples' live default identity remains the owner-scoped
one PR3a/3b shipped, not the legacy one this artifact restores on demand. Its `queueMappings` is
empty per the **Draft 0.3 amendment (PR4)** in §12: every bundled channel already carries real
derivable broker evidence (PR3a/3b), so a legacy Queue mapping for any of them would always disagree
with its correctly-computed derived id — `REJECTED_CONFLICT` by §9's own rule, not a valid migration
target. `schemaMappings`/`messageMappings` are unaffected and remain required/populated. Each entry
also carries `documentPath` - the construct's own normalized definition document path - alongside
`pointer`, since one SourceInstanceId's own bounded multi-file `$ref` closure could otherwise
resolve the same relative pointer inside two different files; every bundled construct is defined in
its own root document today, so each entry's `documentPath` equals that root document's own path.

Service identity is out of scope of this artifact entirely (also per the §12 amendment): each
bundled root document's own `x-aip-service-id` extension (§4.1 resolution path 1) already carries
the same value the pre-PR3a directory-derived formula produced (`service:<example-directory-name>`),
so Service continuity holds by construction of the fixtures, and the artifact's schema has no
service-mapping section. §4.1 path 2 (versioned configured source-to-Service mapping) has no config
surface anywhere in I1 — `configured_mappings` is always empty in
`app/ingestion/orchestrator.py::_RunServiceIdentityResolver` — so it plays no role here either.

## Regression suite (full local run at PR4's tip, this branch)

| Suite | Result |
|---|---|
| `uv run ruff check .` | clean |
| `uv run ruff format --check .` | clean |
| `uv run pytest tests/unit` | 1369 passed |
| `uv run pytest tests/integration` | 300 passed |

## §11 Definition of Done — evidence by area

The spec's DoD is one long paragraph of ~40 individual clauses; grouped here by area, each row
citing the test(s) that prove it. Items marked *(4)* were newly closed or newly given end-to-end,
non-synthetic proof in PR4; all others were proven in PR1/2/3a/3b and re-verified as part of this
record's own full regression run (unaffected by PR4's changes).

| Area | Evidence |
|---|---|
| Registry seam; adapters preserve qualified meaning; multi-source/multi-service | `tests/unit/test_sources_registry.py`; `tests/unit/test_orchestrator.py::test_multi_service_multi_source_discovery`; `tests/integration/test_importer.py::test_import_all_sources_real_examples_end_to_end` |
| Service-identity resolution (extension/configured/manifest paths agree; missing/malformed/ambiguous/conflicting reject) | `tests/unit/test_sources_service_identity.py`; `tests/unit/test_openapi_adapter.py`, `test_asyncapi_adapter.py` |
| ArchitectureIdentityBindings shape/validation, permutation-independent binding index | `tests/unit/test_sources_manifest_bindings.py` |
| RFC 6901 pointer-prefix matching exactness (`/paths/~1foo` vs. `/paths/~1foobar`) | `tests/unit/test_sources_pointers.py` |
| YAML/JSON and key-order equivalence; RFC 8785 canonical hashing | `tests/unit/test_sources_jcs.py`; `tests/unit/test_pr3b_multifile_end_to_end.py` |
| Inline/referenced/anonymous/array schema identity and hashing (§8.1) | `tests/unit/test_sources_owner_ids.py`; `tests/unit/test_openapi_adapter.py`; `tests/unit/test_pr3b_multifile_end_to_end.py` |
| `allOf`/`oneOf`/`anyOf` composition (structural preservation, branch sorting, cycle/dangling-branch outcomes) | `tests/unit/test_pr3b_multifile_end_to_end.py::test_valid_composition_is_accepted_with_limitations_and_diagnosed`, `::test_a_genuine_cross_file_reference_cycle_rejects_the_whole_source` |
| **Explicit shared-identity mapping keyed by (SourceInstanceId, document path, pointer) - same relative pointer in two different files resolves independently; shared-ID/different-hash conflicts reject (schema, message); configured-vs-derived-ID conflicts reject (Queue)** *(4)* | `tests/unit/test_sources_migration_mappings.py::test_build_index_keeps_same_pointer_in_different_documents_independent`, `::test_parse_rejects_entry_missing_document_path`; `tests/unit/test_orchestrator.py::test_shared_identity_mapping_disambiguates_the_same_pointer_in_two_files`; `tests/unit/test_openapi_adapter.py::test_explicit_mapping_to_the_same_id_with_disagreeing_content_conflicts`; `tests/unit/test_asyncapi_adapter.py::test_explicit_message_mapping_to_the_same_id_with_disagreeing_content_conflicts`, `::test_explicit_queue_mapping_disagreeing_with_the_derived_id_rejects`, `::test_explicit_dlq_target_mapping_disagreeing_with_the_derived_id_rejects`; `tests/unit/test_sources_claim_conflicts.py` (cross-source) |
| Referenced/inline AsyncAPI message identity; `message_contract_digest`/`message_document_digest` *(4)* | `tests/unit/test_sources_message_contract.py`; `tests/unit/test_asyncapi_adapter.py` |
| Queue kind/identity evidence paths (extension, AMQP binding, configured mapping), positive+negative, kind-conflict, configured-vs-derived identity-conflict, and multi-server disagreement (including with an explicit mapping also present) *(4 for the third path + all three conflict fixes)* | `tests/unit/test_asyncapi_adapter.py::test_queue_kind_from_amqp_binding_alone`, `::test_agreeing_kind_paths_are_accepted`, `::test_conflicting_kind_paths_reject_the_whole_source`, `::test_missing_kind_evidence_channel_is_unsupported`, `::test_multi_server_disagreement_is_ambiguous`, `::test_explicit_queue_mapping_does_not_override_multi_server_disagreement`, `::test_explicit_queue_mapping_is_used_when_there_is_no_derived_broker_evidence_at_all`, `::test_explicit_queue_mapping_agreeing_with_the_derived_id_is_accepted`, `::test_explicit_queue_mapping_disagreeing_with_the_derived_id_rejects`, `::test_explicit_queue_mapping_conflicting_with_kind_evidence_rejects`, `::test_explicit_dlq_target_mapping_is_used_when_declaring_channel_has_no_derived_broker`, `::test_explicit_dlq_target_mapping_disagreeing_with_the_derived_id_rejects` |
| Unchanged v0.4.2 fixtures + migration mapping restore prior Schema/Message meaning; portable bundled-example identities across checkout paths. Queue identity is deliberately NOT migrated for these specific fixtures (they already carry real broker/namespace evidence PR3a/3b added, which legitimately disagrees with the legacy unscoped Queue ids by construction - migrating it would itself be the §9 conflict case, not a valid target) *(4)* | `tests/integration/test_i1_bundled_migration_determinism.py` (all three tests); `tests/integration/test_importer.py::test_import_all_sources_with_the_real_bundled_migration_mapping_lands_legacy_ids` |
| Reference depth/file-count/byte limits at boundary and boundary+1 | `tests/unit/test_sources_reference_resolution.py` (all boundary/boundary+1 pairs); `tests/unit/test_pr3b_multifile_end_to_end.py` (real-default-value end-to-end cases) |
| Fragment-only/nested-file-relative reference resolution; absolute/percent-encoded-traversal/symlink-escape/unsupported-URI/malformed-fragment/pointer-alias handling | `tests/unit/test_sources_reference_resolution.py`; `tests/unit/test_pr3b_multifile_end_to_end.py` |
| Cycles/duplicate identities/conflicts/invalid inputs fail without partial writes | `tests/integration/test_importer.py::test_import_all_sources_rolls_back_in_full_when_a_later_source_fails`; `tests/integration/test_i1_bundled_migration_determinism.py::test_a_genuine_cross_source_content_conflict_rejects_the_whole_run` |
| Exact OpenAPI (`3.0.3`/`3.1.0`/`3.1.2`)/AsyncAPI (`2.6.0`) version enforcement | `tests/unit/test_openapi_adapter.py`, `test_asyncapi_adapter.py` (`check_supported_dialect_version` cases); real-world conformance evidence: `docs/real-world-validation/quarkus-super-heroes/` (declares `3.1.2`, pinned byte-identical to a real upstream commit) |
| Reimport idempotence; semantic no-op does not advance graph revision; content/property changes do | `tests/integration/test_importer.py::test_import_all_sources_is_idempotent`, `::test_import_all_sources_property_change_advances_revision_through_the_real_pipeline`; `tests/integration/test_revision_fence.py` |
| Mapping-context digest reflects real configured/manifest/shared/migration mappings (including each entry's own documentPath) and adapter versions; unrelated context change triggers reevaluation without spurious revision advance *(4 for shared/migration content)* | `tests/unit/test_orchestrator.py::test_a_real_migration_mapping_changes_the_mapping_context_digest`, `::test_a_document_path_only_change_still_changes_the_mapping_context_digest` |
| Context/checkout-path independence (context entry ordering, physical paths) | `tests/unit/test_sources_identity.py`; `tests/integration/test_i1_bundled_migration_determinism.py::test_two_clean_checkouts_at_different_paths_produce_identical_results` |
| DiscoveryScopeId stability under changed roots/filters; scope_definition_digest tracks the physical root | `tests/unit/test_sources_identity.py`; documented distinction re-confirmed in `test_i1_bundled_migration_determinism.py` |
| Inventory revision/capture-id stability and distinction | `tests/unit/test_sources_inventory.py` |
| Tombstone staleness/scope-mismatch rejection; explicit tombstones and complete inventories retire only intended ownership | `tests/unit/test_sources_tombstones.py`; `tests/unit/test_sources_removal_authority.py` |
| Failed/partial discovery, missing roots, incomplete checkouts preserve state; a failed source blocks the whole run's commit | `tests/unit/test_orchestrator.py::test_missing_root_is_failed_and_not_commit_eligible`, `::test_a_malformed_document_fails_the_whole_run_not_just_that_source`, `::test_one_rejected_source_blocks_commit_but_records_all_outcomes` |
| Shared claims survive removal of one source | `tests/integration/test_importer.py::test_import_all_sources_removes_source_no_longer_discovered` |
| Byte-different/semantically-equivalent inputs share `semantic_input_digest`; dependency-closure encoding/ordering/empty-digest match fixed vectors | `tests/unit/test_sources_identity.py`; `tests/unit/test_sources_reference_resolution.py` (closure-walk tests) |
| Replay determinism; two clean runs from the same initial state produce byte-identical semantic reports; sequential replay is a true no-op | `tests/unit/test_sources_replay.py`; `tests/integration/test_revision_fence.py`; `tests/integration/test_i1_bundled_migration_determinism.py` (the discovery/mapping-layer byte-identity proof) |
| I1 blockers | `0` |

## Limitations and unsupported constructs (explicitly disclosed, not silently omitted)

- Remote/network `$ref` resolution and third-party/out-of-tree adapter loading: out of I1 entirely
  (§3's own scope boundary).
- AsyncAPI 3.x, and every OpenAPI/AsyncAPI version other than the three/one named above: rejected
  `REJECTED_UNSUPPORTED`, never grandfathered.
- `configuredServiceMappings`/`destinationBrokerMappings` (§5.3's mapping-context categories): stay
  explicit empty arrays — no configured instance of either exists or is needed for any bundled
  fixture; this is a legal, disclosed absence per §5.3 ("explicit empty arrays represent absent
  mapping categories"), not an oversight.
- The bundled-example migration artifact (`config/migrations/v0.5.0-bundled-example-identities.yaml`)
  is deliberately not wired into either default config file's active `sources.migrations` list — see
  "Run identity" above.
- `real-world-validation/apache-airflow` fixtures exist on disk but carry no I1-specific
  qualification obligation; only `quarkus-super-heroes` is named in the governing spec's own
  Draft 0.3 amendment.
- Kubernetes/I2 discovery: unrelated increment, untouched by I1.

## Handoff to I2

I2 (`docs/specifications/0.5.0/i2-kubernetes-discovery-vertical-slice.md`) may rely on the registry
seam (`app.sources.registry.SourceAdapter`/`SourceAdapterRegistry`), the discovery/inventory
lifecycle (`app.ingestion.orchestrator.run_filesystem_discovery`, `app.sources.commit_gate`/
`inventory`/`replay`/`claim_reconciliation`/`removal_authority`), and the owner-scoped identity
formulas (`app.sources.owner_ids`, `app.sources.migration_mappings` for any future shared-identity
needs) exactly as built, without reintroducing directory-based ownership or name-based identity for
any new source kind it adds.

## I1 exit statement

> GO — At this branch's tip, all four PRs' work is present and re-verified together: the registry
> seam and owner-scoped RFC 8785 Schema/Message/Queue identity (PR3a), bounded multi-file `$ref`
> resolution with exact composition/version-enforcement semantics (PR3b), and the explicit
> shared-identity/migration mapping mechanism proving portable, deterministic restoration of prior
> canonical meaning for the bundled examples, including two genuine cross-source merges
> (PaymentRequested, InvoiceCreated) and a genuine cross-source content-conflict rejection (PR4).
> `uv run pytest tests/unit` (1369) and `tests/integration` (300) both pass in full; lint/format are
> clean. I1 blockers = 0. I2 may build its Kubernetes discovery vertical slice directly on this
> seam and lifecycle contract.
