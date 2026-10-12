# AIP v0.7.0 I1 — Selected Gateway Configuration Source

**Status:** Draft  
**Release / increment:** v0.7.0 / I1, API-Aware Current State  
**Governing:** [v0.7.0 parent](specification.md), [I0 source-selection decision](i0-source-selection-decision.md), [I0 acquisition/replay plan](i0-acquisition-replay-plan.md), [I0 identity/reconciliation dossier](i0-identity-reconciliation-dossier.md), and [I0 → I1/I2 handoff](i0-i1-i2-handoff.md).

## 1. Goal

I1 turns the APISIX configuration path selected in I0 into deterministic, replayable Current-State evidence.

It shall establish:

- APISIX gateway consumers, routes and services with deterministic identities;
- the source-native configured-access relationship frozen in I0;
- source revision, provenance and authoritative-removal behavior;
- secret-safe normalized capture and replay;
- the API contract/version associations required by the I0 handoff.

I1 does **not** add runtime usage. Consumer-attributed measurements, reconciliation and configured-vs-observed qualification belong to I2.

## 2. Frozen inputs from I0

I1 shall not reinterpret these decisions:

- selected source: **Apache APISIX 3.19.0**, Admin API over etcd;
- consumer identity: `(gateway_instance_id, Consumer.username)`;
- positive configured access: Route-level `consumer-restriction`, `type: consumer_name` (including the APISIX default when `type` is omitted), consumer present in `whitelist`, an authentication plugin on the same Route, and no `allowed_by_methods`;
- `GatewayService`, `GatewayRoute`, `GatewayConsumer`, `ApiContract`, `ApiContractVersion` and application `Service` remain distinct identities;
- credentials and secret values are never Architecture Knowledge;
- unsupported APISIX restriction shapes remain explicit and do not create positive configured access;
- standalone-YAML is not an admitted v0.7 capture surface.

## 3. Scope

I1 shall implement the smallest configuration-source slice needed by I2:

1. **APISIX source declaration and discovery**
   - stable `gateway_instance_id`;
   - operator-asserted `environment` bound to that source instance for later I2 matching;
   - APISIX version and source revision;
   - one discoverable gateway source type / fixture convention, exercised through the real source discoverer rather than a test-only path;
   - duplicate `gateway_instance_id` declarations are rejected deterministically;
   - no credential material in canonical state, provenance or diagnostics.

2. **Separate live capture step**
   - a capture tool reads the I0-defined Admin API inventory; the AIP replay adapter consumes only its normalized output and never contacts APISIX;
   - the capture tool requires successful complete-list reads for every required resource kind and records that completeness in the manifest;
   - require equal etcd revisions before and after the complete capture;
   - a failed list read, incomplete/paginated inventory, or changed revision rejects the capture without changing previously accepted state;
   - the Admin API key and source credential values never enter the fixture, logs, diagnostics or error text.

3. **Secret-safe normalization and replay**
   - redact before retained storage;
   - remove volatile fields;
   - deterministic ordering and serialization;
   - replay uses only the normalized fixture;
   - rejection paths must use sanitized diagnostics and must not echo raw source objects.

4. **Canonical gateway state**
   - deterministic identities for `GatewayConsumer`, `GatewayRoute` and `GatewayService`;
   - preserve source fields needed for configured-access interpretation and later I2 reconciliation;
   - keep gateway entities distinct from application `Service`;
   - add real graph uniqueness constraints for new canonical identities where the model assumes uniqueness.

5. **ConfiguredAccess**
   - create only the I0-frozen APISIX allow-list relationship;
   - a dangling whitelist username, blacklist conflict, unsupported scope/type, method restriction or missing authentication plugin does not become a positive access claim;
   - unresolved/unsupported source facts remain explicit;
   - evidence must explain the source rule that established the relationship.

6. **API contract associations**
   - this slice applies to **OpenAPI only**; AsyncAPI contract entities are out of scope for v0.7 I1;
   - `ApiContract` logical identity is the existing OpenAPI source-instance identity; `ApiContractVersion` identity is that contract identity plus the exact OpenAPI `info.version` string; I1.1 freezes the byte encoding;
   - explicitly associate `Operation` with its contract version and the contract version with the application `Service` declared by that OpenAPI source;
   - existing `Operation` identity remains unchanged; any required change is a stop-and-amend condition;
   - to avoid changing every existing OpenAPI-only graph, these v0.7 contract entities/associations are emitted only when the discovery run contains an admitted gateway configuration source. A no-gateway run must retain the pre-v0.7 snapshot/fingerprint exactly. I1 shall pin this as a golden regression.

