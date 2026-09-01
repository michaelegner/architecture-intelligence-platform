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
AIP candidate SHA (base, before this PR's two additive tests): b4936260fd85ac389fc22fce922fa12ce6eff0de
                                                                (I4.2 merge commit, main@b493626)
```

All results below were captured fresh against this candidate plus the two additive test cases this
PR introduces (no production code changed) — not cited from I4.2's entry-gate run, per that
record's own handoff note that I4.2's results are entry evidence only, not a substitute for I4.3's
own capture.

## Finding-to-test map

| Finding | Bucket | Evidence |
|---|---|---|
| `qsh-grpc-locations` | Not applicable | No gRPC adapter/mechanism exists in `app/` to test; absence of a test is the correct state. |
| `qsh-kafka-fights-topic` | Covered (mechanism) + Named gap (guard) | See below. |
| `qsh-kafka-operation-type-gap` | Covered | `tests/unit/test_adapter.py::test_unrecognized_operation_type_is_silently_skipped`, `test_missing_operation_type_is_silently_skipped` prove the narrow-allowlist behavior that is the actual reason this finding currently produces zero facts. |
| Airflow PostgreSQL dependencies (x3) | Not applicable | No database relation family exists in `app/canonical/model.py` to test. |
| `airflow-execution-api-boundary` | Not applicable | No Execution API caller-identity resolution path exists; absence of a `CALLS` fact is definitionally correct, not a tested behavior. |
| `airflow-runtime-role-identity` | Covered (mechanism) + Named gap (guard) | See below. |
| `airflow-celery-messaging-runtime-status` | Covered | Same two `test_adapter.py` tests as `qsh-kafka-operation-type-gap` - Airflow's diagnostic span also lacks a recognized operation attribute, so it is filtered by the identical code path. |
| `i4-celery-instrumentation-semconv-mismatch` | Covered | Same two `test_adapter.py` tests - the span's `messaging.destination_kind`/`messaging.destination` shape is unrecognized by any current or legacy attribute check, filtered the same way. |

### `qsh-kafka-fights-topic` and the Queue-vs-topic guard (spec §10.2 / §17 "proof that unsupported
topics do not emit Queue relations")

- **Covered (mechanism)**: the two `test_adapter.py` tests above prove *why* zero facts result
  today - the span is filtered before `resolve_queue()` is ever reached.
- **Named gap (guard)**: the §17 bullet asks for proof that a topic-shaped destination *cannot*
  produce a `SENDS`/`RECEIVES_FROM` fact. That proof does not exist and cannot pass today, because
  `resolve_queue()` has no topic-vs-queue refusal path (`decisions/queue-topic-boundary.md`). This
  PR adds `tests/unit/test_queue_resolver.py::
  test_kafka_topic_shaped_destination_is_still_minted_as_observed_only_queue`, which calls
  `resolve_queue(messaging_system="kafka", destination_name="fights", ...)` directly (the literal
  Quarkus scenario) and asserts `OBSERVED_ONLY` - i.e. it pins the current, deliberately-unguarded
  behavior. It is **not** the §17 safety proof; it is the opposite, made explicit and traceable to
  its decision record instead of implicit in prose.

### `airflow-runtime-role-identity` and the Service-identity guard (spec §11 / §17 "distinct roles
sharing an unhelpful `service.name`")

- **Covered (mechanism)**: `tests/unit/test_service_resolver.py::
  test_tier4_observed_only_mints_deterministic_id` already proves Tier 4 mints unconditionally
  regardless of the name's value - the general case underlying this finding.
- **Named gap (guard)**: no test previously used the *literal* Airflow value. This PR adds
  `test_generic_service_name_is_still_minted_as_qualified_observed_only`, calling
  `resolve_service(service_name="unknown_service", ...)` directly and asserting `OBSERVED_ONLY` -
  pinning that `resolve_service()` has no refusal path for a generic/ambiguous name, exactly the
  gap `messaging-operation-compatibility.md` named as a prerequisite for any future messaging-
  attribute widening. Not a safety proof; the current, deliberately-unguarded behavior, made
  literal.

## Distilled tests added (no production code changed)

```text
tests/unit/test_queue_resolver.py
    + test_kafka_topic_shaped_destination_is_still_minted_as_observed_only_queue

tests/unit/test_service_resolver.py
    + test_generic_service_name_is_still_minted_as_qualified_observed_only
```

Both use literal real-world values from the I4.1 decision records (`fights`/`kafka`,
`unknown_service`) rather than analogous placeholders, and both assert the resolvers' current,
unchanged behavior - they document open `DEFER` prerequisites, they do not close them.

## Results (bound to this candidate)

```bash
uv run ruff check .                          -> All checks passed
uv run ruff format --check .                 -> all files formatted
uv run pytest tests/unit tests/integration -q -> 666 passed (664 baseline + 2 new)
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
  and `uv run python -m evaluation run` were each run twice against this exact candidate; results
  were identical both times (666 passed / 666 passed; identical `evaluation run` output byte for
  byte). No drift since I4.2, as expected since no production code changed.

## No new material finding

No new material finding was discovered while building this regression map. The two named gaps
above are the same ones already recorded in I4.1's decision records - this record only makes them
literally test-traceable.
