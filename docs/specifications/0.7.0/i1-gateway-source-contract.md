# AIP v0.7.0 I1.1 — Gateway Source Contract and Identities

**Status:** Proposed — frozen on merge of the I1.1 PR. Implementation slices I1.2–I1.4 SHALL NOT reinterpret it.
**Governing specification:** [`i1-selected-gateway-configuration-source.md`](i1-selected-gateway-configuration-source.md) (Proposed, merged #511, `c217b06`) §§2–6; I0 [decision](i0-source-selection-decision.md), [acquisition/replay plan](i0-acquisition-replay-plan.md), [dossier](i0-identity-reconciliation-dossier.md), [handoff](i0-i1-i2-handoff.md).
**Vectors:** [`i1-vectors/`](i1-vectors/) — hand-authored, independent of any adapter (`ids.json`, `configured-access.json`, `capture-rejections.json`).
**Repository precedent:** the Kubernetes source (v0.5.0 I2): one offline snapshot file, a configured registration the envelope must match, a discoverer, an adapter registered in `default_registry()`, internal-only carrier nodes with their own labels and no edges to public entities.

This document freezes exactly what I1 §6 assigns to I1.1. Where the I1 spec or I0 already decided, it is cited, not repeated.

## 1. Source kind, registration and declaration

- New `SourceKind.APISIX = "apisix"` and a registration model `ApisixSourceConfig`: `id` (configured source id), `root`, `capture_relative_path`, `gateway_instance_id`, optional `configured_scope_id` / `stable_target_identity` (defaulting exactly like `KubernetesSourceConfig`). Settings gain `gateways: list[ApisixSourceConfig]`, empty by default.
- `SourceInstanceId = urn:aip:source:apisix:<sha256(ld(configured source id, gateway_instance_id))>` (vector V07). `ld` is `app.common.encoding.length_delimited`.
- `gateway_instance_id` is an operator-declared, stable, non-empty string; it is **the** identity anchor for all gateway entities (I0 decision §8) and is not the configured source id.
- The capture envelope declares `gateway_instance_id`; it MUST equal the registration's (else `GW_INSTANCE_MISMATCH`, R05).
- `environment` is an operator-asserted, non-empty string in the envelope (I0 decision §5.1). I1 stores it as a source attribute; it takes no part in any id. I2 matches it with runtime captures.
- Two registrations with the same `gateway_instance_id` are both rejected `REJECTED_CONFLICT` / `GW_DUPLICATE_INSTANCE` (R06). Neither commits.

## 2. Discovery convention and fixture

- One file per source: `<root>/<capture_relative_path>` (default name `apisix-capture.json`), UTF-8 JSON, bounded: ≤ 8 MiB, ≤ 10,000 resource objects, nesting ≤ 64. Limit violations are `REJECTED_UNSUPPORTED`. The file's SHA-256 is the source's `content_sha256`.
- Discovery is by registration (like Kubernetes), not by filename scan, so a fixture is proven through the real `SourceDiscoverer` with `source_kind = apisix`; `supports()` on the adapter checks `schema == "aip-apisix-capture/1"`, never the filename.
- Envelope (`aip-apisix-capture/1`, base values in `configured-access.json`): `gateway_instance_id`, `environment`, `apisix_version`, `admin_surface`, `etcd_revision_before`, `etcd_revision_after`, `lists_complete{kind: bool}`, and one array per kind: `consumers`, `routes`, `services`, `upstreams`, `plugin_configs`, `consumer_groups`, `global_rules`.
- **Redaction invariants (the capture tool writes them, the adapter verifies them):** a consumer is `{username, credential_ids[]}`; authentication plugins appear by name with an empty config; `consumer-restriction` keeps its full config (it is not secret); every other plugin appears by name with an empty config. Any field named `key`, `secret`, `password`, `token`, `username`/`password` pairs inside a plugin config, or any non-empty authentication-plugin config makes the capture `REJECTED_INVALID` / `GW_CAPTURE_UNREDACTED` (R07) **without echoing the value**.
- Source revision = `apisix:<apisix_version>+etcd:<etcd_revision_after>` (I0 acquisition plan §2: etcd header revision plus the APISIX version; vector V13); capture complete only when `etcd_revision_before == etcd_revision_after` (R01) and every `lists_complete` entry is `true` (R02).
- `admin_surface` MUST be `admin-api-etcd`; `standalone-yaml` is `REJECTED_UNSUPPORTED` (R03). Unknown `schema` is `REJECTED_UNSUPPORTED` (R04). A missing or mistyped required field is `REJECTED_INVALID` / `GW_CAPTURE_INVALID` (R08).

## 3. Identities and canonical entities (vectors V01–V13; V11 was removed)

All ids use `ld` = 8-byte big-endian UTF-8 byte length + bytes per part and lowercase hex SHA-256.

| Entity | Id | Inputs |
|---|---|---|
| `GatewayConsumer` | `gateway-consumer:owned:<sha256(ld(gateway_instance_id, username))>` | no credential field is ever an input |
| `GatewayRoute` | `gateway-route:owned:<sha256(ld(gateway_instance_id, route id))>` | APISIX Route `id` |
| `GatewayService` | `gateway-service:owned:<sha256(ld(gateway_instance_id, service id))>` | APISIX Service `id`; the kind prefix keeps a route and a service with the same raw id distinct (V05) |
| `ConfiguredAccess` | `configured-access:owned:<sha256(ld(consumer id, route id, rule kind))>` | rule kind `CONSUMER_RESTRICTION_ALLOW_LIST` (V06) |
| `ApiContract` | `api-contract:owned:<sha256(ld(OpenAPI SourceInstanceId))>` | the existing OpenAPI source-instance identity (I1 §3.6) |
| `ApiContractVersion` | `api-contract-version:owned:<sha256(ld(contract id, info.version))>` | exact, non-empty `info.version` string; an absent, empty or non-string version mints no `ApiContractVersion` (V10) |

Fields:
- `GatewayConsumer`: `id`, `gateway_instance_id`, `username`, `credential_ids` (sorted, non-secret).
- `GatewayRoute`: `id`, `gateway_instance_id`, `route_id`, `uri`, `methods` (sorted), `service_id` (APISIX service id or null), `auth_plugins` (sorted names), `plugin_names` (sorted).
- `GatewayService`: `id`, `gateway_instance_id`, `service_id`, `plugin_names`.
- `ConfiguredAccess`: `id`, `consumer_id`, `route_id`, `rule_kind`, `polarity = ALLOW`, `scope = ROUTE`, `evidence_ids`, `source_revision`. It carries no usage, authorization or approval meaning.
- `ApiContract`: `id`, `openapi_source_instance_id`. `ApiContractVersion`: `id`, `contract_id`, `info_version`.
- An absent, empty or non-string `info.version` produces no `ApiContractVersion` and a limitation `CONTRACT_VERSION_MISSING_OR_NOT_STRING` (no empty-string identity is manufactured); it never rejects the OpenAPI source (existing behavior is preserved).

**Representation.** All of these are internal-only carrier nodes with their own labels (`GatewayConsumer`, `GatewayRoute`, `GatewayService`, `GatewayConfiguredAccess`, `ApiContract`, `ApiContractVersion`, `ApiContractAssociation`), owned by their source instance, with **no relationships to public entities**; references are id-valued properties. This follows the infrastructure-carrier precedent and keeps every existing traversal, analysis and NL/MCP surface unchanged. Public exposure is I3.

**Contract associations.** `ApiContractAssociation` is a carrier node: `kind = OPERATION_IN_CONTRACT_VERSION` (`operation_id`, `contract_version_id`) or `CONTRACT_VERSION_DECLARED_FOR_SERVICE` (`contract_version_id`, `service_id`), each with `evidence_ids` pointing at the OpenAPI provenance. Association is not equivalence; an `Operation` id is never changed (stop-and-amend).

## 4. `ConfiguredAccess` interpretation (vectors C01–C15)

A `ConfiguredAccess` is created for `(consumer, route)` iff **all** hold:
1. the route's own `plugins` contains `consumer-restriction`;
2. `type` is omitted (APISIX default) or `consumer_name`;
3. the config has no `allowed_by_methods`;
4. the route's own `plugins` contains a plugin from the frozen supported authentication set `{key-auth, basic-auth, jwt-auth, hmac-auth, ldap-auth}` (plugins that resolve a Consumer). A recognized but unsupported authentication plugin (the *recognized unsupported set*, §4.1) does not qualify and is reported as unsupported, not as absent (C13); a supported plugin alongside an unsupported one still qualifies (C15);
5. the name is in `whitelist`, is **not** in `blacklist`, and exists as a Consumer in the inventory.

Everything else yields no access and, where noted, a **limitation record** (`code`, `subject`; sorted, deterministic):

| Condition | Code | Subject |
|---|---|---|
| unsupported `type` (C03) | `GW_RESTRICTION_UNSUPPORTED_TYPE` | route id |
| no authentication plugin of either set on the route (C04) | `GW_RESTRICTION_NO_AUTH_PLUGIN` | route id |
| only recognized unsupported authentication plugins (C13) | `GW_AUTH_PLUGIN_UNSUPPORTED` | `route:plugin` (sorted, one record per plugin) |
| whitelisted name not in the consumer inventory (C05) | `GW_WHITELIST_DANGLING_CONSUMER` | `route:name` |
| name in whitelist and blacklist (C06) | `GW_WHITELIST_BLACKLIST_CONFLICT` | `route:name` |
| blacklist with no whitelist (C07) | `GW_BLACKLIST_RECORDED` | route id |
| `allowed_by_methods` present (C08) | `GW_RESTRICTION_METHOD_SCOPED` | route id |
| `consumer-restriction` on a Service, via `plugin_config_id`, or in a global rule (C09–C11) | `GW_RESTRICTION_UNSUPPORTED_SCOPE` | `service:id` / `plugin_config:id` / `global_rule:id` |

**4.1 Recognized unsupported set (APISIX 3.19 plugin list as observed in the I0 spike; a recognized list, not a claim about each plugin's consumer-binding semantics):** `multi-auth`, `openid-connect`, `saml-auth`, `wolf-rbac`, `jwe-decrypt`, `cas-auth`, `dingtalk-auth`, `feishu-auth`, `ldap-auth-advanced`. Widening the supported set later is a reviewed amendment; a plugin in neither set counts as absent.

An authentication plugin without a restriction (C12) creates nothing and records nothing. Limitations are source-qualified evidence for I2, never access claims. A `GW_WHITELIST_BLACKLIST_CONFLICT` name is excluded only for that name; other whitelisted names on the route are unaffected (C06).

Evidence: one `Provenance` per source (id `evidence:apisix:<sha256(ld(gateway_instance_id, source_revision))>`, so an APISIX upgrade at an unchanged etcd revision yields a different id (V13); `source_type = "APISIX"`, `evidence_type = DECLARED`, `source_revision`). Each `ConfiguredAccess` carrier's `evidence_ids` point at that APISIX provenance record; the rule semantics are carried by `rule_kind`, not by evidence text. `APISIX` is not added to the public `SourceType` enum in v0.7 I1 (that enum is part of a frozen public schema; widening it is I3's decision).

## 5. Lifecycle

- A complete accepted capture is authoritative for the interpreted kinds of that `gateway_instance_id` only. Objects, access records and limitations absent from a later accepted capture are expired (the existing per-source tombstone / owner-source mechanism).
- A rejected, inconsistent or incomplete capture commits nothing and expires nothing; the `PARTIAL` run gate is unchanged.
- No predecessor-revision expectation is introduced in v0.7 I1.
- Replay of the same fixture produces an identical canonical result and `semantic_input_digest`.
- Removing a gateway registration removes its carriers through the existing source-removal path; contract carriers (§6) follow the gate in §6 on the next run.

## 6. Conditional contract emission and snapshot inclusion (resolved)

- **Observable rule (frozen):** `ApiContract`, `ApiContractVersion` and `ApiContractAssociation` carriers exist in the graph and snapshot **iff** the import request configures at least one gateway source (`sources.gateways` non-empty). A request with none behaves exactly as before v0.7: the `snapshot_id` / fingerprint of a no-gateway graph MUST be unchanged (golden pin in I1.2). *Amended in I1.2 (owner decision, 2026-10-12): the I1.1 text said "the committed source set of the discovery run contains an accepted gateway source", which cannot hold because every configured source (filesystem directory, cluster, gateway) is its own discovery run (`app/graph/import_runs.py`) — an OpenAPI run never contains a gateway source. The gate is therefore the import request's configuration. A configured gateway whose own run is rejected still leaves the OpenAPI-side carriers in place; that rejection only blocks the gateway run's commit.*
- **Mechanism (I1.2 may refine if it keeps the observable rule):** the OpenAPI adapter builds the contract carriers in its model as internal, always-computed data; `run_all_configured_sources` passes `api_contract_associations = bool(sources.gateways)` into each filesystem run; the orchestrator strips the carriers from every source outcome when it is false, and adds `"apiContractAssociations": true` to the mapping-context digest only when it is true, so a toggle changes every OpenAPI source's `semantic_input_digest` (the replay no-op cannot swallow it) and the existing reconciliation adds or expires the carriers; with the flag false the digest is byte-identical to pre-v0.7. `Provenance` carries no source instance id, so the carrier must record `openapi_source_instance_id` itself.
- **Snapshot:** new conditional keys `gateway_configuration_v1` (consumers, routes, services, configured access, limitations, sorted) and `api_contracts_v1` (contracts, versions, associations, sorted) are added to the canonical state **only when non-empty**, following `scoped_observed_calls_v2`. `_CANONICALIZATION_VERSION` stays 4.
- AsyncAPI sources produce no contract carriers in v0.7.

## 7. Diagnostics and per-source outcomes

| Code | Outcome |
|---|---|
| `GW_CAPTURE_INVALID`, `GW_CAPTURE_INCONSISTENT`, `GW_CAPTURE_INCOMPLETE`, `GW_CAPTURE_UNREDACTED`, `GW_INSTANCE_MISMATCH` | `REJECTED_INVALID` |
| `GW_CAPTURE_SURFACE_UNSUPPORTED`, `GW_CAPTURE_SCHEMA_UNSUPPORTED`, limit violations | `REJECTED_UNSUPPORTED` |
| `GW_DUPLICATE_INSTANCE` | `REJECTED_CONFLICT` |
| limitation codes of §4 | informational; the source is `ACCEPTED_WITH_LIMITATIONS` when any exists |

Diagnostic messages never include source values; `subject` strings carry only route/service/plugin_config/global_rule ids and consumer usernames from the inventory.

## 8. Case-to-test map (I1 §5)

| I1 §5 case | Vector | Slice that proves it |
|---|---|---|
| whitelisted → access; `type` default/unsupported; no auth; dangling; whitelist+blacklist; blacklist/method/scope; auth without restriction; multi; unsupported + supported auth plugin | C01–C15 | I1.4 |
| same username on two instances; id distinctness | V01–V06 | I1.4 |
| duplicate instance id; standalone YAML; revision change; incomplete list; unredacted/canary; malformed | R01–R08 | I1.3 (capture side), I1.4 (adapter side) |
| removal; replay identity; atomic import; discoverer path | lifecycle §5 | I1.4 |
| no-gateway snapshot unchanged; `Operation` ids unchanged; contract non-collapse | §3, §6 | I1.2 |
| gateway vs application `Service` distinct with matching names | V03–V05 | I1.4 |
| no Route↔Operation / upstream↔Service inference from similarity | carriers hold no such association | I1.4 |

## 9. Not frozen here

Capture-tool CLI shape (I1.3), writer Cypher and constraints (I1.2/I1.4), exact Python class layout, public exposure and `SourceType` widening (I3), runtime measurement and the environment join (I2).
