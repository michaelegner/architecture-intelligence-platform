# AIP v0.7.0 I1 → I2 Handoff

**Status:** Frozen (merged #517). Governing: [`i1-selected-gateway-configuration-source.md`](i1-selected-gateway-configuration-source.md) §7, [`i1-gateway-source-contract.md`](i1-gateway-source-contract.md), [I0 → I1/I2 handoff](i0-i1-i2-handoff.md).

I1 delivers the **configuration** half of the first v0.7 question. It does not touch runtime usage, reconciliation or any public surface.

## 1. What I2 receives (internal state, snapshot-visible, nothing public)

| State | Where | Notes |
|---|---|---|
| `GatewayConsumer`, `GatewayRoute`, `GatewayService` | graph carriers; snapshot key `gateway_configuration_v1` | identities over `(gateway_instance_id, source id)`; `environment` (operator-asserted) is a field, not part of any id; per-object `created_index` / `modified_index` retained as provenance |
| `GatewayConfiguredAccess` + `GatewaySourceEvidence` | same | the frozen allow-list only: route-level `consumer-restriction`, `type: consumer_name`, name in `whitelist`, a supported authentication plugin on the same route, no `allowed_by_methods`, not in `blacklist`, consumer present in the inventory |
| `GatewayLimitation` | same | facts recorded but not interpreted as access, with the codes of contract §4 (source-qualified, never an access claim) |
| `ApiContract` / `ApiContractVersion` / `ApiContractAssociation` | graph carriers; snapshot key `api_contracts_v1`; present only when the import request configures a gateway source | operation→contract-version and contract-version→Service are explicit associations, never identity; `Operation` ids unchanged |
| source revision | `apisix:<apisix_version>+etcd:<etcd_revision>` | on the evidence carrier and every access record |
| capture tool + fixture | `app/gateway_capture/apisix.py`, `aip-apisix-capture/1` | I2's measurement manifest binds to `gateway_instance_id` and the same operator-asserted `environment` |

## 2. What is canonical, source-qualified, and unresolved

- **Canonical (I1-owned):** the carriers and ids above; the `ConfiguredAccess` interpretation; the lifecycle (complete accepted capture is authoritative for its gateway instance; a rejected capture commits and removes nothing).
- **Source-qualified:** every limitation record; unsupported restriction types, scopes and authentication plugins; the operator-asserted environment.
- **Unresolved for I2 (nothing joined in I1):** Route ↔ `Operation` / API contract version; gateway upstream/target ↔ application `Service`; consumer ↔ runtime attribution beyond the shared `username` within one gateway instance and environment. I1 emits no such association and infers none from names, paths or hosts.

## 3. Facts I2 must respect

- **Usage is `response_source="upstream"`** (I0 decision §5.2); a denied consumer is still counted under its name for rejected attempts.
- **A consumer with no credentials is a 404 from the Admin API** (handled by the capture tool); a consumer with no traffic has no metric series (I0 F5): zero is stated only under the manifest's closed-world assertion.
- **The import report now includes `apisix` runs** (additive amendment of `aip-import-report/1`).
- **Configuring any gateway** turns on the OpenAPI contract carriers for the whole import request; removing the last gateway expires them on the next import.

## 4. Deferred, with owner

| Item | Owner |
|---|---|
| Qualification vocabulary and truth table (O8); runtime measurement ingestion and replay; the reconciliation pipeline (O6/O7) | I2 |
| Bounded enumeration, REST/MCP surface, public exposure of consumer usernames and of gateway evidence (`SourceType` widening) | I3 |
| Restart/counter-reset detection for multi-capture windows | I2, only if needed |
| Cross-check capture for Tyk, packaging, pilot | I4 |

## 5. Needs a reviewed amendment if it changes

The `ConfiguredAccess` interpretation boundary (contract §4); the carrier ids; the conditional snapshot keys; the rule that gateway evidence is not a public `:Evidence` node; the import-report schema amendment.
