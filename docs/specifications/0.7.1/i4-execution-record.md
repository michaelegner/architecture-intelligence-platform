# v0.7.1 I4.2 — Execution record

**Status: I4.2 execution PASS.** Governing: the [I4 specification](i4-deterministic-real-system-and-product-value-qualification.md) §2 and §3. Inputs: the I4.1 package ([`i4-evidence/kafka/`](i4-evidence/kafka/README.md), #601).

Exact tested candidate, read from `git rev-parse HEAD` in a clean checkout of it: **`df3a9e4f4ca7ee89aa5afdde836b2905027dd30f`**, the #601 merge on `main`. I4 is not complete with this record. I4.3 owns the RabbitMQ contrast record, the owner's agent session, the I4 result record, the I4 → I5 handoff and the decision.

## Execution

Nothing was changed for this run: no production code, schema, input, expectation or qualification code. All runs used one detached, clean worktree of the candidate at `/home/michael/code/aip-i42-candidate`. `git status --porcelain --untracked-files=all` was empty before and after every step. Nothing was rerun, repaired or normalized. The A/B run below is the only one on the candidate.

```sh
uv run python docs/specifications/0.7.1/i4-evidence/kafka/ab_replay.py \
  --candidate-sha df3a9e4f4ca7ee89aa5afdde836b2905027dd30f --out <new directory>
```

## A/B result

Run window: 2026-10-19T08:06:15Z to 08:07:45Z. The outputs are in [`i4-evidence/kafka/ab-df3a9e4/`](i4-evidence/kafka/ab-df3a9e4/).

| Check | Result |
|---|---|
| HEAD = candidate and clean tree, before and after | `true` / `true` |
| Inputs (`SHA256SUMS`, 79 files) | verified |
| Run A / run B | separate pytest processes, each with its own Neo4j container; 3 passed / 3 passed |
| Output | 37,199 bytes each, 9 steps; `run-a.json` and `run-b.json` are both `68c5a27f5d6883e72f186d835545997d543f1bac406f931caaa5a3dede3923e2` |
| Comparison | byte-identical, no normalization; verdict **IDENTICAL** |

Each run checks every answer against the [independently authored expectations](i4-evidence/kafka/expected.json) (digest `4c50165f…`), on the semantic service, REST and negotiated MCP:

- Declarations only: `NO_ACCEPTED_CAPTURE`.
- C1 without a mapping source: on `orders.created` both attachments are `UNRESOLVED/NO_MAPPING`, with `NO_MAPPING_SOURCE`. The other Topics' answers are in the byte comparison but not asserted.
- C1 with the mapping:
  - `orders.created`: payment-service `RESOLVED`; ops-tail `UNRESOLVED/NO_MAPPING`; analytics-tap, outside the allow-list, never named.
  - order-service: one row on each of `payments.completed` and `payments.failed`, although the group has two members.
  - `payments.dlq`: `rows: []`.
- Same-snapshot evidence resolves, and the payloads carry the frozen capture and mapping hashes. A forged ref gives `PARTIAL / NOT_RESOLVED`.
- A two-row paged query (`limit: 1`) returns the same rows as the unpaged query.
- `BROKER_MISMATCH` and `UNKNOWN_DESTINATION` are refused.
- Derived `C1-incomplete`: rejected with exactly `KAFKA_CAPTURE_INCOMPLETE`, and the answers are unchanged.
- C2 (real):
  - the payment and ops-tail attachments are removed with no negative claim;
  - both mapping entries remain accepted;
  - the C1 snapshot is now `SNAPSHOT_NOT_AVAILABLE` for query and evidence, and the C1 refs are `NOT_RESOLVED` under C2;
  - an identical C2 replay is a no-op.
- A RabbitMQ Queue answers `DESTINATION_NOT_KAFKA_TOPIC`.

The ground-truth test confirms two more facts:
- C1 holds exactly the stock-CLI G1 assignments.
- The C2 group states are the broker-reported G2 states.

## Gates on the candidate

| Gate | Result |
|---|---|
| `ruff format --check`, `ruff check`, `pyright`, `lint-imports` | clean; 0 errors; 12 contracts kept |
| `pytest tests/unit` | 4,895 passed |
| `pytest tests/integration -m "not qualification"` | 882 passed, 1 skipped (the existing private-fork smoke test), 117 deselected |
| `pytest tests/integration -m qualification` | 117 passed, 883 deselected |
| Exact-candidate CI | 13 check runs on `df3a9e4f4ca7`, all `success`, completed 08:05:14Z–08:09:57Z, read through the check-runs API by SHA. Includes the required `lint + test` and the three `integration-qualification` shards, which ran the replay |

The local gates ran from 08:11:56Z to 08:30:09Z, after CI had finished. The A/B run started at 08:06:15Z, while CI was still running. It does not depend on CI, and CI finished green on the same SHA.

## Finding: snapshot ids depend on the checkout location

The I4.1 smoke runs produced `607bcdc8…`, at the PR head in the `aip-i41` checkout. That differs from this run's `68c5a27f…`, although the code trees of `ff91eb7` and `df3a9e4` are identical.

A probe established the cause:
- One path with two HEADs gives one digest.
- Different paths give different digests.
- A full `canonical_snapshot_state` diff between two checkouts differs only in the declared documents' absolute `source_file`.

This is the known, documented behavior: [`docs/evidence.md`](../../evidence.md) "Snapshot identity", and the v0.5.0 I5 rule that byte-identity runs use one absolute checkout location. It is not new and not specific to Kafka. Consequences:

- The A/B identity above holds for one SHA at one absolute location.
- Snapshot ids, evidence refs and output digests are not comparable across checkout paths. The public outcomes, rows, Services, T and artifact hashes are the same.
- `ab_replay.py` does not record the location. This record does.

## Remaining limitations

- One real system, captured locally in two points in time. Ambiguous and conflicting mappings are covered by the synthetic I2 tests only.
- `C1-incomplete` is derived, not observed.
- Location-bound snapshot identity, as above.
