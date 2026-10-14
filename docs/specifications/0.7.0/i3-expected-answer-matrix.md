# AIP v0.7.0 I3 — Independent Expected-Answer Matrix (I3.1c)

**Status:** I3.1c deliverable (I3 spec §12, §13 "I3.1"; decision record D11). It freezes the independently authored expected public answers for `get_api_consumer_usage` **before** any I3.2 semantic code. The oracle is [`i3-vectors/expected-answers.json`](i3-vectors/expected-answers.json). It is written by [`i3-vectors/author_expected_answers.py`](i3-vectors/author_expected_answers.py), which uses the standard library only and imports nothing from `app`, so no expectation comes from the code it qualifies. It is read-only for implementers: an implementation that disagrees is fixed, or the disagreement goes back to the specification (I3 stop condition). The expectation is never rewritten to match.  
**Governing:** [I3 specification](i3-api-aware-current-state-projection-and-public-answer.md) §12, [decision record](i3-decision-record.md) D1–D12, the [v0.7 schemas](../../../schemas/architecture_intelligence/v0.7/), the frozen [I2 → I3 handoff](i2-i3-handoff.md).  
**Machine check:** `tests/unit/test_v070_i3_expected_answers.py` checks the oracle:
- it is reproduced byte for byte by its author;
- the author imports only the standard library;
- the author's identifier formulas reproduce the frozen I1 (V01, V03) and I2 (M01, M04–M06) vectors, and its D8/D9 derivations equal the models' own helpers;
- every answer, once its wildcards are instantiated (§2), is a valid 0.7 answer under **both** Pydantic and the published schema, is bound to the current snapshot of its world, and echoes its request context;
- every request case is rejected by Pydantic, and by the schema unless it is listed as Pydantic-only;
- every property case holds and is not vacuous; the credential canary is in the world and in no expected payload;
- the evidence cases cover all five kinds and a `NOT_RESOLVED` entry; the refusal cases cover all five query refusal codes;
- this table lists the I3 §12 rows S01–S20, cites only existing cases and cites every case.

**Not claimed:** this checks the oracle's own consistency, not an implementation. I3.2 executes it against the service, I3.3 against REST and MCP, and I4 re-runs it on two clean states.

## 1. Case kinds

| Kind | Content | Used by |
|---|---|---|
| `answer` | `inputs` (a `world` and the `current_snapshot` label), the exact `request` and the complete expected `ApiConsumerUsageAnswer` | I3.2 service tests (`mode: query` and `evidence`), I3.3 adapter tests |
| `property` | `steps` (case ids) and machine-readable `assert` items with an `op` (`pages_concatenate_to`, `no_duplicate_rows`, `suffix_of`, `row_count`, `differ`, `disjoint_rows`, `absent_everywhere`, `present_in_world`); every item has a description and a non-empty cardinality guard, so no property case can pass vacuously | Paging, cross-gateway and canary rows that one literal answer cannot state |
| `request` | A request that must be a validation error (REST 422, MCP validation error; D3). A `pydantic_only` note marks the few rules the JSON Schema cannot express (D12.12) | I3.3 adapters; the model tests |

## 2. Matching procedure (normative for every harness that executes the oracle)

1. **Literal values.** Every id, query digest, evidence ref, cursor, count, status, code and order in an expected answer is a literal. They are fixed by the frozen rules and by the world's inputs (a synthetic snapshot id is an *input*), so there is no run-dependent symbol.
2. **One wildcard.** The string `{{*}}` matches any **non-empty** string and binds nothing. It is used only where the record leaves the text to I3.2: limitation `message` (D12.3) and `producer.version` / `producer.build_revision`.
3. **Exact equality** otherwise: lists are compared positionally, because every list in the contract is sorted and duplicate-free and the validators enforce it.
4. **Instantiation for validation.** To check that an expected answer is itself a valid 0.7 answer, each wildcard is replaced by `"x"`. This is the `instantiate()` of the machine check; it is not a match against a run.
5. **Execution against an implementation.** The harness loads the case's `world.snapshot_state` (§3) as the snapshot state, injects the snapshot id of `inputs.current_snapshot` (so the refs, which are snapshot-bound, are the literals), calls the service with `request`, and requires the actual answer to equal `expected` under rules 1–3 **and** to pass `ApiConsumerUsageAnswer` and the published schema. Property cases hold when every `assert` item holds over the executed steps. For a world with `current_snapshot` ≠ the request's snapshot, the harness makes that snapshot current.
6. **Authority.** The author composes each answer by hand from the world: each case names the Routes and the `(consumer, Route)` pairs it contains, and the counts, limitation codes and outcome it expects. The author's helpers derive identifiers and compose JSON only; they select, filter and qualify nothing.

## 3. Worlds

Each world in `expected-answers.json` serializes as `{"snapshot_state", "internal_only"}`. `snapshot_state` is the **exact frozen handoff state** ([handoff §1](i2-i3-handoff.md)) in the repository's own section and row shapes, so I3.2 loads it as the snapshot state and translates nothing:

- `gateway_configuration_v1`: `consumers`, `routes`, `services`, `configured_access`, `limitations`, `source_evidence`;
- `api_usage_v1`: `windows`, `evidence`, `series`, `limitations`, `mapping_entries`, `attributions`, `reconciliation_rule`, `route_operation`, `target_service`, `qualification_rule`, `coverage`, `interactions`, `qualification_rows`;
- `api_contracts_v1`: `contracts`, `versions`, `associations`; and the canonical `operations` and `services`.

Nothing is produced by AIP execution. The columns of every raw section are checked against the repository's snapshot queries, and the id formulas against the I1 and I2 vectors. The window is the I2 vector window (`gw-prod-1`, `prod`, 2026-10-13T10:00:00Z – 10:10:00Z, extract digests of `i2-vectors` M04).

**Cross-check of the derived sections.** The machine check applies the I2 rules (`reconcile`, `qualify`) to each world's raw facts and requires `attributions`, `route_operation`, `target_service`, `coverage`, `interactions` and `qualification_rows` to equal what the rules derive. This is a check of the *input*, not of the expected answers. Two route-wide limitation codes are stated directly in the world's `coverage` instead of through raw series: `GWM_COUNTER_DECREASED` (legacy-route) and `GWM_UNATTRIBUTED_UPSTREAM` (the `unattributed` world). For those the check injects the series that produce the code and ignores the extra rows they create. `series` and `attributions` are otherwise present only for pairs that have an interaction. `internal_only` is a harness-only input and not snapshot state: the credential canary stands for the plugin configuration of a Consumer and a Route, which never reaches the graph.

**`base`.** Gateway `gw-prod-1` (and a second gateway `gw-prod-2` with the same environment and window, for A14/A18).

| Route (`gw-prod-1`) | Route → Operation | Target Service | Coverage |
|---|---|---|---|
| `orders-route` | `RESOLVED` `listOrders` (explicit entry) | `RESOLVED` `service:orders` (Route label) | sufficient |
| `orders-v2-route` | `RESOLVED` `listOrders` (explicit entry) | `RESOLVED` `service:orders` (Gateway Service label) | sufficient |
| `billing-route` | `RESOLVED` `listInvoices` (explicit entry) | `RESOLVED` `service:billing` (explicit entry) | sufficient |
| `legacy-route` | `UNRESOLVED` | `UNRESOLVED` | unknown: `GWM_COUNTER_DECREASED` (stored limitation carrier) |
| `nocov-route` | `UNRESOLVED` | `UNRESOLVED` | unknown: `GWM_ROUTE_COVERAGE_ABSENT` (no carrier) |
| `bare-route` | `UNRESOLVED` | `UNRESOLVED` | sufficient |
| `conflict-route` | `UNRESOLVED` | `CONFLICT` (Route label `service:orders` vs Gateway Service entry `service:billing`) | sufficient |
| `other-route` (`gw-prod-2`) | `RESOLVED` `listOrders` | `RESOLVED` `service:orders` | sufficient |

Operations: `listOrders`, `getOrder` (no Route resolves to it), `listInvoices`. Services: `service:orders`, `service:billing`. Consumers `spike-alpha`, `spike-beta`, `spike-gamma` on `gw-prod-1` and `spike-alpha` on `gw-prod-2`. Pairs: alpha×orders configured, observed 3; alpha×orders-v2 configured, measured zero; alpha×legacy configured, unestablished; alpha×bare configured, measured zero; beta×orders not configured, observed 2; beta×billing not configured, rejected attempts only (0 upstream, 2 rejected); beta×conflict configured, measured zero; gamma×billing configured, measured zero; alpha(`gw-prod-2`)×other configured, observed 7. The `internal_only` block holds the credential canary (D7); it is a harness input, never an answer field.

