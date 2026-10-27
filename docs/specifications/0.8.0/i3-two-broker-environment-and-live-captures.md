# AIP v0.8 I3: Two-Broker Environment and Live Captures

**Status:** Draft 0.1 (2026-10-27)  
**Governs:** [v0.8 specification](specification.md) §3.6, §4 and §7 I3, as amended by D13–D15 (§13).  
**Baseline:** `main` at `d07eedf` (I2 complete: [completion record](i2-completion-record.md), [handoff](i2-i3-handoff.md)).  
**Hands off to:** I4 (agent run, report and release).

## 1. Purpose

I3 runs wave 1 (parent §4) once, by script, on the Sokol111 local environment with two brokers. It
does two things:

1. It **qualifies the environment and the protocol**:
   - Redpanda and Apache Kafka, bridged by MirrorMaker 2 flows A and B;
   - the §4.2 cut-over;
   - the AIP captures and the broker-tool ground truth;
   - the functional test.
2. It **freezes the expected after-wave reference** that the I4 agent run must reproduce (D14).

Governing result: a repeatable, instrumented migration from Redpanda to Kafka, whose broker
states, offset hand-off, application behaviour and AIP binding picture are each checked
independently and frozen. It claims no stronger delivery guarantee than the evidence supports.

**Non-goals:**
- the agent run, the report and the release (I4);
- the hosted deployment;
- any change to AIP semantics or public contracts.

## 2. Pins

| Item | Pin |
|---|---|
| Sokol111 revisions | unchanged: the v0.7.2 [freeze](../0.7.2/i2-evidence/sokol111/freeze.md) |
| Redpanda | unchanged: `redpandadata/redpanda:v24.3.1` (v0.7.2 digest) |
| Cluster tools | unchanged: k3d v5.9.0 with k3s `v1.35.5+k3s1`, Tilt v0.37.8, Helm v3.22.0, with the v0.7.2 host adaptations |
| Apache Kafka | 4.x, single-node KRaft. The image is pinned by digest in I3a and recorded in the package |
| MirrorMaker 2 | `connect-mirror-maker.sh` from the same Kafka image, one process per flow |
| MinIO, imgproxy | as defined in `ecommerce-infrastructure` `07c0599` |
| Capture utility | unchanged: `harness/kafka-capture/capture.py` with `confluent-kafka==2.16.0` |

Every adaptation stays outside the Sokol111 repositories and is committed in the package as
authored, the v0.7.2 rule.

## 3. Environment (D13)

**Compose additions.** An overlay file, committed in the package, adds three services to the
infrastructure's local Compose stack, on Redpanda's Docker network:
- `kafka`: single node, with an advertised listener that both the Compose containers and the k3d
  workloads can reach;
- `mm2-flow-a`: Redpanda → Kafka, allow-list `tenant.tenant.events`;
- `mm2-flow-b`: Kafka → Redpanda, allow-list `catalog.product.events`, `catalog.category.events`
  and `catalog.attribute.events`.

**MirrorMaker 2 properties** (both flows, committed):
- one source → target pair per flow;
- `replication.policy.class=org.apache.kafka.connect.mirror.IdentityReplicationPolicy`;
- `emit.checkpoints.enabled=true` and `emit.offset-syncs.enabled=true`;
- replication factor 1 for every internal topic: checkpoints, offset-syncs, heartbeats, and the
  Connect config, offset and status topics.

Flow A also sets:
- `sync.group.offsets.enabled=true`, set explicitly because it is off by default;
- an explicit group allow-list: `ecommerce-catalog-service` and `ecommerce-image-service`.

**No loops** (parent §4.1). The two allow-lists are disjoint, and a precondition check proves it
before either flow starts. Each topic is mirrored in one direction only.

**Helm values.** The only change for Catalog and Image is the Kafka bootstrap address, written as
a values overlay and committed.

## 4. Preflight

The preflight must pass before §4.2 step 1. Each check is recorded, and any failure stops the run:

| # | Check |
|---|---|
| P1 | Every MM2 and Connect internal topic exists with replication factor 1 |
| P2 | Both flow configurations set offset-syncs, checkpoints and the identity policy. Flow A has the Catalog/Image group allow-list and `sync.group.offsets.enabled` |
| P3 | The flow A and flow B allow-lists are disjoint |
| P4 | Kafka's advertised listener is reachable from a Compose container and from a k3d probe pod (a metadata request succeeds) |
| P5 | **Group-offset-sync probe:** a throw-away group consumes from a throw-away topic on Redpanda and stops. With no active consumer on Kafka, MM2 installs its translated committed offset on Kafka. This proves the D2 mechanism with Redpanda as the source. The probe topic and group are removed afterwards and are outside both capture scopes |

## 5. Runbook (parent §4.2, steps 1–9)

