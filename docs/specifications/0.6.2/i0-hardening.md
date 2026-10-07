# AIP v0.6.2 I0 — Receiver-route safety and window-correct resolution evidence

**Status:** Draft 0.1 (2026-10-07)  
**Governs:** the I0 product-hardening prerequisite of [`specification.md`](specification.md) §3.3  
**Baseline:** v0.6.1 (`main`)  
**Evidence for the defects:** [`i1-spike-finding.md`](i1-spike-finding.md), `tests/integration/test_v062_i1_gate_spike.py` (#460)

This increment fixes the two evidence-correctness defects H1 and H2 found by the I1 gate spike. It is the
only product change in v0.6.2. It adds no entity kind, relation, claim type, schema, source family, MCP
tool, limitation code or unresolved-observation reason.

## 1. Scope and non-goals

In scope: **H1a** an ingestion guard for Pub/Sub consumer spans (§3), and **H2** observation-window
correctness of resolution evidence (§4).

Out of scope (decided, not deferred by default): snapshot-id stability; per-Subscription qualification;
the behaviour of a `service.name` that does not match a declared Service; Broker-claim and deployment
window semantics; cleanup of observed-only routes already persisted by v0.6.1 (§3.3).

## 2. Defects

**H1.** A consumer span for Service A that names a Subscription B declared by another Service is accepted
today: the guard matches the Subscription by Topic and name only, never by the calling Service. The
accepted span is persisted as an observed `RECEIVES_FROM` A → B that no declaration supports, and the
publisher's dependency answer gains a separate, separately identified claim for A via B with no
limitation.

**H2.** `resolution_evidence_refs` (and whether a destination counts as evidenced at all) are computed
from every Evidence row that resolves, regardless of environment and observation window. Observed
receiver (or provider) evidence from a later window therefore changes the claim of a completed window.
`evidence_refs` are already window-correct.

## 3. H1a — the declared-route ingestion guard

### 3.1 Rule

A consumer observation (`messaging.operation.type` of `receive` or `process`) for a Pub/Sub destination
SHALL be accepted as `Service -[RECEIVES_FROM]-> Subscription` evidence only when, in addition to every
condition of the v0.5.0 I4 specification §9 (declared Topic resolved exactly, Subscription resolved
exactly within it, `SUBSCRIPTION_OF` linking them, Service identity guard accepting):

> the identified Service has, at ingestion time, a **declared** `RECEIVES_FROM` relation to the matched
> Subscription.

"Declared" means the relation carries at least one Evidence node whose `evidence_type` is `DECLARED` (the
predicate of `matches_declared_evidence`). The Service identity is the one the identity guard accepted,
so a Service minted as `OBSERVED_ONLY` by runtime evidence has no declared route and is refused.

### 3.2 Refusal

A span failing the rule SHALL be refused exactly like any other consumer span that does not match: an
in-memory unresolved observation with the existing reason `UNRESOLVED_DESTINATION_SEMANTICS`, creating
no Evidence node, no relation, no entity, no snapshot change and no public evidence or limitation (I4
§12.5). No new reason, code or schema is introduced. The guard SHALL NOT alter the Topic, Subscription
or Service decisions made before it.

### 3.3 Declaration lifecycle is unchanged (explicit decision)

The guard applies to **new observations at ingestion**. It SHALL NOT change how an already persisted
relation is read:

- A route that was declared and observed, whose declaration is later removed, keeps its retained
  observed evidence and continues to resolve exactly as in v0.6.1 (the existing declared →
  `OBSERVED_ONLY` degradation). H1 changes nothing there; H2's window filter applies to its observed
  evidence like any other.
- The projection (`_resolve_pubsub_destinations`) is not changed by H1. A graph cannot distinguish
  "observed pair that never had a declaration" from "declared pair whose declaration was later removed"
  (both are a relation carrying only observed evidence), so a projection rule would also erase the
  lifecycle above. This is a deliberate non-change.
- **Residual, disclosed:** an observed-only `RECEIVES_FROM` → Subscription route for a never-declared
  pair already written by v0.6.1 keeps resolving. It cannot be created again once the guard is in place.
  Cleaning existing data is out of scope; the hosted demo starts from an empty graph.

The three cases are tested separately (§6): declaration + matching observation → resolved; declaration
later removed with the observation retained → v0.6.1 behaviour, pinned; an observation for a pair that
never had a declaration → refused (the actual H1 defect).

## 4. H2 — window-correct resolution evidence

### 4.1 Rule

For a dependency request with an observation context (environment, window start, window end), every
Evidence id considered for **resolution** SHALL be filtered as follows before it is cited or used to
decide whether a destination is evidenced:

- a `DECLARED` Evidence row is kept (declared evidence is not environment- or window-scoped, as for
  qualification);
- an `OBSERVED` Evidence row is kept only if it passes the same predicate as qualification
  (`matches_observed_evidence`: exact environment, non-null `last_seen`, inclusive window);
- every other row is dropped.

This applies in one place, the accepted-evidence filter shared by all resolution paths: HTTP `PROVIDES`,
Queue `RECEIVES_FROM` and Pub/Sub `SUBSCRIPTION_OF` / `RECEIVES_FROM`. The context is threaded into the
resolution helpers; no second filter is introduced.

### 4.2 Consequences (intended)

- Observed evidence outside the requested environment or window is neither cited in
  `resolution_evidence_refs` nor counts toward a destination being evidenced.
- A destination whose only supporting evidence is dropped falls back as today when evidence is
  unavailable (`DIRECT_TARGET_FALLBACK`, with the `UNRESOLVED_IDENTITY` limitation). A `RESOLVED_SERVICE`
  claim SHALL retain at least one **accepted, in-context resolution evidence ref** (declared, or observed
  and passing the §4.1 predicate); if every supporting ref is filtered out it falls back. This is
  path-neutral: an HTTP `PROVIDES` or Queue `RECEIVES_FROM` destination may legitimately resolve from
  in-window observed evidence alone and keeps resolving; the Pitstop Pub/Sub route additionally always
  retains its declared evidence.
- `claim_id` is unchanged for an unchanged destination (it excludes evidence ids). The answer-level
  `evidence_refs` (the union of claim refs) changes accordingly. Drift answers inherit the change.
- "Completed window" is meaningful: an explicit, caller-chosen window wholly in the past whose complete
  claim set does not change when later evidence is ingested. The snapshot id still changes with any
  ingested evidence and a stale snapshot is still refused (not changed here).

## 5. Unchanged surfaces

Public answer shapes, JSON Schemas, the four MCP tools, claim identity, qualification rules, Broker and
deployment projections, the unresolved-reason strings, the snapshot fingerprint, and any frozen golden,
evaluation reference or release artifact. If implementing this specification would change a frozen
artifact, implementation stops and the question returns to the owner.

## 6. Acceptance criteria

1. Unit: a consumer span for another Service's Subscription, and one from an observed-only Service, are
   refused with `UNRESOLVED_DESTINATION_SEMANTICS` and produce no fact; a consumer with a declared route
   is accepted as before.
2. Unit: out-of-window and other-environment observed ids are dropped from resolution refs and do not
   make a destination evidenced; declared ids and in-window observed ids are kept; HTTP, Queue and
   Pub/Sub variants; drift copies the result.
3. Integration (real Neo4j), as separate tests: declaration + matching observation → route resolved with
   observed evidence; declaration later removed with the observation retained → v0.6.1 behaviour pinned
   (if observation contradicts §3.3, implementation stops and returns to the owner); an observation for
   a never-declared pair → refused at ingestion, nothing persisted, snapshot unchanged.
4. Integration: the spike's cross-queue and later-window characterizations are replaced by tests of the
   new behaviour (cross-queue ⇒ five claims, no fact, snapshot unchanged; later receiver traffic ⇒ the
   completed window's complete claim set is unchanged). The remaining G4/G5 spike tests are rerun and
   pass; the snapshot-id and stale-snapshot tests still hold.
5. One test of the refusal through the real `/v1/traces` endpoint. Each guard is shown to be load-bearing
   by disabling it and seeing the new tests fail.
6. No frozen golden, evaluation reference, schema or release artifact changes; the full unit and
   integration suites, ruff, pyright and import-linter pass.

## 7. Decisions recorded

2026-10-07, owner (at planning): H1 is an ingestion guard only (a projection rule was considered and
rejected because it would erase the declaration lifecycle, §3.3); H2 is applied at the shared
accepted-evidence filter for all resolution paths.
