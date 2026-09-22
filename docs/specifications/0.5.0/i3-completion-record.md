# I3 Completion Record — v0.5.0 Runtime Identity Reconciliation and `DEPLOYED_AS`

**Status:** COMPLETE. Per the governing spec's own §25 closing sentence: I3 completion is not release
qualification. I5 and I6 remain required.

Governing spec: `docs/specifications/0.5.0/i3-runtime-identity-reconciliation.md` (Draft 0.4, amended
by PR #218). Per §25: I3 is complete only when all three parent-spec identity paths are implemented
exactly, Path C uses Pod UID + the current I2 owner chain and never name/label similarity, the exact
OTel Resource allowlist is executable, Path C's temporal compatibility (persisted `last_seen` and
exact environment equality under one executable Observation Context predicate) is executable,
same-path multiplicity produces `AMBIGUOUS` deterministically, observed-only Service minting cannot
qualify `DEPLOYED_AS`, agreement unions evidence and reports the strongest agreed method,
contradiction always wins over precedence, ambiguous/unresolved/conflicting cases emit no deployment
claim, supported Pod replacement preserves logical Workload association, the mapping artifact is
versioned/validated/evidence-backed/snapshot-bound, `DEPLOYED_AS` is exposed as its own public claim
and never relabeled as a dependency, REST and negotiated MCP semantics are equivalent to
`ArchitectureIntelligenceService`, `get_architecture_drift` remains deployment-agnostic, every public
deployment claim and non-resolved resolution evidence ref is drillable at the same snapshot, REST
evidence listing/lookup require and enforce the same snapshot id, `DeploymentResolution`
grouping/id/cardinality/filtering/ordering are executable and deterministic, unreferenced Kubernetes
infrastructure/evidence remains internal, `schema_version = "0.5"` validates all new/old answer
cases, standard negotiated MCP exposes exactly three read-only tools and causes zero graph writes,
the v0.4.x direct MCP envelope is absent, the deterministic evaluator invokes
`ArchitectureIntelligenceService` directly, two clean qualification runs are byte-identical, all
pre-I3 regression suites remain green, limitations are documented, and this record pins the
implementation candidate revision, reconciliation rule/schema revisions, mapping artifact revision,
fixture digests, and qualification report/evidence revisions.

## Run identity

I3 was delivered as nine sequential implementation/record PRs (spec + six implementation slices, two
of which split into their own reviewed delivery PRs — slice 5 into 5a/5b, slice 6 into 6a/6b) plus one
spec amendment, each independently reviewed and merged, per §23's six suggested implementation
slices:

