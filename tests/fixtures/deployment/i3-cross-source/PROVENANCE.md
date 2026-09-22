# I3 Cross-Source Qualification Fixture Provenance

Spec §22: "I3 qualification SHALL include one frozen cross-source fixture containing: declared AIP
Service(s), I2 Kubernetes bundle, I2 owner-chain facts, explicit workload annotation cases,
configured mapping artifact, OTel resource identity observations, positive and contradictory
identities." §22 also states: "The Kubernetes side SHOULD reuse I2's independently captured bundle
where practical, but I3 does not claim independent real-system interoperability merely because one
component of the fixture is real," and "Authored OTel/resource-identity fixture data used to
exercise specific conflict matrices SHALL be identified as authored."

This directory discloses exactly which parts of this fixture are real vs. authored, per both
requirements.

## Real component (reused, not modified)

The Kubernetes side of this fixture **is** `tests/fixtures/kubernetes/i2-independent-capture/`
(`resources.yaml` + `envelope.yaml`) — the same real `kubectl get -o yaml` capture I2 slice 6 already
qualified. It is imported unmodified, by the exact same `KubernetesSourceConfig` (`id=
"aip-i2-independent-capture"`, `cluster_uid="599e90a5-7ab8-426f-807f-92a65dcc8822"`) I2's own
`tests/integration/test_kubernetes_independent_capture.py` uses — see that directory's own
`PROVENANCE.md` for the full capture procedure and upstream-system disclosure. This is not a new,
separate capture; the same frozen bytes are read again here for a different (I3) purpose. I3 does
not claim independent real-system interoperability merely because this one component is real.

Critically, the real captured `Deployment`/`ReplicaSet` in that bundle already carries a real,
API-server-persisted `architecture-intelligence.io/service-id: service:runtime-demo` annotation
(visible directly in `resources.yaml`) — this fixture's Path A explicit-annotation case is therefore
also real, not an authored addition, and its real owner chain (Pod `658bd464-c78f-4ca2-b7e4-
2b04e158f4ee` → ReplicaSet `4b2e9d49-0c0b-4960-9856-b7ca3c4a63fb` → Deployment
`947e8f54-9bc1-445d-8306-cf7266871ba4`, namespace `aip-runtime-demo`) is what Path C's owner-chain
resolution exercises.

## Authored components (disclosed)

- **Declared AIP Service(s)**: `service:runtime-demo` and `service:runtime-demo-alt` are authored
  declarations (via the real `import_source` path, not raw Cypher), not derived from any capture.
  `service:runtime-demo` matches the real annotation's own target exactly; `service:runtime-demo-alt`
  exists only to produce this fixture's own contradictory-identity scenario (below).
- **`service-workload-mapping-agree.yaml`** (Path B): an authored mapping artifact naming the real
  Workload (`aip-runtime-demo`/`runtime-demo` Deployment) to `service:runtime-demo` — agrees with the
  real Path A annotation.
- **`service-workload-mapping-conflict.yaml`** (Path B): an authored mapping artifact naming the
  *same* real Workload to `service:runtime-demo-alt` instead — disagrees with the real Path A
  annotation, producing this fixture's contradictory-identity scenario (§21.4 "A vs B disagree").
- **OTel resource-identity observations** (Path C): authored `RuntimeSpan` objects, built directly in
  `tests/integration/test_i3_cross_source_qualification.py` (matching every other I3 OTel
  integration test's own convention — no checked-in OTel JSON fixture exists anywhere in this repo),
  naming the real captured Pod UID (`658bd464-c78f-4ca2-b7e4-2b04e158f4ee`) with `service.name`
  either agreeing (`runtime-demo`) or disagreeing (`runtime-demo-alt`) with the declared/annotated
  identity. Exactly which test uses which, since not every scenario in this file touches Path C at
  all: `test_cross_source_all_three_paths_agree_produces_one_resolved_explicit_claim` (and the
  byte-repeatability/ordering tests built on it) persist an *agreeing* span; `test_cross_source_
  path_a_vs_path_c_contradiction_produces_conflict` persists a *disagreeing* one (real Path A vs.
  this authored Path C observation); `test_cross_source_path_a_vs_path_b_contradiction_produces_
  conflict` persists no OTel span at all (its own contradiction is Path A vs. Path B only).

## Why one real Workload is enough for both a positive and a contradictory scenario

The fixture's only real, independently captured component (the Kubernetes owner chain) has exactly
one Workload. Rather than authoring a second, fabricated Workload merely to have "two" - which would
dilute the real-capture provenance for no qualification benefit, since Path A/B/C's own identity
formulas are evaluated per-Workload regardless of how many Workloads exist - both required outcome
families (positive and contradictory) are produced from the *same* real Workload across different
test scenarios, by varying only the inherently-configuration-time Path B/C inputs (which are
authored regardless of whether the underlying Workload came from a real capture or not). This keeps
the one real component genuinely singular and frozen, while still satisfying §22's own requirement
that the fixture, taken as a whole, contain both a positive and a contradictory identity case.