## 4. Source lifecycle

I1 reuses the existing AIP source lifecycle:

```text
complete live capture
→ revision fence
→ redact + normalize
→ replay fixture
→ discover
→ canonicalize
→ atomic import
```

An accepted complete capture is authoritative only for the APISIX-owned gateway state of that gateway instance.

A later accepted capture may remove missing gateway objects and configured-access relationships from that source contribution.

A failed, incomplete, inconsistent or rejected capture removes nothing.

Source failures map to the existing deterministic per-source rejected outcome. The existing discovery-run commit gate remains unchanged: a `PARTIAL` run does not partially commit accepted source state.

## 5. Minimum qualification cases

I1 tests shall cover at least:

- whitelisted consumer with authentication plugin → positive `ConfiguredAccess`;
- omitted restriction `type` uses APISIX's `consumer_name` default; explicit unsupported type does not;
- restriction without an authentication plugin → no positive access;
- dangling whitelist username → unresolved, no positive access;
- same username in whitelist and blacklist → no positive access;
- blacklist, `allowed_by_methods`, unsupported restriction scope → no positive access;
- authentication without an enumerating restriction → no configured consumer relationship;
- several consumers on one Route and one Consumer on several Routes remain distinct relationships;
- same username on two gateway instances → distinct consumers;
- duplicate `gateway_instance_id` declarations → deterministic rejection;
- standalone-YAML source → rejected as unsupported;
- known fake consumer keys **and Admin API key canaries** are absent from fixture, evidence, provenance, canonical storage, logs, rejection diagnostics and error messages;
- changed before/after etcd revision → capture rejected;
- unchanged revision but failed/incomplete resource-list acquisition → capture rejected;
- route/consumer/access removal in a later complete capture → authoritative removal;
- identical replay → identical canonical result;
- no-gateway OpenAPI run → unchanged pre-v0.7 snapshot/fingerprint;
- `GatewayService` and application `Service` remain distinct even with matching names;
- OpenAPI contract/version associations do not collapse contract, operation and application-service identities;
- I1 does not infer Route↔Operation or gateway↔application-Service reconciliation from similarity;
- hand-authored gateway fixtures are discovered through the production discoverer and rejected through the normal per-source outcome path when invalid.

Expected results should be authored independently from the production adapter.

## 6. Implementation slices

Keep I1 small:

- **I1.1 — contract and identities:** freeze ids, OpenAPI contract activation/identity, relation names, source declaration/discovery, fixture shape and expected cases.
- **I1.2 — contract associations:** add conditional OpenAPI `ApiContract` / `ApiContractVersion` associations and pin unchanged no-gateway snapshots.
- **I1.3 — APISIX capture:** separate live capture tool, complete-inventory assertion, revision fence, canary-based redaction and normalized replay fixture.
- **I1.4 — gateway state and ConfiguredAccess:** canonical gateway entities, DB constraints, source lifecycle and qualification.
- **I1.5 — handoff:** deterministic replay check, regression/docs updates, completion record and concise I1 → I2 contract.

Slices may be combined when that keeps review simpler.

## 7. I1 → I2 handoff

I2 shall receive stable internal state for:

```text
GatewayConsumer
GatewayRoute
GatewayService
ConfiguredAccess + evidence
ApiContract / ApiContractVersion / Operation associations
source revision + gateway instance + operator-asserted environment
explicit unsupported/limitation markers
```

I1 does not hand I2 resolved Route↔Operation or gateway↔application-Service conclusions.

## 8. Definition of Done

I1 is complete when:

- the separate APISIX capture path produces a complete, revision-consistent, normalized fixture and replay is deterministic;
- source discovery uses the production discoverer and invalid sources use the normal rejected-source path;
- secret canaries, including the Admin API key, are absent from all retained and diagnostic outputs;
- gateway identities and configured-access semantics match the I0 freeze;
- new canonical identity assumptions have matching graph constraints;
- source updates/removals are atomic and bounded to APISIX-owned state;
- OpenAPI contract/version associations are explicit, preserve existing `Operation` ids, and do not affect no-gateway snapshot/fingerprint pins;
- the minimum qualification cases pass;
- existing v0.5/v0.6 behavior remains green;
- relevant model/ingestion documentation is updated: `docs/canonical-model.md`, `docs/graph-model.md`, `docs/ingestion.md` / `docs/adapter-development.md`, and `docs/evidence.md` if evidence vocabulary changes;
- the I1 → I2 handoff identifies what is canonical, what is source-qualified, and what remains unresolved for I2.
