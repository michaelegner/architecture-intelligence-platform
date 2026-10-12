# AIP v0.7.0 I0 — Gateway Capability Survey and Semantic Freeze

**Status:** Draft 0.1 — for review before I1 implementation  
**Release / increment:** v0.7.0 / I0, API-Aware Current State  
**Repository path:** docs/specifications/0.7.0/i0-gateway-capability-survey-and-semantic-freeze.md  
**Entry baseline inspected:** main at 2ad3a6feeae2b93d581d49224d8bb5d441e1c88d  
**Governing authority:** [accepted v0.7.0 parent specification](specification.md), especially §§1–11, 23–25, 29, 31 and 34–36; [research landscape](../../landscape.md), especially “API Gateways — Configured Access and Observed Usage”.  
**Normative words:** MUST/SHALL/SHALL NOT have their parent-spec meaning. Text explicitly marked **[I0 proposal — review before freeze]** is not yet a frozen decision.

---

## 1. Purpose and exit outcome

I0 answers one preparatory question before AIP implements gateway evidence:

> **Which gateway source gives AIP the smallest real, replayable evidence surface needed to qualify configured consumer/API access against independently observed consumer-attributed usage without collapsing source-native semantics?**

I0 SHALL:

1. survey Kong, Gravitee, Apache APISIX and Tyk against one comparable capability matrix;
2. preserve each source's native configured-access meaning rather than normalize all four into a generic subscription;
3. freeze the minimum source-neutral semantic distinctions required by the v0.7 question;
4. select exactly one gateway for I1–I4 implementation and real-system qualification;
5. record the selected source's configuration and measurement acquisition/replay plan;
6. retain at least one differently shaped gateway as a later semantic cross-check.

I0 does **not** implement a gateway adapter, canonical schema extension, REST/MCP tool, runtime measurement ingestion path or public answer.

The minimum I0 exit result is a reviewed decision that makes I1 implementable without silently assuming source semantics, identity mappings or commercial-only capabilities.

## 2. Scope and non-goals

### 2.1 In scope

I0 covers only the evidence needed for the first bounded v0.7 question:

> **Which configured consumer/API relationships have matching observed runtime usage in a selected environment and observation window, and which remain unestablished from the available evidence?**

For each candidate gateway, I0 SHALL establish:

- the native objects and relationships that represent API exposure;
- the native objects and relationships that represent consumer/application identity;
- the exact native configured-access relationship, if any;
- how request-derived usage can be attributed to that consumer identity;
- what environment/window and measurement-coverage semantics are available;
- what configuration and measurement data can be captured and replayed deterministically;
- which required capabilities are OSS/self-hosted versus proprietary/paid;
- what identity reconciliation is explicit, user-authored, ambiguous or unsupported;
- what source-native distinctions would be lost by a naïve common model;
- the practical setup, synchronization and replay burden relevant to the v0.7 product-value gate.

### 2.2 Explicitly out of scope

I0 SHALL NOT:

- implement four adapters;
- add gateway-specific canonical types merely because one product exposes them;
- define the final public REST path or MCP tool;
- define architectural Intent, policy correctness, authorization correctness, ownership or compliance;
- infer business capability/domain boundaries from gateway configuration;
- treat ACL membership, key policy, consumer restriction, plan or subscription as interchangeable;
- treat a route/service as an application Service or API contract/operation without explicit reconciliation;
- treat absence of metrics as zero usage;
- select a source because it resembles the desired AIP model;
- require proprietary functionality while presenting the selected qualification path as OSS/self-hosted;
- broaden v0.7 into API management, cataloging or analytics.

## 3. Frozen semantic invariants

The following parent-spec distinctions are fixed and SHALL NOT be reopened by source selection. I0 **adopts parent §§9–11 as the baseline semantic vocabulary, identity-domain separation and integration-style boundary**. Any deviation requires a reviewed amendment to this I0 specification and, where it would change the parent contract, to the parent specification.


~~~text
gateway route/service != application Service != API contract/operation
configured access != observed consumer-attributed usage
ACL/entitlement != formal product subscription
consumer identity != credential secret
unattributed request != request by a particular consumer
association != entity equivalence
API endpoint != application/domain/business capability/owner/authorization boundary
gateway presence != system-wide integration style
missing measurement != zero usage
observed usage != approved or intended usage
configured access != architectural Intent
~~~

A source may carry richer semantics. I0 SHALL preserve them as source-native evidence or explicitly defer them; it SHALL NOT weaken the distinctions above to create a visually uniform model.

## 4. Required survey evidence

