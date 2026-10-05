# AIP v0.6.0 I5 — Real-System Qualification and Product Demonstration

**Status:** Proposed — revision 0.1, for owner review; no I5 capture, qualification or pilot result is claimed by this specification.  
**Increment:** I5 of v0.6.0, Locality-Aware Current State.  
**Entry:** I4 is completed and merged ([PR #420](https://github.com/michaelegner/architecture-intelligence-platform/pull/420)). Its [completion record](i4-completion-record.md) and [I4 → I5 handoff](i4-i5-handoff.md) qualify candidate `460c6c20eb704caac479111da31292204fa2a1aa` for a **bounded I5 handoff only**; they do not qualify a future I5/I6 candidate or establish production capacity.  
**Authority:** [Accepted parent specification](specification.md) §§14.1, 20–25, 26–31, 33; [I1 controlled-capture acquisition runbook](i1-capture-acquisition-runbook.md), including its stop conditions and E1–E7; [I1 support matrix](i1-locality-support-matrix.md); [I2 completion and rehearsal](i2-completion-record.md); [I3 public-answer contract](i3-bounded-current-state-projection-and-public-answers.md); [I4 accepted specification](i4-deterministic-semantic-qualification.md), frozen [coverage register](i4-coverage-register.md), [completion record](i4-completion-record.md) and [handoff](i4-i5-handoff.md).

## 1. Purpose and exit claim

I5 SHALL establish that the **existing, independently qualified v0.6 locality semantics work on genuinely emitted runtime evidence** and can be understood by a developer undertaking a service change. I5 does not design another locality model.

The minimum end-to-end developer question is:

> Before changing `service:orders` in a multi-Workload rollout, which direct HTTP dependencies are positively established for each evidenced caller Workload, and what can AIP **not** conclude?

Success combines three distinct results: (1) a separately acquired **actual controlled two-Workload capture** and independently authored truth, (2) unchanged Quarkus Super Heroes and Apache Airflow baseline revalidation, and (3) a replayable, task-led demonstration of the supported new question and its limitations. The technical capture and demo are **not** a production product pilot.

**Blocking boundaries:** no assignment by Service/Deployment name, `DEPLOYED_AS` mapping, labels or co-location; no claim of local absence from non-observation; no inferred target location, region/tenant scope, Kafka locality, causal path, Intent, historical snapshot availability or universal dependency. No new production feature, source adapter, public route/tool, schema or default switch is authorized by I5.

## 2. Frozen inputs and non-substitution

| Input | Binding rule |
|---|---|
| I4 completed candidate and full A/B evidence | Preserve its exact commit, independently authored oracle, schema and raw results. Do not call the later I5 candidate “I4-qualified” without a new run. |
| [I1 acquisition runbook](i1-capture-acquisition-runbook.md) | This governs the **actual** run, identities, recording/replay wire path, capture envelopes, checksums, stop criteria and expected-result template. Reuse; do not invent a second acquisition protocol. |
| [I2 rehearsal](../../../tests/fixtures/locality/rehearsal/RUN-RECORD.md) | Proven working plumbing and capture format, labelled **REHEARSAL**. It cannot be relabelled as I5 independent acquisition. |
| [I4 B01a/B01b](i4-vectors/expected-i4.json) | Independently frozen **synthetic** same-day P1→P3 replacement qualification. Useful regression, **not** proof that the I5 two-Workload deployment was actually recorded. |
| [Quarkus Super Heroes](../../real-world-validation/v0.5.0/quarkus-super-heroes/) and [Apache Airflow](../../real-world-validation/v0.5.0/apache-airflow/) v0.5 dossiers | Pin and revalidate existing upstream-derived ground truth, modes, expected answers and findings unchanged. Lack of two upstream-evidenced caller-locality dependencies remains a coverage gap. |
| v0.5.1 task-led Quarkus demo | Keep its original evidence and no-v2 answer/snapshot pins. Show the new controlled reference as a separate example, never as telemetry emitted by Quarkus. |

The I1 runbook's illustrative Operation ID shorthand does not supersede the importer: the independent expected dossier SHALL use the **actual accepted canonical IDs** from the declaration import report (for example, IDs containing the full `service:` prefix where applicable). An expected value must not be copied from an AIP answer.

## 3. Actual controlled acquisition (I5.1)

**Acquisition owner and expected-answer author:** Michael Egner, as already frozen in the I1 runbook. The owner may stop an invalid run; a rehearsal executor or agent cannot silently promote synthetic data to independent truth.

Use the I1 harness with one throwaway `kind` cluster, namespace `aip-locality`, two **distinct Deployment Workloads** `orders` (W1) and `orders-canary` (W2), one canonical caller `service:orders`, and actual HTTP CLIENT calls to `pricing` (O1) and `legacy-pricing` (O2). The same cluster/namespace is sufficient. One Deployment's successive ReplicaSets are **not** two Workloads.

The run SHALL, in this order:

1. Pin repository/harness revisions, built/application and Collector images by digest, tools and configuration. Create the cluster; obtain `clusterUid` from the real `kube-system` Namespace UID; preserve command/output.
2. Capture **real SDK-produced** CLIENT Resource attributes and HTTP interactions, including API-server-issued `k8s.pod.uid`, independently emitted `k8s.cluster.uid` byte-equal to the Kubernetes envelope `clusterUid`, `service.name`, `deployment.environment.name` and exact Pod/namespace consistency fields. Do not enrich these identities inside the Collector or synthesize runtime traffic/spans.
3. Record at least five minutes of traffic with **P1 and P2 both Running**; acquire **C1 while both Pod UID/owner chains coexist**, including namespace, Deployment, ReplicaSet, Pod, source revision, observed `capturedAt` and selected capture scope. Capture is non-atomic across `kubectl` calls; disclose this.
4. Promote by removing the old `orders` Deployment/P1, continue canary traffic, and record authoritative **C2** under the **same configured source and physical root**, with P1 absent and P2 still present. Preserve the unedited C1 files separately without using them as an active historical snapshot. Finish all traffic and captures in one UTC day according to the runbook's time margin.
5. Export the unmodified Collector `otlp.jsonl` and all applied manifests. Pin C1/C2 envelopes/resources, SDK/Collector configuration, accepted declaration imports, telemetry, UIDs, source revisions, times and SHA-256 in `RUN-RECORD.md` and `SHA256SUMS`. Record each stop-condition check.

**Stop, do not substitute a fixture**, if the runbook's requirements fail: distinct W1/W2 owner UIDs, stable P1/P2 UIDs through overlap, authentic CLIENT attributes, byte-equal cluster identity, admitted UTC-day timing, source envelope checksums, unedited recordings, or evidence that the receiver actually accepted the recorded traffic. Stop on incomplete or conflicting ownership rather than repairing it by name or an inferred mapping.

An acceptable artifact directory is `tests/fixtures/locality/two-workload-capture/` as proposed by I1. Its raw inputs and provenance MUST be distinguished from the committed I2 rehearsal and any extra synthetic negative fixtures. Live Kubernetes is needed **only to acquire** this evidence; later replay does not need a cluster.

## 4. Independent expected truth before AIP evaluation (I5.2)

**Chronology is an acceptance rule:** complete acquisition and independently inspect source evidence; freeze/commit `RUN-RECORD.md`, canonical declared Operation IDs, the original input hashes and an `expected.md` **before the first AIP evaluation of that capture**. Record the expectation commit and the later evaluation candidate separately. Expected outcomes SHALL be justified by exact recorded spans/Resources, selected Kubernetes owner chains and applicable I1/I2 rules; neither AIP output nor an agent narrative may author ground truth.

Minimum independently authored assertions, applying the frozen I1 E1–E7 template:

| State | Required positive/negative oracle |
|---|---|
| **C1**, same whole-UTC-day observation window | W1/P1's real `orders CALLS pricing` is `APPLICABLE` and `CONFIRMED` only where the imported declaration independently supports it; W2/P2's real `orders CALLS legacy-pricing` is `APPLICABLE` and `OBSERVED_ONLY` without that declaration. |
| **C1**, unfiltered locality query | Enumerates **both** actual captured caller Workloads; optional W1/W2 comparison shows separately supported different Operations. Do not turn a missing edge on the other side into an absence or exclusive-use claim. |
| **C1**, evidence-mode drill-down | Actual v2 IDs, source/capture refs, selected C1 revision, Workload UIDs, source lineage and answer snapshot agree; unauthorized/wrong-caller refs are not exposed. |
| **C1**, scope boundaries | Source or configured `DEPLOYED_AS` placement does not attribute calls; target runtime locality stays `UNKNOWN`; local Workload coverage is unavailable, so no `NOT_OBSERVED_IN_WINDOW`/negative-dependency assertion. |
| **C2**, after authoritative replacement | P1's previously recorded scoped event is retained but its Workload attribution becomes `UNRESOLVED` with the frozen capture-missing reason; it is not reassigned to P2/W2 or declared absent. P2's independent supported call remains eligible when C2 is time-compatible. |
| **C1 versus C2** | Two distinct canonical snapshot IDs where selected capture changes. A C1-bound evidence request or cursor after C2 is stale/refused per the frozen contract; a saved C1 file is **not** a browser for unavailable historic snapshot state. |
| **v1/v2 coexistence** | Legacy unscoped v1 coverage and counts do not acquire fabricated Workload attribution or double count under v2 replay; accepted v2 changes the conditional canonical fingerprint as specified. |

Record exact expected evidence IDs/lineage and **forbidden** claims for each row. Preserve a full original-Resource recording and any actual capture-format limitations. Additional conflicting/missing-attribute negatives MAY reuse the existing synthetic oracle, but MUST be separately labelled and never counted as evidence of the actual captured system.

## 5. Replay, cross-system checks and defect disposition (I5.2–I5.3)

Replay in a fresh AIP graph with scoped-evidence ingestion **explicitly enabled for this controlled reference and its configuration pinned** (without changing the default or the no-v2 Quarkus baseline). Use only the runbook's frozen wire path: one unmodified OTLP-JSON line per request into the **pinned replay Collector** (no processors, queue or retries) and one protobuf request to AIP `/v1/traces`. Require 200 responses, one-to-one recorded request counts, preserved arrival order and identity attributes; do not parse `otlp.jsonl` directly as AIP protobuf. Import declarations and C1 first. Evaluate C1 **before** selecting C2; replay/evaluate C2 in the declared staged sequence, without resurrecting C1.

Run the actual-capture oracle twice in **independent clean processes/states**, retaining canonical answer bytes and corresponding request, candidate/build identity, graph/import revision, producer, source/configuration digests, container and process IDs, and any failures. Compare each against **pre-authored** expected and forbidden facts and compare the raw canonical A/B bytes without masking identifiers. Exercise direct service, REST and **negotiated MCP** semantic parity, same-snapshot scoped evidence lookup, bounded enumeration/continuation and selected Workload comparison, including required abstention/refusal. A passing test result without the correct positive local claims does not qualify.

On the **same explicit I5 candidate** also re-run pinned Quarkus Super Heroes and Apache Airflow v0.5 evaluations, their known source-mode/claim limitations, the v0.5.1 task-led demo/no-v2 pins, and material v0.6 regression gates. Keep the original dossiers and independently recorded truth immutable: mark every unsupported/insufficient/unresolved answer as such instead of filling gaps with the new controlled capture. Quarkus remains the primary real-world developer workflow; Airflow must still demonstrate the limits of observed application dependencies. Neither is falsely promoted to the two-locality reference.

Classify findings as `CORRECT`, `MISSING_SUPPORTED`, `UNSUPPORTED`, `UNRESOLVED`, `INSUFFICIENT_EVIDENCE` or **semantic defect**, with original evidence and case identity. A false local/global/absence assertion, missing independently supported positive, wrong Workload/capture lineage, silent source-mode change, adapter drift or cross-run nondeterminism is a **stop/qualification failure**. For a genuine cross-system defect, authorize only a general correction, keep the independent expectations unchanged unless a reviewed semantic amendment is necessary, then re-run both upstream targets **and** the controlled reference on the corrected SHA. The I4 baseline cannot be substituted for a later changed candidate.

**Release boundary:** I6, not I5, reruns mandatory qualifications against the **exact final release SHA** after any I5/I6 implementation, fixture, schema, default or packaging change. Do not flip the scoped-evidence default, re-freeze the four-tool golden path, publish tags/images or resolve carried security debt #323 by implication in I5.

## 6. Task-led demonstration (I5.3)

Extend the v0.5.1 Quarkus developer entry point, not a second agent application. Demonstrate this sequence with an ordinary REST or MCP client and human-readable, reproducible requests/responses:

1. **Before editing a Service**, show what the preserved Quarkus dossier establishes and what its original replay does **not** establish about caller locality.
2. Switch explicitly to the **separate actual controlled `service:orders` capture**, labelled with the acquisition run ID and provenance. Ask **“Where are its direct HTTP dependencies established?”** with environment/whole-UTC-day scope **without supplying Workload IDs**. Show both actual W1/O1 and W2/O2 positive answers and their distinct qualification.
3. Compare those two **evidenced** Workloads at the same C1 snapshot; drill into admissible v2 and Kubernetes capture refs. Explain exact caller attribution and `CONFIRMED` versus `OBSERVED_ONLY`, without inferring remote/local target placement, negative differences or global dependency sets.
4. Show the **post-promotion C2** limitation: P1's retained event is `UNRESOLVED` in the current capture; the C1↔C2 time boundary is not a historical comparison API. Explain prominently that useful rollout-overlap comparison requires recording C1 **before** the later authoritative capture displaces P1.
5. Show a declared/`DEPLOYED_AS`-only or missing-local-observation case that **abstains** correctly, with actual included/excluded candidate inventory, completeness, bounds and unknown local coverage.

Publish a short setup/runbook, exact request/response transcripts, expected-versus-actual table and demonstration narration. Keep the actual capture, independently authored expected truth, unchanged upstream Quarkus/Airflow, any separately synthetic negatives and optional agent commentary visibly distinct. The **replay/demo** SHALL need no running Kubernetes cluster, Kafka broker, upstream Quarkus build, LLM key or GT agent. An optional LLM/GT consumer can display the qualified output but cannot strengthen it or count as evidence.

## 7. Product pilot: a separate decision gate (I5.4)

A technically useful demonstration is **not** product validation. Before any external or representative pilot results are observed, a named pilot owner SHALL freeze concrete service-change tasks, independently checkable answers, a with/without-AIP baseline with comparable source access, and **owner-chosen numeric or categorical success/stop criteria** for time, supported coverage, justified abstention, avoided false local/global assumptions, setup/capture overhead and user/agent preservation of evidence scope. The parent supplies **no default threshold**; I5 must not invent one.

If a pilot executes, record observed results and an explicit `CONTINUE`, `NARROW`, `DEFER` or `STOP` decision against those pre-frozen criteria. If it does **not** execute, explicitly record `NOT_RUN` with pilot owner, follow-up owner/action, missing product-value evidence and the required **v1.0-rc stable-contract admission-ledger** carry-forward; make **no** customer-outcome or stable-contract-readiness claim. A `NOT_RUN` pilot does not retrospectively invalidate the technical reference capture or independent Quarkus/Airflow qualification.

The I4 owner acceptance of **measured one-host cost for bounded I5 handoff** is preserved; it is **not** a product pilot, production sizing approval, numerical SLO or adoption of proposed ADR 0012 retention/compaction.

## 8. Execution slices and exit artifacts

| Slice | Work | Exit evidence |
|---|---|---|
| **I5.1 — Independent acquisition** | Execute the existing I1 harness, record C1 overlap and C2 replacement, pin authentic raw capture and provenance; **no AIP evaluation yet** | Actual `RUN-RECORD.md`, immutable capture/declarations/manifests/telemetry, per-file hashes, owner stop-condition sign-off, labelled `ACTUAL_CONTROLLED_REFERENCE` |
| **I5.2 — Independent oracle and deterministic qualification** | Freeze exact source-derived expected and forbidden facts **before** running AIP; perform two clean replays and service/REST/MCP/evidence checks | Prior expectation commit, actual positive/abstaining C1/C2 results, raw canonical A/B artifacts, candidate and CI/run identity, finding ledger |
| **I5.3 — Two upstream systems and user walkthrough** | Re-run unmodified Quarkus/Airflow truth; extend the task-led Quarkus entry point with separately labelled actual-reference replay | Per-system classifications and compatibility pins, reproducible user walkthrough and source-aware transcripts |
| **I5.4 — Completion and I6 handoff** | Reconcile executed results, owner decisions, observed capture cost and pilot outcome/`NOT_RUN`; hand exact revisions/limits forward | I5 completion dossier with per-case dispositions, pilot record, actual-vs-synthetic labels, outstanding #323, I6 final-candidate obligations |

Slices may be split for review, but **never invert acquisition → independent expectation freeze → first AIP evaluation** or treat an implementation test as the expected author.

## 9. Definition of Done and stop conditions

I5 may be marked **technical qualification complete** only when the following are demonstrated by auditable artifacts:

1. Independently acquired, actually emitted two-Workload CLIENT traffic has verifiable Pod UID, byte-equal cluster identity, correct distinct Deployment owner chains, bounded UTC-day context and original C1/C2 snapshots, with all mandatory I1 acquisition gates passed.
2. An expected-result file frozen **before the first AIP query** proves the observed positive W1/O1 and W2/O2 claims, selected C1 comparison, correct C2 unresolved P1, P2 persistence, source/Operation attribution and explicit forbidden negative/global/target-locality claims.
3. Two independent clean replays agree with that oracle and with each other at raw canonical-byte level; service/REST/negotiated MCP and scoped same-snapshot evidence agree, with no unauthorized reference leak or missing supported positive.
4. Quarkus and Airflow independent baselines remain truthful on the tested I5 candidate; no dossier is rewritten, and any actual cross-system fix is rerun across **both upstream systems** and the controlled reference.
5. A developer can reproduce the task-led demonstration **offline**, with no live cluster or LLM, and see what changed and what cannot be concluded under C1→C2 capture replacement.
6. The completion record pins tested commit, source/image/schema/config/telemetry/capture/expectation digests, clean processes and containers, commands, CI statuses, semantic outcomes, supported/missing/unsupported/unresolved facts, unmeasured costs, and any open findings. It separately records a bounded pilot decision or `NOT_RUN` with its v1.0-rc carry-forward.
7. An I6 handoff explicitly requires final-SHA independent qualification, four-tool golden-path/default review, version/release security gates, deferred-dimension ROADMAP reconciliation and owner-controlled publication decision. Known issue #323 is carried, not falsely cleared.

**Hard stop:** if the real independent two-locality capture cannot be acquired or its identities independently justified, I5 **cannot** claim real-execution locality qualification or show the I2 rehearsal/I4 synthetic bridge as its substitute. Record `BLOCKED`, preserve acquired evidence, and request an explicit parent scope/gate amendment before any diminished claim. An absent product pilot instead follows §7's separate `NOT_RUN` policy; it is not the same failure.

**No release claim:** I5 completion is neither `RELEASE_READY_NOT_PUBLISHED` nor `SHIPPED_VERIFIED`. Those are I6 outcomes only.
