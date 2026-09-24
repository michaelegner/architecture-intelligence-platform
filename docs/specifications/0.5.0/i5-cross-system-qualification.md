# AIP v0.5.0 I5 — Cross-System Qualification and Model Hardening

**Status:** Draft 0.1 — qualification contract; no I5 target has been qualified<br>
**Target release:** `v0.5.0`<br>
**Release increment:** I5 — Cross-System Qualification and Model Hardening<br>
**Governing parent:** [`specification.md`](specification.md), Draft 0.2, git blob `b4c0163edc3d1dc1891e432029094f99966a3598` at `554582418352a7daa4fc93693c3537e910d70d90`, especially §§3–5, 22–24, 28–31<br>
**Entry baseline:** I1–I4 complete; I4 `GO` recorded in [`i4-completion-record.md`](i4-completion-record.md)<br>
**Exit:** `FINAL_CANDIDATE_QUALIFIED`; I6 retains release and publication authority

---

## 1. Purpose and boundaries

I5 tests whether the v0.5.0 architecture model and source lifecycle remain evidence-correct across
two materially different systems that were authored independently of AIP. It combines fresh
real-system comparisons with frozen independent captures and deterministic negative fixtures for
semantics the selected systems do not exercise. Findings may justify only general hardening.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, and **MAY** are
normative. The parent specification and I1–I4 increment contracts govern the meaning of facts;
this document governs their I5 qualification, not a new interpretation of those facts.

I5 SHALL preserve:

```text
non-observation != absence
source disappearance != authorized source removal
unresolved identity > guessed identity
unsupported > falsely supported
Queue != Topic != Subscription
Service != Kubernetes Service != Workload != Pod
WHERE something is != HOW it interacts
```

I5 does not add a source family, Canonical Model family, broker adapter, public tool, locality
qualification, health inference, or Intent. The I4 `GO` means Pub/Sub is part of I5 coverage; it
does not turn the Kafka consumer group in the Quarkus profile into a Subscription. I5 does not
publish a release or make the I6 `RELEASE_READY` decision.

## 2. Targets and independence

The two I5 real-system targets are:

| Target | Role | Existing upstream pin | Existing dossier |
| --- | --- | --- | --- |
| Quarkus Super Heroes | Independently authored reference application with REST, Kafka, and OTel behavior | `8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce` | [`quarkus-super-heroes/`](../../real-world-validation/quarkus-super-heroes/) |
| Apache Airflow | Independently governed OSS system with public REST API, distinct process roles, and Celery/Redis topology | `3adbbe1c58e4532df1964cb7794805e763816ee8` (release `3.3.1`) | [`apache-airflow/`](../../real-world-validation/apache-airflow/) |

These are materially different in authorship, deployment and runtime structure, and messaging
mechanism. Quarkus is a reference application, not production software. Airflow's observed Celery
signals have the evidence limits recorded in its prior dossier. Neither target is required to
exhibit a supported fact its pinned upstream system does not actually provide.

The pins above are the initial I5 target identities. Before a target's qualifying run, its I5
dossier SHALL reconfirm its exact upstream commit, image digest and dependency/runtime identities
where applicable. A changed upstream pin requires a documented reason, independent ground-truth
review against the new pin, and a new profile freeze before any qualifying comparison. Previous
v0.3 results and expected files are research and regression inputs, never v0.5 qualification
results or automatically valid v0.5 ground truth.

## 3. Pre-execution freeze gate

Before the first qualifying AIP comparison for each target, a versioned I5 dossier under
`docs/real-world-validation/v0.5.0/<target>/` SHALL freeze:

1. the upstream source, release/image/dependency identities, selected components, exclusions,
   startup and traffic profile, and exact AIP input/source identities;
2. independently authored positive and forbidden facts, with source citations and explicit
   unsupported, unresolved, or insufficient-evidence cases;
3. the capture origin and completeness bounds for declarations, Kubernetes resources, OTel data,
   inventories, tombstones, and any mapping artifact used;
4. the supported expectation vocabulary, comparison projection, observation-window and clean-state
   procedure, one absolute checkout location for the paired byte-identity runs, deterministic
   ordering/serialization policy, and rerun criteria;
5. the profile revision and content digests, plus the first eligible candidate comparison point.

