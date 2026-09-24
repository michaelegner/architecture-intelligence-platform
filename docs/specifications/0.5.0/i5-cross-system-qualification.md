# AIP v0.5.0 I5 Specification — Cross-System Qualification and Model Hardening

**Status:** Draft 0.2. This draft restructures the increment specification to the I2-I4 form and adds
the decisions the parent's §33 decision register assigns to I5. It supersedes Draft 0.1 (#235,
`3f413f6`). No I5 target has been qualified yet<br>
**Target release:** `v0.5.0`<br>
**Release increment:** I5 — Cross-System Qualification and Model Hardening<br>
**Parent:** [`specification.md`](specification.md), Draft 0.2, git blob
`b4c0163edc3d1dc1891e432029094f99966a3598`, especially §§5, 22, 31, 33, 34<br>
**Entry baseline:** I4-complete `main`, commit `554582418352a7daa4fc93693c3537e910d70d90` (#234)<br>
**Dependencies:** I1 complete ([record](i1-completion-record.md)); I2 complete
([record](i2-completion-record.md)); I3 complete ([record](i3-completion-record.md)); I4 complete
as `GO` ([record](i4-completion-record.md))<br>
**Exit:** `FINAL_CANDIDATE_QUALIFIED`. I6 retains release and publication authority

---

## 1. Purpose

I5 answers:

> **Do the v0.5.0 architecture model and source lifecycle remain evidence-correct across two
> materially different systems that were authored independently of AIP, and does every finding
> justify only general, evidence-backed hardening?**

I5 combines four kinds of evidence:
- fresh real-system comparisons;
- upstream-sourced offline inputs;
- frozen independent captures;
- deterministic negative fixtures for semantics the selected systems do not exercise.

I5 SHALL preserve:

```text
non-observation != absence
source disappearance != authorized source removal
unresolved identity > guessed identity
unsupported > falsely supported
Queue != Topic != Subscription
Service != Kubernetes Service != Workload != Pod
WHERE something is != HOW it interacts
AIP Input != AIP Expected Output
AIP Output MUST NOT define Ground Truth
```

---

## 2. Normative language and frozen parent decisions

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD
NOT**, and **MAY** are normative.

The parent already freezes the following for I5:

1. **§22.1:** a frozen validation contract before any target execution, covering I1 lifecycle, I2,
   I3, I4 (`GO`) and evidence drill-down, with at least two materially different independently
   authored systems plus deterministic negative fixtures;
2. **§22.2:** exactly the four dispositions `FIX`, `DEFER`, `DOCUMENT_UNSUPPORTED` and `NO_CHANGE`.
   Target-specific names, aliases, heuristics and fixture exceptions are prohibited. A new Canonical
   Model family, adapter or public tool after validation starts requires an amendment;
3. **§22.3:** clean-state rerun, two byte-identical deterministic evaluations, zero unexplained
   facts, zero guessed identities, zero silent unsupported cases, and a single frozen candidate;
4. **§33:** I5 owns "real systems, revisions, expected facts". This specification freezes the systems,
   revisions and per-target fact scope (§§5-8). The literal expected facts are frozen by the
   per-target dossier slices (§14) under the §6 contract, before any qualifying comparison.

The parent and the I1-I4 increment contracts govern the *meaning* of facts. This specification
governs only their I5 qualification and SHALL NOT reinterpret them.

---

## 3. Entry baseline and integration gate

I5 starts from `554582418352a7daa4fc93693c3537e910d70d90`. It assumes the following I1-I4 handoffs
are executable. Each is pinned by its completion record:

```text
I1  source-adapter seam; SourceInstanceId/revision identity; inventory authority; tombstones;
    ACCEPTED / ACCEPTED_WITH_LIMITATIONS / REJECTED_* results; atomic commit
I2  OFFLINE_ONLY Kubernetes envelope; DECLARED_MANIFEST / CAPTURED_RESOURCE evidence modes;
    Workload/Pod/owner-chain claims; no interaction inference
I3  Service -[DEPLOYED_AS]-> Workload via Path A (annotation), B (configured mapping),
    C (Pod UID + owner chain); CONFLICT / AMBIGUOUS / UNRESOLVED; public WorkloadRef
I4  Topic / Subscription; PUBLISHES_TO / SUBSCRIPTION_OF / RECEIVES_FROM -> Subscription;
    runtime no-minting; consumer group != Subscription; spec §20 settled decisions
All ArchitectureIntelligenceService (service / REST / negotiated MCP) with same-snapshot evidence
```

**Known integration gaps.** Before any qualifying run, Slice 1 SHALL close these gaps in the
qualification tooling. They are tooling defects, not model findings:

1. **Nondeterministic, incomplete label choice.** `real_world_validation/capture.py::_node_label`
   selects one label from the registry's label set with `next(iter(frozenset))`. For
   `RECEIVES_FROM` (Queue|Subscription) and `CARRIES` (Queue|Topic), capture is therefore
   nondeterministic and incomplete.
2. **No v0.5 fact classes in capture.** Capture has no runtime-status classification for
   `PUBLISHES_TO` or `RECEIVES_FROM -> Subscription`. The comparator cannot express `DEPLOYED_AS`
   claims or resolutions at all.
3. **Stale reference canonicalization.** The evaluator's authoring-time
   `evaluation/architecture_answers/reference/snapshot.py` still computes canonicalization v1. The
   candidate uses v3 (I4 §11).

A mismatch between an assumed handoff and the candidate SHALL be recorded as an I5 finding (§11). It
SHALL NOT be worked around in qualification tooling.

---

## 4. Scope and non-goals

### 4.1 In scope

1. The two real-system targets and their revisions (§5).
2. The ground-truth authorship and freeze contract (§6).
3. The v0.5 expectation vocabulary and comparison projection (§7).
4. Per-target frozen scope (§8).
5. The coverage matrix (§9), including I1 lifecycle scenarios on real declarations (§10).
6. Comparison, findings and dispositions (§11).
7. Determinism and clean-state revalidation (§12).
8. The qualification tooling needed to express v0.5 facts (Slice 1).
9. Evidence-justified general fixes (`FIX`) and the I5 completion record.

### 4.2 Out of scope

```text
a new source family, Canonical Model family, adapter, broker adapter, or public tool
live Kubernetes clusters, live brokers, or cluster/broker writes
AIP-authored AsyncAPI, OpenAPI, or Kubernetes manifests presented as upstream evidence
widening the OTel messaging operation key (I4 §9)
locality qualification, health inference, Intent
a third real-system target
release, publication, or the I6 RELEASE_READY decision
```

The I4 `GO` puts Pub/Sub inside I5 coverage. It does not turn the Quarkus Kafka consumer group into a
Subscription.

---

## 5. Targets, revisions and independence

| Target | Role | Upstream pin | Prior dossier (research input) |
| --- | --- | --- | --- |
| Quarkus Super Heroes | Independently authored reference application: REST, Kafka, OTel, and upstream Kubernetes manifests | commit `8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce` | [`quarkus-super-heroes/`](../../real-world-validation/quarkus-super-heroes/) |
| Apache Airflow | Independently governed OSS system: public REST API, distinct process roles, Celery/Redis topology | release `3.3.1`, commit `3adbbe1c58e4532df1964cb7794805e763816ee8` | [`apache-airflow/`](../../real-world-validation/apache-airflow/) |

The two targets differ materially in authorship, deployment and runtime structure, and messaging
mechanism. Quarkus is a reference application, not production software.

**Quarkus Kubernetes input.**
- The Quarkus target SHALL include the upstream project's own Kubernetes manifests at the pinned
  commit (upstream `deploy/k8s`). They are imported offline through the I2 envelope as
  `DECLARED_MANIFEST`. This is I5's only real-target Kubernetes and `DEPLOYED_AS` evidence.
- Slice 2 SHALL confirm that the manifests exist at the pin and record their paths and digests. If
  they do not exist, the freeze records a coverage gap (§9). I5 SHALL NOT author substitute manifests.
- Airflow has no Kubernetes input in I5.

**Pins and prior results.**
- Each target's dossier SHALL reconfirm the pin, image digests, and dependency and runtime
  identities.
- A changed pin requires three things before any qualifying comparison: a documented reason, a fresh
  ground-truth review against the new pin, and a new freeze.
- v0.3 results, expected files and findings are research and regression inputs. They are never v0.5
  qualification results or automatically valid v0.5 ground truth.

---

## 6. Ground-truth authorship and freeze contract

The required workflow is the v0.3 method ([`README.md`](../../real-world-validation/README.md)):

```text
upstream contracts / docs / config / source / independent runtime evidence
        -> independent dossier (every fact cited)
        -> owner review and merge = freeze
        -> first qualifying AIP comparison
```

The prohibited workflow is:

```text
run AIP -> inspect its output -> search upstream for confirmation -> write expected facts to match
```

**Who authors the facts.**
- An implementing agent MAY draft the expected and forbidden facts, but only from upstream sources,
  docs, config, and independent runtime evidence.
- Every fact SHALL cite its upstream source (file and line, doc URL, or config key).
- AIP graph contents, API responses, comparator output, and generated prose SHALL NOT determine
  ground truth.
- The owner's review and merge of the dossier PR is the freeze. A dossier PR SHALL NOT contain or
  reference qualifying AIP output for that target.

**What each dossier freezes.** For each target, and for any new independent capture or negative
fixture before its first qualifying use:
1. the upstream, image and dependency identities; the components and exclusions; the startup and
   traffic profile; and the exact AIP inputs and source identities;
2. the positive and forbidden facts, with explicit `UNSUPPORTED`, `UNRESOLVED_IDENTITY` and
   `INSUFFICIENT_EVIDENCE` cases;
3. the capture origin and completeness bounds for declarations, Kubernetes resources, OTel data,
   inventories, tombstones, and any mapping artifact;
4. the comparison projection, observation window, clean-state procedure, the single absolute
   checkout location for the paired byte-identity runs (§12), the ordering and serialization policy,
   and rerun criteria;
5. the profile revision and content digests, and the first eligible candidate.

Each dossier SHALL classify every input into exactly one of three kinds, and SHALL NOT present one
kind as another:
- **upstream-supplied:** evidence supplied by the upstream system;
- **independently captured:** evidence captured from a running system;
- **AIP operator configuration:** for example a Path B mapping artifact (§8.1). This is AIP input,
  never ground truth.

**Changing expected facts after the freeze.**
- It requires a cited upstream-evidence correction, a new freeze revision, and rerunning the affected
  comparisons.
- Changing expectations to make AIP pass is prohibited.
- A material change to components, scope, traffic, capture authority or comparison rules requires a
  versioned scope-change record and re-reviewed expectations. It cannot replace a failed comparison.

---

## 7. Expectation vocabulary and comparison projection

I5 extends the v0.3 `expected.yaml` vocabulary to the v0.5 supported fact classes:

| Fact class | Endpoints | Qualification carried |
| --- | --- | --- |
| `PROVIDES`, `CALLS` | Service -> Operation | declared/observed evidence; `CALLS` status |
| `SENDS`, `RECEIVES_FROM` | Service -> Queue | status (`CONFIRMED` / `OBSERVED_ONLY` / `NOT_OBSERVED_IN_WINDOW`) |
| `PUBLISHES_TO` | Service -> Topic | status, as for `SENDS` (I4 §20 item 6) |
| `SUBSCRIPTION_OF` | Subscription -> Topic | declared evidence |
| `RECEIVES_FROM` | Service -> Subscription | declared/observed evidence |
| `CARRIES` | Queue or Topic -> Message | declared evidence |
| `DEPLOYED_AS` | Service -> Workload | public claim `resolution_method` and `supporting_methods` (`RESOLVED_EXPLICIT` / `RESOLVED_CONFIGURED` / `RESOLVED_OBSERVED`), or public resolution status (`RESOLVED_EXPLICIT` / `RESOLVED_CONFIGURED` / `RESOLVED_OBSERVED` / `CONFLICT` / `AMBIGUOUS` / `UNRESOLVED`) |

**How facts are compared.**
- Relation facts are captured from the graph with every admitted label of each endpoint considered
  deterministically.
- `DEPLOYED_AS` is captured only through `ArchitectureIntelligenceService`'s public deployment
  projection. It is never a graph edge (I3).
- A fact is in scope when its type is in the dossier's scope and either endpoint is a scoped entity.
- An in-scope fact that is not expected is `INCORRECT_SUPPORTED`.
- Forbidden facts are expressed as explicit negative expectations. Each one fails as
  `INCORRECT_SUPPORTED` if it is present.
- `UNSUPPORTED`, `UNRESOLVED_IDENTITY` and `INSUFFICIENT_EVIDENCE` entries are dossier-authored
  pass-through classifications.

---

## 8. Frozen per-target scope

### 8.1 Quarkus Super Heroes

**In-scope components.** `rest-fights`, `rest-heroes`, `rest-villains`, `rest-narration`, and
`event-statistics` as a messaging boundary. `grpc-locations` and `ui-super-heroes` are excluded.

**Inputs.**
- The upstream OpenAPI documents.
- The v0.3 `rest-fights` Architecture Manifest, as a disclosed AIP input carrying upstream-cited
  `CALLS`.
- OTel through the pinned collector.
- The upstream Kubernetes manifests (§5).

**Fact scope:**
- **REST.** `PROVIDES` and `CALLS` for the in-scope REST services. v0.3 froze 35 `PROVIDES` and 3
  `CALLS`; they SHALL be re-reviewed against the pin rather than copied.
- **Kafka `fights` (negative).**
  - There is no upstream AsyncAPI. The expectation is therefore **no** Queue, Topic or Subscription
    fact, and **no** `SENDS`, `PUBLISHES_TO` or `RECEIVES_FROM` for `fights`.
  - The producer's legacy `messaging.operation` key stays unsupported, as I4 §9 requires.
  - The mechanism is classified `UNSUPPORTED`.
- **Kubernetes (I2).** The Workloads (and, where present, Kubernetes Services and Ingresses) are
  discovered offline from the upstream manifests as `DECLARED_MANIFEST`. There is no interaction
  fact from Kubernetes alone.
- **`DEPLOYED_AS` (I3), per Workload and conditional on the frozen manifest evidence.**
  - Slice 2 SHALL record, for each in-scope upstream Workload, whether it carries an
    `architecture-intelligence.io/service-id` annotation that Path A evaluates to a declared Service
    id (I3 §7).
  - Slice 2 SHALL freeze the expected outcome from that recorded evidence, applying I3 §10's
    agreement and precedence rules. The table gives the outcome for each combination:

    | Frozen upstream evidence for a Workload | Disclosed Path B mapping for it | Expected public outcome |
    | --- | --- | --- |
    | No Path A-evaluable annotation | none | No `DEPLOYED_AS` claim from name similarity. The frozen resolution outcome follows I3 §13. This is the real-target name-only negative. |
    | No Path A-evaluable annotation | agreeing | `RESOLVED_CONFIGURED`, `supporting_methods = [RESOLVED_CONFIGURED]` |
    | Path A-evaluable annotation | none | `RESOLVED_EXPLICIT`, `supporting_methods = [RESOLVED_EXPLICIT]` |
    | Path A-evaluable annotation | agreeing | `RESOLVED_EXPLICIT`, `supporting_methods = [RESOLVED_EXPLICIT, RESOLVED_CONFIGURED]` |

  - At most one disclosed Path B configured-mapping artifact MAY bind declared Quarkus Services to
    their upstream Workloads. It is AIP operator configuration (§6), not ground truth.
  - The artifact SHALL be authored from the upstream manifest identities so that it agrees with any
    Path A evidence. A disagreeing mapping would be I3 `CONFLICT` and is not a Quarkus qualification
    case. Conflict is covered by supporting fixtures (§9).
  - If every in-scope Workload carries a Path A-evaluable annotation, both real-target cases that
    need a Workload without one become unavailable: the name-only negative and the configured-only
    `RESOLVED_CONFIGURED` positive. Each is then recorded as a §9 gap covered only by supporting
    fixtures.
- **Path C** is not exercised on this target. The Compose runtime has no Pod UID. It is covered by
  supporting fixtures (§9).
- **Unsupported.** gRPC (`grpc-locations`).

### 8.2 Apache Airflow

**In-scope components.** `airflow-apiserver`, plus the scheduler, worker and triggerer roles as
identity cases.

**Inputs.**
- The pinned upstream REST OpenAPI, bounded to the operations the dossier selects.
- Native OTel.
- No AsyncAPI, manifest or Kubernetes input.

**Fact scope:**
- `PROVIDES` for the selected operations. v0.3 froze 9, and they SHALL be re-reviewed against the pin.
- Postgres dependencies stay `UNSUPPORTED`.
- Process-role runtime identity is `UNRESOLVED_IDENTITY`.
- Celery/Redis messaging is `INSUFFICIENT_EVIDENCE`. It SHALL NOT produce `SENDS`, `RECEIVES_FROM`,
  `PUBLISHES_TO`, or any Queue or Topic fact without independently established sender and receiver
  identity.

---

## 9. Coverage matrix

I5 SHALL qualify this matrix. The final report SHALL reconcile it row by row. An area with no
eligible evidence is recorded as a gap and SHALL NOT be claimed qualified.

| Area | Evidence type | Source | Required outcome |
| --- | --- | --- | --- |
| I1 lifecycle | Real declarations | Quarkus and Airflow declarations through the I1 seam | §10 scenarios |
| I1 lifecycle (not safely inducible upstream) | Negative fixture | Existing I1 tests, reused with disclosure | Regression evidence only |
| I2 offline discovery | Upstream-sourced input | Quarkus upstream `deploy/k8s` at the pin (§5) | Workloads/claims per §8.1; no interaction |
| I2 captured resources and owner chain | Independent capture | [`tests/fixtures/kubernetes/i2-independent-capture/`](../../../tests/fixtures/kubernetes/i2-independent-capture/) | Supporting evidence: an AIP-operated `kind` capture, not a third target |
| I3 Path A/B | Real target plus disclosed mapping | Quarkus (§8.1) | The §8.1 per-Workload outcomes frozen in Slice 2. A real-target case the upstream evidence cannot provide (name-only negative, or configured-only positive) is a gap covered by the I3 supporting fixture |
| I3 Path C, conflict, ambiguity | Hand-authored fixture over a real capture | [`tests/fixtures/deployment/i3-cross-source/`](../../../tests/fixtures/deployment/i3-cross-source/) | Supporting evidence |
| I4 positive (fan-out, competing consumers, scoped DLQ) | Hand-authored fixtures | [`tests/fixtures/pubsub/`](../../../tests/fixtures/pubsub/README.md) (ASB, GCP) | Supporting evidence; no live broker claimed |
| I4 negative (consumer group ≠ Subscription) | Real target plus fixture | Quarkus Kafka (§8.1) and the `kafka/` fixture | No Pub/Sub or Queue fact is minted |
| Public answers and provenance | Real runs | Both targets | Service = REST = negotiated MCP; same-snapshot drill-down; zero writes |
| v0.4 Architecture Answer contract | Regression | `evaluation/architecture_answers` | Preserved under the documented v0.5 changes |

I5 SHALL NOT claim that each target exercises every v0.5 capability. Reusing a fixture does not
make it independent real-system evidence. Existing I1-I4 tests are regression evidence. They never
substitute for the two fresh real-system runs.

---

## 10. I1 lifecycle scenarios on real declarations

For each target, starting from a committed baseline import of that target's frozen declarations:

| Scenario | Operation | Required outcome |
| --- | --- | --- |
| Reimport | Import the same inventory again | No-op: no ownership, snapshot or fact change |
| Complete same-scope inventory without one source | Authoritative inventory omits a declaration | Only that source's ownership is removed, as I1 §6 permits |
| Explicit tombstone | Tombstone one source | That source's ownership is removed; others are untouched |
| Failed or incomplete discovery | Discovery `PARTIAL` or `FAILED` | Nothing commits; prior state is preserved; absence never removes ownership |
| Changed scope | Import under a different scope | No removal outside the authorized scope |
| Conflicting source | A second source contradicts an owned fact | `REJECTED_CONFLICT`; nothing commits |

Each scenario's exact input mutation SHALL be frozen in Slice 4 before it is executed. Mutations are
applied to a copy of the frozen declarations and never to the upstream pin.

---

## 11. Comparison, findings and dispositions

Each target run SHALL begin from a documented clean AIP state and the frozen profile.

The report binds all of the following:
- the upstream and profile identity;
- the candidate SHA;
- the rule, schema and mapping revisions;
- the input and capture digests;
- the observation window;
- the inventory authority;
- the actual-facts artifact;
- the comparator artifact;
- the logs.

Facts outside the declared evidence or supported scope are reported with their limitation. They are
never silently dropped or forced into a supported class.

**Classification** reuses the six v0.3 values from
[`README.md`](../../real-world-validation/README.md):

| Classification | I5 meaning |
| --- | --- |
| `CORRECT` | An independently supported expected fact is represented correctly. |
| `MISSING_SUPPORTED` | An in-scope supported fact established by independent evidence is absent. |
| `INCORRECT_SUPPORTED` | An in-scope emitted fact contradicts ground truth, including a forbidden fact or an invented identity or relation. |
| `UNSUPPORTED` | The upstream mechanism lies outside the admitted v0.5 semantics and remains explicit. |
| `UNRESOLVED_IDENTITY` | A possible relationship lacks enough admitted identity evidence to resolve safely. |
| `INSUFFICIENT_EVIDENCE` | Independent evidence cannot establish the proposed expectation. |

**Findings.** Severity is separate from classification. Every material mismatch or limitation SHALL
have:
- a finding id;
- its target and scenario;
- the expected and the actual behavior;
- evidence references;
- the affected contract;
- a severity;
- exactly one disposition.

**Dispositions** (parent §22.2):

```text
FIX                  general, evidence-justified production defect to correct
DEFER                plausible change outside supported or safely evidenced I5 scope
DOCUMENT_UNSUPPORTED mechanism intentionally outside current supported semantics
NO_CHANGE            current behavior is correct for its claimed scope
```

**Requirements per disposition:**
- **`FIX`** requires all of:
  - an independently evidenced general defect;
  - a contract-level explanation;
  - distilled regression coverage;
  - impact checks against both targets and every existing fixture.

  A `FIX` SHALL NOT add product names, target-specific aliases, fixture special cases, guessed
  identities, or weakened guards to production code.
- **`DEFER` and `DOCUMENT_UNSUPPORTED`** require an explicit limitation. They cannot conceal a
  supported false positive.
- **`NO_CHANGE`** requires evidence that the current behavior satisfies the frozen contract.

Zero fixes is a valid outcome.

---

## 12. Determinism and clean state

**Runs after the last fix.**
- I5 SHALL rerun both targets and every supporting scenario from clean state against one candidate.
- It SHALL run deterministic Architecture Answer evaluation twice. Both runs use that candidate, the
  frozen input and profile revisions, and the **same absolute checkout location**, and they SHALL
  produce byte-identical output.

**Location-dependent values.**
- Declared `Evidence.source_file` carries an absolute path into `snapshot_id` and `model_revision`
  (I4 §20 item 9).
- The paired runs therefore retain and report their raw paths and snapshot values, without location
  normalization.
- A rerun at another location starts a new pair and is not byte-compared with the former pair.

**Normalization of other fields.** Ordering, capture and time-dependent fields follow the normalization
policy frozen in the dossier (§6 item 4). The report retains the raw evidence needed to audit it.

**New candidates.**
- The evaluator's reference canonicalization SHALL match the candidate before these runs (Slice 1).
- Any executable or qualification-relevant change after a run creates a new candidate and reopens
  the affected gates.

---

## 13. Required qualification matrix

At minimum:

- **I1 lifecycle.** Every §10 scenario passes on both targets' real declarations.
- **Quarkus REST.** All re-reviewed `PROVIDES` and `CALLS` are `CORRECT`, with zero
  `INCORRECT_SUPPORTED`.
- **Quarkus Kafka `fights`.** It yields no Queue, Topic, Subscription, `SENDS`, `PUBLISHES_TO` or
  `RECEIVES_FROM` fact. The legacy operation key creates no fact.
- **Quarkus Kubernetes.** The upstream-manifest Workloads are discovered offline as
  `DECLARED_MANIFEST`, and no interaction fact comes from Kubernetes.
- **Quarkus `DEPLOYED_AS`.**
  - Every in-scope Workload yields exactly its §8.1 outcome as frozen in Slice 2.
  - Name similarity never resolves.
  - Every claim's and resolution's evidence drills down at the same snapshot.
- **Airflow.**
  - The selected `PROVIDES` are `CORRECT`.
  - Postgres is `UNSUPPORTED`.
  - Role identity is `UNRESOLVED_IDENTITY`.
  - Celery is `INSUFFICIENT_EVIDENCE`.
  - No messaging fact is guessed.
- **Supporting evidence.** The I2 capture, the I3 cross-source fixture, and the I4 ASB/GCP/Kafka
  fixtures pass at the final candidate.
- **Public surfaces.** Service, REST and negotiated MCP answers are identical for representative
  HTTP, messaging and deployment claims. MCP has exactly three tools. Public reads cause zero graph
  writes.
- **Determinism.** The two deterministic evaluations are byte-identical at one checkout location.
- **v0.4 contract.** The v0.4 Architecture Answer contract is preserved.
- **Accounting.** There are zero unexplained canonical facts, zero guessed identities, and zero
  silent unsupported cases.

---

## 14. Implementation slices

I5 SHOULD be delivered in these bounded slices, one PR each (Slice 6 is one PR per `FIX`).

### Slice 1 — Qualification tooling foundation

```text
real_world_validation capture: deterministic multi-label endpoints (all admitted labels)
PUBLISHES_TO / RECEIVES_FROM -> Subscription status classification
DEPLOYED_AS claim/resolution capture via the public deployment projection
expected.yaml vocabulary widened to §7; forbidden-fact expectations
evaluation reference canonicalization at the candidate's version (v3)
docs/real-world-validation/v0.5.0/README.md and dossier template
```

Exit: the comparator can express, capture and deterministically compare every §7 fact class. Unit
tests pin the multi-label fix. No target facts are frozen yet, and no production semantics change.

### Slice 2 — Quarkus v0.5 freeze dossier

Exit: the owner has reviewed and merged a dossier under
`docs/real-world-validation/v0.5.0/quarkus-super-heroes/`. It contains:
- the pin reconfirmation;
- the upstream `deploy/k8s` confirmation (paths and digests, or a recorded gap);
- the cited expected and forbidden facts per §8.1;
- any disclosed Path B mapping artifact;
- the profile and runbook.

### Slice 3 — Airflow v0.5 freeze dossier

Exit: the same as Slice 2, under `docs/real-world-validation/v0.5.0/apache-airflow/`, per §8.2.

### Slice 4 — Supporting evidence and lifecycle freeze

Exit: the §10 scenario mutations and the §9 supporting-evidence revisions are frozen. The coverage
matrix is published with every row's evidence type, source revision and expected outcome.

### Slice 5 — Qualifying runs and findings

Exit: both targets and every §9 row have run against one candidate. Every material result has a
finding with exactly one disposition, and a cross-system finding ledger is published.

### Slice 6 — Accepted fixes (conditional)

Exit: each `FIX` merges separately, with the §11 evidence, regression coverage and a two-target impact
check. If there are no `FIX` dispositions, the slice is skipped with a recorded reason.

### Slice 7 — Final-candidate revalidation and completion record

Exit: the §12 revalidation is complete and the §13 matrix is green at one candidate.
`docs/specifications/0.5.0/i5-completion-record.md` pins the candidate, dossier and fixture digests,
run identities, findings, limitations and the I6 handoff. The I5 exit decision is recorded.

---

## 15. Documentation requirements

Before I5 completion, update at least:

```text
docs/real-world-validation/README.md        (v0.5.0 section and method delta)
docs/real-world-validation/v0.5.0/           (dossiers, ledger, report)
docs/specifications/0.5.0/i5-completion-record.md
any living doc whose statement a FIX changes
```

Documentation SHALL distinguish:
- qualified behavior;
- supporting-evidence-only behavior;
- unsupported, unresolved and deferred behavior;
- coverage gaps.

---

## 16. Definition of Done

I5 is `FINAL_CANDIDATE_QUALIFIED` only when all of the following hold:
- both targets' dossiers were frozen before their first qualifying comparison;
- both fresh real-system comparisons are complete;
- every §9 row is qualified or recorded as a gap;
- every §13 item holds at one candidate;
- every finding has exactly one disposition, and no material supported mismatch is unresolved;
- every `FIX` meets §11 and none is target-specific;
- the §12 byte-identity evidence is recorded;
- the I5 completion record pins the candidate, rule and schema revisions, dossier and fixture digests,
  run identities, CI evidence, limitations and the I6 handoff.

A blocked gate yields no I5 qualification. I5 qualification is neither a publication decision nor
evidence of a shipped artifact.

---

## 17. Handoff to I6

I5 provides I6 with:
- one qualified candidate SHA;
- the frozen dossiers and coverage matrix;
- the finding ledger, dispositions and known limitations;
- the evidence of byte-identical evaluation.

I6 performs its own exact clean-checkout release gates. It records distinct candidate, evidence and
decision identities, refreshes the committed release evaluation report, and decides release
readiness and publication under parent §§23-26.

---

## 18. Relationship to later releases

I5 qualifies v0.5 Current-State semantics only:
- namespace and cluster context from Kubernetes stays identity/evidence context, not locality.
  Locality is `v0.6`;
- no finding establishes Intent. Intent is `v0.7`.

---

## 19. Stop conditions

Implementation SHALL stop for specification review if any of these becomes necessary:

1. a new source family, Canonical Model family, adapter, broker adapter, or public tool;
2. an AIP-authored AsyncAPI, OpenAPI, or Kubernetes manifest presented as upstream evidence;
3. a target-specific name, alias, heuristic, or fixture exception in production code;
4. widening the OTel messaging operation key or any other I4 §9 boundary;
5. changing expected facts to make AIP pass, or freezing facts after inspecting qualifying output;
6. a `FIX` that weakens an I1-I4 guard, or that changes a Queue claim id or I4 §20 decision;
7. a live cluster, live broker, or cluster/broker write;
8. a byte-identity difference traceable to production nondeterminism;
9. a semantic ambiguity the governing specifications do not settle;
10. a third real-system target or a change of either target's pin without §5's re-freeze.

---

## 20. Review checklist before implementation

- [ ] The two targets and their pins are fixed, and v0.3 results are research input only.
- [ ] The Quarkus upstream Kubernetes manifests are the only real-target Kubernetes input, and I5
      authors no substitute.
- [ ] An agent-drafted fact is cited to upstream evidence, and the owner's merge is the freeze.
- [ ] No AIP output influences ground truth.
- [ ] The §7 vocabulary covers every v0.5 supported fact class, including `DEPLOYED_AS` through the
      public projection.
- [ ] Quarkus Kafka is a negative case, and the consumer group is never a Subscription.
- [ ] Quarkus `DEPLOYED_AS` expectations are per Workload and conditional on the frozen upstream
      annotation evidence (I3 §10 precedence). Name similarity never resolves, and any Path B mapping
      is disclosed AIP configuration that agrees with Path A.
- [ ] Every §9 matrix row names its evidence type, and supporting fixtures are not called real-system
      evidence.
- [ ] The §10 lifecycle scenarios cover inventory, tombstone, failure, scope, reimport and conflict.
- [ ] The dispositions are exactly the parent's four, with no target-specific fix.
- [ ] Byte-identity runs use one absolute checkout location, with no location normalization.
- [ ] Slice 1 closes the §3 tooling gaps before any qualifying run.
- [ ] I6 retains release authority.

Acceptance of this checklist is the implementation entry gate.

---

## 21. References

- [`specification.md`](specification.md) §§5, 22, 31, 33, 34
- [`i1-source-ingestion-foundation.md`](i1-source-ingestion-foundation.md),
  [`i2-kubernetes-discovery-vertical-slice.md`](i2-kubernetes-discovery-vertical-slice.md),
  [`i3-runtime-identity-reconciliation.md`](i3-runtime-identity-reconciliation.md),
  [`i4-source-independent-pubsub-semantics.md`](i4-source-independent-pubsub-semantics.md)
- [`i1-completion-record.md`](i1-completion-record.md) through
  [`i4-completion-record.md`](i4-completion-record.md)
- [`docs/real-world-validation/README.md`](../../real-world-validation/README.md) and
  [`cross-system/`](../../real-world-validation/cross-system/README.md): the v0.3 method, taxonomy and
  reporting shape
- `real_world_validation/` (the comparator) and `evaluation/architecture_answers/` (deterministic
  evaluation)
