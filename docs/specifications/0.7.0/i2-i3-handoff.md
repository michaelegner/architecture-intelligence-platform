# AIP v0.7.0 I2 → I3 Handoff

**Status:** Frozen when merged with I2.4. Governing: [`i2-consumer-attribution-and-configured-vs-observed-qualification.md`](i2-consumer-attribution-and-configured-vs-observed-qualification.md) §§10–13, [`i2-measurement-contract.md`](i2-measurement-contract.md), [I1 → I2 handoff](i1-i2-handoff.md).

I2 delivers the **runtime** half of the first v0.7 question and the qualification of configured against observed access. It adds no public surface: no REST, MCP, `SourceType`, public evidence or consumer-name exposure. I3 owns all of that.

## 1. The exact internal state I3 may project

Everything is in the conditional snapshot key `api_usage_v1`, together with `gateway_configuration_v1` and `api_contracts_v1`. The key is absent when no accepted measurement source exists. All rows are sorted by stable keys; null properties are omitted; no section is persisted outside the carriers listed in §2.

| Section | Rows | Content |
|---|---|---|
| `windows` | one per accepted measurement source | gateway instance, environment, window bounds, settled / no-restart / stable-seconds fields, `disabled_labels`, `route_coverage_json`, `window_reasons` (empty = valid), `evidence_ids`, owning `source_instance_id` |
| `evidence` | one per window | internal `OBSERVED` evidence carrier (not a `:Evidence` node) |
| `series`, `limitations`, `mapping_entries` | per series / route-level limitation / mapping entry | raw measurement facts incl. `status` and `request_count_delta` |
| `reconciliation_rule`, `attributions`, `route_operation`, `target_service` | I2.3 | outcomes `RESOLVED` / `UNRESOLVED` / `AMBIGUOUS` / `CONFLICT` for consumer, Route, Operation, contract version and application Service |
| `qualification_rule`, `coverage` | I2.4 | per window and `GatewayRoute`: `SUFFICIENT_FOR_ZERO` / `UNKNOWN_COVERAGE` and its limitation codes |
| `interactions` | I2.4 | per window, `GatewayRoute`, `GatewayConsumer` with at least one series: `upstream_request_count`, `rejected_attempt_count`, `evidence_ids` |
| `qualification_rows` | I2.4 | the bounded union of configured and attributed observed pairs: `configured_status`, `usage_status`, `coverage`, counts, `limitations`, `evidence_ids`, `interaction_id` when present |

Counts are omitted (not zero) for a window with a reason: no usage can be stated from it.

## 2. What is canonical, source-qualified, and unresolved

- **Canonical (I2-owned):** the measurement carriers and ids (M04–M13), the derived interaction and row ids (M06–M09), the four outcomes, the two qualification vocabularies and the precedence of contract §7; the lifecycle (one window per source, replacement, removal, rejected import commits nothing).
- **Source-qualified:** the operator-asserted environment, the capture tool's attested stable seconds (replay cannot re-derive them), coverage assertions in `route_coverage`, and every limitation code.
- **Derived, not stored:** reconciliation outcomes, coverage, interactions and qualification rows are pure functions of stored facts (`app/sources/apisix_reconciliation.py`, `app/sources/apisix_qualification.py`); their rule ids and versions are in the snapshot, so a rule change is a fingerprint change.
- **Unresolved for I3:** the public vocabulary and wire schema (the internal outcome and status names are not public wire vocabulary), the REST/MCP shape, bounded enumeration and pagination, whether consumer usernames and gateway evidence become publicly visible (`SourceType` widening), and the natural-language/Cypher reachability of any of it.

## 3. Facts I3 must respect

- `OBSERVED_USAGE` requires a valid positive **upstream** delta; rejected attempts and unattributed traffic never establish usage, and a rejected attempt never creates configured access.
- `MEASURED_ZERO` only for a configured pair on a `SUFFICIENT_FOR_ZERO` Route in a valid window. Absence of evidence elsewhere is `USAGE_UNESTABLISHED`, never "unused".
- `NO_MATCHING_CONFIGURED_ACCESS_FACT` is not denial, unauthorized, misconfigured or forbidden; observed-only usage is not a policy finding.
- The Route → Operation → contract version chain and the gateway target → `Service` chain are independent and never infer from names, hosts or paths.
- The environment is operator-asserted; one window per `(gateway_instance_id, environment)`; no history.

## 4. Deferred, with owner

| Item | Owner |
|---|---|
| Public projection, REST/MCP, bounded enumeration, consumer-name and evidence exposure, `SourceType` | I3 |
| Tyk cross-check capture, packaging, pilot | I4 |
| Broker-mediated consumer attribution | v0.7.1 |
| Restart/counter-reset inference for multi-capture windows | not in v0.7 |

## 5. Needs a reviewed amendment if it changes

Every item of I2 spec §14, the `api_usage_v1` section set above, the derived-not-stored rule, the rule ids/versions, and the rule that APISIX measurement evidence is an internal carrier and not a public `:Evidence` node.
