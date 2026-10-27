# AIP v0.8 I2: Completion Record

**Status:** COMPLETE on merge of the I2c PR. The closure SHA is added in a follow-up only if the owner asks.
**Outcome:** `READY_FOR_I3` if the owner records it on merging the I2c PR.

This record covers the [I2 spec](i2-assessment-projection-and-tool.md), Draft 0.5, under the [v0.8 specification](specification.md), Draft 0.3. Each slice's approved plan is kept verbatim in its PR description.

## Run identity

| Slice | Deliverables | PR | Merge commit | Merged (UTC) |
|---|---|---|---|---|
| I2 spec | [`i2-assessment-projection-and-tool.md`](i2-assessment-projection-and-tool.md), parent Draft 0.3 (D9–D12), I1 §5.5 | #641 | `62cde7bc6f355eecadc28b8651f0dbd8cde6f899` | 2026-10-26T15:45:41Z |
| I2a | promise record: carriers, ids and vectors, `event_catalogs` import wiring, lifecycle, D12 revision | #643 | `13ca216e92d9f2554b7f1ec88436a26b1deeb6ad` | 2026-10-26T16:41:19Z |
| I2b | assessment R1–R7, D9 crossing, projection, C1 and two-broker expected answers | #644 | `e05b09a54ab4bff3bf08469710c76ec0e8e794e6` | 2026-10-26T18:43:16Z |
| I2c | experimental tool and REST behind the flag, frozen v0.8 schemas, evidence mode, two field descriptions, this record, [`i2-i3-handoff.md`](i2-i3-handoff.md) | this PR | read from `gh pr view --json mergeCommit` after merge | |

The merge commits above were read from `gh pr view --json mergeCommit,mergedAt`.

## Acceptance (I2 §9)

| # | Status | Evidence |
|---|---|---|
| **B1** | Met | `tests/integration/test_v080_i2b_c1_binding_picture.py` (qualification tier): C1 gives exactly the nine §8.1 rows |
| B2, B3 | Met | `tests/integration/test_v080_i2b_two_broker.py`: the §8.2 table, the Redpanda-only request, the missing Kafka capture, R7 with and without a Kafka capture, an incomplete capture rejected |
| B4, B10 | Met | `tests/unit/test_v080_i2b_assessment.py`: R1–R7, the crossing table, the never-emitted statuses, the delivery flag and limitation |
| B5, B6 | Met | `tests/unit` and `tests/integration/test_v080_i2a_promise_record.py`: ids equal the vectors; lifecycle; a lookup-only change is re-evaluated |
| B7 | Met | flag off: `tests/unit/test_v080_i2c_surfaces.py` (six tools, no route) and the existing discovery tests; flag on: `tests/integration/test_v080_i2c_binding_picture_surface.py`, seven tools over the real negotiated transport, MCP = REST = service, answers valid against the advertised `outputSchema` and the frozen schema |
| B8 | Met | `tests/unit/test_v080_i2c_surfaces.py`: with the two descriptions removed, the v0.7.1 schemas and the OpenAPI snapshot hash to their `e05b09a` digests |
| B9 | Met | the I2c integration module: every ref minted for the nine C1 rows resolves at the same snapshot; the full chain of Product Query × `catalog.product.events` resolves (promise with the lookup entry, attachment, mapping); forged and cross-context refs are `NOT_RESOLVED`; a non-current snapshot is `SNAPSHOT_NOT_AVAILABLE`; no member text. Unit: an old ref submitted with the current snapshot is `NOT_RESOLVED` |

## Decisions and deviations

| # | What | Where |
|---|---|---|
| 1 | D9–D12 as recorded in the I2 spec §11 | #641 |
| 2 | Q1: one EventCatalog per environment (`EVENTCATALOG_DUPLICATE_SOURCE`); Q2: the source instance id formula | #643, I2 §2 |
| 3 | The five refactor goldens were regenerated when the adapter was registered (the #582 precedent, owner-accepted); snapshots and answers are unchanged | #643 |
| 4 | Catalog services resolve only to declared Services; the brokers of an environment are those with an accepted capture or mapping source; refs have their own domain, with the tool name hashed | #644, I2 §5–§6 |
| 5 | Every accepted capture per broker is kept; a row aggregates every supporting attribution (`group_ids[]`); `captured_at` only when the evidence shares one T | #644 reviews, I2 §6 |
| 6 | The flag-on app builds its own MCP server and dispatches to its own service; the flag-off singleton is unchanged | this PR |
| 7 | The evidence mode reruns the query projection for the same context and resolves only the refs it mints (the projection gained an optional `minted` parameter) | this PR |
| 8 | The flag-off guard proof is at unit level through `create_app`, not over the real transport in the integration module: the singleton server's session manager can run only once per process | this PR |
| 9 | Routes are checked through the app's OpenAPI paths: this FastAPI version keeps included routers lazy, so `app.routes` does not list their paths | this PR |
| 10 | The config accepts both `experimental.binding_picture` (the spec's spelling) and the YAML alias `binding-picture` | this PR |

## Specification questions still open

- An R2 row of a Service whose in-scope groups span two captures on one broker has no single T. `captured_at` is omitted, never chosen. C1 and the two-broker fixture never reach this case.

## Deferred work

- The hosted deployment with the flag on (I4).
- The two-broker environment and live captures (I3).

## Remaining limitations

- The semantics are experimental and are not a v1.0 contract (parent §2).
- The catalog is generated, and its promises are assumed confirmed.
- Cross-broker delivery is never established by AIP.
