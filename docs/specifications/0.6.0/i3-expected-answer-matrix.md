# AIP v0.6.0 I3 — Independent Expected-Answer Matrix (I3.1c)

**Status:** I3.1c deliverable (I3 spec §14, §15 I3.1 row; decision record D15). It freezes the independently authored expected answers for the public locality contract **before** any I3.2 semantic code. The oracle is [`i3-vectors/expected-answers.json`](i3-vectors/expected-answers.json). It is written by [`i3-vectors/author_expected_answers.py`](i3-vectors/author_expected_answers.py), which uses the standard library only and imports nothing from `app`, so no expectation comes from the code it qualifies. Like the I1 oracle, it is read-only: an implementation that disagrees is fixed, or the disagreement goes back to the specification (I3 §17 stop condition). The expectation is never rewritten to match.  
**Governing:** [I3 specification](i3-bounded-current-state-projection-and-public-answers.md) rev 0.2, [decision record](i3-decision-record.md) D1–D16, the [v0.6 schemas](../../../schemas/architecture_intelligence/v0.6/).  
**Machine check:** `tests/unit/test_v060_i3_expected_answers.py` checks the oracle:
- it is reproduced byte for byte by its author;
- the author imports only the standard library;
- every full answer, once instantiated (§2.4), is a valid 0.6 answer under **both** Pydantic and the published schema;
- every request case is rejected;
- this table lists the I3 §14 rows S01–S15, cites only existing cases and cites every case.

**Not claimed:** this checks the oracle's own consistency, not an implementation. I3.2/I3.3 execute it, and I4 re-runs it on two clean states. The rehearsal rows are a replay of I2.6a, **not** I5 evidence.

## 1. Case kinds

| Kind | Content | Used by |
|---|---|---|
| `answer` | `inputs` (world, fixture), the exact `request`, and the complete expected `LocalityAnswer` | I3.2 service tests (`mode: query`), I3.3 evidence-mode and surface tests |
| `property` | `inputs`, ordered `steps` and machine-readable `assert` items (`path` with `equals`, `at_least`, `at_most`, `all_equal`, `contains`, `subset_of`, `equals_step`, `not_equals_step` or a stated `equals_expr`; `len(...)` paths are non-empty cardinality checks, so no property case can pass vacuously) | Multi-page, generated-cardinality and cross-reader rows that one literal answer cannot state |
| `request` | A request that must be a validation error (REST 422, MCP validation error; D9) | I3.3 adapters; the model tests |

## 2. Matching procedure (normative for every harness that executes the oracle)

