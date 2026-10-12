# AIP v0.7.0 I0 — Identity and Reconciliation Dossier

**Status:** Frozen (merged #509). Artifact 5 of spec §15.
**Governing specification:** [`i0-gateway-capability-survey-and-semantic-freeze.md`](i0-gateway-capability-survey-and-semantic-freeze.md) §§7, 9; parent [`specification.md`](specification.md) §§10, 15, 29. Decisions: [`i0-source-selection-decision.md`](i0-source-selection-decision.md) §§8–9.
Join classes are survey vocabulary (spec §9), not the I2 public vocabulary. I2 implements the pipeline and freezes outcome names.

## 1. Identity domains for the selected source (APISIX)

| Domain (parent §10) | APISIX source identity | Stable? | Secret? | Notes |
|---|---|---|---|---|
| Gateway consumer | Consumer `username` (Admin API resource id) | Yes within a gateway instance; unique by resource id (F13) | No | Standalone-YAML duplicates overwrite silently (F12); not supported |
| Credential/key | credential id (`cred-1`) or the embedded key in a Consumer's `key-auth` | Credential id yes | **Key value is a secret** | Value never retained; credential id only where needed (decision §4.3) |
| Runtime attribution | metric label `consumer` = Consumer `username` | Same as above | No | Empty string = unattributed (F3) |
| Gateway route | Route `id` | Yes | No | Carries `uri`, `methods` |
| Gateway service | Service `id` | Yes | No | Auto-generated ids under the Ingress Controller are unpredictable (DOC) |
| API contract / contract version | `ApiContract` / `ApiContractVersion` (own identities; contract + version string) | n/a | No | From OpenAPI ingestion; never the application `Service` id |
| API operation | existing AIP `Operation` id | n/a | No | Owning contract version is an explicit association, not part of the id decision here |
| Application Service | existing AIP `Service` id | n/a | No | Never derived from a gateway object |

Multiple credentials per consumer are expected (F14); all attribute to the same username and the same series. Many consumers to one credential is not representable (a key belongs to one consumer).

## 2. Joins (spec §9 classification)

| Join | Class for APISIX | Basis | Failure outcome |
|---|---|---|---|
| Gateway Consumer ↔ runtime attribution | `EXPLICIT_SOURCE_REFERENCE` | metric `consumer` label equals Consumer `username`, same gateway instance and operator-asserted environment | Different or missing instance/environment → `UNRESOLVED`; username collision across instances is two identities |
| Gateway Route ↔ API Operation | `USER_AUTHORED_MAPPING_REQUIRED`; `DETERMINISTIC_NORMALIZATION` only when exactly one candidate | Route `uri` + `methods` vs Operation method + path, using a documented base-path rule | 0 candidates `UNRESOLVED`; >1 `AMBIGUOUS`; route `uri` with wildcard or regex that spans operations `AMBIGUOUS`; method-less route `AMBIGUOUS` unless exactly one operation matches |
| Gateway Route ↔ API Contract/Version | `USER_AUTHORED_MAPPING_REQUIRED` | Derived from the Operation's explicit association to its `ApiContractVersion` once the operation join resolves; never from route name, and never through the application `Service` | Version not evidenced → `UNRESOLVED` |
| Gateway upstream/target ↔ application Service | `USER_AUTHORED_MAPPING_REQUIRED`; `EXPLICIT_SOURCE_REFERENCE` if a route or service `labels` entry names an AIP Service | Upstream `nodes` host:port is not an identity | Host/port/name similarity never resolves; several plausible Services `AMBIGUOUS` |
| Gateway Service ↔ application Service | `USER_AUTHORED_MAPPING_REQUIRED` | Same as above | Same |

Name similarity, URL or path similarity, and graph proximity alone never resolve a join when more than one candidate exists. Association is not equivalence.

The two chains are independent and must not be merged: `Route → Operation → ApiContractVersion → ApiContract` (what the route exposes) and `upstream/target → application Service` (what serves it). Resolving one says nothing about the other; the contract-version → Service association from OpenAPI is evidence of declaration, not identity.

## 3. Unsupported or ambiguous inputs recorded for I1/I2

- `blacklist`, `allowed_by_methods`, `type` other than `consumer_name`, restriction on a Service/Consumer/plugin_config/global rule: recorded as unsupported source scope (decision §4.2).
- Consumer groups: unsupported in the first slice.
- Routes behind an upstream that load-balances across nodes belonging to different AIP Services: `AMBIGUOUS` for the target join.
- A route without `consumer-restriction` or with an open authentication plugin: no per-consumer `ConfiguredAccess`.

## 4. Cross-check (Tyk) identity notes, for I4

Tyk identifies the subject by a **key** (hashed) with an `alias`; the per-consumer metric needs a custom instrument (F7). The alias is not unique (F6), so the Consumer↔attribution join is `AMBIGUOUS` unless an external uniqueness rule is asserted. This difference is the point of the cross-check and must not be normalized away.

## 5. Mapping burden summary (survey column)

User-authored mappings required for the first slice: Route ↔ Operation (unless uniquely normalizable), upstream/Service ↔ application Service, and the gateway-instance and environment declaration. Explicit: consumer ↔ attribution.
