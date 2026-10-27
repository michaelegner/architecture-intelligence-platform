# v0.8 I3 evidence package

**Governs:** [I3 specification](../i3-two-broker-environment-and-live-captures.md) Draft 0.2, §2–§8.
**Status:** I3a: the authored environment, the scripts, the checker and the committed reference.
Nothing in this package has run live yet; the staged run is I3b.

## What is in this package

| Path | Content | From |
|---|---|---|
| `environment/docker-compose.i3.yml` | Compose project `aip-v08-i3`: `kafka` (single-node KRaft, `kafka:29092` on `shared-network`, `localhost:19092` for the host), `mm2-flow-a`, `mm2-flow-b`, `mm2-probe` (behind profiles) | I3a, authored |
| `environment/mm2-*.properties` | The three MirrorMaker 2 workers, as in the I3 §3 worker-state table | I3a, authored |
| `environment/values-i3-{catalog,image}.yaml` | Helm values overlays: the upstream `config` string with one line changed, `brokers: "redpanda:29092"` → `brokers: "kafka:29092"` | I3a, authored |
| `environment/upstream-values/` | The two upstream values files, copied unchanged from `Sokol111/ecommerce-infrastructure@07c059908b99e08448cf1c2c7dad6a865fe5ccf0` (`environments/local/values/`), so the one-line difference is testable | upstream |
| `declarations/` | The after-wave declarations: byte copies of `../i2-vectors/two-broker/declarations/` (I1 §4.1 rules) | I3a |
| `expected-after.json`, `expected-after.sha256` | The expected after-wave semantic rows (I2 §8.2), committed before any run and never edited (C7) | I3a |
| `raw/`, `captures/`, `checks.json`, `observed-metadata.json` | The run record | I3b |

## Adaptations (disclosure)

- **The second broker and the bridge are authored for the showcase.** Sokol111 runs one
  Redpanda broker. Apache Kafka `4.1.2` and the three MirrorMaker 2 workers come from this
  package, not from Sokol111.
- **The only change to a Sokol111 service is the broker address** of Catalog and Image
  (`kafka.brokers`, used for both producing and consuming). Nothing is committed to a Sokol111
  repository.
- **No Helm release exists.** Tilt renders the charts (`k8s_yaml(helm(...))`). Step 8 renders the
  chart's `templates/configmap.yaml` exactly as the Tiltfile does
  (`environments/local/Tiltfile` lines 149–152 and 209–217 at `07c0599`: `helm dependency build`,
  release name = chart name, namespace `dev`, `values/<chart>.yaml` then `values.debug.yaml`), plus
  the overlay. Before it applies the ConfigMap, it records the live one and checks that both have the
  same name and namespace and that the only changed line is `kafka.brokers`. Then it scales the
  deployment back to 1.
- **Tilt must be stopped after the S1 bring-up**, or it re-applies the old values. Step 8 checks
  that no process is named `tilt` (`pgrep -x`, so a shell that only carries the text cannot match). Stop `tilt up` with Ctrl-C and never run `tilt down`: the Tiltfile also manages the
  Sokol111 Compose stacks (`docker_compose(...)`, including Redpanda), and `tilt down` removes them.

## Pins

| Item | Pin |
|---|---|
| Kafka and MirrorMaker 2 | `apache/kafka:4.1.2@sha256:5cc2a2fd93fa2687b44015eee04fb2c3edd9e526bd64bf8bec5ff1e268772e0e` (`connect-mirror-maker.sh` of the same image) |
| Sokol111 infrastructure | `ecommerce-infrastructure@07c059908b99e08448cf1c2c7dad6a865fe5ccf0` |
| Service APIs (functional test) | catalog `7cecb3e1131dbd5199ce25e9cf101d75d3365171`, image `2167948573ced4b2854d8aed93fb83b242cf2e7f`, product-query `692895e8f23a7d8b87befa7ae345d05f74ebe6a9`, category-query `1638e1def7f298928c9cadbadb7f41053c439cf5`, tenant `d9b90972f77b6a2df7ebee0f52e0cd8124937fe7` |

**I3b obligation: MinIO and imgproxy.** Sokol111's `compose/storage.yml` uses `latest` tags for
MinIO and `minio-init`, and v0.7.2 never started them. I3a invents no pin. I3b records the exact
resolved image references (`repository@sha256:…`) of MinIO, `minio-init` and imgproxy in this
package. The I4 reset procedure (I3 §12 handoff) uses those references and never pulls `latest`
again. The I3 completion record checks this.

## MirrorMaker 2 timing

The Kafka 4.1 defaults (600 s topic and group refresh, 60 s checkpoints and group-offset sync)
are too slow for a staged run. Every worker sets them to 10 s:
`refresh.topics.interval.seconds`, `refresh.groups.interval.seconds`,
`emit.checkpoints.interval.seconds`, `sync.group.offsets.interval.seconds`; `offset.lag.max=1`.
Kafka Connect commits the replicated source offsets, which the replication checks read, every
`offset.flush.interval.ms` (default 60 000 ms); every worker sets it to 10 000 ms. The dedicated
MirrorMaker 2 worker takes it only with the target cluster's prefix
(`kafka.`, `redpanda.`, `kprobe.offset.flush.interval.ms`): at 4.1.2,
`MirrorMakerConfig.workerConfig` forwards a bare top-level key only for a fixed list of prefixes,
so P1a rejects a bare key.
`offset.lag.max` is a resync threshold, not a replay guarantee (I3 §13): the replay amount is
measured or estimated (`checker.py handoff`).

