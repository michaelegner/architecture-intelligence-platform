# AIP v0.7.0 I2.1 — Measurement Contract and Independent Vectors

**Status:** Proposed (I2.1). Once merged, I2.2–I2.4 SHALL NOT reinterpret it; changes need a reviewed amendment.
**Governing specification:** [`i2-consumer-attribution-and-configured-vs-observed-qualification.md`](i2-consumer-attribution-and-configured-vs-observed-qualification.md) (Proposed, merged #520, `9930a15`) §§4–10, 12. Context: [I1.1 contract](i1-gateway-source-contract.md), [I1 → I2 handoff](i1-i2-handoff.md), I0 [acquisition/replay plan](i0-acquisition-replay-plan.md) and [identity/reconciliation dossier](i0-identity-reconciliation-dossier.md).
**Vectors:** [`i2-vectors/`](i2-vectors/) — hand-authored, independent of any adapter (`ids.json`, `manifest-rejections.json`, `series-deltas.json`, `reconciliation.json`, `qualification.json`). The reference reading below is re-implemented without importing `app` in `tests/unit/test_v070_i2_vectors.py`.
**Repository precedent:** the I1 gateway source (one registration, one offline fixture, a discoverer, an adapter, internal-only carriers with no edges to public entities).

This document freezes exactly what I2 §12 assigns to I2.1. Where the I2 spec, I1.1 or I0 already decided, it is cited, not repeated. It adds **no** production code.

## 1. Source kind, registration and cardinality

- New `SourceKind.APISIX_MEASUREMENT = "apisix-measurement"` and a registration model `ApisixMeasurementSourceConfig`: `id` (configured source id), `root`, `gateway_instance_id`, `environment`; the three fixture file names default to the names in §2 and are not operator-configurable in v0.7.
- `SourceInstanceId = urn:aip:source:apisix-measurement:<sha256(ld(configured source id, gateway_instance_id, environment))>` (vectors M01, M02). `ld` is `app.common.encoding.length_delimited`.
- **Cardinality (I2 §10.1):** one registration holds exactly one observation window. At most one registration may exist per `(gateway_instance_id, environment)`; two or more registrations for the same pair are all rejected `REJECTED_CONFLICT` / `GWM_DUPLICATE_SOURCE` and none commits (X20). Registrations that differ in gateway or environment coexist (X21).
- The measurement source never owns I1 carriers, and the I1 APISIX source never owns measurement carriers. `gateway_instance_id` and `environment` are the same operator-declared values the I1 source uses; this is the only link between the two sources.
- Discovery is by registration (like the Kubernetes and I1 sources); `supports()` checks the manifest `schema`, never a file name.

## 2. Fixture, manifest and binding

Files under `<root>`: `apisix-metrics-start.txt`, `apisix-metrics-end.txt`, `apisix-measurement-manifest.json`, and the optional `apisix-mapping.json` (§5). Bounds (violation = `REJECTED_UNSUPPORTED` / `GWM_LIMIT_EXCEEDED`): manifest ≤ 1 MiB; each extract ≤ 8 MiB and ≤ 100,000 series.

### 2.1 Normalized extract (frozen format)

One text file per boundary, UTF-8, containing only `apisix_http_status` samples, **already normalized by the capture tool and verified (not repaired) by the adapter**:

- one sample per line, `\n` terminated (LF only; the last line is terminated; an empty file = no series);
- shape `apisix_http_status{<labels>} <integer>`; the value is a non-negative base-10 integer (a non-integer is rejected, not rounded);
- labels are the source labels **minus `node`**, in **ascending alphabetical label-name order**, written `name="value"` exactly as Prometheus text exposes them (escapes kept verbatim);
- required labels: `code`, `consumer`, `response_source`, `route`; all other labels (for example `matched_uri`, `matched_host`, `service`, `request_type`) are preserved verbatim and are part of the series identity;
- `response_source` ∈ `{upstream, apisix}` (closed set; any other value is `GWM_EXTRACT_INVALID`; widening needs an amendment);
- lines are in strictly ascending byte order of the full line (so a duplicate series key is also rejected);
- no timestamps, comments, `# HELP`/`# TYPE` lines or other metrics.

The label order is alphabetical because I2 §4.2 requires "sort labels deterministically"; the I0 spike file `i0-spike/apisix/expected-capture.txt` shows APISIX's source label order and is evidence of the *raw* shape, not of the normalized form.

A series' identity is its full label string (everything between the braces). Two series that differ only in a non-required label (for example `matched_uri`) are distinct series; their deltas are summed when aggregating by `(route, consumer, response_source)` (series-deltas.json `expected_pair_totals`).

### 2.2 Manifest (`aip-apisix-measurement/1`)

UTF-8 JSON object with these fields, all required, no unknown-field tolerance beyond ignoring additional keys:

| Field | Type / rule |
|---|---|
| `schema` | `"aip-apisix-measurement/1"` (else `GWM_SCHEMA_UNSUPPORTED`; a non-string is `GWM_MANIFEST_INVALID`) |
| `gateway_instance_id`, `environment` | non-empty strings; MUST equal the registration's |
| `apisix_version` | non-empty string |
| `window_start`, `window_end` | `YYYY-MM-DDTHH:MM:SSZ` (whole-second RFC 3339 UTC); `window_start >= window_end` is **not** a rejection (§3) |
| `start_settled`, `end_settled`, `no_restart` | JSON booleans |
| `start_scrape_count`, `end_scrape_count` | integers ≥ 1; ≥ 2 when the boundary is `settled` (two identical consecutive scrapes are what settled means) |
| `start_stable_seconds`, `end_stable_seconds` | non-negative JSON integers: whole seconds the final extract of that boundary was observed unchanged before capture ended (*added in I2.2a, review of #525*); evidence for the first-in-window reading (§3), not a rejection input beyond type |
| `disabled_labels` | sorted list of unique strings (Plugin Metadata `disabled_labels` for `prometheus`) |
| `route_coverage` | `{APISIX route id: boolean}`: Prometheus plugin enabled for that Route for the whole window |
| `start_sha256`, `end_sha256` | lowercase hex SHA-256 of the **exact bytes** of the respective extract file (M03) |

### 2.3 Validation order and outcomes

Checks run in this order and the first failure decides the outcome (the tests pin the order):

1. manifest `schema` → 2. field presence/types/consistency → 3. gateway/environment equal the registration → 4. hash binding → 5. extract normalization.

A rejected import commits nothing and removes nothing previously accepted (I2 §10.2).

## 3. Window validity and series deltas (I2 §5)

**Reading frozen here:** I2 §5 lists "start and end belong to the declared same gateway instance and environment" as a delta precondition. The extracts carry no instance label, so this precondition is realized by step 3 above: a manifest that names a different gateway or environment than the registration is `REJECTED_INVALID` / `GWM_INSTANCE_MISMATCH` (X02, X03), exactly like I1 R05. Nothing is accepted that could be attributed to the wrong instance.

The other §5 preconditions do not reject; the import is accepted and the window carries these **window reasons**, each a limitation code (series-deltas.json `window_validity`, W01–W11):

| Reason | When |
|---|---|
| `GWM_WINDOW_NOT_SETTLED` | `start_settled` or `end_settled` is false |
| `GWM_WINDOW_RESTART` | `no_restart` is false |
| `GWM_WINDOW_ORDER_INVALID` | `window_start >= window_end` |
| `GWM_VERSION_INCOMPATIBLE` | `apisix_version` is not exactly `3.19.0` (the release I0 selected and inspected; `3.19.1`, `3.190.0` and `3.20.0` are all incompatible until a reviewed amendment admits them with evidence) |

The window is **valid** iff it has no reason. In an invalid window no delta is usable: no `OBSERVED_USAGE`, no `MEASURED_ZERO`, counts are `null`.

For a valid window each exact series yields one status:

| Status | Condition | Delta |
|---|---|---|
| `DELTA` | present at both boundaries, `end >= start` | `end - start` (may be 0) |
| `DECREASED` | present at both, `end < start` | none |
| `DELTA_FIRST_IN_WINDOW` | absent at start, present at end, **and** the window has no reason, `start_stable_seconds >= 20` (the reviewed threshold; the ~14 s publication lag measured in I2.2a plus margin), the series' Route is `true` in `route_coverage`, and `consumer` ∉ `disabled_labels` | the end value (the start sample is read as 0) |
| `ONE_BOUNDARY_END` | absent at start, present at end, preconditions of the row above not met | none; a missing boundary is not read as 0 |
| `ONE_BOUNDARY_START` | present at start, absent at end | none; never repaired (a counter cannot vanish without a restart or reset) |

A series absent at both boundaries does not exist; no zero-valued series is manufactured. *Amended in I2.2a (review of #524, I2 spec §5 amended with it):* the `DELTA_FIRST_IN_WINDOW` reading is what lets a consumer's first request in a window establish usage; it never applies in an invalid window and never to a series seen at the start.

## 4. Carriers, ids and fields (internal only)

All ids use `ld` and lowercase hex SHA-256. Consumer and Route ids are the frozen I1 formulas (`gateway-consumer:owned:…`, `gateway-route:owned:…`).

| Carrier | Id | Notes |
|---|---|---|
| Measurement window | `measurement-window:owned:<sha256(ld(gateway_instance_id, environment, window_start, window_end, start_sha256, end_sha256))>` (M04) | fields: those inputs, `apisix_version`, the settled / no-restart / stable-seconds fields, `disabled_labels`, per-Route coverage as canonical JSON, the sorted window reasons (empty = valid) |
| Measurement evidence | `evidence:apisix-measurement:<same inputs as the window>` (M05) | `evidence_type = OBSERVED`; an internal carrier, **not** a public `:Evidence` node (same reasoning as I1's `GatewaySourceEvidence`) |
| `MeasurementSeries` (*refined in I2.2b; replaces the unstored “source-series carrier”*) | `measurement-series:owned:<sha256(ld(window id, series key))>` (M10); the series key is the full label string between the braces | one per series present at either boundary, whatever its status, so the consumer/route pairs of the §7 row universe survive (*amended in I2.2b after the review of #526*): the I2 §6 fields (`gateway_instance_id, environment, window_start, window_end, route, consumer, code, response_source`), `status` (§3, or `WINDOW_INVALID` for every series of a window with a reason), `request_count_delta` (only for `DELTA` / `DELTA_FIRST_IN_WINDOW`, else null), every label as canonical JSON, the evidence id |
| `MeasurementLimitation` (*I2.2b*) | `measurement-limitation:owned:<sha256(ld(window id, code, route, response_source))>` (M11) | one per `(code, route, response_source)` for series without a usable delta in a valid window (`GWM_SERIES_ONE_BOUNDARY`, `GWM_COUNTER_DECREASED`), for the route-wide coverage downgrade (§7); holds a route id, never a count or value. None are stored for an invalid window (its reasons are on the window carrier) |
| `MeasurementMappingEntry` (*I2.2b*) | `measurement-mapping:owned:<sha256(ld(gateway_instance_id, environment, kind, source id, target id))>` (M12, M13) | one per mapping-artifact entry (`route_operation`, `target_service_route`, `target_service_service`); an exact repeat collapses, a disagreement stays as two entries for I2.3 |
| `ObservedConsumerInteraction` | `observed-consumer-interaction:owned:<sha256(ld(consumer id, route id, environment, window_start, window_end))>` (M06–M08) | fields: ids, `upstream_request_count`, `rejected_attempt_count`, `evidence_ids`; no cross-window identity (M07) |
| Qualification row | `usage-qualification:owned:<sha256(ld(consumer id, route id, environment, window_start, window_end))>` (M09) | the domain prefix keeps it distinct from the interaction id over the same inputs |

`SourceType` is not widened; no relationship to public entities (I2 §11, I3 decides exposure).

## 5. Mapping artifact (`aip-apisix-mapping/1`)

Optional file `apisix-mapping.json` in the measurement source root. Absent = no explicit mappings (not an error). UTF-8 JSON:

~~~text
{ "schema": "aip-apisix-mapping/1",
  "gateway_instance_id": "<must equal the registration's>",
  "route_operation": [ { "route_id": "<APISIX Route id>", "operation_id": "<Operation.id>" } ],
  "target_service":  [ { "kind": "route" | "service", "id": "<APISIX id>", "service_id": "<canonical Service.id>" } ] }
~~~

Entries have exactly these fields, all non-empty strings; any violation is `REJECTED_INVALID` / `GWM_MAPPING_INVALID`; wrong schema `GWM_SCHEMA_UNSUPPORTED`; wrong gateway `GWM_INSTANCE_MISMATCH` (manifest-rejections.json Y01–Y06). Duplicate entries are not rejected: they are reconciliation inputs (§6).

## 6. Reconciliation rules (vectors J, K, T)

Outcomes (not public wire vocabulary): `RESOLVED`, `UNRESOLVED`, `AMBIGUOUS`, `CONFLICT`.

**Runtime joins (J01–J06).** `consumer` label resolves iff non-empty, equal to a `GatewayConsumer.username` (exact, case-sensitive, no trimming), same gateway instance and environment. `route` label resolves iff equal to a `GatewayRoute.route_id` of the same gateway instance and environment. Else `UNRESOLVED`; the series stays source evidence.

**Route → Operation (K01–K17).**
1. *Statements*: all explicit `route_operation` entries naming the Route. Two or more distinct `operation_id`s → `CONFLICT`. Exactly one → `RESOLVED` if the Operation exists, else `UNRESOLVED` (dangling). Explicit statements are authoritative; the fallback is not consulted and is not compared with them (K04).
2. *Fallback (no statement)*: only when the Route has a non-empty `uri`, an empty `uris`, and the `uri` contains no `*`. Candidates are Operations (across all OpenAPI sources) whose `path` equals the `uri` exactly, with, when the Route lists `methods`, an Operation `method` among them (both ASCII-upper-cased). Exactly one → `RESOLVED`; none → `UNRESOLVED`; several → `AMBIGUOUS`. No base-path stripping, no template or pattern conversion.
3. *Contract chain*: evaluated only when the Operation is `RESOLVED`, from its `OPERATION_IN_CONTRACT_VERSION` associations: none → `UNRESOLVED`, one distinct version → `RESOLVED`, several distinct → `CONFLICT`. A resolved Operation with an unresolved contract chain stays resolved.

**Target → application Service (T01–T14).** *Statements* about a Route's target are: `target_service` entries with `kind=route, id=<Route id>`; entries with `kind=service, id=<its referenced Gateway Service id>`; label `aip/service` on the Route; label `aip/service` on its referenced Gateway Service. The label key is exactly `aip/service`. Two or more distinct `service_id`s → `CONFLICT` (including a single object mapped twice, T13). Exactly one: `RESOLVED` if a canonical `Service.id` equals it, else `UNRESOLVED`. None → `UNRESOLVED`. Entries for unrelated objects are not statements (T14). No similarity of any kind.

**Independence (T15, T16).** The two chains never read each other's result.

## 7. Coverage and qualification (vectors Q)

**Coverage** is evaluated per Route and is route-wide (owner decision, 2026-10-13). Route `R` is `SUFFICIENT_FOR_ZERO` iff all hold: the window is valid; `R` is present in `route_coverage` and `true`; `consumer` ∉ `disabled_labels`; **no upstream series on `R`** is `DECREASED`, `ONE_BOUNDARY_*`, or unattributed (empty `consumer`, or a `consumer` that does not resolve to a known `GatewayConsumer`). Otherwise `UNKNOWN_COVERAGE`. Only `response_source="upstream"` series affect coverage and usage state; `apisix`-source series contribute only to `rejected_attempt_count` (Q10, Q12). Limitation codes explaining `UNKNOWN_COVERAGE` for a row: the window reasons when the window is invalid (and only those), else any of `GWM_CONSUMER_LABEL_DISABLED`, `GWM_ROUTE_COVERAGE_ABSENT`, `GWM_ROUTE_PROMETHEUS_DISABLED`, `GWM_COUNTER_DECREASED`, `GWM_SERIES_ONE_BOUNDARY`, `GWM_UNATTRIBUTED_UPSTREAM` that apply to the row's Route.

**Universe.** Configured `(consumer, route)` pairs ∪ pairs with at least one series whose consumer **and** route resolve (any status, any source). Series for an unknown Route, or an unattributed consumer, create no row (Q20). Rows are ordered by `(consumer, route)`.

**Row fields.** `configured_status` ∈ {`CONFIGURED_ACCESS_ESTABLISHED`, `NO_MATCHING_CONFIGURED_ACCESS_FACT`}; `usage_status`; `coverage` (the Route's); `upstream_request_count` = sum of valid upstream deltas over the pair's series, `rejected_attempt_count` = sum of valid `apisix`-source deltas (both `null` in an invalid window); `limitations` (sorted codes).

**Usage status** (first match wins):

1. window valid and `upstream_request_count > 0` → `OBSERVED_USAGE` (positive attributed delta wins even when other series on the Route are broken, Q18; it needs no Route coverage);
2. window valid, pair **configured**, Route `SUFFICIENT_FOR_ZERO` → `MEASURED_ZERO` (no series, or only zero-delta upstream series, or only rejected attempts: Q02, Q03, Q10);
3. otherwise `USAGE_UNESTABLISHED` — in particular any pair without a configured fact and without positive usage (Q09), any invalid window (Q21, Q22), and any pair on a Route with `UNKNOWN_COVERAGE` (Q04–Q08, Q11, Q13, Q15–Q17).

A row never changes the configured-access status from runtime evidence, and rejected attempts never create a configured fact (N2). `NO_MATCHING_CONFIGURED_ACCESS_FACT` is not a denial or policy finding.

## 8. Diagnostics and outcomes

| Code | Outcome |
|---|---|
| `GWM_MANIFEST_INVALID`, `GWM_BINDING_MISMATCH`, `GWM_EXTRACT_INVALID`, `GWM_INSTANCE_MISMATCH`, `GWM_MAPPING_INVALID` | `REJECTED_INVALID` |
| `GWM_SCHEMA_UNSUPPORTED`, `GWM_LIMIT_EXCEEDED` | `REJECTED_UNSUPPORTED` |
| `GWM_DUPLICATE_SOURCE` | `REJECTED_CONFLICT` |
| window reasons and row limitation codes (§3, §7) | informational: one `GWM_MEASUREMENT_LIMITATIONS` diagnostic with a count, no values; the source is `ACCEPTED_WITH_LIMITATIONS` when any exists |

*I2.2b reading (the contract was silent):* an absent required file is rejected with that file's own code - manifest `GWM_MANIFEST_INVALID`, either extract `GWM_EXTRACT_INVALID` - before any content check; a required file that resolves outside the registered root counts as absent; the mapping artifact is optional. File-size bounds are checked before any file is parsed (`GWM_LIMIT_EXCEEDED`). The source's `content_sha256` is the length-delimited digest of the manifest, both extracts and the mapping bytes (empty when absent).

Messages never include extract or manifest values beyond ids, Route ids and consumer usernames already in the inventory. How these appear in the import report is an I2.2 decision (it must amend `aip-import-report/1` additively, as I1.4 did).

## 9. Case-to-test map (I2 §9.3, §13)

| I2 case | Vector | Slice that proves it against production code |
|---|---|---|
| P1, P2 (no series and zero-delta series), N1 (unsettled, restart, label disabled, route absent, Prometheus disabled), N2, N3 (+ rejected, unknown consumer), N4 | Q01–Q14 | I2.4 |
| one-boundary, decreased, route-wide downgrade, positive wins, observed-only, unknown Route, invalid window, multi-code sum, bounded universe | Q15–Q24 | I2.4 |
| same username on two instances; environment mismatch | J03, J04, X02, X03 | I2.3 (joins), I2.2 (registration binding) |
| unknown Route unresolved | J05, Q20 | I2.3 |
| conflicting Route/Operation; conflicting target-Service | K03, T06, T07, T13 | I2.3 |
| unambiguous exact fallback; ambiguity; no base-path/wildcard | K05–K13 | I2.3 |
| independence of the two chains | T15, T16 | I2.3 |
| manifest, binding, normalization, schema | X01–X19, X22 | I2.2 |
| one window per source; one source per `(gateway, environment)` | X20, X21 | I2.2 |
| mapping artifact | Y01–Y06 | I2.2 (parse), I2.3 (use) |
| window validity | W01–W11 | I2.2 (flag), I2.4 (use) |
| ids | M01–M09 | I2.2 (source, window, evidence), I2.4 (interaction, row) |

## 10. Not frozen here

Capture-tool CLI shape and settle timeout defaults (I2.2); writer Cypher and constraints (I2.2–I2.4); the `api_usage_v1` snapshot block layout (I2.4); import-report amendment (I2.2); exact Python class layout; public exposure, consumer-name exposure and `SourceType` widening (I3); restart or counter-reset inference (not in v0.7).

## 10.1 Findings from the I2.2a real-APISIX run (no contract semantics changed)

- **Counter lag is longer than the settle rule's natural poll interval.** (Bound into the manifest in I2.2a after the review of #525: `start_stable_seconds` / `end_stable_seconds` record the stability the tool actually observed, and the first-in-window reading requires `start_stable_seconds >= 20`, so a fixture captured under the bare two-scrape rule cannot license it.) Against digest-pinned APISIX 3.19.0 in etcd mode, `apisix_http_status` series appeared ~14 s after the requests; scrapes taken seconds apart were identical (and empty) throughout the lag, so "two consecutive identical scrapes" alone settled on the wrong extract. The capture tool therefore requires the two identical scrapes to be at least a quiet period apart (`--quiet-seconds`, default 20 s; the bare rule is `0`). The manifest and every validation rule are unchanged: `*_settled = true` still means "stable", only the tool's evidence for it is stronger.
- **A series first created inside the window has no start-boundary sample.** The real run showed it: the 401 series, created by the window's own traffic, existed at the end boundary only. Read strictly (a missing boundary is never 0) a consumer's first request in a window could not establish usage; the only positive case in the run worked because a readiness request before the start boundary had already created the series. The review of #524 asked for an amendment rather than an accepted limitation, so §3 now reads such a series as starting at 0 (`DELTA_FIRST_IN_WINDOW`) under the stated preconditions, and keeps `ONE_BOUNDARY_END` otherwise. I2 spec §5, §8 and §14 are amended to match; vectors F01–F12, X23–X25 and Q15/Q18/Q25–Q30 changed accordingly.

## 11. Interpretations to confirm in review

These are readings the I2 spec leaves open; they are frozen here only if this PR is accepted as written:

1. Normalized label order is alphabetical (§2.1).
2. Gateway/environment mismatch is a rejection, while the other window preconditions are limitations (§3).
3. `response_source` is a closed set (§2.1).
4. A decreased or one-boundary series downgrades coverage for the whole Route (§7, owner decision).
5. Positive usage wins over broken series elsewhere on the Route (§7 step 1).
6. In an invalid window, attributed pairs still get rows, with `USAGE_UNESTABLISHED` and `null` counts (§7).
7. Explicit Route→Operation statements are not cross-checked against the fallback (§6).
8. Version compatibility is exactly `3.19.0`, the inspected release, not the whole `3.19.*` line (§3; review of #522).
9. A series first created inside a valid, covered window whose start boundary was recorded stable for at least 20 s is read as starting at 0 (§3, amended in I2.2a; evidence-binding added after the review of #525). The recorded duration is the capture tool's attestation, not something replay can re-derive.
10. Missing-file codes (§8) and the refined measurement carriers (§4, M10–M13) are I2.2b readings of a contract that was silent on them.
