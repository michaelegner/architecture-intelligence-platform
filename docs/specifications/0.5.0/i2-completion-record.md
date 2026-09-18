# I2 Completion Record — v0.5.0 Kubernetes Discovery Vertical Slice

**Status:** COMPLETE. I2 completion is not release publication or `SHIPPED_VERIFIED` — I3/I4
disposition, I5 independent qualification, and I6 exact-artifact release/post-release gates remain
required by the parent specification (§13).

Governing spec: `docs/specifications/0.5.0/i2-kubernetes-discovery-vertical-slice.md` (Draft 0.2,
post-I1 integration amendment). Per §13: I2 is complete only when its scope/claim/exposure decisions
are reviewed and accepted, the I1 integration check is committed with its tested revision, the
internal versioned schemas/registration/envelope validation are executable, all mandatory §11 cases
pass with zero guessed identities/unsupported positive claims/unauthorized expirations, evidence
mode/snapshot continuity/sanitized provenance survive persistence and handoff, regressions pass and
no new public MCP tool or architecture claim exposure is introduced, limitations and `OFFLINE_ONLY`
support wording are published in repository documentation, and candidate/rule/schema/fixture/report/
evidence revisions are recorded.

## Run identity

I2 was delivered as eleven sequential PRs plus this completion PR, each independently reviewed and
merged, per the user-approved delivery plan (§12's six suggested slices, several further split by
AskUserQuestion when their own scope warranted it — mirroring I1's own PR3a/3b precedent):

| Slice | Scope | Merge commit | PR # |
|---|---|---|---|
| Prerequisite A | Source-neutral orchestration, persisted inventory/tombstone lifecycle | `b0c656a` | #190 |
| Prerequisite B | Canonical Model generalization for infrastructure entities/contributions/claims | `c4b4ec9` | #191 |
| 2a | Envelope validation, bounded sanitized loading, §6 identity formulas | `6a0eebf` | #195 |
| 2b-i | Kubernetes source registration and discovery/adapter wiring | `5405b91` | #198 |
| 2b-ii | Predecessor-revision threading, `K8S_STALE_INVENTORY` | `e70cd8d` | #199 |
| 3a | Workload/Pod canonical mapping, `WORKLOAD_EXISTS` | `fb835a5` | #200 |
| 3b | Network Service/Ingress canonical mapping | `bcfd83e` | #201 |
| 4a | Owner-chain resolution, `WORKLOAD_OWNS_POD` | `451fc60` | #202 |
| 4b | Service selection, `NETWORK_SERVICE_SELECTS_WORKLOAD` | `59267a4` | #203 |
| 4c | Ingress backend resolution, `INGRESS_ROUTES_TO_NETWORK_SERVICE` | `0cda410` | #204 |
| 5 | Shared lifecycle replay, conflict, scope/removal qualification | `f5468ea` | #208 |
| 6 | Independent frozen-capture qualification, surface regression, I3 handoff, completion record | `d82a0fa` (candidate; see "Immutable qualification identity" — merge commit will differ) | #209 |

**Adapter/rule identity** (unchanged since slice 2b-i): `kubernetes-adapter@1`,
`kubernetes-discoverer@1`.

## Fixture identities

Two distinct Kubernetes fixture bundles, qualifying two distinct claims:

| Fixture | Path | Qualifies |
|---|---|---|
| Authored, checked-in | `tests/fixtures/kubernetes/i2/` | Deterministic, hand-authored end-to-end coverage of all four §7.1 entity kinds and all four §7.2 claim kinds — used throughout slices 3-6 for repeatable, precisely-shaped test scenarios. |
| Independently captured | `tests/fixtures/kubernetes/i2-independent-capture/` | §11's "at least one independently captured, frozen resource bundle" requirement — a real `kubectl get -o yaml` capture from a real (throwaway) `kind` cluster running this repo's own `examples/runtime-demo/` app, proving real owner-chain resolution against genuine API-server-assigned UIDs and correct allowlist handling of real kubectl-injected noise fields. See that directory's own `PROVENANCE.md` for the full capture procedure, upstream system/revision, and temporal-atomicity disclosure. |

Both fixtures use `CAPTURED_RESOURCE` evidence mode; `tests/integration/test_importer.py` also
exercises `DECLARED_MANIFEST` via dynamically-written inline bundles (slices 2b-4c/5's own dynamic
test helpers).

## Immutable qualification identity

§13: "candidate, rule/schema, fixture, report, and evidence revisions are recorded" — pinned here by
exact content digest/SHA, not by path alone, so this record identifies exactly which artifact set was
qualified. This section is itself a record-only addition, not part of the qualified candidate below
— it cites a commit that already existed and was already independently CI/CodeQL-verified before this
section was written, avoiding the "a commit cites its own not-yet-created SHA" self-reference problem
without needing to wait for this PR's eventual merge commit (§13 asks for the qualified candidate
revision, not specifically the merge SHA).

