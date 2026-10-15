# AIP v0.7.0 I4 — Deterministic, Real-System and Product-Value Qualification

**Status:** Proposed — revision 0.2, incorporating PR #547 review. This specification freezes the I4 qualification method and exit gates; it does not claim that I4 has run, that a release candidate is qualified, or that v0.7.0 is release-ready. Revision 0.2 makes parent §22 coverage explicit, treats Tyk consumer ambiguity as a dossier-only semantic check, hardens the Route→Operation bridge shape, and makes v0.7 qualification-tooling generalization an I4.1 prerequisite.  
**Release / increment:** v0.7.0 / I4, Deterministic, Real-System and Product-Value Qualification.  
**Entry:** I3 is complete and closed by #546 (`e5f0379d04f7628f57501b878aab6509d1e78c8d`). The frozen [I3 completion record](i3-completion-record.md) and [I3 → I4 handoff](i3-i4-handoff.md) are the qualification inputs.  
**Authority:** [accepted v0.7.0 parent](specification.md), especially §§22–26; [I0 source-selection decision](i0-source-selection-decision.md); [I0 acquisition/replay plan](i0-acquisition-replay-plan.md), especially §§4–5; [I0 → I1/I2 handoff](i0-i1-i2-handoff.md), including the O11 remainder owned by I4; [I3 decision record](i3-decision-record.md) D1–D12; [I3 expected-answer matrix](i3-expected-answer-matrix.md); [I2 → I3 handoff](i2-i3-handoff.md). The v0.7 public schemas and the I3 oracle remain frozen.

## 1. Purpose and exit result

I4 qualifies the implemented v0.7 question:

> **Which configured consumers are related to this API exposure, which of them have independently observed usage in the selected environment/window, and what remains unresolved or unsupported?**

I4 adds **qualification evidence**, not new architecture semantics and not another public feature.

I4 is complete only when one exact candidate has:

1. passed the frozen independent semantic oracle and negative cases twice from clean state;
2. produced equivalent service, REST and negotiated MCP answers;
3. replayed the selected **APISIX** source end-to-end from pinned configuration and request-derived measurement evidence;
4. passed one independent **Tyk** semantic cross-check without pretending Tyk's native access concept is identical to APISIX consumer restriction;
5. completed a bounded product-value pilot with an explicit `CONTINUE | NARROW | DEFER | STOP` disposition;
6. preserved the existing v0.5/v0.6 dependency, locality, messaging and evidence behaviour.

The output is an I4 qualification record and an I4 → I5 handoff tied to the exact tested SHA. It is **not** publication or post-release verification.

## 2. Frozen inputs and non-negotiable semantics

I4 SHALL treat these as read-only qualification inputs:

- `schemas/architecture_intelligence/v0.7/api-consumer-usage-request.schema.json`;
- `schemas/architecture_intelligence/v0.7/api-consumer-usage-answer.schema.json`;
- `docs/specifications/0.7.0/i3-vectors/expected-answers.json`;
- `docs/specifications/0.7.0/i3-vectors/author_expected_answers.py`;
- `docs/specifications/0.7.0/i3-expected-answer-matrix.md`;
- the selected-source APISIX configuration/measurement fixtures and I2 reconciliation/qualification rules;
- `docs/specifications/0.7.0/i2-vectors/*` as the independent reconciliation/measurement/qualification truth used by I2, including the Route→Operation ambiguity cases;
- the I3 route/tool map and same-snapshot evidence rules.

The semantic invariants stay unchanged:

~~~text
configured access != observed usage
missing measurement != zero usage
unattributed request != consumer usage
gateway Route/Service != API Operation/Contract != application Service
consumer identity != credential secret
association != equivalence
configured access != Intent
Current State != authorization/compliance judgment
~~~

A disagreement with frozen expected truth is a defect or a reviewed specification issue. I4 SHALL NOT edit expected outputs to fit AIP execution.

## 3. Exact candidate and two clean runs

I4 SHALL select one full 40-hex `I4_CANDIDATE_SHA`.

I4 SHALL **generalize and extend the existing qualification machinery**, not silently reuse it as-is: `evaluation/i4` is currently v0.6-specific (worker test list, register/required cases/checks, pytest capture and v0.6 baseline pinning). I4.1 SHALL introduce a reviewed per-release/profile mechanism or equivalent generalization that preserves the reproducibility of the v0.6 I4 record while adding the v0.7 API-usage profile. `verify_candidate`, `ci_blockers(...)`, `compare_runs` and `benchmarks/i4_metadata.py` remain the preferred building blocks. This qualification-tooling change SHALL land and be reviewed **before `I4_CANDIDATE_SHA` is selected**; qualification-tooling code is part of the candidate identity. The I3 benchmark `benchmarks/api_usage_cost.py` is a historical measurement tool only: an I4 cost artifact must run through an I4 wrapper or amendment that also verifies the exact candidate and check-run identity required below.