**Bounded waits.** Each wait for replication, a checkpoint, an installed group offset or a group
state has the deadline
`3 × sync.group.offsets.interval.seconds + refresh.groups.interval.seconds` = 40 s
(`MM2_DEADLINE_SECONDS` in `harness/v08/i3/lib.sh`, unit-tested against the property files). Before
the deadline a check is `PENDING` and is polled again; after it, the check is `FAILED`. Every
verdict records its elapsed time and deadline.

Waits that do not depend on MirrorMaker 2 have their own deadlines (`lib.sh`):

| Wait | Deadline | Basis |
|---|---|---|
| A group reads `Empty` or `Dead` (step 4, A-R) | 75 s | the consumer leaves, or its session timeout ends: 45 s, the Kafka client default (the upstream config sets none), plus 30 s |
| A stopped deployment has no pod (steps 3, 4) | 60 s | the 30 s default termination grace period, plus 30 s |
| Catalog and Image are `Stable` on Kafka (step 8) | 120 s | two restarted pods join their groups; the images are already on the node |

I3b records the observed times in the run README.

**Flow B's checkpoints topic.** Flow B syncs no group (`groups = ^$`), but P1b at step 7 still
expects `kafka.checkpoints.internal` on Redpanda: at `apache/kafka` 4.1.2,
`MirrorCheckpointConnector.start()` creates the checkpoints topic whenever the flow is enabled,
before it loads any consumer group.

**Replication factor 1.** The Kafka 4.1 default `replication.factor` for mirrored data topics is 2,
which fails on a single-node target. Every worker sets it, and each internal topic's replication
factor, to 1.

## Scripts (`harness/v08/i3/`)

Each script stops (exit 2) on a failed precondition or check. No wrapper chains them: the operator,
and in I4 the agent, runs them one by one. Every script needs `I3_RAW_DIR` (the run's `raw/`).

| Script | What it does |
|---|---|
| `preflight/p1a.sh`, `p3.sh` | Static checks of the three property files (P1a, P3) |
| `preflight/p4.sh` | Starts `kafka`; `kafka:29092` answers from a Compose container and from a k3d probe pod (`--rm`) |
| `preflight/p5.sh` | The group-offset-sync probe on `mm2-probe`. Before it starts, every name the teardown may delete must be absent: the probe container (running or stopped), and the probe topic, group and internal topics on both brokers; the teardown, armed only then, removes exactly those, also on failure |
| `steps/01.sh` … `09.sh` | Parent §4.2, one step each (step 8 needs `SOKOL111_INFRA`) |
| `capture.sh c1-prime \| a-r \| a-k` | One capture through `harness/kafka-capture/capture.py`, with G before and G′ after (on Kafka both `--describe` and `--describe --state`); A-R also checks that the moved groups read `Empty` or `Dead`; each capture rewrites `checks.json` |
| `functional_test.py` | The §6 functional test through Connect-RPC; `--dry-run` prints the planned calls |
| `checker.py` | The rules; exit 0 `PASSED`, 3 `PENDING`, 2 `FAILED`; `collect` writes `checks.json` |

Order in I3b (I3 §12): S1 bring-up, traffic, `capture.sh c1-prime`; preflight P1a, P3, P4, P5;
steps 1–8; the functional test; step 9; `capture.sh a-r`, `capture.sh a-k`. Step 3 stops Catalog,
waits until its last pod is gone, and only then checks Image's lag on `catalog.product.events`
(parent §4.2: the precondition to continue).

## Functional test (D15)

The driver calls these methods, as named in the pinned protos:

1. `tenant.v1.TenantRegistrationService/RegisterTenant`, `GetRegistrationStatus` (until
   `REGISTRATION_STATUS_COMPLETED`); `catalog.v1.AttributeService/CreateAttribute`
   (`ATTRIBUTE_TYPE_TEXT`); `catalog.v1.CategoryService/CreateCategory`
   (`CATEGORY_ATTRIBUTE_ROLE_SPECIFICATION`); `image.v1.ImageService/CreatePresign`
   (`OWNER_TYPE_DRAFT`, `IMAGE_CONTENT_TYPE_PNG`, `IMAGE_ROLE_MAIN`), the upload to `upload_url`,
   `ConfirmUpload`; `catalog.v1.ProductService/CreateProduct`; then
   `product_query.v1.ProductQueryService/GetProductById` until `small_image_url` and
   `large_image_url` are set.
2. `catalog.v1.CategoryService/UpdateCategory` (with the version), then
   `category_query.v1.CategoryQueryService/GetCategoryById` until the new name is returned.
3. `catalog.v1.AttributeService/GetAttributeById` and `UpdateAttribute` (with the version), then
   `GetProductById` and `GetCategoryById` until `attributes[].name` holds the new name.

Every object name carries the run id. The record has the method, the response SHA-256, the elapsed
time and pass or fail; never a token, a password, a request body or the presigned URL.

**Open for I3b: the token.** `RegisterTenant` takes the environment's S2S client-credentials token,
as in v0.7.2 (`--s2s-token-command`). The catalog and image write RPCs probably need a user token
of the new shop's merchant, not the S2S token (`--token-command`). The driver therefore runs the
user token command only after the registration is `COMPLETED`, with `AIP_I3_TENANT_SLUG`,
`AIP_I3_EMAIL` and `AIP_I3_PASSWORD` of the new shop in its environment. I3b settles which token
each call needs, and the endpoint URLs (`--endpoint NAME=URL`); it records both in the run README,
but never a token or the password. A missing id in a response fails the step with its name; a
missing `version` is 0 (protojson omits zero values).

## Deviation from the I3a plan

The checker's hand-made `raw/` inputs are inline in `tests/unit/test_v080_i3a_checker.py`, not in a
`tests/fixtures/v080_i3_checker/` directory: each test builds exactly the broker-tool output it
needs, which keeps the case and its input together.