I0 SHALL use current first-party product documentation and, where practical, direct inspection of a pinned OSS/self-hosted version or immutable fixture.

For every material capability claim, the survey record SHALL identify:

- product and exact version or documentation version/date where available;
- source URL or inspected artifact;
- OSS/self-hosted versus proprietary/paid availability;
- exact native object/field/plugin/policy involved;
- whether the claim is documented, directly inspected or still unresolved;
- whether it is sufficient for AIP's bounded question.

Marketing pages, dashboards and architecture diagrams are not enough by themselves to establish a source contract.

AIP's research landscape is an input and index. It is not the qualification evidence for source selection.

## 5. Comparable capability matrix

I0 SHALL produce one matrix with one row per gateway and, at minimum, these columns:

| Area | Required question |
|---|---|
| API exposure | What native route/service/API object establishes exposed API scope? |
| Consumer identity | What stable logical consumer/application identity exists? |
| Credential separation | Can credentials/keys remain distinct from consumer identity? |
| Configured access | What exact source-native relationship establishes configured access? |
| Target scope | Can configured access be bounded to API/version/route/service/operation? |
| Runtime attribution | Can request-derived usage be deterministically attributed to the same consumer identity? |
| Runtime target | Can the same request measurement identify the relevant route/service/API target? |
| Environment | How is deployment/environment identity established? |
| Observation window | What timestamps/aggregation window are available? |
| Coverage | Can measured zero be distinguished from missing/unknown measurement? |
| Replayability | Can configuration and measurements be captured and replayed deterministically? |
| Revision identity | What immutable or reproducible source revision/capture identity is available? |
| Removal/authority | Can AIP establish the source's authoritative inventory/removal scope? |
| Secrets | Can required evidence be captured without retaining credential secrets? |
| OSS boundary | Which required capabilities are available in the chosen OSS/self-hosted path? |
| Mapping burden | Which joins are explicit, user-authored, ambiguous or unsupported? |
| Operational cost | Setup, synchronization, collection and replay burden for the first slice |
| Native distinctions | Which semantics would be lost by a generic subscription/access abstraction? |

The matrix SHALL distinguish **unsupported**, **not established by available evidence**, and **not investigated**. These are not equivalent.

## 6. Source-native configured-access semantics

For each gateway, I0 SHALL write the configured-access proposition in source-native terms before proposing any AIP mapping.

Illustrative research hypotheses from the parent/landscape are:

~~~text
Kong       -> Consumer + gateway configuration, optionally ACL membership
Gravitee   -> Application + Plan + Subscription + API
APISIX     -> Consumer + consumer-restriction or equivalent route/service rule
Tyk        -> Key/consumer identity + access policy/API/version scope
~~~

These are **starting hypotheses, not frozen mappings**. I0 SHALL verify the actual source semantics and exact product/version surface.

The survey SHALL answer:

1. what configuration fact exists;
2. what subject identity it names;
3. what API/gateway scope it applies to;
4. whether the relation means registered, allowed, subscribed, grouped, restricted or something else;
5. what source revision establishes it;
6. what AIP proposition can be safely preserved without strengthening the source meaning.

If two products expose different meanings, I0 SHALL retain those differences even if their graph shapes look alike.

## 7. Consumer identity and credential boundary

I0 SHALL distinguish at least:

~~~text
logical consumer/application identity
credential/key/token identity
runtime attribution identity
~~~

The selected source must permit a stable, non-secret identity that can be represented and replayed without storing credential material.

I0 SHALL document:

- stable consumer/application identifier;
- display/name fields that are non-authoritative;
- credential identifiers needed only for attribution, if any;
- secret material that must never enter AIP evidence/provenance;
- how runtime measurement identity maps back to the configured consumer;
- ambiguous, many-to-one or many-credential cases.

A credential value itself SHALL NOT become the canonical consumer identity.

## 8. Request-derived measurement and coverage survey

The selected gateway must support a credible path to **request-derived** consumer-attributed usage.

For every candidate, I0 SHALL determine whether the available source can establish:

- consumer attribution;
- route/service/API target attribution;
- request timestamp or bounded aggregation window;
- environment/deployment identity, distinguishing whether it is source-reported or operator-supplied capture context;
- request count or equivalent observed-use signal;
- measurement provenance and version;
- sampling/retention/aggregation behavior;
- whether zero is a measured zero or merely absence of data.

A dashboard total, log line or metric without deterministic consumer attribution is insufficient for the first positive v0.7 question.

