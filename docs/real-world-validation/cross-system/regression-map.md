# I4.3 — Distilled Regression and Synthetic Revalidation

Spec §27's I4.3 scope: "Deliver the finding-to-test map, distilled tests, v0.2 result,
unit/integration/I1 contract results, and determinism verification." I4.1/I4.2 approved zero `FIX`
dispositions, so spec §17's mandatory regression coverage ("every accepted semantic fix SHALL have
deterministic tests") is vacuously satisfied — there is no fix. This record instead maps every
ledger finding to what the *existing* test suite already proves about its current, unchanged
behavior, and candidly names the §17 coverage bullets that cannot yet pass, because the guards they
would verify do not exist. That is exactly what `DEFER` means, not a gap to paper over.

## Candidate identity

```text
AIP candidate SHA: cb1c4e38fdd5962cdd054be91e9d3761b62cf9d5
```

This is the exact commit the results below were captured against — it already contains all four
distilled test additions this PR introduces (no production code changed). This record was written
in a following, documentation-only commit, per the discipline that a result must name the literal
commit it was captured against rather than a base SHA plus an uncommitted description of pending
changes.

## Finding-to-test map

| Finding | Bucket | Evidence |
|---|---|---|
| `qsh-grpc-locations` | Not applicable | No gRPC adapter/mechanism exists in `app/` to test; absence of a test is the correct state. |
| `qsh-kafka-fights-topic` | Covered (mechanism) + Named gap (guard) | See below. |
| `qsh-kafka-operation-type-gap` | Covered | `tests/unit/test_adapter.py::test_legacy_messaging_operation_attribute_shape_is_not_recognized` uses the complete, independently-captured Quarkus attribute shape (`messaging.operation: publish`, `messaging.destination.name`, `messaging.system: kafka`) and asserts zero facts — this is the actual shape, not a generic missing/unrecognized-value stand-in. |
| Airflow PostgreSQL dependencies (x3) | Not applicable | No database relation family exists in `app/canonical/model.py` to test. |
| `airflow-execution-api-boundary` | Not applicable | No Execution API caller-identity resolution path exists; absence of a `CALLS` fact is definitionally correct, not a tested behavior. |
| `airflow-runtime-role-identity` | Covered (mechanism) + Named gap (guard) | See below. |
| `airflow-celery-messaging-runtime-status` | Covered | `test_celery_instrumentation_semconv_shape_is_not_recognized` uses the complete, independently-captured Celery-instrumentation shape (`messaging.destination_kind`, `messaging.destination`, no operation attribute, no `messaging.system`) and asserts zero facts. |
| `i4-celery-instrumentation-semconv-mismatch` | Covered | Same test as `airflow-celery-messaging-runtime-status` — this finding *is* that attribute shape. |

`test_unrecognized_operation_type_is_silently_skipped` and
`test_missing_operation_type_is_silently_skipped` (pre-existing) remain relevant background —
they prove the current allowlist's general missing/unrecognized-value handling — but are not cited
as proof that either specific legacy shape is unrecognized, since neither test uses either shape's
actual attribute keys. The two new tests above close that gap directly.

### `qsh-kafka-fights-topic` and the Queue-vs-topic guard (spec §10.2 / §17 "proof that unsupported
topics do not emit Queue relations")

- **Covered (mechanism)**: `test_legacy_messaging_operation_attribute_shape_is_not_recognized`
  proves *why* zero facts result today for this exact shape — the span is filtered before
  `resolve_queue()` is ever reached.
- **Named gap (guard)**: the §17 bullet asks for proof that a topic-shaped destination *cannot*
  produce a `SENDS`/`RECEIVES_FROM` fact. That proof does not exist and cannot pass today, because
  `resolve_queue()` has no topic-vs-queue refusal path (`decisions/queue-topic-boundary.md`). This
  PR adds `tests/unit/test_queue_resolver.py::
  test_topic_shaped_destination_is_still_minted_as_observed_only_queue`, which calls
  `resolve_queue(messaging_system="kafka", destination_name="events-topic", ...)` — a topic-shaped
  destination under a general messaging system name, not an upstream-specific one (spec §17) — and
  asserts `OBSERVED_ONLY`. It is **not** the §17 safety proof; it is the opposite, made explicit
  and traceable to its decision record instead of implicit in prose.

### `airflow-runtime-role-identity` and the Service-identity guard (spec §11 / §17 "distinct roles
sharing an unhelpful `service.name`")

- **Covered (mechanism)**: `tests/unit/test_service_resolver.py::
  test_tier4_observed_only_mints_deterministic_id` already proves Tier 4 mints unconditionally
  regardless of the name's value - the general case underlying this finding.
- **Named gap (guard)**: no test previously exercised the general ambiguous/generic-name case
  using a real motivating value. This PR adds
  `test_generic_service_name_is_still_minted_as_qualified_observed_only`, calling
  `resolve_service(service_name="unknown_service", ...)` and asserting `OBSERVED_ONLY` — pinning
  that `resolve_service()` has no refusal path for a generic/ambiguous name (Airflow's actual
  reported value cited as the motivating instance, not as an Airflow-specific rule), exactly the
  gap `messaging-operation-compatibility.md` named as a prerequisite for any future messaging-
  attribute widening. Not a safety proof; the current, deliberately-unguarded behavior, made
  concrete.

## Distilled tests added (no production code changed)

```text
tests/unit/test_queue_resolver.py
    + test_topic_shaped_destination_is_still_minted_as_observed_only_queue

tests/unit/test_service_resolver.py
    + test_generic_service_name_is_still_minted_as_qualified_observed_only

tests/unit/test_adapter.py
    + test_legacy_messaging_operation_attribute_shape_is_not_recognized
    + test_celery_instrumentation_semconv_shape_is_not_recognized
```

All four assert canonical facts and evidence semantics using neutral destination/service values
(spec §17), except `messaging_system="kafka"` and `service_name="unknown_service"`, which are
general messaging-system and ambiguous-name values rather than upstream-specific identifiers — both
document open `DEFER` prerequisites; none close them.

## Results (bound to this candidate)

```bash
uv run ruff check .                          -> All checks passed
uv run ruff format --check .                 -> all files formatted
uv run pytest tests/unit tests/integration -q -> 668 passed (664 baseline + 4 new)
uv run python -m evaluation run              -> 10/10 PASS (v0.2 deterministic evaluation)
uv run --with pip-audit pip-audit             -> No known vulnerabilities found
```

### I1 contract results (spec §27, listed separately from unit/integration generally)

```bash
uv run pytest tests/unit/test_real_world_validation_model.py \
              tests/unit/test_real_world_validation_comparator.py \
              tests/unit/test_real_world_validation_main.py \
              tests/unit/test_real_world_validation_capture_cli.py \
              tests/unit/test_real_world_validation_loader.py \
              tests/unit/test_real_world_validation_reporter.py \
              tests/integration/test_real_world_validation_capture.py -q
-> 61 passed
```

### Determinism verification

- `tests/unit/test_real_world_validation_comparator.py::
  test_output_is_deterministically_sorted_by_classification_then_identity` already asserts the
  comparator's output ordering is deterministic.
- Fresh, candidate-bound proof for this iteration: `uv run pytest tests/unit tests/integration -q`
  and `uv run python -m evaluation run` were each run twice against commit `cb1c4e3`; results were
  identical both times (668 passed / 668 passed; identical `evaluation run` output byte for byte).

## No new material finding

No new material finding was discovered while building this regression map. The two named gaps
above are the same ones already recorded in I4.1's decision records - this record only makes them
concretely test-traceable, using the real, complete attribute shapes rather than generic
stand-ins.