The runbook is a set of **individually verifiable operations**, not one end-to-end migration
script:
- There is one script per step.
- Each script first checks and records its own precondition, and stops if it fails.
- Every command runs through a pinned Compose helper: fixed project name, project directory, files
  and `--env-file /dev/null`.
- Each command writes `raw/NN-*.txt` (stdout), `raw/NN-*.meta` (UTC, command, exit code) and
  `raw/NN-*.err` (only when stderr is not empty), as in v0.7.2.

The I4 agent gets the runbook as reference material. It chooses and runs each next action itself,
and it inspects each precondition (§12).

**The three kinds of check (parent §4.2), never conflated:**

| Check | How it is measured |
|---|---|
| *Replication caught up* | Per source partition, the flow's committed source offset (read from its Connect offsets topic) equals the source end offset (`rpk topic describe -p` on Redpanda, `kafka-get-offsets.sh` on Kafka). Source side only; offsets are never compared across clusters |
| *Consumer caught up* | Lag 0 for a named group on a named topic (`rpk group describe` on Redpanda, `kafka-consumer-groups.sh --describe` on Kafka) |
| *Application behaviour verified* | The functional test (§6) |

**Offset hand-off (step 6).** Per group (Catalog, Image) and partition of `tenant.tenant.events`,
the script records:
- (a) the final committed offset on Redpanda;
- the latest checkpoint, decoded with
  `org.apache.kafka.connect.mirror.formatters.CheckpointFormatter`: upstream and downstream offset;
- (c) the committed offset installed on Kafka;
- the offset-sync records around (a), decoded with `OffsetSyncFormatter`.

Rule: the checkpoint's upstream offset equals (a), and (c) equals the checkpoint's downstream
offset. Otherwise the script waits for the next sync, with a bounded number of retries. It stops if
(c) is missing or differs from the checkpoint.

**Replay amount.** The amount of possible reprocessing is **measured**, or estimated conservatively
from the recorded positions. It is not assumed from configuration:
- **Measured:** the number of records between the installed downstream offset (c) and the
  downstream position that corresponds to (a). The offset-sync records give that position when they
  bracket (a).
- **Upper estimate:** when no offset-sync bracket exists, the record states the conservative upper
  estimate that the recorded positions support.
- **No bound:** if no bound can be established, the record says so.

`offset.lag.max` is MM2's resync threshold, not a guarantee. This amends parent §4.2, which called
it an "accepted replay bound". The step-6 equality checks and stop conditions are unchanged.

**Checker.** `checker.py`, standard library only, reads `raw/` and writes one machine-readable
`checks.json`: each check's inputs, rule, result and the `raw/` files it used. Unit tests prove it
on hand-made outputs, covering every pass and stop case.

## 6. Traffic and the functional test (D15)

**Traffic.** All traffic comes from the system's own flows:
- the tenant registration RPC, called with the environment's own S2S client-credentials token, as
  in v0.7.2;
- the tenant seeder job;
- the catalog, category, attribute and image RPCs.

MinIO and imgproxy run, so image upload and promotion work. No consumer is started by hand, and no
offset is reset.

**Functional test** (parent §4.4), after step 8:
1. Create a shop, then a product with an image in it. Product Query returns the product with its
   current image URL (the tenant, product and image-promotion flows).
2. Update a category. Category Query returns the change (the category flow).
3. Update an attribute definition. Product Query and Category Query return the change (the
   attribute flow).

**Rules:**
- Every test object has a run-unique name that contains the run id.
- Read-model checks poll with a bounded timeout, never a fixed sleep. A timeout is a recorded
  failure.
- Each step records the RPC method, a digest of the response, the elapsed time and pass or fail.
  No token or credential is recorded.

## 7. Captures and declarations (parent §4.3)

| Capture | Broker | Allow-list | When |
|---|---|---|---|
| C1′ | Redpanda (`kafka:sokol111-local`) | the C1 groups (Catalog, Category Query, Image, Product Query) | before step 1, with traffic as for C1 |
| A-R | Redpanda | the same allow-list (no scope change) | after step 9 |
| A-K | Kafka (`kafka:sokol111-kafka`) | {Catalog, Image} | after step 9 |

**Rules:**
- **Ground truth:** `rpk group describe` and `kafka-consumer-groups.sh --describe` for each
  allow-listed group are taken just before and just after each capture (G and G′, as in v0.7.2).
- **Moved groups:** after the wave, Catalog and Image on Redpanda must read `Empty` or
  broker-reported `Dead`. A group that cannot be described makes the capture incomplete
  (`KAFKA_CAPTURE_INCOMPLETE`): the run stops. It is never read as a detachment.
- **After-wave declarations** are committed before A-R and A-K are taken. They follow the I1 §4.1
  rules, with the I2 fixture `i2-vectors/two-broker/declarations/` as the template.
- **Mappings:** the I1 §7 mappings are used unchanged.
- **Disclosure:** MirrorMaker 2's internal groups are outside both capture scopes.

