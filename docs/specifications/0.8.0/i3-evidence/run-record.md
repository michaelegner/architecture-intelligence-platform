# v0.8 I3b run record

Stage checkpoints of the staged live run (I3 spec §9). Raw files: [`raw/`](raw/). Sokol111
revisions: the v0.7.2 freeze. Harness revisions (branch `feat/v0.8-i3b-live-run`). Each stage's
revision is the newest commit before its first recorded `.meta` time:

| Commit (UTC) | Harness | Ran on it |
|---|---|---|
| 16:13:03Z | `9a1af65` | S1 and C1′. From 17:47 the working tree also held the uncommitted driver and token changes that became `836e5f9`; the probe `S1-15` (17:51:35) ran on them |
| 17:56:16Z | `836e5f9` | P1a, P3, P4 attempt 1 |
| 18:57:47Z | `7e45f3f` | P4 attempt 2, P5, steps 1–9, the functional test, A-R, A-K |

## S1: bring-up and C1′ (started 2026-10-27T16:13:29Z)

| Time (UTC) | What | Result |
|---|---|---|
| 16:13 | Host check: ports 9092, 19092, 29092, 3001, 8080, 9000, 27017, 80, 443, 5000 and 10350 are free; 0 dangling images; before-run inventory of containers, volumes, networks and images taken | ok |
| 16:14 | 16 Sokol111 repositories cloned at the v0.7.2 freeze commits; each `HEAD` is checked against the freeze | ok |
| 16:15 | k3d v5.9.0, Tilt v0.37.8 and Helm v3.22.0 downloaded; the published SHA-256 checked | ok |
| 16:16 | Host adaptations in the local clone only, as in v0.7.2: the k3d CA path, `--kubelet-arg=fail-cgroupv1=false` (cgroup v1 host), and `network: host` dropped from the `logto-seed` build ([`raw/S1-02`](raw/S1-02-adaptations.txt)) | ok |
| 16:16–16:18 | `make cluster-inject-ca`, `make init` (cluster, Traefik, Alloy); `KUBECONFIG` and the Helm homes isolated; `~/.kube` untouched | ok |
| 16:19 | `tilt up` for the Go services, the seeder, MinIO, `minio-init` and imgproxy | partial, see below |
| 16:50 | **Logto secrets missing.** `logto-credentials` held only `*-client-id` keys, and the tenant service failed with `couldn't find key tenant-m2m-client-secret`. The pinned `logto-seed` takes a new app's secret from the `POST /applications` response, which carries none with the cached Logto 1.45.0 image (`svhd/logto@sha256:097cd476…`, the same image as v0.7.2). For an existing app it reads `/applications/<id>/secrets`. | found |
| 16:51 | `tilt trigger logto-seed` (the environment's own seed, run again): every app "already exists", the secrets were read, and `Updated K8s secret`. All ten keys are present. This is an operational re-run, not a code change; v0.7.2 needed one Tilt restart too. | fixed |
| 16:50 | **MinIO unavailable (stop).** `minio/minio:latest` and `minio/mc:latest` fail to pull: `pull access denied … repository does not exist`. Docker Hub returns 404 for both repositories, `quay.io/minio/*` returns 401 to anonymous pulls, and the official binaries at `dl.min.io` return 410 Gone. The upstream source release `RELEASE.2025-10-15T17-29-55Z` is on GitHub. imgproxy `darthsim/imgproxy:v3.25` resolves. | **stopped: owner decision** |
| 16:58 | **Owner decision:** MinIO from Bitnami's frozen builds, pinned by digest: `bitnamilegacy/minio@sha256:451fe685…` (MinIO `DEVELOPMENT.2025-05-24T17-08-30Z`) and `bitnamilegacy/minio-client@sha256:00dcc4e5…` (mc `DEVELOPMENT.2025-05-21T01-59-54Z`). | decided |
| 16:58–17:47 | Adaptation in the local clone's `compose/storage.yml` only ([`raw/S1-07`](raw/S1-07-adaptation-minio.txt)). It sets the two pinned images, `entrypoint: ["minio"]`, the Bitnami data path `/bitnami/minio/data`, and `MC_CONFIG_DIR=/tmp/.mc` for the init job. The image has no `curl`, so the healthcheck is a bash `/dev/tcp` probe of `/minio/health/live`. A first probe without a `Host` header got 400, and the fixed probe returns 200. `minio-init` created the `images` bucket and its 1-day `drafts/` rule; imgproxy is healthy. | ok |
| 17:47 | Every Tilt resource is `ok` | ok |
| 17:47 | **Host DNS:** this host's resolver (a router with rebind protection) does not resolve `*.127.0.0.1.nip.io`. Calls go to `127.0.0.1` with the ingress host name in `Host`, which Traefik routes by. This is a host adaptation; nothing in Sokol111 changes. | adapted |
| 17:48 | Traffic: `RegisterTenant` for `i3shop` with the platform token from `tokens/token.py` returns `REGISTRATION_STATUS_COMPLETED` ([`raw/S1-10`](raw/S1-10-register-tenant.txt)). The registration starts the seeder Job `seeder-i3shop`: 20 attributes, 4 categories and the demo products, with images, complete without error in 10 s ([`raw/S1-11`](raw/S1-11-seeder-log.txt)). `catalog.product.events` holds 120 records (60 in v0.7.2, when image upload failed). | ok |
| 17:49 | Before C1′: the four groups are `Stable` with lag 0 on every assigned topic | ok |
| 17:49:03 | **C1′** captured ([`captures/c1-prime/`](captures/c1-prime/kafka-consumer-state.json)): all four groups `Stable`. G and G′ around it are byte-identical for each group. | ok |
| 17:49 | Image references recorded: Compose containers with their repository digests ([`raw/S1-12`](raw/S1-12-compose-images.txt)), cluster pods ([`raw/S1-13`](raw/S1-13-cluster-images.txt)), and versions ([`raw/S1-14`](raw/S1-14-versions.txt)) | ok |
| 17:49:30 | `tilt up` stopped with SIGINT, never `tilt down`. The Compose stack and the five deployments keep running. | ok |
| 17:48–17:51 | **Token scope:** `GetRegistrationStatus` needs `tenants:read`. The platform app has only `tenants:write` (403). The service app's role grants `tenants:read`, but a client-credentials token carries only the scopes it requests, and the seeder's scope omits it (403). `token.py ecommerce` now requests `tenants:read` too. The driver polls the status with the service token and sends no shop header on tenant calls. The read-only probe returns `COMPLETED` ([`raw/S1-15`](raw/S1-15-status-probe.txt)). | fixed (on the working tree; committed as `836e5f9`) |

**Checkpoint S1 (2026-10-27T17:52Z): complete.**
- **Passed:** bring-up with MinIO and imgproxy; traffic; C1′ with G = G′; the image references are
  recorded.
- **Adaptations made:** the Bitnami MinIO images (owner decision), the `logto-seed` re-run, and
  host DNS through `127.0.0.1` plus `Host`.
- **Driver fixes found:** the status-poll token, `tenants:read`, and `--connect-to`. They are
  unit-tested and committed as `836e5f9` before S3, the only stage that uses the driver.
- **Next:** S2, preflight P1a–P5 and steps 1–2.

## S2: preflight and steps 1–2 (started 2026-10-27T18:44:47Z; harness `836e5f9`, then `7e45f3f` from P4 attempt 2)

| Time (UTC) | What | Result |
|---|---|---|
| 18:44 | Stack check: the six Compose containers healthy, the five deployments ready, Tilt not running, no `aip-v08-i3` container yet | ok |
| 18:45 | P1a ([`raw/P1a-p1a.check.json`](raw/P1a-p1a.check.json)) and P3 ([`raw/P3-p3.check.json`](raw/P3-p3.check.json)) | PASSED |
| 18:45:46–49 | **P4 attempt 1** ([`raw/P4-attempt1-*`](raw/)): `frozen_compose up -d kafka` (exit 0) at 18:45:46; the Compose-side probe ran at 18:45:49 and failed (`Connection to node -1 … could not be established`). The broker logged `Transition from STARTING to STARTED` at 18:45:50. A hand retry of the same probe at 18:46 answers. **Cause:** `p4.sh` probes right after `up -d`, with no bounded wait for the broker to start (a harness race, not a broker fault). | **stopped: owner decision** |
| 18:55 | **Owner decision:** fix P4 and rerun. `p4.sh` now polls the broker every 2 s, bounded by `KAFKA_START_DEADLINE_SECONDS` (60 s), records the wait, then probes. Harness commit `7e45f3f`, guard test proven by removing the wait. | decided, fixed |
| 18:57 | **P4 attempt 2**: the broker answered 2 s after `up -d` (it was already running); the probes from a Compose container and from the k3d pod `aip-i3-kafka-probe` (`--rm`, gone afterwards) both answer ([`raw/P4-*`](raw/)) | PASSED |
| 18:59–19:00 | **P5** probe flow, Redpanda → Kafka: P1b ([`raw/P5-mm2-probe-p1b.check.json`](raw/P5-mm2-probe-p1b.check.json)) passed. Hand-off ([`raw/P5-sync.check.json`](raw/P5-sync.check.json)): (a) 3, checkpoint 3 → 3, (c) 3. The replay amount is `NO_BOUND` (no offset sync at or above the final upstream offset). The verdict was evaluated 64 s after the wait started; the last attempt began before the 40 s deadline, and each attempt's collection takes about 20 s (two topic dumps with a 10 s consumer timeout each). Teardown at 19:00:46: the container, both probe topics, the internal topics and the group on both brokers were removed. Each name is confirmed absent afterwards. | PASSED |
| 19:01 | **Step 1:** `catalog.attribute.events`, `catalog.category.events` and `catalog.product.events` created on Kafka with Redpanda's partition count (1) and RF 1; end offsets 0 ([`raw/01-*`](raw/)) | ok |
| 19:02 | **Step 2:** flow A started; P1b ([`raw/02-mm2-flow-a-p1b.check.json`](raw/02-mm2-flow-a-p1b.check.json)) passed; replication of `tenant.tenant.events` caught up, last replicated offset 0 of end offset 1, after 17 s ([`raw/02-replication.check.json`](raw/02-replication.check.json)) | PASSED |

**Checkpoint S2 (2026-10-27T19:03Z): complete.**
- **Passed:** P1a, P3, P4 (attempt 2), P5 with its teardown, step 1 and step 2.
- **Open risk (owner clarification):** P5 shows only that group-offset sync works for the probe
  group. The I3 §10 risk "Redpanda's reading of the moved groups" stays **unresolved** until
  step 4 and the A-R moved-group check pass for Catalog and Image.
- **Live state:** flow A runs; flow B is stopped; Catalog and Image still consume from Redpanda.
- **Next:** S3, steps 3–9, the functional test, A-R and A-K. It runs on harness `7e45f3f`.

## S3: the cut-over and the after-wave captures (started 2026-10-27T19:12Z, harness `7e45f3f`)

| Time (UTC) | What | Result |
|---|---|---|
| 19:12 | **Step 3:** Catalog scaled to 0 at 19:12:11; its last pod was gone by 19:12:43. Image on `catalog.product.events`: offset 120, lag 0 ([`raw/03-image-lag.check.json`](raw/03-image-lag.check.json)). | PASSED |
| 19:13 | **Step 4:** Image scaled to 0, its pod gone. On Redpanda, `ecommerce-catalog-service` and `ecommerce-image-service` both read `Empty` ([`raw/04-groups-state.check.json`](raw/04-groups-state.check.json)). | PASSED |
| 19:13 | **Step 5:** Product Query (attribute 20, product 120) and Category Query (attribute 20, category 4) at lag 0 on Redpanda ([`raw/05-*`](raw/)) | PASSED |
| 19:14 | **Step 6:** hand-off on `tenant.tenant.events` partition 0 for both groups: (a) 1, checkpoint 1 → 1, (c) 1, after 27 s ([`raw/06-handoff.check.json`](raw/06-handoff.check.json)). The replay amount by the committed rule is `NO_BOUND`: the only offset sync is 0 → 0, none at or above the final upstream offset 1. **Observed alongside it, not a change to the rule:** the end offset of `tenant.tenant.events` is 1 on both brokers ([`raw/06-kafka-tenant-end`](raw/06-kafka-tenant-end.txt), [`raw/06-redpanda-tenant-end`](raw/06-redpanda-tenant-end.txt)), equal to (a) and (c). So no record lay after the installed offset at hand-off. | PASSED |
| 19:15 | **Step 7:** flow B started; its internal topics exist with RF 1, including `kafka.checkpoints.internal` on Redpanda, created although flow B syncs no group ([`raw/07-mm2-flow-b-p1b.check.json`](raw/07-mm2-flow-b-p1b.check.json)) | PASSED |
| 19:15 | **Step 8:** Tilt not running. Each ConfigMap was rendered exactly as the Tiltfile renders it, plus the overlay. The rendered and live ConfigMaps have the same name and namespace, and only the brokers line differs ([`raw/08-configmap-*.check.json`](raw/)). Applied; both deployments scaled to 1. On Kafka, both groups `Stable` (Catalog 1 member, Image 2: its tenant and product consumers) ([`raw/08-kafka-groups.check.json`](raw/08-kafka-groups.check.json)). On Redpanda both stay `Empty`. | PASSED |
| 19:16:33 | **Functional test** `--run-id s3r1` through `127.0.0.1` plus `Host` ([`raw/FT-functional.check.json`](raw/FT-functional.check.json)). Step 1: shop `i3-s3r1`, attribute, category, image upload and confirm, product, then Product Query returns both image URLs. Step 2: the category update reaches Category Query. Step 3: the attribute update reaches Product Query and Category Query. Every call passed. A secret scan of the records found no token, secret or password. | PASSED |
| 19:17 | **Step 9:** flow B replication caught up on all three catalog topics ([`raw/09-replication-b.check.json`](raw/09-replication-b.check.json)). Lag 0 for Product Query and Category Query on Redpanda, and for Catalog and Image on Kafka ([`raw/09-*-lag.check.json`](raw/)). | PASSED |
| 19:18 | **New traffic, checked for duplicates:** Kafka's catalog topics hold 122, 22 and 6 records. Every record is tenant `i3-s3r1`: the functional test's shop. Its registration started the seeder Job `seeder-i3-s3r1`, which seeded that shop's demo catalog; the remaining records are the test's own writes. On Redpanda, `catalog.product.events` holds 120 `i3shop` records (S1) and 122 `i3-s3r1` records (mirrored), with 242 unique `event_id`s. The attribute topic holds 42 records with 42 unique ids, the category topic 10 with 10. **No `catalog.*` record is duplicated** (parent §4.2) ([`raw/09-catalog-tenants-and-event-ids`](raw/09-catalog-tenants-and-event-ids.txt)). | ok |
| 19:19:02 | **A-R** ([`captures/a-r/`](captures/a-r/kafka-consumer-state.json)): Redpanda, the four C1 groups. Catalog and Image `Empty`, the two query services `Stable`. G = G′ for each group; the moved-group check passed ([`raw/AR-moved-state.check.json`](raw/AR-moved-state.check.json)). | PASSED |
| 19:19:22 | **A-K** ([`captures/a-k/`](captures/a-k/kafka-consumer-state.json)): Kafka, Catalog and Image, both `Stable`. G = G′ (offset and state rows). | ok |

**Checkpoint S3 (2026-10-27T19:20Z): complete.**
- **Passed:** steps 3–9, the functional test, A-R and A-K. `checks.json` holds 22 verdicts, all
  `PASSED`. P4's evidence is its recorded exit codes; P4 writes no verdict file.
- **Risk resolved:** "Redpanda's reading of the moved groups" — step 4 and the A-R moved-group
  check both read `Empty` for Catalog and Image.
- **Live state:** both flows run; Catalog and Image consume from Kafka.
- **Next:** S4. Write `observed-metadata.json`; freeze (sanitize, secret scan, `SHA256SUMS`,
  verify); the replay test; the completion record and the handoff; teardown.

## S4: freeze, replay and teardown (started 2026-10-27T19:21Z)

| Step | What | Result |
|---|---|---|
| 1 | `observed-metadata.json` written from the recorded files: capture T values and digests, harness revisions, the Sokol111 freeze, image references, tools, endpoints, adaptations | ok |
| 2 | Sanitized: `/home/…/aip-v08-i3b` → `<AIP checkout>` and `/home/…/sokol111-i3b` → `<run home>` in 47 files. No other edit. The upstream author's path in the removed line of the k3d diff is upstream content and stays. | ok |
| 3 | Secret scan over the final bytes: the five real Logto client secrets (read from the cluster, never printed) in 297 files gave 0 hits; no JWT, private key or bearer header. `client_secret` occurs only as an environment-variable name in the upstream values. `minioadmin123` is Sokol111's published local-development default. | ok |
| 4–5 | `SHA256SUMS` over `raw/`, `captures/`, `checks.json` and `observed-metadata.json` (278 files), computed after steps 2–3 and verified with `sha256sum -c`. `expected-after.json` still matches `expected-after.sha256`; git shows both unchanged (C7). | ok |
| 6 | `tests/integration/test_v080_i3b_replay.py` (qualification tier): the package digests; A-R plus A-K give exactly `expected-after.json` (rows and limitations), and a second import is a no-op; C1′ gives the nine I2 §8.1 rows. Replacing A-R with C1′ fails the test. | 3 PASSED |
| 7 | Teardown of what `created.txt` lists, each name checked first (created after 16:13:29Z, absent from the before-inventory, no foreign user): the `aip-v08-i3` and `ecommerce` Compose projects with their volumes, the `logto` network, the k3d cluster with its registry and `shared-network`, and the images the run built. Pulled base images stay. Afterwards containers, volumes and networks equal the before-inventory; `~/.kube` is untouched. | ok |
| 7a | **Found in teardown:** three anonymous volumes from P5's `mm2-probe` container (18:59:27Z; `apache/kafka` declares `VOLUME`s). P5's `rm -sf` leaves them, so they were removed by hand once confirmed unused. `p5.sh` now uses `rm -sfv`, with a guard test. The evidence of the run is unchanged. | fixed |
| 7b | **Gap found in review (#649):** no Redpanda deletion is recorded for P5's group `aip-probe-group`, which was `Empty` there at 19:00:15 (`raw/P5-source-group`). The teardown's `present redpanda-group` (on `rpk group list`) did not find it, so the absence check may not see `Empty` groups. The environment is gone, so this cannot be verified here; [`i3-i4-handoff.md`](../i3-i4-handoff.md) §4 asks I4 to verify it at bring-up. The frozen evidence is unchanged. | open, for I4 |

**Checkpoint S4: complete.** The package is frozen and replays. The environment is torn down.