Every I4 harness, replay, benchmark and result artifact SHALL record and verify:

- candidate SHA and checkout HEAD;
- producer/build revision;
- relevant schema/oracle/source/configuration digests;
- runtime and Neo4j versions;
- command or test entry point;
- CI/check-run identity for that exact SHA.

The full deterministic qualification SHALL run twice, **A and B**, with:

- separate processes;
- fresh disposable Neo4j state;
- independently recreated fixture/source state;
- the same frozen inputs and request contexts.

For equivalent cases, A and B semantic answers SHALL be byte-identical after canonical JSON serialization. This is deliberately stricter than parent §26's minimum "semantically identical" requirement and follows AIP's existing exact-candidate qualification discipline. No generated-id remapping, field removal, wildcard substitution or semantic normalization is permitted for A/B equality.

The I3 oracle matching rules apply only when comparing an answer to independently authored expected truth.

If any later I4 fix changes production code, schemas, fixtures, rules or qualification code, the affected mandatory gates SHALL rerun on the new candidate SHA.

## 4. Deterministic semantic qualification

The existing I3 oracle is the primary independent truth set. I4 SHALL rerun all 57 frozen cases unchanged:

- 32 answer cases;
- 3 property cases;
- 22 request-validation cases.

The oracle already covers configured+observed, measured zero, insufficient measurement, observed-only, unattributed traffic, unresolved/conflicting associations, gateway-vs-application identity, window/snapshot failures, same-snapshot evidence, paging and deterministic ordering.

It **does not** cover every parent §22 item. In particular, the frozen 57 cases contain no public-answer `AMBIGUOUS` Route→Operation result and no ambiguous-consumer-identity case. I4 SHALL close those gaps without editing the I3 oracle.

### 4.1 Parent §22 coverage register

I4.1 SHALL freeze a register with one row for **each of the twelve parent §22 requirements**, naming the independent expectation and executable evidence before I4.2 runs. At minimum:

| Parent §22 case | I4 authority / execution |
|---|---|
| 1 configured + observed | frozen I3 A01 + APISIX replay |
| 2 configured + no applicable measurement | frozen I3 A03/A11/A13 as applicable + APISIX insufficient case |
| 3 configured + measured zero | frozen I3 A02 + APISIX closed-coverage replay |
| 4 observed + no configured access | frozen I3 A04 + APISIX replay |
| 5 unattributed request | frozen I3 A10 + APISIX replay |
| 6 ambiguous consumer identity | **Dossier-only cross-source qualification** grounded in Tyk spike F6. The frozen APISIX/I2 pipeline has no `AMBIGUOUS` consumer outcome, so I4 SHALL NOT invent one. The Tyk dossier must decide whether duplicate-alias attribution is `REPRESENTABLE_WITH_SOURCE_SPECIFIC_DISTINCTION` or exposes a `MODEL_GAP`. If an APISIX-shaped executable sanity case is retained, it may only assert the already-qualified A10-style behavior: an unresolvable label yields no consumer row and route-wide unattributed/insufficient evidence; it is not new ambiguity evidence. |
| 7 ambiguous Route→Operation mapping | I2 independent reconciliation vectors **K06/K08** establish `AMBIGUOUS`; I4 SHALL author one additive public-projection bridge vector **as the exact frozen I2 handoff state**, before execution. Its stdlib-only author script uses new I4 ids and imports nothing from `app`; tests cross-check the raw facts through the existing `reconcile`/`qualify` rules before projecting. The expected answer must assert `api.reconciliation = AMBIGUOUS` with no `operation_id`, increment the `ambiguous` count in the `API_OPERATION` association summary, and show that an `API_OPERATION` target query does not select that Route. |
| 8 gateway object distinct from application Service | frozen I3 A06–A09 and A19 + identity invariants |
| 9 source revision removal/update | real APISIX revision transition (§4.2 / §5) |
| 10 same-snapshot evidence | frozen E01/E02 + APISIX replay |
| 11 deterministic ordering/replay | frozen paging/property cases + A/B runs |
| 12 v0.5/v0.6 regression | §4.3 legacy regression |

