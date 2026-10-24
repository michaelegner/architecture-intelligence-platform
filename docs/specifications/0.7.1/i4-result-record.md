# v0.7.1 I4 — Result record

**Status:** COMPLETE on merge of this PR. **Owner decision: `CONTINUE`.** Governing: the [I4 specification](i4-deterministic-real-system-and-product-value-qualification.md) §6, under the [I3 → I4 handoff](i3-i4-handoff.md). The next step is [I5](i4-i5-handoff.md).

**Qualified candidate:** `df3a9e4f4ca7ee89aa5afdde836b2905027dd30f`, the #601 merge on `main`.

## Slices

| Slice | Content | PR | Merge commit |
|---|---|---|---|
| I4 spec | [I4 specification](i4-deterministic-real-system-and-product-value-qualification.md) | #599 | `ccecf4e` |
| I4.1 | the frozen real-Kafka inputs, independent expectations, the replay qualification test, `ab_replay.py` | #601 | `df3a9e4` (the candidate) |
| I4.2 | exact-candidate execution record, A/B | #605 | `1d2bf3a` |
| I4.3a | RabbitMQ contrast, the session kit and the record template | #606 | `bd6f36f` |
| I4.3 kit | step-by-step session kit | #608 | `8e8c37f` |
| I4.3b | the filled session record, this record, the [I4 → I5 handoff](i4-i5-handoff.md) | this PR | read from `gh pr view --json mergeCommit` after merge |

The merge commits were read from `gh pr view --json mergeCommit,mergedAt`.

## Results

- **Deterministic replay.** A/B on the candidate: two separate pytest processes, each with its own Neo4j container. Both outputs are `68c5a27f5d6883e72f186d835545997d543f1bac406f931caaa5a3dede3923e2`, byte-identical, with no normalization. The command, run from a clean checkout of the candidate:
  ```sh
  uv run python docs/specifications/0.7.1/i4-evidence/kafka/ab_replay.py \
    --candidate-sha df3a9e4f4ca7ee89aa5afdde836b2905027dd30f --out <new directory>
  ```
  The gates and exact-candidate CI are in the [execution record](i4-execution-record.md). The outputs are in [`ab-df3a9e4/`](i4-evidence/kafka/ab-df3a9e4/).
- **Inputs.** The [I4.1 package](i4-evidence/kafka/README.md) covers 79 files in [`SHA256SUMS`](i4-evidence/kafka/SHA256SUMS). Among them:

  | Input | SHA-256 |
  |---|---|
  | `c1/kafka-consumer-state.json` | `cc2f84870b0e732d8476b8e06dc207cd5ca562dfb1d66ff48c39c469908f2e92` |
  | `c2/kafka-consumer-state.json` | `cd2e95d206becf35b41f3ed93198365d0e75de4e12e89f9c05ccc41f2c1ea18a` |
  | `mapping/kafka-service-mapping.json` | `72873c02cdf89d85aa5683e196e2c530af20085faef5f5d788670e6f3e2909d9` |
  | `expected.json` ([`EXPECTED.sha256`](i4-evidence/kafka/EXPECTED.sha256)) | `4c50165f1398b7690229fe44f25dc2d88215961ca7d47fa2c04ed966386a104c` |

  The expectations come from stock `kafka-consumer-groups` output and the application configuration. Each part was written before its own capture: the C1 part before C1, the C2 part before C2 (package README, "Ordering").
- **Real Kafka.** `hungCS22hcmiu/ecommerce-system@cd65365`, captured locally at C1 (`2026-10-19T06:21:23Z`) and C2 (`2026-10-19T06:23:28Z`).
  - **C1:** on `orders.created`, payment-service is `RESOLVED`, and the operator's console consumer `ops-tail` is `UNRESOLVED / NO_MAPPING`. `analytics-tap`, a group outside the allow-list on `payments.completed`, is never named.
  - **C2:** the attachments are removed without a negative claim.
  - Every answer that `expected.json` covers matches it on service, REST and negotiated MCP.
- **RabbitMQ.** [`SOURCE_SPECIFIC`, no MODEL_GAP](i4-evidence/rabbitmq/README.md). A supplementary capture (S5) shows that a RabbitMQ consumer's native id needs the channel number. This fits the I0 D1 envelope, so no scope decision is needed.
- **Agent session.** [`agent-session.md`](i4-evidence/agent-session.md): one change (renaming a field of `OrderCreated`), three arms, Claude Code with Opus 5.5.
  - **Without AIP,** the agent found payment-service through the code. It named the broker check as a next step but did not run it.
  - **With C1,** it found `ops-tail`, which code search cannot find, and made its owner a condition before the old field name is dropped.
  - **With C2,** it kept "no attachment at T" apart from "does not consume" for payment-service. It did so only partly for `ops-tail`.
  - In no arm did it present a capture as a complete impact assessment.