The observed-usage evidence SHALL be **independent of the configured-access fact**: it must come from an actual request-derived measurement path and SHALL NOT be satisfied by a gateway merely restating that a consumer was configured, matched an ACL/policy, or was permitted by configuration. The measurement may be emitted by the same gateway product, but the proposition it establishes must be based on an observed request event or request aggregation rather than the configuration relationship itself.

A missing measurement path does not make a source invalid for all future AIP use; it makes it insufficient for this first bounded validation unless another independent, replayable request-derived source supplies the attribution.

For environment identity, the survey SHALL record one of:

~~~text
SOURCE_REPORTED
OPERATOR_ASSERTED_CAPTURE_CONTEXT
UNRESOLVED
~~~

A source-reported environment must identify the actual deployment/context from the measurement source. An operator-asserted capture context is acceptable only when it is explicit, provenance-bearing, immutable for the replay fixture and not inferred from an arbitrary free-form label at query time. I0 SHALL record which mode the selected path uses and what evidence binds the measurement to that environment.

## 9. Identity and association burden

I0 SHALL inventory, but not yet implement, the required joins:

~~~text
Gateway Consumer
    ↔ runtime attribution identity

Gateway Route/Service
    ↔ API Contract/Version/Operation

Gateway upstream/target
    ↔ application Service
~~~

**[I0 proposal — review before freeze]** Each join SHALL be classified as one of:

~~~text
EXPLICIT_SOURCE_REFERENCE
DETERMINISTIC_NORMALIZATION
USER_AUTHORED_MAPPING_REQUIRED
AMBIGUOUS
UNRESOLVED
UNSUPPORTED
~~~

These labels are survey vocabulary only and do not pre-freeze I2 public qualification vocabulary.

Name similarity, URL similarity, path similarity or graph proximity alone SHALL NOT count as a resolved association when more than one plausible target exists.

The selected source SHOULD minimize required manual mapping, but mapping convenience SHALL NOT override semantic fidelity.

## 10. Replayability and source lifecycle

The selected gateway SHALL have a concrete plan for deterministic configuration and measurement capture/replay before I0 exits.

The plan SHALL identify:

- pinned product version;
- exact configuration acquisition surface;
- exact request-measurement acquisition surface;
- fixture/capture format;
- secret-redaction boundary;
- stable source identity;
- revision/capture identity;
- authoritative inventory/removal scope;
- expected ordering/canonicalization requirements;
- how a clean replay can reproduce positive and negative/insufficient cases;
- how the capture remains independently inspectable without uncontrolled SaaS state.

I1 owns implementation of the selected gateway configuration source. I2 owns runtime measurement acquisition/replay and configured-vs-observed qualification. I0 only freezes enough of the acquisition contract to prove those increments are feasible.

## 11. OSS/self-hosted and operational feasibility gate

I0 SHALL NOT choose a source solely from semantic richness.

For each candidate it SHALL record whether the minimum first-slice path can be reproduced with:

- an OSS/self-hosted distribution;
- a locally runnable or otherwise controlled fixture;
- no mandatory commercial analytics subscription;
- no real external customer credentials;
- bounded setup effort;
- bounded recurring synchronization/measurement effort.

Commercial-only capabilities MAY be recorded as richer source possibilities, but SHALL NOT be silently used to justify selection if the intended qualification path does not have access to them.

## 12. Selection rule

Exactly one source SHALL be selected for I1–I4.

### 12.1 Mandatory semantic/evidence gates

A candidate is ineligible if the first bounded question cannot be demonstrated with:

1. a real source-native configured consumer/API relationship;
2. stable non-secret consumer identity;
3. request-derived consumer-attributed usage;
4. bounded environment/window semantics;
5. explicit measurement-coverage limitations;
6. deterministic configuration and measurement capture/replay.

### 12.2 Feasibility and cost comparison

Among candidates passing the mandatory gates, I0 SHALL compare:

- semantic fidelity to the source-native configured-access meaning;
- quality and determinism of consumer-attributed request evidence;
- replayability and source-revision clarity;
- OSS/self-hosted availability of the minimum path;
- mapping burden;
- setup cost;
- synchronization/collection cost;
- suitability for independent positive and negative cases.

The decision SHALL NOT rely on an implicit preference. The source-selection record MUST contain a per-criterion comparison for every eligible candidate and name the **deciding criterion or criteria**. If two candidates are effectively tied on semantic/evidence quality, prefer the one with the simpler deterministic replay path; if still tied, prefer lower mapping/operational burden. Popularity, prior roadmap preference or implementation familiarity may not break a tie.

### 12.3 Selection output

The decision record SHALL state:

~~~text
selected gateway
selected product/version
why it passes each mandatory gate
why each non-selected gateway was not selected for this first slice
known selected-source limitations
required manual mappings
planned configuration capture
planned request-measurement capture
cross-check gateway retained for I4, chosen because its native configured-access relationship class is materially different from the selected gateway's (for example subscription/application vs ACL/restriction vs key/policy), not merely because it ranked second
~~~

A non-selected gateway is not declared unsupported by AIP generally; it is merely not chosen for the first qualified implementation.

## 13. Semantic freeze for I1/I2

I0 SHALL freeze enough source-neutral meaning that I1 and I2 do not invent semantics in code.

At minimum the reviewed I0 output SHALL freeze:

1. the exact source-neutral names and meanings required for API Contract, API Contract Version, API Operation, Gateway Service, Gateway Route, Application Service, Gateway Consumer / Consumer Application, Configured Access Relationship and Observed Consumer Interaction;
2. which of those are canonical entities/relations versus source-only evidence distinctions;
3. which source-native configured-access concept the selected gateway actually establishes;
4. the selected gateway's stable consumer identity and safe identifier policy;
5. the selected runtime attribution identity and its mapping to the configured consumer;
6. the selected gateway route/service/API target identities needed for reconciliation;
7. the source-specific distinctions that SHALL remain explicit rather than normalized.

I0 SHALL NOT freeze the final public REST/MCP response schema, qualification truth table or public tool name; those remain I2/I3 responsibilities.

## 14. Parent decision handoff

I0 SHALL resolve the parent specification's open decisions only to the depth required for the next increment.

| Parent decision | I0 obligation |
|---|---|
| O1 Selected initial gateway | **Freeze in I0** |
| O2 Exact source-neutral entity/relation vocabulary | **Freeze in I0 for the canonical/source-evidence model used by I1/I2; I3 only owns public wire naming/schema** |
| O3 Source-specific configured-access mapping | **Freeze in I0 for selected gateway** |
| O4 Consumer identity and safe stable identifier policy | **Freeze selected-source identity boundary in I0; I2 may refine runtime reconciliation details** |
| O5 Runtime measurement source, attribution semantics and coverage model | **Freeze selected measurement source/capability and required semantics; I2 freezes implementation/truth-table details** |
| O6 Route/service ↔ API contract/operation association rules | **Freeze in I0 at the semantic/rule level; I2 implements and qualifies them** |
| O7 Gateway target ↔ application Service association rules | **Freeze in I0 at the semantic/rule level; I2 implements and qualifies them** |
| O8 Qualification vocabulary/truth table | Deferred to I2 |
| O9 Enumeration/truncation | Deferred to I3 |
| O10 REST/MCP contract | Deferred to I3 |
| O11 Real-source replay packaging / cross-check source | Select replay strategy and cross-check source in I0; I4 freezes final qualification packaging |

The parent §35 heading says “Decisions I0 must freeze”, but its own **Required before** column places O8–O10 in later increments and O11 at I4. This I0 specification intentionally narrows that heading under the parent §5 rule that increment specifications may freeze deferred details at the increment that actually needs them. I0 freezes only the parts of O5–O7/O11 needed to make I1/I2 feasible and leaves O8–O10 to their designated increments.

If a parent decision cannot safely be narrowed to the depth above, I0 SHALL record it as unresolved and block the dependent increment rather than guess.

## 15. Required I0 artifacts

I0 SHALL produce, at minimum:

1. **Capability survey matrix** for Kong, Gravitee, APISIX and Tyk, with evidence references and version bounds.
2. **Semantic decision record** freezing the minimum source-neutral distinctions and source-native configured-access meaning.
3. **Source-selection decision** naming one selected gateway and one semantic cross-check gateway.
4. **Selected-source acquisition/replay plan** covering configuration and consumer-attributed request measurements.
5. **Identity/reconciliation dossier** listing explicit, user-authored, ambiguous and unsupported joins.
6. **I0 → I1/I2 handoff** listing exactly what is frozen, what is deferred and what would require a reviewed amendment.

These artifacts SHALL live under `docs/specifications/0.7.0/` either as separate I0 files or as one reviewed I0 completion package plus referenced evidence files. The specification itself is not evidence that the survey was performed.

Survey evidence SHALL be reproducible enough for later review. For web documentation, record the URL and retrieval date and, where licensing/size permits, pin an archived excerpt, checksum, release tag or product-version-specific documentation reference. For directly inspected products, record the exact product version and fixture/configuration revision. If a vendor page is mutable and cannot be archived, record the retrieval date and the exact claim being relied on so drift is visible rather than silently accepted.