The dossier SHALL identify which evidence is independently supplied by the upstream system, which
is independently captured from a running system, and which is hand-authored as a deterministic
negative fixture. AIP graph contents, API responses, comparator output, or generated prose SHALL
NOT determine ground truth. Expected facts SHALL be frozen before inspecting the candidate's
qualifying output. A change to expected facts after comparison requires a cited upstream-evidence
correction, a new freeze revision, and rerunning affected comparisons; changing expectations solely
to make AIP pass is prohibited.

The I5 specification fixes the validation contract. Exact expected facts, capture identities, and
run commands belong in those dossiers and their runbooks. No I5 target comparison is qualifying
until this gate is recorded for that target. The same rule applies to any new independent capture
or negative fixture before its first qualifying use. A material change to target components,
supported scope, traffic, capture authority, or comparison rules after this freeze requires a
versioned scope-change record, re-reviewed expectations, and rerunning affected scenarios. The
change cannot silently replace a failed comparison.

## 4. Coverage and evidence allocation

I5 SHALL publish a coverage matrix before comparison and reconcile it in the final report. For
each row, the matrix identifies a real-system run, a frozen independent capture, or a deterministic
negative fixture; the expected/forbidden outcome; the source and candidate revisions; and the
comparison or test evidence. An existing fixture may be reused only with its provenance, bounds,
and revision disclosed. Reuse does not turn a hand-authored fixture into independent real-system
evidence.

| Required area | Minimum I5 scenario and evidence boundary |
| --- | --- |
| I1 source lifecycle | Real target declarations enter through the I1 seam. Frozen complete same-scope inventory, explicit tombstone, failed/incomplete discovery, changed scope, reimport, and conflicting-source cases prove permitted preservation or removal; absence alone never removes ownership. Deterministic fixtures may cover lifecycle transitions the upstream profiles cannot safely induce. |
| I2 Kubernetes | At least one independently captured frozen resource bundle proves bounded offline discovery and owner-chain evidence. Negative cases cover missing/invalid identity and the absence of application interaction inferred from Kubernetes alone. The existing I2 `kind` capture is supporting evidence from an AIP-operated demo, not a third independently authored target or proof of live Kubernetes discovery. |
| I3 reconciliation | Positive declared-Service/Workload association through an admitted identity path; negative ambiguity, cross-path conflict, service-name-only, and Kubernetes-only cases. Evidence resolves through the Pod UID/owner chain where that path is exercised; no `DEPLOYED_AS` fact or dependency is guessed. |
| I4 Pub/Sub (`GO`) | Real Quarkus Kafka behavior is assessed only to the extent its frozen declarations/runtime evidence supports it. Frozen Azure Service Bus and Google Pub/Sub positive fixtures and the Kafka negative fixture exercise source-independent Topic/Subscription distinctions, fan-out versus competing consumers, scoped identity, and no consumer-group equivalence. These fixtures do not claim a live broker adapter or independently operated Azure/Google systems. |
| Public answers and provenance | Representative supported HTTP, messaging, and deployment claims have same-snapshot evidence drill-down and mapping provenance. Service, REST, and negotiated MCP preserve the same qualified answer; reads cause no graph writes. Unsupported and unresolved cases remain visible without fabricated claims. |

Coverage across the two targets and supporting evidence SHALL be explicit; I5 SHALL NOT claim that
each target individually exercises every v0.5 capability. If an area has no eligible evidence,
the matrix records the gap and I5 does not claim it qualified. Existing I1–I4 tests are regression
evidence, not substitutes for the two fresh real-system runs. The frozen v0.4 Architecture Answer
contract and qualified legacy scenarios SHALL remain valid under the intentional v0.5 changes.

## 5. Comparison and finding contract

Each target run SHALL begin from a documented clean AIP state and the frozen target profile. The
report binds the upstream/profile identity, AIP candidate SHA, rule/schema/mapping revisions,
input and capture digests, observation window, inventory authority, actual-facts artifact,
comparator artifact, and relevant logs. The comparison uses the frozen expected and forbidden
facts, not a candidate-derived expected file. Facts outside the declared evidence and supported
scope are reported with their limitation instead of silently dropped or forced into a supported
class.