## Done criteria (spec §6)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Independently expected cases and two clean runs on one SHA pass, with no unexplained mismatch | Met | A/B IDENTICAL on `df3a9e4` ([execution record](i4-execution-record.md)). Each part of the expectations predates its capture ([package README](i4-evidence/kafka/README.md) "Ordering"). The digest difference from the I4.1 smoke run is explained: snapshot ids depend on the checkout location |
| 2 | Real Kafka gives a resolved and an unresolved answer end to end, matching independent ground truth, with public evidence and T | Met | C1 with mapping: payment-service `RESOLVED`, `ops-tail` `UNRESOLVED / NO_MAPPING`, each with T and resolvable evidence. The ground-truth test ties C1 to G1 and C2 to G2 ([execution record](i4-execution-record.md)) |
| 3 | RabbitMQ distinctions stay explicit; any model gap has a reviewed scope decision | Met | [RabbitMQ record](i4-evidence/rabbitmq/README.md): `SOURCE_SPECIFIC`, no MODEL_GAP, so no scope decision is needed. A Queue answers `DESTINATION_NOT_KAFKA_TOPIC` on every surface |
| 4 | REST/MCP parity, evidence safety, source lifecycle and existing-tool compatibility pass | Met | [Execution record](i4-execution-record.md), on the candidate. **Parity:** every replay answer is checked on service, REST and negotiated MCP. **Evidence safety:** a forged ref gives `PARTIAL / NOT_RESOLVED`; C1 refs do not resolve under C2. **Lifecycle:** C2 removes attachments; C1's snapshot becomes `SNAPSHOT_NOT_AVAILABLE`; a repeated C2 import is a no-op; the derived incomplete capture is rejected with `KAFKA_CAPTURE_INCOMPLETE`. **Existing tools:** the unit, integration and qualification tiers (4,895 / 882 / 117 passed) and exact-candidate CI are green |
| 5 | The product-value check shows whether broker evidence changes an actual coding-agent decision and ends with an explicit decision | Met | [Session record](i4-evidence/agent-session.md). The evidence changed the next action (the `ops-tail` gate). Owner decision: `CONTINUE` |

## Owner decision

**`CONTINUE`.** From the [session record](i4-evidence/agent-session.md): "The semantics hold against independent ground truth: real Kafka C1/C2, A/B identical, and RabbitMQ kept SOURCE_SPECIFIC. In the session, broker evidence surfaced a consumer that code search could not find (ops-tail) and turned it into a rollout gate, without the agent presenting the capture as complete. Carried limits: one local system, the allow-list needs upkeep, and the sorted-evidence_refs friction."

## Limitations

- **Scope of the evidence:**
  - One real system, captured locally at two points in time.
  - One agent session on one change.
  - Ambiguous and conflicting mappings are covered only by the synthetic I2 tests.
  - `C1-incomplete` is derived, not observed.
- **Location-bound snapshot identity:** snapshot ids, evidence refs and output digests depend on the absolute checkout path ([`docs/evidence.md`](../../evidence.md) "Snapshot identity"). The A/B identity holds for one SHA at one path.
- **The capture allow-list needs upkeep:** a group outside it is never seen (here `analytics-tap`, on `payments.completed`). The answer says so (`CAPTURE_SCOPE_LIMITED`), but it cannot name the missing group.
- **The session ran on AIP `108390f`, not on the candidate.** Between the two commits, `app/`, `schemas/`, `pyproject.toml`, `uv.lock`, `Dockerfile`, `harness/` and the frozen Kafka inputs are identical. `SHA256SUMS` verifies on `108390f`. In those paths, the only additions are the A/B outputs and the session template. The session's snapshot ids are not comparable with the A/B digests, because of the location rule above.
- **The `evidence_refs` sort rule is not advertised:** evidence mode rejects unsorted `evidence_refs` (`must be sorted and duplicate-free`), the convention `get_evidence` also follows. The advertised request schema states only `uniqueItems`, and the tool description does not mention the order. In the session, the agent needed one retry.
- **Kit:** the step-1 checkout check also stops on untracked files. In the session, the untracked memtrace store `.memdb/` triggered it. The check that ignores untracked files passed.