| Artifact | Revision |
|---|---|
| **Candidate revision** (the qualified implementation commit this record's report/evidence below was run against) | `d82a0fa1190f485482ab2ce2262e124a1280049d` (PR #209 tip at the time of qualification) |
| Governing spec (`docs/specifications/0.5.0/i2-kubernetes-discovery-vertical-slice.md`) | git blob `c538661e50d589aa61b8ac00fa6aba967cb61470` |
| Executable internal schema — envelope validation (`app/sources/kubernetes_envelope.py`) | git blob `e1cd79e8c31465cf23f60c558d6287f38762c6b7` at the candidate revision |
| Executable internal schema — canonical infrastructure model (`app/canonical/infrastructure.py`) | git blob `83bb7f0d96757db734e133ea93e91c3758e0bd60` at the candidate revision |
| Adapter/discoverer rule versions | `kubernetes-adapter@1`, `kubernetes-discoverer@1` (`app/ingestion/kubernetes_adapter.py`/`kubernetes_discoverer.py`) |
| Authored fixture content (`tests/fixtures/kubernetes/i2/resources.yaml`) | sha256 `fa987f007a4e667644c43fded0eb698b2150259f13f408a7b9e6bbd1246fba07` (its own `envelope.yaml`'s pinned digest) |
| Independently captured fixture content (`tests/fixtures/kubernetes/i2-independent-capture/resources.yaml`) | sha256 `de2fc2015dcbe33e7cbe0d1768b67cdfa001b696a3f239899e2baa7a3dc2ee14` (its own `envelope.yaml`'s pinned digest); full capture provenance in that directory's `PROVENANCE.md` |
| Report (regression suite result below) | Local full-suite run at the candidate revision (recorded below); independently corroborated by GitHub Actions CI run [35325550552](https://github.com/michaelegner/architecture-intelligence-platform/actions/runs/35325550552) (`conclusion: success`) at that same SHA |
| Evidence (static analysis) | CodeQL run [35325550424](https://github.com/michaelegner/architecture-intelligence-platform/actions/runs/35325550424) (`conclusion: success`) at the candidate revision |

## Regression suite (full local run at the pinned candidate revision, `d82a0fa`)

| Suite | Result |
|---|---|
| `uv run ruff check .` | clean |
| `uv run ruff format --check .` | clean |
| `uv run pytest tests/unit` | 1621 passed |
| `uv run pytest tests/integration` | 347 passed |

No pre-existing I1 (OpenAPI/AsyncAPI/Manifest/filesystem) or OTel/MCP test was modified to
accommodate I2 — the full suite above includes every prior increment's own regression tests,
unmodified, still passing alongside every new Kubernetes-specific one.

## §11 Definition of Done — evidence by area

| Area | Evidence |
|---|---|
| Envelope schema validation; bounded sanitized YAML/JSON loading; bounds/security (limits, nesting, aliases/tags, traversal/symlink escape) | `tests/unit/test_sources_kubernetes_envelope.py` |
| §6 identity formulas (`SourceInstanceId`, logical resource id, incarnation); resource identity (same name across namespaces/clusters/kinds, missing identity, UID replacement, API-version rejection) | `tests/unit/test_sources_kubernetes_envelope.py`; `tests/unit/test_ingestion_kubernetes_adapter.py` |
| Source registration/binding, live discovery/adapter wiring, predecessor-revision threading, `K8S_STALE_INVENTORY` | `tests/unit/test_ingestion_kubernetes_discoverer.py`; `tests/integration/test_importer.py` (predecessor/stale-inventory group) |
| Workloads (all three supported kinds, declaration-only and captured presence, zero-replica making no health claim) | `tests/unit/test_sources_kubernetes_mapping.py`; `tests/integration/test_importer.py::test_import_kubernetes_source_commits_real_facts_for_all_four_entity_kinds` |
| Owner chains (all three supported paths; ReplicaSet bridge; absent/stale UID; cross-namespace owner; multiple controllers; cycles; unsupported controller) | `tests/unit/test_sources_kubernetes_owner_chain.py`; `tests/integration/test_importer.py::test_pod_with_multiple_controller_owners_rejects_the_source_and_commits_nothing` |
| Selectors (one/many Pods, one/many Workloads, partial unresolved matches, absent/empty selector, ExternalName, no matches, declaration-only template) | `tests/unit/test_sources_kubernetes_service_selection.py` |
| Ingress (named/numeric ports, default backend, multiple routes, missing Service/port, unsupported resource backend) | `tests/unit/test_sources_kubernetes_ingress_backend.py` |
| Normalization (YAML/JSON, map/file/resource ordering, identical duplicates, resourceVersion-only changes, changed UID) | `tests/unit/test_sources_kubernetes_mapping.py`; `tests/integration/test_importer.py::test_captured_uid_replacement_advances_the_graph_revision`, `::test_resource_version_only_change_does_not_advance_the_graph_revision` |
| Replay (unchanged bundle and mapping context; changed rules/context; first import vs. sequential no-op; two clean runs byte-identical) *(slice 5)* | `tests/integration/test_importer.py::test_kubernetes_two_clean_discovery_runs_produce_byte_identical_semantic_reports`, `::test_kubernetes_unchanged_reimport_is_a_true_replay_no_op`, `::test_kubernetes_mapping_context_digest_change_triggers_reevaluation_not_a_silent_no_op` |
| Inventory (complete empty successor, missing bundle/file, digest mismatch, PARTIAL/FAILED, scope narrowing, stale transition, explicit source removal) *(slice 5)* | `tests/integration/test_importer.py::test_kubernetes_complete_empty_successor_withdraws_prior_source_owned_facts`, `::test_kubernetes_namespace_scope_narrowing_preserves_out_of_scope_claims`, `::test_kubernetes_explicit_tombstone_authorizes_whole_source_removal` |
| Ownership (two sources support one claim; one removed; incompatible current contributions; recreated Pod cannot resolve an old UID) *(slice 5)* | `tests/integration/test_importer.py::test_kubernetes_entity_shared_by_two_sources_survives_one_source_withdrawing`, `::test_two_kubernetes_sources_with_conflicting_content_for_one_logical_resource_commit_nothing`, `::test_kubernetes_recreated_pod_uid_replacement_drops_old_uid_from_owner_chain_claim` |
| Atomicity (failure in one Kubernetes object/source preserves all prior contributions and inventories in the run) | `tests/integration/test_importer.py::test_pod_with_multiple_controller_owners_rejects_the_source_and_commits_nothing`, `::test_two_kubernetes_sources_with_conflicting_content_for_one_logical_resource_commit_nothing` |
| **Independently captured, frozen resource bundle qualifying the owner-chain handoff** *(slice 6)* | `tests/fixtures/kubernetes/i2-independent-capture/` + `PROVENANCE.md`; `tests/integration/test_kubernetes_independent_capture.py` |
| **Surface (internal claims absent from REST/MCP answers; no CALLS/SENDS/RECEIVES_FROM/DEPLOYED_AS/locality claim from Kubernetes alone) — real bundle, real transport** *(slice 6)* | `tests/integration/test_kubernetes_surface_regression.py` (extends the existing generic hand-built-model proof, `tests/integration/test_importer.py::test_persisted_infrastructure_facts_do_not_leak_into_the_public_snapshot`) |
| **§9 I3 handoff completeness — the retained Service-ID annotation genuinely queryable, not just hashed** *(slice 6)* | `InfrastructureContribution.service_id_annotation` (`app/canonical/infrastructure.py`); `tests/unit/test_ingestion_kubernetes_adapter.py::test_service_id_annotation_is_carried_onto_the_workload_contribution_only`; `tests/integration/test_importer.py::test_kubernetes_service_id_annotation_survives_persistence_as_unqualified_input` |
| Regression (qualified I1 OpenAPI/AsyncAPI/Manifest ingestion and existing OTel/direct/negotiated MCP behavior preserved) | Full regression suite above — unmodified pre-existing suites, all still passing |

## Limitations and unsupported constructs (explicitly disclosed, not silently omitted)

- `OFFLINE_ONLY` (§2's scope decision): no live Kubernetes client, kubeconfig loading, watches,
  polling, or cluster writes. A change to `LIVE_INCLUDED` requires a reviewed specification amendment
  before implementation.
- No Helm rendering, Kustomize execution, template evaluation, or remote reference fetching.
- ConfigMaps, Secrets, environment extraction, logs, exec, network probes, and credentials are never
  read as architecture evidence (§5's allowlist boundary).
- `ReplicaSet` is an internal owner-chain bridge only — never promoted to its own canonical entity,
  never a fourth Workload kind.
- No application `Service` is created from Kubernetes metadata; no `DEPLOYED_AS` relation; no
  locality-qualified projection, health/readiness, reachability, causal flow, or Intent claim. I2
  never evaluates the retained `architecture-intelligence.io/service-id` annotation into an AIP
  Service identity — that is explicitly I3's job.
- The internal four claim kinds, the resource/incarnation index, and Kubernetes-sourced
  `Evidence`/`Provenance` records are not exposed via REST or MCP (§9's Draft 0.2 amendment) — proven
  against a real bundle over real transport in slice 6
  (`tests/integration/test_kubernetes_surface_regression.py`).
- The independently captured fixture (`tests/fixtures/kubernetes/i2-independent-capture/`) is a
  one-time, throwaway `kind`-cluster capture with a self-declared authority record, disclosed as such
  in its own `PROVENANCE.md` — not a claim of interoperability with any particular commercial/managed
  Kubernetes distribution beyond a stock upstream API server, and not a live dependency of the test
  suite (no cluster access is needed to run it).
- I5 still owns the two-system release qualification (§11) — I2's own independent capture satisfies
  I2's own, narrower owner-chain-interoperability bar, not I5's release-qualification bar.

## Handoff to I3

Per §9, the I3 handoff includes the following — each row cites exactly where/how it is queryable
today, all confirmed present at this completion record's own revision:

| §9 handoff item | Where it lives |
|---|---|
| Logical Workload/Pod IDs and exact captured UID bindings | `InfrastructureEntity.id` (logical, §6 formula); `InfrastructureContribution.captured_resource_uid` (capture-only, `None` for `DECLARED_MANIFEST`) |
| Namespace/cluster and evidence mode | `InfrastructureEntity.namespace`/`cluster_uid`; `InfrastructureContribution.evidence_mode` |
| Owner-chain hop evidence and unresolved/conflicting outcomes | `InfrastructureClaim{kind: WORKLOAD_OWNS_POD}.evidence_refs`; `K8S_OWNER_UNRESOLVED`/`K8S_OWNER_INVALID` diagnostics (§10) |
| Retained explicit Service-ID annotation as unqualified input | `InfrastructureContribution.service_id_annotation` — **fixed in slice 6** (previously only folded into the opaque `resource_semantic_digest` hash, not itself queryable; see `app/canonical/infrastructure.py`'s own docstring for the full history) |
| Source, inventory, mapping context/rule, and graph snapshot references | `InfrastructureContribution.source_instance_id`/`mapping_rule_id`/`mapping_rule_version`; `CurrentInventory` (discovery-scope-keyed); the real snapshot fingerprint every commit advances (`app/graph/revision_fence.py`) |
| Bundle capture provenance and completeness limitations | `Provenance.source_file`/`source_revision` (per-contribution evidence); `PROVENANCE.md` for the independently captured bundle specifically; §10 diagnostic codes for any `ACCEPTED_WITH_LIMITATIONS` outcome |

I3 applies parent §§15-17 and defines its own temporal compatibility with its chosen OTel
observation. I2 never evaluates the Service-ID annotation into an AIP Service identity, and no
cross-capture UID join or freshness assumption is authorized implicitly by this handoff — both
remain explicit I3 design decisions, not inherited defaults.

## Corrected I2 exit statement

> **COMPLETE** — At the pinned candidate revision (`d82a0fa`), all six of §12's suggested implementation slices are
> present and re-verified together, several further split into their own reviewed delivery PRs
> where their own scope warranted it (the twelve PRs in "Run identity" above): the shared I1
> lifecycle seam and Canonical Model generalization (prerequisite A/B), envelope validation and
> identity (slice 2, split 2a/2b-i/2b-ii), all four §7.1 canonical infrastructure entity kinds and
> all four §7.2 claim kinds (slices 3-4, split 3a/3b/4a/4b/4c), shared lifecycle replay/conflict/
> scope/removal qualification against real Kubernetes bundles (slice 5), and independent
> frozen-capture qualification, real-transport surface regression, and a closed I3 handoff (slice 6).
> `uv run pytest tests/unit` (1621) and `tests/integration` (347) both pass in
> full; lint/format are clean. No production regression was found in any pre-existing I1/OTel/MCP
> suite. I2 completion is not release publication or `SHIPPED_VERIFIED` — I3/I4 disposition, I5
> independent qualification, and I6 exact-artifact release/post-release gates remain required by the
> parent specification.