I5 reuses the established six finding classifications as its finding taxonomy:

| Classification | I5 meaning |
| --- | --- |
| `CORRECT` | An independently supported expected fact is represented correctly. |
| `MISSING_SUPPORTED` | An in-scope supported fact established by independent evidence is absent. |
| `INCORRECT_SUPPORTED` | An in-scope emitted fact contradicts independent ground truth, including an invented identity or relation. |
| `UNSUPPORTED` | The upstream mechanism lies outside the admitted v0.5 semantics and remains explicit. |
| `UNRESOLVED_IDENTITY` | A possible relationship lacks enough admitted identity evidence to resolve safely. |
| `INSUFFICIENT_EVIDENCE` | Independent evidence cannot establish the proposed expectation. |

Severity is separate from classification. Every material mismatch or limitation SHALL have a
finding id, target/scenario, expected and actual behavior, evidence references, affected contract,
severity, and exactly one disposition:

```text
FIX                  general, evidence-justified production defect to correct
DEFER                plausible change outside supported or safely evidenced I5 scope
DOCUMENT_UNSUPPORTED mechanism intentionally outside current supported semantics
NO_CHANGE            current behavior is correct for its claimed scope
```

A `FIX` needs an independently evidenced general defect, a contract-level explanation, distilled
regression coverage, and impact checks against both systems and existing fixtures. Product names,
target-specific aliases, special cases for a fixture, guessed identities, or weakened negative
guards SHALL NOT enter production code. `DEFER` and `DOCUMENT_UNSUPPORTED` require an explicit
limitation; they cannot conceal a supported false positive. `NO_CHANGE` requires evidence that the
current result already satisfies the frozen contract. Zero fixes is a valid outcome when the
evidence supports it.

After validation begins, a new Canonical Model family, adapter, or public tool requires a
specification amendment and explicit approval before work proceeds. A semantic ambiguity not
settled by the governing specifications also stops the affected work for a specification decision;
tests or observed output cannot decide what the contract should mean.

## 6. Revalidation and exit

After all accepted fixes, I5 SHALL rerun both real-system targets and every supporting positive
and negative scenario from clean state against one candidate. It SHALL run deterministic
Architecture Answer evaluation twice at that same candidate and frozen input/profile revisions,
from clean state at the same absolute checkout location, with byte-identical output. Declared
`Evidence.source_file` currently carries an absolute path into `snapshot_id` and
`model_revision` (I4 §20 item 9); the paired runs SHALL therefore retain and report their raw
paths and snapshot values, without location normalization. A rerun at another checkout location
starts a new pair and is not byte-compared with the former pair. Ordering, capture, and
time-dependent fields in the comparison must follow the pre-frozen normalization policy; the
report retains the raw evidence needed to audit that normalization. The evaluator's reference
canonicalization must match the candidate's qualified v0.5 semantics before these I5 runs; I6
owns refreshing the committed release evaluation report. Any executable or
qualification-relevant change after the run creates a new candidate and reopens affected I5 gates.

The final I5 report SHALL contain:

- the frozen target identities, dossier/fixture digests, coverage matrix, candidate SHA, rule and
  schema revisions, run identities, and clean-state evidence;
- expected-versus-actual results, all findings and dispositions, accepted fixes and regressions,
  known limitations, and cross-system impact assessment;
- evidence/provenance drill-down for representative claims and negative proof of guessed or
  unsupported facts;
- inventory, tombstone, failed/incomplete discovery, changed-scope, conflict, and atomicity results;
- two byte-identical deterministic evaluations and preservation of the v0.4 Architecture Answer
  contract under the documented v0.5 migration;
- the explicit I5 exit decision and any unresolved blockers.

`FINAL_CANDIDATE_QUALIFIED` requires both fresh real-system comparisons, complete disclosed
coverage through the allowed evidence types, zero unexplained canonical facts, zero guessed
identities, zero silent unsupported cases, no unresolved material supported mismatch, and the
revalidation evidence above. A blocked gate yields no I5 qualification. I6 subsequently performs
its own exact clean-checkout release gates, records distinct candidate/evidence/decision identities,
and decides release readiness and authorized publication under parent §§23–26. I5 qualification
alone is neither a publication decision nor evidence of a shipped artifact.