## 8. Expected reference and replay

- **The reference is committed before the live run:** `i3-evidence/expected-after.json` holds the
  semantic rows of I2 §8.2 (crossing, status, reason, `cross_broker_producers`, per broker × Topic
  × consumer). It is committed in I3a together with `expected-after.sha256` and never edited
  afterwards.
- **Observed metadata is kept apart:** the capture T values, source revisions and digests go into
  `observed-metadata.json` after the run. The package keeps the two files separate.
- **Replay test (I3b, qualification tier):** the production import of the frozen package (the
  after-wave declarations, A-R, A-K, both mappings, the catalog) plus `get_binding_picture` for
  `catalog-management` on both brokers gives exactly the `expected-after.json` rows. A second
  import is a no-op.
- **Before-capture check:** C1′ gives the nine rows of I2 §8.1 with the I1 declarations.
- **Disclosure:** "no live attachment here" (parent §3.6) stays a report-level comparison (I2 §4).

## 9. Stages

Each stage fits one daily usage window and ends with a checkpoint record: what ran, which checks
passed, and where the next stage starts.

| Stage | Content |
|---|---|
| S1 | Bring-up (Compose stack, k3d, Tilt, MinIO, imgproxy), traffic, C1′ with G/G′ |
| S2 | Kafka and both MM2 flows configured, preflight P1–P5, §4.2 steps 1–2 |
| S3 | Steps 3–9, the after-wave declarations, A-R and A-K with G/G′, the functional test |
| S4 | Freeze the package, `observed-metadata.json`, the replay test |

A failed stage is recorded and the owner is asked (stop rule). Environment teardown removes only
what the run created (memory rule: check before deleting by name).

## 10. Risks to resolve first

| Risk | Probe | Stop condition |
|---|---|---|
| MM2 checkpoints and group-offset sync with Redpanda as the source | P5 | no installed offset, or a checkpoint that does not decode |
| Redpanda's reading of the moved groups (`Empty` or `Dead`) | describe the stopped groups once in S2, before the cut-over is committed to | a group that cannot be described |
| The v0.7.2 k3d host adaptations | S1 bring-up | a new adaptation that touches a Sokol111 repository |
| MinIO and imgproxy on the WSL2 host | S1 image upload through the RPC | image promotion does not complete |

## 11. Acceptance

| # | Check |
|---|---|
| C1 | Preflight P1–P5 passes and is recorded |
| C2 | The §4.2 protocol runs end to end. `checks.json` covers every step with its precondition and result |
| C3 | Replication progress per source partition is recorded; the hand-off (a), checkpoint and (c) is recorded per group and partition; the replay amount is measured or estimated (or "no bound" is stated) |
| C4 | C1′, A-R and A-K meet parent §4.3, with G/G′ ground truth |
| C5 | The functional test passes all three steps, and is recorded separately from AIP's claims (parent §4.4) |
| C6 | The replay test reproduces `expected-after.json` exactly, and C1′ reproduces the nine §8.1 rows |
| C7 | The committed `expected-after.json` digest equals `expected-after.sha256` from before the run |

**Stop rule** (parent §7): if a step cannot be done as specified, record the attempt and ask. Never
fake a result.

## 12. Delivery and I4 handoff

| PR | Content | Acceptance |
|---|---|---|
| I3a | the Compose overlay, MM2 properties, Helm values overlay, preflight and runbook scripts, `checker.py` with unit tests, after-wave declarations, `expected-after.json` + `.sha256`. No live run | checker unit tests; the digest committed |
| I3b | the live run S1–S4, the frozen `i3-evidence/` package, the replay test, the completion record, `i3-i4-handoff.md` | C1–C7 |

**I4 receives:**
- the reset procedure (environment back to the before-wave state);
- the runbook as reference material;
- `expected-after.json` as the reference answer.

The agent must carry out the wave itself (Proof C): it chooses each next action, inspects each
precondition and stops on a failed check. Its captures must reproduce `expected-after.json`.

## 13. Decisions

| # | Decision | Source |
|---|---|---|
| D13 | Kafka (KRaft) and one MM2 container per flow run in the infrastructure's local Compose stack, on Redpanda's network; only the bootstrap address changes for Catalog and Image; every adaptation is disclosed and stays outside the Sokol111 repos | owner, 2026-10-27 |
| D14 | I3's scripted run qualifies the environment and protocol and freezes the expected reference; I4 resets, the agent carries out the wave, and its captures feed the report and must match the reference | owner, 2026-10-27 |
| D15 | MinIO and imgproxy run; the functional test is driven through the services' Connect-RPC endpoints with the environment's S2S token; no UIs | owner, 2026-10-27 |
| — | `offset.lag.max` is a resync threshold, not a replay guarantee; the replay amount is measured or estimated (amends parent §4.2) | owner plan review, 2026-10-27 |
