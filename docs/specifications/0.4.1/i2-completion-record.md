# I2 Completion Record — v0.4.1 Messaging Semantic Guards

One concise record covering all three I2 slices, matching this repository's established precedent
(`docs/specifications/0.4.1/i1-completion-record.md`). See
[`i2-messaging-semantic-guards.md`](i2-messaging-semantic-guards.md) for the full spec this record
qualifies against.

## Run identity

- **I2.1 (Pure Guard Decisions):** merged to `main` as `5cfccf7` (PR #115, 2026-09-10) plus a
  same-PR review-round follow-up fixing two real spec violations in the matchers'
  namespace-eligibility and alias-disambiguation logic (`24556bc`, squashed into `5cfccf7` on
  merge).
- **I2.2 (Atomic Production Wiring):** merged to `main` as `aedda84` (PR #116, 2026-09-10) plus a
  same-PR review-round follow-up completing the real-Neo4j persistence assertions to all four
  artifact types and fixing the C13 composed-matrix case to use a genuinely namespaced service
  (`7b902d4`, squashed into `aedda84` on merge).
- **I2.3 (Frozen Qualification and Completion) candidate:**
  `690434601043cd0d7e20f26a4e1e5eb0dbd2a2c5` on branch
  `feature/v0.4.1-i2.3-frozen-qualification-completion` (PR #117) — a documentation/test-only
  slice; the review round added two literal-captured-shape regressions (below) on top of the two
  synthetic-reachability tests, no production code changed throughout.
- **CI, verified via the GitHub API against this exact SHA** (not `gh pr checks`, per this
  repository's standing rule that an unscoped/PR-view check query can silently miss what's actually
  attributed to the candidate commit —
  `gh api repos/michaelegner/architecture-intelligence-platform/commits/6904346.../check-runs`):
  `lint + test` ×2, `CodeQL`, `analyze (actions)`, `analyze (python)`,
  `dependency security scan (pip-audit, spec §29)` ×2 — all `completed`/`success`.
- **Environment / data used throughout I2's persistence-boundary tests:** the real
  `examples/` reference fixture landscape (module-scoped, shared within each integration test file),
  with distinct `environment` values per test to avoid cross-test evidence-id collisions.

## Regression suite (I2.3 candidate, full local run)

| Suite | Result |
|---|---|
| `uv run ruff check .` | clean |
| `uv run ruff format --check .` | clean |
| `uv run pytest tests/unit` | 930 passed |
| `uv run pytest tests/integration` | 254 passed |

930 unit tests = the 867 v0.4.1-I1 baseline + 36 (I2.1 guard matrices) + 4 (I2.1 review-round
regressions) + 17 (I2.2 composed matrix C1-C17) + 2 (I2.2 mixed-batch regressions) + 2 (I2.3
synthetic-reachability regressions) + 2 (I2.3 review-round literal-captured-shape regressions,
below). 254 integration tests = the 248 v0.4.1-I1 baseline + 6 (I2.2 real-Neo4j persistence proof,
one positive control + five refusal families) — I2.3 adds no new integration tests, only unit-level
frozen-shape/reachability proofs, since the frozen-shape regressions themselves are unit-level
(spec §20 already establishes this: recognition is checked before any guard or Neo4j access is
reached at all).

## Destination guard: default-deny (spec §9-11)

A messaging destination becomes Queue-compatible only via a deterministic declared-Queue match, or
explicit `messaging.destination_kind: queue` evidence with no declared match and no ambiguity.
`messaging.system` alone (e.g. `"kafka"`) is never positive Queue evidence and never sufficient
proof of topic topology — no protocol/vendor classification table of any kind exists in the
implementation. `app/telemetry/queue_resolver.py::resolve_queue` is no longer called by production
code; it remains, unmodified, as a historical/shared-primitive characterization only (its own unit
tests keep passing, with an updated comment).

## Service-identity guard: OTel SDK placeholder family (spec §14-17)

An undeclared runtime service identity mints `OBSERVED_ONLY` only when it passes a deterministic
predicate that refuses exactly `unknown`/`unknown-service`/`unknownservice` (after normalization)
and any `unknown_service:<process>`-shaped value — the real OpenTelemetry SDK fallback format, not
an application-name denylist. `FraudService`/`LegacyPricingService`-style distinctive names remain
mintable. The guard is scoped to the messaging path only:
`app/telemetry/service_resolver.py::resolve_service`/`resolve_runtime_span` remain fully unchanged
and are still what `correlate_http_call_observations` uses — the v0.4.0 hero finding
(`OrderService -> LegacyPricingService = OBSERVED_ONLY`) is untouched, confirmed by a dedicated
regression (`test_messaging_placeholder_refusal_does_not_change_http_service_resolution`).

## Frozen Quarkus and Airflow regressions (spec §30-31)

Review caught a real gap in the first draft of this slice: the frozen-shape and synthetic-
reachability tests used neutral stand-in values (`orders-topic`, `task-queue`) rather than the
literal captured attributes, so they proved the attribute-key recognition boundary is name-generic
but not that the *exact real captured inputs* were ever exercised — weaker evidence than the
ADR/this record's own claim. Fixed by adding two new tests using the literal captured values
verbatim, and switching the Quarkus synthetic-reachability test's destination to the real `fights`
value as well; the pre-existing neutral-name tests are kept alongside them (spec §17's own
genericity convention, still useful evidence in its own right).

| Case | Test | Result |
|---|---|---|
| Quarkus neutral-name shape (`messaging.operation: publish`, no `.type`) stays unrecognized | `test_legacy_messaging_operation_attribute_shape_is_not_recognized` | unmodified, passing |
| Quarkus **literal** captured shape (`messaging.destination.name: fights`, `messaging.system: kafka`) stays unrecognized | `test_quarkus_fights_topic_exact_captured_shape_is_not_recognized` | new — zero facts/entities/unresolved |
| Quarkus synthetic reachability (`fights`/`kafka`, recognized `operation.type`, no kind) | `test_quarkus_shape_destination_guard_reachability_with_a_recognized_operation_type` | refuses `unresolved_destination_semantics` |
| Airflow neutral-name shape (`messaging.destination`, not `.name`) stays unrecognized | `test_celery_instrumentation_semconv_shape_is_not_recognized` | unmodified, passing |
| Airflow **literal** captured shape (`service.name: unknown_service`, `messaging.destination: default`) stays unrecognized | `test_airflow_unknown_service_exact_captured_shape_is_not_recognized` | new — zero facts/entities/unresolved |
| Airflow synthetic reachability (`service.name: unknown_service`, recognized operation type, declared Queue) | `test_airflow_shape_service_identity_guard_reachability_with_a_recognized_operation_type` | refuses `placeholder_service_identity` |

Neither synthetic test asserts that `messaging.system: kafka` alone means topic (spec §30's explicit
constraint), and neither predicate under test inspects the words "Quarkus"/"Airflow", a role name,
or a fixture path (spec §31) — both are generic, reachable via any currently-recognized operation
shape.

## Scope preservation (spec §35)

- Operation-attribute recognition: unchanged — `send`/`receive`/`process` on
  `messaging.operation.type` remains the complete surface, confirmed by the two unmodified
  frozen-shape tests above.
- Canonical Model / graph schema: unchanged — no `Topic`, `Subscription`, or new relation family.
- Public contracts: unchanged — `ArchitectureAnswer<T>` schema family, `schema_version="0.4"`,
  exactly three read-only MCP tools, no new configuration switch capable of disabling either guard.
- `app/telemetry/queue_resolver.py`/`resolve_service`/`resolve_runtime_span`: unchanged in behavior;
  only their callers within the messaging path changed (I2.2).

## I2 exit statement (spec §42)

> GO — At `690434601043cd0d7e20f26a4e1e5eb0dbd2a2c5`, AIP's production runtime messaging path requires both
> deterministic Queue-compatible destination semantics and safe service identity before deriving a
> canonical `SENDS`/`RECEIVES_FROM` observation. Topic-shaped, unresolved, conflicting, ambiguous,
> and placeholder inputs produce zero Service/Queue/Evidence/relation artifacts from the refused
> span, while declared Queues and explicit unambiguous runtime-only Services preserve valid
> `OBSERVED_ONLY` behavior. The frozen Quarkus Kafka and Airflow/Celery shapes remain unsupported
> with zero invented messaging facts; operation recognition, the Canonical Model, public v0.4
> schemas, and the exactly three read-only MCP tools remain unchanged. I2 release blockers = 0.

ADR 0013 remains `Accepted` — satisfied, not superseded, by this record's implementation. Its own
"Implementation record" section names the exact entry points, merged candidates, and regression
tests above.
