# AIP v0.7.0 I0 → I1/I2 Handoff

**Status:** Frozen (merged #509). Artifact 6 of spec §15.
**Governing specification:** [`i0-gateway-capability-survey-and-semantic-freeze.md`](i0-gateway-capability-survey-and-semantic-freeze.md) §§13–15, 18. Decisions: [`i0-source-selection-decision.md`](i0-source-selection-decision.md).

## 1. Frozen by I0 (I1/I2 SHALL NOT reinterpret)

| Item | Where | Decision |
|---|---|---|
| O1 selected gateway | decision §1 | APISIX 3.19.0, Admin API over etcd |
| O2 vocabulary | decision §7 | reuse `Service` (application Service only) and `Operation`; new `ApiContract`, `ApiContractVersion`, `GatewayService`, `GatewayRoute`, `GatewayConsumer`, `ConfiguredAccess`, `ObservedConsumerInteraction`; contract↔Service and operation↔contract-version are explicit associations; everything else source-only |
| O3 configured-access mapping | decision §4 | allow-list `consumer-restriction` on a Route, `type: consumer_name`, `whitelist`; everything else recorded as unsupported |
| O4 consumer identity | decision §8, dossier §1 | Consumer `username` within a declared gateway instance; no secret input; credential id only where needed |
| O5 measurement | decision §5 | `apisix_http_status`, usage = `response_source="upstream"`, operator-asserted environment, window from manifest, closed-world rule for zero |
| O6/O7 association rules | decision §9, dossier §2 | rule level; no similarity-only resolution |
| O11 cross-check and replay strategy | decision §6, acquisition plan | Tyk is the I4 cross-check; normalized-artifact equality for replay |

## 2. What I1 receives

- Configuration source: Admin API list reads with the before/after etcd revision consistency rule, redaction before storage, revision and removal scope per the acquisition plan §2.
- Evidence rules: parent §12 (identity, relationship kind, revision, provenance, removal scope, unsupported fields) and §13 (atomic import, authoritative removal within owned scope, failed/partial never erases state, rejected per-source outcome, inherited `PARTIAL` commit gate).
- To define in I1: relation names and evidence for the Operation↔`ApiContractVersion` and `ApiContractVersion`↔`Service` associations (decision §7), whether `Operation` ids change, the exact `GatewayConsumer` id encoding, the source declaration (including `gateway_instance_id`), fixture layout, and the `ConfiguredAccess` schema fields (rule kind, polarity, scope).

## 3. What I2 receives

- Measurement extraction per acquisition plan §3 and decision §5.
- Reconciliation joins and classes (dossier §2), to be implemented as a deterministic pipeline.
- Cases the truth table must cover (acquisition plan §5; parent §17 matrix). Qualification vocabulary and truth table (O8) are I2's.
- Ingestion-concurrency baseline (parent §14, last paragraph) applies to any new runtime ingestion path.

## 4. Deferred, with owner

| Item | Owner |
|---|---|
| Qualification vocabulary and truth table (O8) | I2 |
| Bounded enumeration and truncation (O9) | I3 |
| REST path, MCP tool name, public response schema (O10); public exposure of consumer usernames (parent §29) | I3 |
| Real-source replay packaging and Tyk cross-check capture (O11 remainder) | I4 |
| Counter reset/restart detection for multi-capture windows | I2, only if a window beyond a fresh-start fixture is needed |
| Explicit `labels` key for the upstream → Service reference | I2 |

## 5. Needs a reviewed amendment if it changes

Selected gateway or version; the configured-access interpretation boundary (decision §4.2); the usage definition (`response_source="upstream"`); the operator-asserted environment rule; the closed-world coverage rule; any new canonical entity beyond the seven in decision §7, or any collapse of contract identity into application-Service identity; any use of a credential value as identity.

## 6. Preconditions for I1 to start

`READY_FOR_I1` recorded in [`i0-completion-record.md`](i0-completion-record.md) and PR B merged.