Only the Route→Operation case is an additive executable I4 bridge expectation. It SHALL be authored and reviewed **before** the candidate is executed against it and shall follow the exact-handoff-state discipline learned in I3.1c. The Tyk consumer-identity row is dossier-only because the frozen v0.7 pipeline cannot express an `AMBIGUOUS` consumer outcome. Neither changes the 57-case I3 oracle or public contract.

### 4.2 Source revision update/removal

Using the real APISIX import path, qualify at least one revision transition where configured access, Route inventory or measurement state changes.

The new snapshot SHALL reflect authoritative current state; stale cursors/evidence shall not silently bind to the new state.

### 4.3 Legacy regression

Run the relevant deterministic v0.5/v0.6 suites for:

- service dependencies;
- architecture drift;
- locality query/evidence;
- generic evidence;
- messaging/Broker/AsyncAPI;
- source lifecycle/replay;
- existing demo/golden snapshot invariants that are not release-slice-owned.

A v0.7 capability may add the fifth tool but SHALL NOT change the meaning of the four earlier tools.

### 4.4 Security and boundary regression

Verify:

- no gateway credential material is emitted;
- APISIX usernames remain source-qualified identities, not persons/applications;
- public surfaces remain read-only;
- forged/cross-context evidence refs remain `NOT_RESOLVED`;
- no API ownership, authorization, subscription/product or Intent judgment is introduced.

## 5. Selected-source real-system qualification — APISIX

APISIX is the selected v0.7 production source and SHALL be qualified end-to-end from **captured configuration plus request-derived measurements**, not only synthetic canonical state.

The governing replay definition is the I0 [acquisition/replay plan](i0-acquisition-replay-plan.md) §§4–5 and the O11 remainder in the [I0 → I1/I2 handoff](i0-i1-i2-handoff.md): normalized capture/replay artifacts, pinned source/product identity and normalized-artifact equality are qualification inputs, not conventions invented by I4.

The selected source is pinned to **APISIX 3.19.0** and image `apache/apisix@sha256:9a7e45dc943fbf10ec916d1232bae4cda9302ae28a4696cfb83c2da01d261141` (I0 decision/spike). I4.1 SHALL freeze the exact replay package and distinguish:

- **real captures** obtained from the pinned APISIX instance with controlled configuration/traffic;
- **derived qualification variants** produced as deterministic, reviewable edits of a pinned real capture where the condition is impractical to recapture directly.

Derived variants MAY exercise invalid manifests/windows or narrowly controlled negative conditions, but they SHALL remain labelled derived and SHALL NOT substitute for the parent §23 requirement that the selected gateway's positive and negative/insufficient semantics are grounded in real source behavior.

Before I4.2 execution, I4.1 SHALL identify which cases are real captures and which are derived. At minimum the real capture set SHALL include:

1. configured access + observed upstream usage;
2. observed usage with no matching configured access;
3. unattributed upstream traffic;
4. at least one insufficient/unestablished measurement outcome;
5. **two real source revisions/captures** sufficient to exercise current-state update/removal;
6. query → same-snapshot evidence resolution from the imported capture.

Measured-zero requires explicit closed coverage. It SHALL be a real controlled capture if the pinned APISIX capture procedure can establish it; otherwise I4 SHALL record why the replay plan's coverage attestation supports a deterministic derived case and SHALL NOT represent metric absence alone as zero.

An invalid/unavailable window may be a deterministic derived replay variant, provided the base capture is real and the mutation is independently specified before execution.

The replay package SHALL be:

- independently inspectable;
- pinned to explicit APISIX/source format versions and image digests;
- free of real secrets;
- reproducible without uncontrolled SaaS state;
- imported through the production source/import path;
- sufficient to produce positive and negative/insufficient outcomes.

The selected-source replay SHALL execute through service, REST and negotiated MCP and SHALL reproduce identically from a second clean state.

A failure to replay the selected source deterministically is an I4 blocker **and triggers the parent §23 consequence: source selection must be reconsidered under I0 rather than replacing missing real analytics with synthetic semantics**.

## 6. Cross-source semantic check — Tyk

I4 SHALL perform one independent semantic cross-check against **Tyk**, the retained differently shaped gateway source from the I0 survey.

This is **not** a second production adapter.

A documentation/capture-based mapping dossier is sufficient if it is based on the existing real Tyk 5.13.0 spike assets under `docs/specifications/0.7.0/i0-spike/tyk/*` and the I0 spike findings, especially **F6: Tyk alias is not unique**. It records:

- the native configured-access relationship;
- consumer/application/key identity distinctions;
- the F6 ambiguity explicitly: two distinct keys with the same `alias` merge into one request series, therefore alias alone cannot license one resolved canonical consumer identity;
- how request usage would be attributed;
- environment/window and coverage semantics;
- source-specific concepts that do not map cleanly to APISIX consumer restriction;
- how the frozen AIP vocabulary would represent or deliberately leave those distinctions source-specific.

The cross-check asks only:

> **Can the frozen AIP vocabulary represent the Tyk source without pretending its native access concept means the same thing as APISIX consumer restriction?**

Acceptable outcomes:

- **REPRESENTABLE** — common meaning is preserved without semantic collapse;
- **REPRESENTABLE_WITH_SOURCE_SPECIFIC_DISTINCTION** — the common model remains correct while a Tyk-native distinction stays explicit;
- **MODEL_GAP** — the source exposes a distinction the frozen vocabulary cannot preserve safely.

`REPRESENTABLE_WITH_SOURCE_SPECIFIC_DISTINCTION` is the parent §24 path for a native semantic that remains explicit and unnormalized. `MODEL_GAP` is reserved for a distinction the frozen vocabulary cannot preserve safely; it is a blocker for v0.7 unless the release scope explicitly excludes that distinction with reviewed justification. Neither outcome is solved by renaming unlike native concepts into one generic “subscription”.

## 7. Public-surface parity

For one graph/request/snapshot:

~~~text
service answer
==
REST response body
==
MCP structuredContent
~~~

Only transport wrappers/status differ.

I4 SHALL cover in both clean runs:

- query mode;
- evidence mode;
- paging/continuation;
- partial answer;
- semantic refusal;
- malformed REST request → 422;
- malformed MCP request → tool error;
- independent HTTP/MCP client discovery, call and reconnect.

The advertised MCP request/output schemas SHALL remain equivalent to the published v0.7 schemas.

## 8. Cost and operational evidence

I3 measured the current implementation; I4 SHALL rerun the relevant cost measurement on the exact I4 candidate through the I4 identity/check-run machinery described in §3. The I3 benchmark output by itself is not an I4 artifact.

The measurement is evidence, **not an SLO**.

Record at least:

- end-to-end first-page cost;
- canonical-state read/fingerprint cost;
- projection cost;
- evidence-mode cost;
- complete cursor-walk page/row counts;
- selected-source import/replay cost;
- unresolved/ambiguous rates in the real replay;
- manual mappings needed to obtain the answer.

Carry the I3 findings explicitly:

- whole canonical state read on each request;
- whole selection enriched before page slicing;
- evidence ref map rebuilt for the whole selection.

**F1 sequencing decision:** the owner SHALL decide in I4.1, before `I4_CANDIDATE_SHA` is selected, whether page-before-enrich lands before qualification or is deferred past I4. If it lands first, all qualification/cost gates run on that changed implementation. If it is deferred, I4.2 qualifies the I3-handoff implementation unchanged. I4.2 SHALL NOT start while this choice is open; once the candidate is pinned, F1 SHALL NOT land without selecting a new candidate and rerunning the affected gates.

I4 may recommend optimization but SHALL NOT hide qualification findings by changing semantics, dropping rows or weakening evidence rules.

## 9. Product-value pilot

The pilot SHALL use a **realistic coding-agent task**, not a dashboard exercise. The owner runs **one recorded coding-agent session** against the **pinned APISIX replay world used by I4.2**, using the public Architecture Intelligence surface. The record SHALL name the agent/client and model/version used; the agent is a consumer of AIP, never semantic authority. This is intentionally a bounded single-session pilot, so its `CONTINUE | NARROW | DEFER | STOP` disposition SHALL be reported as evidence from that one session, not generalized user research.

Preferred task:

> An agent is about to change an API Operation and asks which configured consumers are related to that exposure, which have independently observed usage in the selected completed window, and what remains unresolved.

The pilot SHALL record:

- useful answer coverage;
- setup effort;
- source synchronization effort;
- consumer-attribution effort;
- identity-mapping effort;
- unresolved/ambiguous rate;
- manual input required;
- time/cost to keep evidence current, measured over **at least two synchronization cycles**: the initial pinned capture/import and one controlled APISIX revision/measurement refresh;
- whether the answer materially improves the coding-agent decision.

The pilot SHALL explicitly separate:

1. **semantic correctness** — what the evidence establishes;
2. **product usefulness** — whether obtaining and maintaining that evidence is worthwhile.

It ends with exactly one owner-reviewed disposition:

~~~text
CONTINUE
NARROW
DEFER
STOP
~~~

