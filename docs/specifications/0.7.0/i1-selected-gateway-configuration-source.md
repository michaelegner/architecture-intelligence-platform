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
- positive configured access: Route-level `consumer-restriction`, `type: consumer_name`, consumer present in `whitelist`, without `allowed_by_methods`;
- `GatewayService`, `GatewayRoute`, `GatewayConsumer`, `ApiContract`, `ApiContractVersion` and application `Service` remain distinct identities;
- credentials and secret values are never Architecture Knowledge;
- unsupported APISIX restriction shapes remain explicit and do not create positive configured access.

## 3. Scope

I1 shall implement the smallest configuration-source slice needed by I2:

1. **APISIX source declaration**
   - stable `gateway_instance_id`;
   - APISIX version and source revision;
   - no credential material in canonical state or provenance.

2. **Consistent configuration capture**
   - read the I0-defined Admin API inventory;
   - require equal etcd revisions before and after the capture;
   - reject inconsistent captures without changing previously accepted state.

3. **Secret-safe normalization and replay**
   - redact credential values before retained storage;
   - remove volatile fields;
   - deterministic ordering and serialization;
   - replay uses only the normalized fixture and never contacts APISIX.

4. **Canonical gateway state**
   - deterministic identities for `GatewayConsumer`, `GatewayRoute` and `GatewayService`;
   - preserve source fields needed for configured-access interpretation and later I2 reconciliation;
   - keep gateway entities distinct from application `Service`.

5. **ConfiguredAccess**
   - create only the I0-frozen APISIX allow-list relationship;
   - unsupported, malformed or unresolved source facts do not become positive access claims;
   - evidence must explain the source rule that established the relationship.

6. **API contract associations**
   - represent `ApiContract` and `ApiContractVersion`;
   - explicitly associate `Operation` with its contract version;
   - explicitly associate the contract version with the application `Service` declared by the OpenAPI source;
   - preserve existing `Operation` identity unless review shows that this is impossible.

## 4. Source lifecycle

I1 reuses the existing AIP source lifecycle:

```text
complete inventory
→ revision fence
→ redact
→ normalize
→ canonicalize
→ atomic import
```

An accepted complete capture is authoritative only for the APISIX-owned gateway state of that gateway instance.

A later accepted capture may remove missing gateway objects and configured-access relationships from that source contribution.

A failed, inconsistent or rejected capture removes nothing.

The existing discovery-run commit gate remains unchanged: a `PARTIAL` run does not partially commit accepted source state.

## 5. Minimum qualification cases

I1 tests shall cover at least:

- whitelisted consumer → positive `ConfiguredAccess`;
- two consumers on one route remain distinct;
- same username on two gateway instances → distinct consumers;
- blacklist, `allowed_by_methods`, unsupported restriction type/scope → no positive access;
- authentication without an enumerating restriction → no configured consumer relationship;
- credential values never reach fixture, evidence, provenance or canonical storage;
- changed before/after etcd revision → capture rejected;
- route/consumer/access removal in a later complete capture → authoritative removal;
- identical replay → identical canonical result;
- `GatewayService` and application `Service` remain distinct even with matching names;
- OpenAPI contract/version associations do not collapse contract, operation and application-service identities;
- I1 does not infer Route↔Operation or gateway↔application-Service reconciliation from similarity.

Expected results should be authored independently from the production adapter.

## 6. Implementation slices

Keep I1 small:

- **I1.1 — contract and identities:** freeze exact ids, relation names, fixture shape and expected cases.
- **I1.2 — contract associations:** add `ApiContract` / `ApiContractVersion` associations while preserving existing OpenAPI behavior.
- **I1.3 — APISIX capture:** acquisition, revision fence, redaction and normalized replay fixture.
- **I1.4 — gateway state and ConfiguredAccess:** canonical gateway entities, source lifecycle and qualification.
- **I1.5 — handoff:** deterministic replay check, regression tests, completion record and concise I1 → I2 contract.

Slices may be combined when that keeps review simpler.

## 7. I1 → I2 handoff

I2 shall receive stable internal state for:

```text
GatewayConsumer
GatewayRoute
GatewayService
ConfiguredAccess + evidence
ApiContract / ApiContractVersion / Operation associations
source revision + gateway instance
explicit unsupported/limitation markers
```

I1 does not hand I2 resolved Route↔Operation or gateway↔application-Service conclusions.

## 8. Definition of Done

I1 is complete when:

- APISIX configuration can be captured consistently and replayed deterministically;
- secrets are redacted before retained storage;
- gateway identities and configured-access semantics match the I0 freeze;
- source updates/removals are atomic and bounded to APISIX-owned state;
- contract/version associations are explicit without collapsing identity domains;
- the minimum qualification cases pass;
- existing v0.5/v0.6 behavior remains green;
- the I1 → I2 handoff identifies what is canonical, what is source-qualified, and what remains unresolved for I2.