## 16. Stop conditions

I0 SHALL stop and require a reviewed amendment if:

- none of the four sources can support consumer-attributed request evidence for the bounded question;
- the only viable path depends on unavailable proprietary functionality;
- configured access cannot be expressed without falsely equating materially different native semantics;
- selected-source identity requires retaining credential secrets;
- the source cannot be captured/replayed deterministically enough for I4 qualification;
- a required route/service/API association is inherently ambiguous and no bounded mapping mechanism is acceptable;
- selection would require adding a broad API-product/catalog model not justified by the first question;
- source choice would force a change to the parent release question or Current-State/Intent boundary.

Outcome mapping for these conditions:

- violation of the parent semantic/evidence boundary, unavoidable credential-secret retention, or inability to express configured access without false equivalence → `STOP`;
- viable question but only unavailable/proprietary evidence path or currently impractical deterministic replay → `DEFER`;
- ambiguity or model breadth that can plausibly be resolved by narrowing the source/question/mapping contract → `NARROW_AND_REVIEW`.

A stop condition is preferable to silently weakening the evidence claim.

## 17. Draft research hypotheses to challenge

The repository landscape and parent specification currently suggest, but do not freeze, the following:

- **APISIX** may provide a relatively direct Consumer/restriction plus request-metric path with good local replay potential.
- **Tyk** may provide a strong but semantically different key/policy/API/version path useful for testing whether the model stays source-neutral.
- **Kong** remains a mature reference/fallback with Consumer and ACL-style semantics and established observability options.
- **Gravitee** exposes richer application/plan/subscription semantics and may be especially useful as a semantic stress test.

I0 reviewers SHALL treat these as hypotheses to test against current first-party evidence, not as ranking or selection authority.

## 18. I0 exit criteria

I0 is complete only when all of the following are reviewed and recorded:

- all four gateways have comparable evidence-backed capability rows;
- source-native configured-access semantics are explicit for all four;
- the minimum source-neutral vocabulary can represent all four without relabelling their native relationship as a generic subscription;
- one gateway is selected by the §12 gates;
- one differently shaped gateway is retained for I4 semantic cross-check, where “differently shaped” means a materially different native configured-access relationship class from the selected gateway;
- selected consumer identity and secret boundary are frozen;
- selected configuration acquisition/replay path is concrete;
- selected request-derived measurement acquisition/replay path is concrete;
- environment/window and coverage limitations are explicit;
- required identity mappings are classified;
- proprietary-only dependencies are explicit;
- I1 and I2 can start without inventing semantic decisions in implementation;
- no adapter/schema/public API implementation has been smuggled into I0.

**[I0 proposal — review before freeze]** The terminal I0 outcome is one of:

~~~text
READY_FOR_I1
NARROW_AND_REVIEW
DEFER
STOP
~~~

The meanings are:

- `READY_FOR_I1`: one source passes all mandatory gates, required semantics are frozen, and the I1/I2 handoff is implementable without unresolved semantic assumptions;
- `NARROW_AND_REVIEW`: the bounded question appears viable, but the scope, source choice or semantic model must be narrowed through a reviewed amendment before implementation;
- `DEFER`: the question remains valid, but required evidence/replay capability is not presently available or practical; no implementation starts in v0.7 until the dependency changes;
- `STOP`: the proposed bounded question cannot be supported without violating the parent semantic/evidence boundaries or introducing unacceptable secret/proprietary/ambiguity dependencies.

The **I0 specification owner / release owner** records the terminal outcome in an I0 completion record under `docs/specifications/0.7.0/`, linked from the source-selection/decision artifact and the implementing PR. A ROADMAP change is required only if the outcome changes the release direction (`DEFER`/`STOP` or a material scope change), not for ordinary `READY_FOR_I1` completion.

Only `READY_FOR_I1` authorizes I1 implementation.

## 19. Summary

I0 is a semantic and source-selection increment, not an adapter implementation.

Its job is to ensure that AIP chooses the first gateway because the source can actually support the bounded architecture question with real, replayable evidence—not because its terminology happens to resemble a convenient canonical model.

The required discipline is:

~~~text
survey native evidence
        ↓
preserve semantic differences
        ↓
prove consumer-attributed measurement feasibility
        ↓
compare replay/mapping/cost burden
        ↓
select one source
        ↓
freeze only the semantics I1/I2 genuinely need
~~~

If I0 succeeds, I1 starts with a bounded source contract and no hidden semantic assumptions.