A semantically correct result may still be `NARROW`, `DEFER` or `STOP` if synchronization or mapping cost is disproportionate.

## 10. Qualification ledger and findings

Each mandatory qualification row SHALL have:

- test/case id;
- expected result source;
- actual result;
- candidate SHA;
- run A/B identity;
- source/fixture digest where applicable;
- surface(s) exercised;
- status;
- finding/disposition if not passing.

Use an I4-only result vocabulary; it does not become public API vocabulary:

~~~text
I4_CORRECT
I4_EXPECTED_NEGATIVE
I4_SEMANTIC_DEFECT
I4_REPLAY_DEFECT
I4_SURFACE_MISMATCH
I4_MODEL_GAP
I4_PRODUCT_VALUE_FAIL
I4_NOT_RUN
~~~

A mandatory `I4_NOT_RUN`, unexplained mismatch, or changed expectation after execution blocks I4 completion.

Expected negative/insufficient outcomes pass only when they match the independently frozen expected limitation; “everything unresolved” is not a successful qualification strategy. The coverage register SHALL separately count positive/resolved cases and expected-negative/abstaining cases for each relevant scenario class, so a class cannot pass solely because every execution abstained.

## 11. Required artifacts

I4 SHALL produce:

1. **qualification coverage/register** mapping parent §§22–25 requirements to exact executable evidence;
2. **APISIX replay package/report** with pinned configuration, measurements, versions and results;
3. **Tyk semantic cross-check dossier**;
4. **two-clean-run qualification ledger** tied to one candidate SHA;
5. **product-value pilot record** with the explicit disposition;
6. **I4 completion record**;
7. **I4 → I5 handoff** naming the qualified candidate and all remaining release work.

The handoff SHALL state clearly that I5 owns release candidate freeze, release-content re-freeze, publication and post-publication verification.

## 12. Execution slices

Keep I4 bounded:

| Slice | Work | Exit evidence |
|---|---|---|
| **I4.1 — Freeze qualification plan** | Twelve-row parent §22 coverage register; one executable Route→Operation bridge expectation; dossier-only Tyk consumer-ambiguity qualification; reviewed per-release generalization of `evaluation/i4`; F1 before/defer owner decision; exact candidate rules; APISIX real-vs-derived replay package/case set; pilot method | Reviewed register with no parent §22–25 gap; qualification tooling, replay assets and expectations frozen before candidate selection/execution; v0.6 I4 remains reproducible |
| **I4.2 — Deterministic + APISIX qualification** | Two clean runs, full frozen oracle, surface parity, legacy/security regression, selected-source replay, cost rerun | Zero unexplained semantic/surface/replay mismatch on one exact SHA |
| **I4.3 — Cross-source + product value + handoff** | Tyk semantic check, coding-agent pilot, disposition, completion record and I5 handoff | Cross-source result + explicit product disposition + reviewed handoff |

Do not split further unless execution exposes a material independent review boundary.

## 13. Stop conditions

Stop I4 and report before continuing if:

- frozen expected truth and implementation disagree on semantics;
- APISIX cannot reproduce required real-source evidence deterministically;
- a public answer leaks a credential or changes legacy tool meaning;
- Tyk exposes a source distinction that the frozen vocabulary would have to collapse incorrectly;
- run A/B or service/REST/MCP differ semantically;
- a required case cannot be executed on the exact candidate;
- the product pilot cannot distinguish architecture evidence from unsupported dependency/ownership inference.

A fix requires a reviewed change and a rerun at a new candidate SHA. Do not repair the result ledger or oracle after seeing AIP output.

## 14. Definition of Done

I4 is complete only when:

- all 57 frozen I3 cases pass unchanged on the exact candidate;
- all twelve parent §22 cases are explicitly mapped in the coverage register, with consumer ambiguity qualified by the Tyk dossier and Route→Operation ambiguity by the executable exact-handoff-state bridge case;
- two fresh runs are semantically identical;
- APISIX real-source replay passes positive, negative/insufficient, revision and evidence cases;
- service, REST and MCP are equivalent;
- Tyk cross-source semantics are represented without semantic collapse;
- v0.5/v0.6 dependency/locality/messaging/evidence regressions pass;
- security/read-only/credential boundaries remain intact;
- measured cost and known limitations are recorded;
- the product-value pilot ends in `CONTINUE`, `NARROW`, `DEFER` or `STOP`;
- every mandatory result is bound to one exact SHA with no unexplained skip;
- the completion record and I4 → I5 handoff are reviewed.

A green CI run alone is not I4 completion.