1. **Literal values.** IDs computable from frozen rules are literal: v2 IDs (I1 v2 contract §2) and assertion IDs (I2 D9/D14.1), together with every request-derived value and every disposition, reason, code, count and order.
2. **Symbols.** A string `{{NAME}}` is a placeholder for a value only the run knows.
   - **Scalars:** `SNAPSHOT_ID`, `MODEL_REVISION`, `PRODUCER_VERSION`, `BUILD_REVISION`, `ASSESSMENT:<label>`, `WORKLOAD_ID:<label>`, `DECLARED:<label>`, `FIRST_SEEN:<label>`, `LAST_SEEN:<label>`.
   - **Pre-bound** by the harness from the built fixture **before** matching: `SOURCE:<capture>` (the capture's `source_instance_id`), and in requests `REF:<what>`, which names the fixture's own evidence ID of that kind (`DECLARED`, `V1`, `K8S_POD`).
   - **Spread:** a list element `{{...NAME}}` stands for **one or more** values, bound as a set. `K8S:<capture>/<pod>` is the Kubernetes Pod and owner evidence refs of that Pod in that capture, whose count is an importer detail.
   - **Wildcard:** `{{*}}` matches any non-empty string and binds nothing. It is used only for limitation `message`.
   - **Binding:** a symbol binds on first use, and every later use must equal it. Distinct names bind distinct values. `SNAPSHOT_ID` and `MODEL_REVISION` must carry the same digest (`SnapshotRef`).
3. **Sets.** A list whose contract sort key contains a symbol is compared as a set after binding. Its actual order is already enforced by the contract validator, which must also pass. Every other list is compared positionally.
4. **Instantiation for validation.** To check that an expected answer is itself a valid 0.6 answer, each symbol is replaced by a distinct, syntactically valid stand-in, and a spread symbol by one value. Lists with symbols are then re-sorted by their contract key. This is the procedure `instantiate()` in the machine check implements; it is not a match against a run.
5. **A match.** An actual answer matches when an injective binding exists under which it equals the expected answer (rules 1–3). The answer must also pass `LocalityAnswer` and the published schema. Property cases match when every `assert` item holds.

## 3. Worlds and inputs

- **Rehearsal (X01–X03, P08):**
  - Source: the I2.6a recording `tests/fixtures/locality/rehearsal/` (REHEARSAL – NOT I5).
  - Each capture is replayed into its own clean state: declarations, then one capture, then `otlp.jsonl`, with the flag on (as `test_locality_rehearsal_replay.py` does).
  - Pod, Workload and cluster UIDs come from the recorded envelope and identities, not from AIP output.
  - The span time bounds are `FIRST_SEEN`/`LAST_SEEN` symbols.
- **World K (all other cases):** a synthetic world that every case's `inputs` spell out.
  - **Captures:** A, B, C and X (cluster, namespaces, revision, `capturedAt`, Pods and owners). X captures P1's UID in cluster K2 (I2 D4 S04).
  - **v2 records:** given by key fields, CLIENT Resource and spans, from which v2 `first_seen`/`last_seen`/count/samples follow (I1 v2 contract §3).
  - **Declarations:** `service:orders` CALLS O1 is declared, and O1 is declared by `service:pricing`. O2 and O3 are owned through observed `PROVIDES` (SERVER spans).
- **Disclosed graph adjustments (X05, X06):** the missing-owner Operation O4 has a `PROVIDES` edge whose evidence does not resolve, and the ambiguous Operation O5 has two evidenced providers. Real ingestion may not produce these states, so the harness writes them directly and says so. They are D8 negative fixtures, not observed systems.
- **Generated inputs (X25, P01–P04, P09):** explicit, deterministic templates in `inputs`, where `n` runs over the stated range. Expected values are stated as properties (counts, page size, cursor position, cardinalities), not as thousands of literal entries.
  - `generated_captures` adds accepted K2 captures `G{n}` with their own namespace and no Pods. They raise `S` without forming a pair.
  - `generated_pods` imports each generated caller Pod **and** its `WORKLOAD_OWNS_POD` owner into the named capture (A), with a stated UID, name and owner (one shared Workload, or Deployment `orders-w{n}` per Pod for P03), so I2 resolves every generated candidate (PR #388 review).
  - `generated_v2` gives one v2 per generated Pod.

## 4. I3 §14 rows

| Row | I3 §14 requirement | Cases | Status | Note |
|---|---|---|---|---|
| S01 | Two actual caller Workloads | X01, X02 | COVERED | Rehearsal C1: W1 → O1 `CONFIRMED`, W2 → O2 `OBSERVED_ONLY`, two localities of one Service, target `UNKNOWN` |
| S02 | Same provider, two Operations | X04 | COVERED | One `service:pricing` group, members O1 + O3, `member_qualifications` both, no pooled label (D8) |
| S03 | Missing/ambiguous provider | X05, X06 | COVERED | `PROVIDER_OWNER_MISSING` / `_AMBIGUOUS` entries, no provider group, `PARTIAL` (D8, D9) |
| S04 | No v2 / refused attribution | X07, P06 | COVERED | `NOT_ANSWERED` / `INSUFFICIENT_EVIDENCE` with the empty inventory (Q1); a refused CLIENT never yields v2, so it is the X07 input state; v0.5 unchanged per P06 |
| S05 | Wrong day / environment | X08, X09 | COVERED | Phase-3 `INAPPLICABLE` candidates stay listed (L10b, L17d) |
| S06 | Two captures / source selection | X10, X11, X12, X13, X14 | COVERED | Missing-Pod source as a pair limitation; unrelated capture not a pair; explicit selector; stale selector = implicit no-cover (D13.3); conflicting source not preferred |
| S07 | Pod churn C1 → C2 | X03, P08 | COVERED | Retained P1 v2 `UNRESOLVED` [`LOCALITY_CAPTURE_MISSING_POD`]; a C1 snapshot is refused after C2 |
| S08 | Complete and incomplete inventory | X12, X13, X24, P02, P04 | COVERED | Counts equal listed items; two pages on one snapshot, and the final continuation page stays `PARTIAL` (D16.11); a non-current `snapshot_id` and cursor misuse are refused |
| S09 | I2 page or I3 presentation cap splits a Workload group | P01, P02, P03, X25 | PROPERTY | `k = 400` at `S = 5`; I2 truncation; Workload cap with `i2_truncated = false`; `S > 2,000` fails closed before reading (D4, D6) |
| S10 | Selected comparison | X02, X14, X15, X16, X19, P09, Q03, Q04, Q08 | COVERED | Positive-only differences; `EVALUATED_NO_POSITIVE` (R5); invented `UNKNOWN` (R4); phase-3-only `UNKNOWN` (R6b); `in_both`; `PARTIAL` (R6); malformed compare requests |
| S11 | Unsupported scope/relations | X20, X21, X22, X23 | COVERED | `UNSUPPORTED_REQUEST` with the I2 `LOCALITY_UNSUPPORTED_*` reason; no local absence |
| S12 | Scoped drill-down | X26, X27, X28, P05, P06, Q05 | COVERED | v2 resolves, another caller's is `NOT_FOUND` (D16.1); R8 refs `NOT_FOUND`; stale snapshot; capture refs resolve only here (R7); legacy readers stay v2-free; 21 refs invalid |
| S13 | API and schema parity | X01–X28, Q01–Q08 | DEFERRED | The schema half is checked here: every answer validates under both validators. Service/REST/negotiated-MCP equality of the same cases is I3.3 (I3 §13) |
| S14 | Replay and permutation | P07 | PROPERTY | Identical canonical bytes across permuted import and span order |
| S15 | Regression and isolation | P06 | DEFERRED | Golden no-v2 pin, old dependency/drift/deployment/evidence/Pub/Sub semantics and zero graph writes are re-asserted by I3.2/I3.3 suites (I3 §14), and P06 covers the isolation half |

## 5. Cross-references

| Source | Cases |
|---|---|
| I1 oracle L04a (`provider_services`) | X01 (O1 → `service:pricing`, O2 → `service:legacy-pricing`) |
| I1 oracle L32a (group shape and evidence union) | X04 |
| I1 oracle L32b (no provider dependency minted) | X05, X06 |
| Rehearsal E1–E3 | X01 |
| Rehearsal E4–E5 | X03 |
| Rehearsal E6 (v1 buckets) | Not an I3 answer: it stays with `test_locality_rehearsal_replay.py` (I2) |
| Rehearsal E7 (snapshots differ) | P08 |
| D15 R1, R2, R3 | X25; P01; X11 and X12 |
| D15 R4, R5, R6, R6b | X15; X14; P09; X16 |
| D15 R7, R8 | P05; X27 |
| D9 Q1 (no positive is `NOT_ANSWERED` with payload) | X07, X08, X09, X12, X13 |
| D16.4 provider filter | X18 |
| D16.10 (`SELECTION_NOT_ESTABLISHED` from `compare`) | X15, X16 |
| D3 `caller_localities` filter | X17 |
| Request validation (D3, D9) | Q01, Q02, Q06, Q07 |

## 6. Execution (I3.2c)

This section was added in I3.2c. §1–§5 and the oracle are unchanged.

[`tests/integration/test_locality_oracle.py`](../../../tests/integration/test_locality_oracle.py) runs every `mode: "query"` case against `ArchitectureIntelligenceService.get_service_dependencies_by_locality` on real Neo4j.
- **Answer cases:** X01–X25.
- **Property cases:** P01–P04 and P07–P09.
- **Matching:** each answer must also pass the published 0.6 schema and the `LocalityAnswer` model, and is matched with the §2 procedure ([`locality_oracle/matcher.py`](../../../tests/integration/locality_oracle/matcher.py)). `tests/unit/test_locality_oracle_matcher.py` gives every matcher rule its own positive and negative test.
- **Evidence mode (I3.3a):** X26–X28 and the property cases P05 and P06 run against `ArchitectureIntelligenceService.resolve_scoped_locality_evidence`. `SNAPSHOT_ID` is bound from the built world's current snapshot, and `REF:*` to the fixture's own evidence ids (§2 rule 2). P06's NL step uses a stub provider that names the v2 ids, as I2's isolation tests do.
- **Partition guard:** `test_every_case_is_executed` pins the split: every answer and property case runs here, and Q01–Q08 stay with the unit machine check above.

The world builder, [`locality_oracle/world.py`](../../../tests/integration/locality_oracle/world.py), uses these write paths:
- the real importer for declarations and captures;
- the production per-POST persistence for v2 records and observed `PROVIDES`.

Its disclosed deviations, in addition to the §3 X05/X06 adjustments:
- **X25:** the first 3 of the 2,000 generated captures go through the real importer. The rest are cloned as `SourceState` capture properties, and the harness asserts that the clone writer reproduces what the importer wrote for the real ones (owner decision: about 13 minutes of imports per run).
- **P08:** C2 is imported over C1 from a temporary copy in which only `completeness.expectedPriorInventoryRevision` is set to the committed C1 revision. The recorded envelopes are both first imports, so the importer would otherwise refuse C2 as a stale predecessor. The committed fixture is unchanged (owner decision).

**Cross-surface parity (S13, I3.3c).** [`tests/integration/test_locality_surface_parity.py`](../../../tests/integration/test_locality_surface_parity.py) builds the world of every answer case X01–X28 once and asks three surfaces sharing one service and one snapshot: the service directly, REST (`POST …/by-locality[/evidence]`) and negotiated MCP over the real transport (guard, SDK session manager, `tools/call`). The REST body and the MCP `structuredContent` must equal the service answer exactly. Each must also pass the published schema, and the service answer must match the oracle. `tests/unit/test_mcp_locality_contract_parity.py` checks that the fourth tool's advertised `inputSchema.request` and `outputSchema` equal the published v0.6 request and answer schemas after `$ref` resolution. `test_independent_client_discovers_four_tools_and_drills_a_locality_answer_down` drives the httpx-only independent client over real HTTP against the production app: it discovers four tools, runs the query and then evidence mode, and reconnects. S13 and S15 are therefore executed; the DEFERRED status in §4 refers to I3.1c's own scope.

**Finding.** The first run of P07 (X10) showed that the canonical snapshot state ordered the rows of one Pod captured by two sources only by id, so the snapshot id depended on Neo4j's return order. I3.2c fixes this in `repository._project_deployment_captured_pods` (whole-row sort). It changes no expectation and no frozen vector.