| Item | Scope | Merge commit | PR # |
|---|---|---|---|
| Spec | I3 governing specification, Draft 0.3 | `5e4b2dcdde0bc6ea29b4e1bfce1770515c0374ca` | #210 |
| Slice 1 | Contract and public schema foundation | `5197c8332bde6f9963d4a46f5df9f6cdeedb24c8` | #212 |
| Slice 2 | OTel runtime identity evidence | `e24a204eeddba49045a8faeb46db1425afded6d9` | #213 |
| Slice 3 | Explicit and configured paths (Path A/B) | `d0d3c1de8ebedf1472a1969c3bc4fd516fae8bc4` | #215 |
| Spec amendment | Draft 0.3→0.4, public adapter consolidation (ADR 0016) | `6592b02084550d38a25729c140079d4e299f8713` | #218 |
| Slice 4 | Observed path (Path C) | `588699fbd8e99148512c6e267131fbc131a58955` | #220 |
| Slice 5a | Public adapter consolidation, REST parity | `08d352616ff7a38b937f5deddd9db46f27073612` | #221 |
| Slice 5b | Deployment public exposure | `5b7561bd238f2849bc459026b2b577a4fea91eab` | #222 |
| Slice 6a | Deterministic qualification (§21 matrix, §22 fixture) | `dbf066b593b8b19f18596a0be27dc2724885cdbc` | #224 |
| Slice 6b | Documentation and this completion record | (this PR's own merge commit — see "Immutable qualification identity" for why the *implementation* candidate revision is pinned to slice 6a instead) | #225 |

**Reconciliation rule identity** (frozen since slice 1, unchanged since):
`DEPLOYMENT_RECONCILIATION_RULE_ID = "service-workload-reconciliation"`,
`reconciliation_rule_version = 1` (`app/architecture_intelligence/contracts.py`,
`app/architecture_intelligence/deployment_projection.py`). **Runtime identity normalization rule**
(frozen since slice 2):
`normalization_rule_id = "otel-runtime-identity-observation"`, `normalization_rule_version = 1`
(`app/provenance/model.py`). **Canonicalization version** (bumped 1→2 in slice 5b to bind the mapping
digest into snapshot identity): `_CANONICALIZATION_VERSION = 2`
(`app/architecture_intelligence/repository.py`).

**Path B has no single global rule-id/version constant analogous to the above** — a disclosed,
intentional design difference (flagged in PR #224, not silently ignored): each mapping entry's own
provenance is `(artifact_id, artifact_revision, mapping_id, content_digest_prefix)`, computed by
`compute_service_workload_mapping_evidence_id`, rather than one global adapter-style version. This
gives every mapping claim exact, self-contained provenance without needing a second, redundant
version signal — see §21's own "mapping-content change changes reconciliation context/snapshot"
requirement, satisfied via the content digest rather than a bumped rule version.

## Fixture identities

| Fixture | Path | Qualifies |
|---|---|---|
| Per-test hand-built fixtures | Inline in `tests/unit/test_architecture_intelligence_deployment_projection.py`, `tests/unit/test_architecture_intelligence_deployment_reconciliation.py`, and every `tests/integration/test_architecture_intelligence_deployment_*.py` file | Deterministic, precisely-shaped coverage of every individual §21.1-§21.7 required case, one scenario per test. |
| §22 frozen cross-source fixture | `tests/fixtures/deployment/i3-cross-source/` | The spec's own required "one frozen cross-source fixture" — reuses I2's real, independently captured Kubernetes bundle (`tests/fixtures/kubernetes/i2-independent-capture/`, itself already qualified by I2 slice 6) unmodified, combined with authored Path B mapping artifacts and authored Path C OTel observations; see its own `PROVENANCE.md` for the full real-vs-authored disclosure. Exercised by `tests/integration/test_i3_cross_source_qualification.py` (9 tests): all-three-paths-agree, Path A-vs-B conflict, Path A-vs-C conflict, byte-repeatability, resource-ordering invariance, OTel-batch-ordering invariance, zero-graph-write, and real Path B/C evidence resolving through both REST and negotiated MCP. |

The §22 fixture and every integration-level per-test fixture are imported through the real
`import_kubernetes_source`/`import_source` paths (`CAPTURED_RESOURCE`/`DECLARED_MANIFEST` I2 evidence
modes) — no test writes Kubernetes or Service facts via raw Cypher. The unit-level hand-built
fixtures in `test_architecture_intelligence_deployment_projection.py`/
`test_architecture_intelligence_deployment_reconciliation.py` are pure in-memory `CurrentKubernetes
Workload`/`RuntimeIdentityObservationRow`/`PathResolutionResult` constructions passed directly to
`resolve_path_a`/`b`/`c`/`reduce_cross_path_resolutions` — they never touch Neo4j at all, by design
(the same fast, precisely-shaped-per-case pattern every prior I3 slice's own unit suite already
uses).

## Immutable qualification identity

Per §25's own record requirement — pinned here by exact content digest/SHA, not by path alone. This
section is itself a record-only addition (matches I2's own completion record precedent, avoiding a
commit citing its own not-yet-created SHA): it cites PR #224's merge commit, which was already
independently CI/CodeQL-verified before this section was written.

| Artifact | Revision |
|---|---|
| **Candidate revision** (the qualified implementation commit this record's report/evidence below was run against) | `dbf066b593b8b19f18596a0be27dc2724885cdbc` (PR #224 merge — slice 6a, the last content-bearing I3 PR) |
| Governing spec (`docs/specifications/0.5.0/i3-runtime-identity-reconciliation.md`) | git blob `68c8765ca392896e24f78ea4c91075f0067f0779` |
| Public contract shapes (`app/architecture_intelligence/contracts.py`) | git blob `b654af8990eb310f7832636a8f10b077b5c85f7c` at the candidate revision |
| Cross-path reducer (`app/architecture_intelligence/deployment_reconciliation.py`) | git blob `1f9056a8038987e50ae54054685d047904141c3a` at the candidate revision |
| Path A/B/C resolvers (`app/architecture_intelligence/deployment_projection.py`) | git blob `e68a582efff73754376f673806d6591a98a9ffb1` at the candidate revision |
| Deployment repository reads (`app/architecture_intelligence/deployment_repository.py`) | git blob `4f3ff893e2b00cb5398a453dbd46bfd3e0b08527` at the candidate revision |
| Path B mapping-artifact loader (`app/sources/service_workload_mapping.py`) | git blob `4105ee429244f3977b7de218b464beeeda6daecd` at the candidate revision |
| Reconciliation rule/schema revisions | `DEPLOYMENT_RECONCILIATION_RULE_ID = "service-workload-reconciliation"`, `reconciliation_rule_version = 1`; `normalization_rule_id = "otel-runtime-identity-observation"`, `normalization_rule_version = 1`; `_CANONICALIZATION_VERSION = 2`; public `schema_version = "0.5"` |
| §22 fixture content (`tests/fixtures/deployment/i3-cross-source/service-workload-mapping-agree.yaml`) | sha256 `8a4d34e40fcf4ea85272740ffbb3e1ac6dc1c230dbb5e578e10a18200e398d57` |
| §22 fixture content (`tests/fixtures/deployment/i3-cross-source/service-workload-mapping-conflict.yaml`) | sha256 `13a475b9340890f3b9c3b9a0ecf6d762be7fba963740a8e1c16bbae56bcefd06` |
| §22 fixture's real Kubernetes component (`tests/fixtures/kubernetes/i2-independent-capture/resources.yaml`, reused unmodified) | sha256 `de2fc2015dcbe33e7cbe0d1768b67cdfa001b696a3f239899e2baa7a3dc2ee14` (already independently pinned by I2's own completion record) |
| Report (regression suite result below) | Local full-suite run at the candidate revision (recorded below); independently corroborated by GitHub Actions CI at that same SHA — `lint + test`, `integration-core`, `demo-e2e`, `dependency security scan (pip-audit, spec §29)`, `quality` all `conclusion: success` (run [35783364014](https://github.com/michaelegner/architecture-intelligence-platform/actions/runs/35783364014)) |
| Evidence (static analysis) | CodeQL `analyze (python)` and `analyze (actions)`, both `conclusion: success`, run [35783364012](https://github.com/michaelegner/architecture-intelligence-platform/actions/runs/35783364012) |

## Regression suite (full local run at the pinned candidate revision, `dbf066b`)

| Suite | Result |
|---|---|
| `uv run ruff check .` | clean |
| `uv run ruff format --check .` | clean (340 files) |
| `uv run pytest tests/unit` | 1815 passed |
| `uv run pytest tests/integration` | 405 passed |

For comparison, I2's own completion record reported 1621 unit / 347 integration passed at its pinned
tip. I3 added 194 unit tests and 58 integration tests across all six slices, all currently green
alongside every prior increment's own regression tests, unmodified.

## §21/§25 Definition of Done — evidence by area

| Area | Evidence |
|---|---|
| §21.1 Path A (annotation cases, missing/exact-case/similarity-only) | `tests/unit/test_architecture_intelligence_deployment_projection.py` (Path A section); `tests/integration/test_architecture_intelligence_deployment_repository.py` |
| §21.2 Path B (mapping artifact, all cases incl. delimiter-bearing/duplicate/unknown-field) | `tests/unit/test_architecture_intelligence_deployment_projection.py` (Path B section); `tests/unit/test_sources_service_workload_mapping.py`; `tests/integration/test_architecture_intelligence_deployment_repository.py` |
| §21.3 Path C (Pod UID/owner chain/exact resolution/consistency/temporal, incl. explicit environment-exact-match) | `tests/unit/test_architecture_intelligence_deployment_projection.py` (Path C section); `tests/integration/test_architecture_intelligence_deployment_path_c.py` |
| §21.4 Cross-path reduction (every A/B/C combination, incl. real Path C data, AMBIGUOUS-through-the-reducer) | `tests/unit/test_architecture_intelligence_deployment_reconciliation.py`; `tests/integration/test_i3_cross_source_qualification.py::test_cross_source_all_three_paths_agree_produces_one_resolved_explicit_claim`, `::test_cross_source_path_a_vs_path_b_contradiction_produces_conflict`, `::test_cross_source_path_a_vs_path_c_contradiction_produces_conflict` |
| §21.5 Pod replacement (stable claim id across a Pod UID swap) | `tests/integration/test_architecture_intelligence_deployment_path_c.py::test_path_c_pod_replacement_preserves_claim_id` |
| §21.6 Surface/evidence (REST/MCP/service equivalence, deployment/dependency separation, `WorkloadRef` field allowlist, evidence drill-down for Path A/B/C, unreferenced evidence hidden, no synthesized CALLS, zero graph writes) | `tests/integration/test_api_architecture_intelligence_deployments.py`; `tests/integration/test_mcp_service_dependencies_equivalence.py`; `tests/integration/test_mcp_architecture_drift_equivalence.py::test_drift_never_returns_deployed_as_over_mcp_even_when_a_deployment_resolves`; `tests/integration/test_api_architecture_intelligence_equivalence.py::test_evidence_resolve_rest_matches_service_for_real_deployment_evidence`; `tests/integration/test_mcp_evidence_equivalence.py::test_deployment_evidence_resolves_identically_direct_vs_mcp`; `tests/integration/test_i3_cross_source_qualification.py::test_cross_source_evidence_resolve_rest_matches_service_for_path_b_and_c_evidence`, `::test_cross_source_evidence_resolve_mcp_matches_service_for_path_b_and_c_evidence`, `::test_cross_source_deployment_resolving_read_causes_zero_graph_writes`; `tests/unit/test_architecture_intelligence_contracts.py::test_workload_ref_exposes_exactly_its_frozen_field_allowlist`; `tests/integration/test_architecture_intelligence_deployment_evidence_visibility.py::test_unreferenced_kubernetes_evidence_stays_hidden` |
| §21.7 Determinism (ordering invariance, byte-repeatability, `resolution_id` sensitivity/stability, one-resolution-per-group-key) | `tests/integration/test_i3_cross_source_qualification.py::test_cross_source_resource_ordering_has_no_effect_on_deployment_resolution`, `::test_cross_source_otel_batch_ordering_has_no_effect_on_path_c_resolution`, `::test_cross_source_byte_repeatability_of_deployment_reconciliation`; `tests/unit/test_architecture_intelligence_deployment_projection.py::test_path_b_mapping_entry_ordering_has_no_effect_on_resolution`, `::test_compute_deployment_resolution_id_deterministic_and_context_sensitive`; `tests/unit/test_architecture_intelligence_deployment_reconciliation.py::test_reducer_produces_exactly_one_resolution_per_group_key_across_multiple_groups` |
| §22 Frozen cross-source fixture | `tests/fixtures/deployment/i3-cross-source/` + `PROVENANCE.md`; `tests/integration/test_i3_cross_source_qualification.py` (9 tests) |
| Kubernetes-only infrastructure with no A/B/C resolution creates no `DEPLOYED_AS`; `DEPLOYED_AS` never leaks as `CALLS`/`SENDS`/`RECEIVES_FROM` | `tests/integration/test_kubernetes_surface_regression.py` (pre-existing, still green); `tests/integration/test_i3_cross_source_qualification.py::test_cross_source_all_three_paths_agree_produces_one_resolved_explicit_claim`'s own explicit `dependency_claim_ids == []` assertion |
| MCP tool count remains exactly three; the v0.4.x direct envelope is absent; the evaluator invokes `ArchitectureIntelligenceService` directly | `tests/unit/test_mcp_discovery.py`; `docs/mcp.md`'s own disclosed ADR 0016 decision (slice 5a) |
| `schema_version = "0.5"` and committed v0.5 schemas validate all new/old answer cases | `tests/unit/test_architecture_intelligence_contracts.py`; `schemas/architecture_intelligence/v0.5/` |
| Two clean qualification runs are byte-identical | `tests/integration/test_i3_cross_source_qualification.py::test_cross_source_byte_repeatability_of_deployment_reconciliation` |
| Regression (pre-I3 I1/I2/OTel/MCP behavior preserved) | Full regression suite above — unmodified pre-existing suites, all still passing |

## Limitations and unsupported constructs (explicitly disclosed, not silently omitted)

- Per spec §28's stop conditions, none of which were crossed: no fourth MCP tool; no name/label/fuzzy
  identity matching (Path A/B/C are all exact-match only); no new Kubernetes resource kind beyond
  I2's own eight; no new discovery-source family; no second ownership/expiry engine for materializing
  `DEPLOYED_AS`; no live Kubernetes client; no locality-qualified output (`namespace` on `WorkloadRef`
  is identity context only, per `docs/graph-model.md`); no container/sidecar canonical entities; no
  exposure of arbitrary Kubernetes/OTLP payloads; conflict is never weakened to precedence-based
  winner selection; `schema_version` widened to `"0.5"`, never left claiming `"0.4"`; REST/MCP never
  independently derive or qualify Architecture Knowledge outside `ArchitectureIntelligenceService`.
- Multi-Service-per-Workload is not modeled in v0.5 (per parent spec) — same-path multiplicity is
  `AMBIGUOUS`, cross-path disagreement is `CONFLICT`, never a list of simultaneously valid Services.
- Path B has no single global versioned rule-id constant analogous to I2's `kubernetes-adapter@1` or
  I3's own Path A/C reconciliation-rule identity — a disclosed, intentional per-mapping-entry
  provenance design (see "Run identity" above), not a gap.
- `get_evidence`/`GET /api/evidence`'s convenience (context-free) forms re-derive a real Observation
  Context per Pod-resolved observation group from that group's own persisted timestamps, rather than
  accepting an arbitrary caller-supplied one — see `docs/evidence.md`'s own disclosure of this slice
  5b design decision, retained unchanged through slice 6.
- The §22 frozen fixture's own contradictory-identity scenarios exercise Path A-vs-B and Path A-vs-C
  conflicts specifically (the combinations its one real captured Workload naturally supports); the
  full pairwise/triple conflict matrix (including B-vs-C) is covered by the hand-built §21.4 reducer
  unit tests in `tests/unit/test_architecture_intelligence_deployment_reconciliation.py`, not
  separately re-proven against this one real-capture-based fixture.
- I5 still owns two-system release qualification; I3's own §22 fixture satisfies I3's narrower,
  increment-scoped qualification bar, not I5's release-qualification bar (same relationship I2's own
  completion record described for its independent-capture fixture).

## Handoff to I4 and I5

Per §26, I3 provides I5 with: stable `Service -[DEPLOYED_AS]-> Workload` claim semantics (frozen
reconciliation rule id/version, above); positive and negative cross-source identity fixtures
(`tests/fixtures/deployment/i3-cross-source/`, plus every hand-built §21 case); the public
`WorkloadRef` projection (`app/architecture_intelligence/contracts.py`); public evidence lineage for
every path (`docs/evidence.md`); the `CONFLICT`/`AMBIGUOUS`/`UNRESOLVED` conflict/ambiguity taxonomy
(`docs/graph-model.md`); the exact §9.7 temporal compatibility rule
(`docs/opentelemetry.md#observation-context-compatibility-i3`); and the exact reconciliation rule
version pinned in this record.

I3 provides no new Pub/Sub semantics to I4. Per §26, I4 SHALL NOT use `DEPLOYED_AS`, Kubernetes
co-location, or Workload identity as evidence that a Queue/Topic/Subscription relationship exists —
nothing in this implementation introduces such a coupling (`DEPLOYED_AS` remains produced entirely
inside `app.architecture_intelligence.deployment_reconciliation`, never referenced from
`app/telemetry/` or any messaging-resolution code path).

I5 may harden I3 only when independent cross-system evidence demonstrates a real model defect.
Target-specific identity exceptions remain prohibited.

## Corrected I3 exit statement

> **COMPLETE** — The pinned *implementation* candidate revision (`dbf066b`, slice 6a's own merge)
> contains all code and test changes I3 required: contract and schema foundation (slice 1), bounded
> OTel runtime identity evidence (slice 2), explicit and configured identity paths (slice 3), the
> observed path with real Pod-UID/owner-chain/temporal qualification (slice 4), public adapter
> consolidation and the full public deployment vertical slice (slice 5, split into reviewed delivery
> PRs 5a/5b), and full §21 deterministic qualification against one frozen §22 cross-source fixture
> (slice 6a). `uv run pytest tests/unit` (1815) and `tests/integration` (405) both pass in full at
> that revision; lint/format are clean; no production regression was found in any pre-existing
> I1/I2/OTel/MCP suite. This 6b PR (#225) adds no further code or test changes on top of that
> candidate — only the §24 documentation updates and this completion record itself, split into its
> own reviewed PR for the same reason I2's own completion record cited (a qualification/completion
> record PR needs its own already-merged predecessor SHA to cite, not a self-reference). **I3 itself
> is COMPLETE only once this PR merges** — the pinned code candidate alone satisfies §25's technical
> bullets, but §25 also requires the documentation and this very record to exist. I3 completion is
> not release publication or `SHIPPED_VERIFIED` — I5 independent qualification and I6 exact-artifact
> release/post-release gates remain required by the parent specification.