**Variants.** `unattributed` (A10: unattributed upstream traffic on `orders-route`, one configured pair), `not-settled` (A11: end boundary unsettled, window reason `GWM_WINDOW_NOT_SETTLED`, every Route's limitation is the window reason), `reversed` (A20: `window_start` after `window_end`, reason `GWM_WINDOW_ORDER_INVALID`), `no-measurement` (A13: configured gateway, no accepted window), `new-snapshot` (A16, A17, E02c: an unrelated import made snapshot B current; the data is unchanged).

## 4. I3 §12 rows

| Row | Requirement (I3 §12) | Cases | Status | Note |
|---|---|---|---|---|
| S01 | configured + observed | A01 | COVERED | `CONFIGURED_ACCESS_ESTABLISHED` + `OBSERVED_USAGE`, 3 upstream |
| S02 | configured + measured zero | A02 | COVERED | `MEASURED_ZERO`, `SUFFICIENT_FOR_ZERO` |
| S03 | configured + insufficient measurement | A03 | COVERED | `USAGE_UNESTABLISHED`, `COVERAGE_UNKNOWN`; the stored limitation carrier gives the Route a distinct ref (D12.13) |
| S04 | observed-only | A04 | COVERED | `NO_MATCHING_CONFIGURED_ACCESS_FACT` + `OBSERVED_USAGE`; no `CONFIGURED_ACCESS` ref |
| S05 | rejected attempt only | A05 | COVERED | no usage established, rejected count only |
| S06 | unresolved Route → Operation | A06 | COVERED | row kept, `api.reconciliation = UNRESOLVED`, no `operation_id` |
| S07 | conflicting target Service | A07 | COVERED | `application_service.reconciliation = CONFLICT`, no `service_id` |
| S08 | exact Operation target | A08 | COVERED | only the Route resolved to the Operation; the summary counts all seven scope Routes |
| S09 | exact Service target | A09 | COVERED | only the Route independently resolved to the Service; `conflict-route` is excluded and counted as `conflict` |
| S10 | unattributed traffic | A10 | COVERED | no consumer row invented; `GWM_UNATTRIBUTED_UPSTREAM` visible on the Route |
| S11 | empty rows + invalid window | A11, A20 | COVERED | `rows: []` with `window.valid = false`, reasons, `WINDOW_NOT_VALID`; A20 shows a reversed window stays addressable and omits counts |
| S12 | selected Route + no pair rows | A12 | COVERED | `rows: []`, Route coverage and limitation visible |
| S13 | gateway with no measurement source | A13 | COVERED | `NOT_ANSWERED` / `MEASUREMENT_WINDOW_NOT_AVAILABLE`, `data` null |
| S14 | same env/window on two gateways | A14, A14b, A14c | PROPERTY | `gateway_instance_id` selects exactly one window; sources differ; rows are disjoint |
| S15 | page boundary | A15a, A15b, A15c, A15d, A15e, A15 | PROPERTY | stable cursor, no duplicate or lost row for unmodified cursors; a substituted well-formed `after` returns only later rows of the same selection; a cursor bound to other inputs is `CURSOR_QUERY_MISMATCH` |
| S16 | unrelated import during paging | A16 | COVERED | old cursor → `SNAPSHOT_NOT_AVAILABLE` with the current snapshot |
| S17 | stale snapshot | A17 | COVERED | `SNAPSHOT_NOT_AVAILABLE` |
| S18 | evidence drill-down | E01a, E01b, E01c | COVERED | the recomputed ref resolves to the sanitized payload of its kind (all five kinds; a conflict exposes only the raw statements; no `basis`) |
| S19 | forged/cross-snapshot evidence ref | E02a, E02b, E02c | COVERED | forged, cross-snapshot and cross-context refs are indistinguishable `NOT_RESOLVED`; a stale evidence snapshot is refused |
| S20 | credential canary | C01 | PROPERTY | absent from every expected answer and evidence payload; I3.3 repeats it over REST and MCP transcripts |

## 5. Further cases (decision record D6, D3)

| Case | Content |
|---|---|
| A18a | `UNKNOWN_TARGET`: a well-formed Service id that is not in the snapshot |
| A18b | `TARGET_NOT_IN_WINDOW_SCOPE`: an existing Route of `gw-prod-2` requested under `gw-prod-1` |
| A19 | `NO_ROUTE_SELECTED` with data: a known Operation (`getOrder`) no Route resolves to; the summary shows why |

## 6. Request validation cases

| Case | Request | Rejected by |
|---|---|---|
| V01 | Service target with an Operation id | both |
| V02 | Operation target that is a display name | both |
| V03 | Route target with a short digest | both |
| V04 | empty `gateway_instance_id` | both |
| V05 | `gateway_instance_id` with trailing whitespace | both |
| V06 | environment of 129 characters | both |
| V07 | window start that is not whole-second UTC | both |
| V08 | `limit` 0 | both |
| V09 | `limit` 201 | both |
| V10 | cursor without `snapshot_id` | Pydantic only (cross-field) |
| V11 | cursor that is not an API usage cursor | Pydantic only (cursor decoding) |
| V12 | cursor in a non-canonical encoding | Pydantic only (canonical form) |
| V13 | consumer filter that is a username | both |
| V14 | unknown field (a Cypher fragment) | both |
| V15 | credential-like field | both |
| V16 | unknown mode | both |
| V17 | evidence refs not sorted | Pydantic only (order) |
| V18 | duplicate evidence refs | both |
| V19 | no evidence refs | both |
| V20 | 21 evidence refs | both |
| V21 | evidence request without `snapshot_id` | both |
| V22 | evidence request with a `limit` | both |

A reversed window is **not** a validation error: it is the answer case A20.

## 7. Use by the next slices

- **I3.2** executes every `answer` and `property` case against `ArchitectureIntelligenceService` on the world snapshot states, with the snapshot id injected (§2.5).
- **I3.3** executes the same cases over REST and MCP, adds the `request` cases to the adapters, and repeats C01 on the transport transcripts.
- **I3.4/I4** re-run the oracle on two clean states. Any change to an expectation needs a reviewed amendment of this matrix and of the decision record it traces to.
