# I4.4 — Final-Candidate Real-System Revalidation

Spec §27's I4.4 scope: "Deliver clean Quarkus and Airflow runs against the same final candidate,
actual-facts/report hashes, comparison reports, final dispositions, and known limitations." Spec §19
("no substitution") requires this real-system execution regardless of I4.1/I4.2's `NO_CHANGE`
outcome — a source diff or content-equivalence argument does not satisfy it.

**Revision note (PR #52 review):** the first version of this record had three gaps, corrected below:
it collapsed Quarkus's comparator-only result and its overall dossier result into one number,
silently dropping the frozen `INSUFFICIENT_EVIDENCE` finding (§"Final dispositions" below); it
omitted several mandatory identity fields (§"Candidate identity", per-system sections); and its
Quarkus window-closing procedure was an undocumented, inconsistent per-run operator judgment call
rather than one committed, bounded rule (§"Method note"). Fixing the third finding surfaced a real
bug in the runbook's own drain-check endpoint (see "Window-closing procedure" under Quarkus below) —
both Quarkus runs were repeated end to end under the corrected, now-committed procedure; Airflow's
runs did not need repeating, since its own drain barrier was already one deterministic bounded rule
in both original runs. A second re-review round found one further gap: the Quarkus "profile
revision" still cited only the AIP candidate SHA, which does not contain the `runbook.md` fix (that
landed in a later, profile-only commit) — corrected in the Quarkus section's "profile revision"
block below with an explicit per-file component manifest, plus a table-label fix distinguishing
locally built service images' **Image ID** from pulled infrastructure images' **RepoDigest** (both
content-addressed, but not the same field). Neither correction required another real-system run: the
runbook content the two reported runs actually executed is byte-identical to what is now committed.

Both profiles were executed twice each, back-to-back, from clean state, against the identical pinned
AIP candidate image — never rebuilt between runs — per spec §20's repeatability requirement.

## Candidate identity (spec §3 / §20)

```text
AIP candidate SHA:        9f95d48046ab1942bb1a77c9a3a887a542120b98
Dependency lock (uv.lock) SHA-256:
                           7945b63c47391d7bd81a9c7025dc2004907c33db6147cb169795357a27381a6a
AIP candidate image:       aip-candidate-9f95d48 (local build, not pushed to a registry)
AIP image ID:              sha256:67a27be2ec4ea370f24ad6b3e0129d58400b27fbdd2cf20ac3128482365d5aa2
```

The same image ID was verified (`docker inspect ... --format='{{.Image}}'`) as the running
`architecture-intelligence` container in every one of the four qualifying runs below (plus the two
superseded Quarkus runs the procedure fix repeated) — the image was built once, before any run, and
reused unmodified throughout, so no run could have been comparing against a different candidate
build.

```text
Environment:  Linux 5.15.153.1-microsoft-standard-WSL2 x86_64
Docker:       29.7.2
Compose:      v5.3.1 (Compose v2 spec)
```

### Effective Compose configuration (spec §19's "committed profile")

Both compose profiles pin `architecture-intelligence` to the pre-built candidate image via a local,
gitignored `docker-compose.override.yml` layering `image: aip-candidate-9f95d48` onto the committed
`build: ../../../..` key (Compose only rebuilds a service with both keys set when the named image is
missing or `--build` is passed explicitly — neither happened in any run here, so the base commit's
own `build:` directive was never exercised). To make that override's effect auditable rather than
merely asserted, the fully resolved `docker compose config` output for each profile (secrets
redacted to the literal string `REDACTED`, since they are per-run generated values, not part of the
profile identity) is committed and hashed:

```text
artifacts/quarkus-compose-config.yaml   SHA-256: 735d423c9095305bd3622c9375bcf1b05d04c169e7c13e5dd8db674873d494ed
artifacts/airflow-compose-config.yaml   SHA-256: d767f087194292d252e6ec19b3e63ec85aad27df2ee2dace16c8ed153c6ce207
```

Both files show `architecture-intelligence.image: aip-candidate-9f95d48` as the effective image for
that service — confirmed by `grep` against each committed file, not merely described in prose.

## Quarkus Super Heroes

```text
Upstream commit:            8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
AIP candidate SHA:          9f95d48046ab1942bb1a77c9a3a887a542120b98  (unchanged — see
                             "Candidate identity" above; the profile-only fix below does not move
                             this)
Ground-truth revision:      docs/real-world-validation/quarkus-super-heroes/expected.yaml @ 9f95d48
Comparison-tool revision:   real_world_validation/ @ 9f95d48
```

**Quarkus profile revision (PR #52 re-review — a single commit SHA is insufficient here, since
`runbook.md`'s window-closing fix landed in a later commit than the unchanged `runtime/`,
`expected.yaml`, `ground-truth.md`, and `profile.md`, and the AIP candidate SHA above must not be
conflated with the profile's own revision):**

```text
runbook.md (window-closing procedure, corrected — see below):
                             a81a01f778e143e69b00cd5be068e34679adb68a
                             Git blob f259061353d7d0722d36ebb2452d49e46a75c3ba
runtime/docker-compose.yml: Git blob 4b4d4c76febb8caa0c96f06e36c90bfdbe2ac1aa (unchanged since 9f95d48)
runtime/traffic.sh:         Git blob 0ae949aeddfab9f692c6383a51909f38fea2b982 (unchanged since 9f95d48)
expected.yaml:               Git blob 82dc7182d1643be72a48d12d5f7515047b3e5dd3 (unchanged since 9f95d48)
ground-truth.md:              Git blob f763a269a2b04a0d3192233e3a82899feba41d2a (unchanged since 9f95d48)
profile.md:                  Git blob 7deb2e5ce04d9d28f6c1b48308519cc34054c5c4 (unchanged since 9f95d48)
```

`git diff 9f95d48..a81a01f -- docs/real-world-validation/quarkus-super-heroes/` touches only
`runbook.md` — every other profile file is byte-identical to the AIP candidate commit, so this
component manifest is the complete, exact profile the two qualifying runs below executed. Both runs
were captured using this exact corrected `runbook.md` content (typed and run interactively, not
executed as a script, but character-for-character the same procedure now committed at `a81a01f`) —
so, per spec §20's own allowance, this identity correction did not require repeating the runs a
second time; it only needed the record to name the revision actually used.

Image identity — service images are locally built and never pushed to a registry, so their content
address is a local **Image ID** (`docker inspect --format='{{.Id}}'`), not a **RepoDigest**; the
infrastructure images below are pulled from a registry and so carry a real `RepoDigest`
(`docker inspect --format='{{json .RepoDigests}}'`) — both are content-addressed, but they are not
the same Docker identity field, and PR #52 re-review correctly flagged the table as conflating them:

```text
Base image (all 6 services), RepoDigest:
                              registry.access.redhat.com/ubi10/openjdk-25-runtime:1.24
                             @sha256:68525bc239f93a62070625354e3b863be0963f61f1338794011665d5b8a946f5

Locally built service images, Image ID (never pushed, so no RepoDigest exists):
rest-fights:8ea0337          sha256:e2d3a3bfb61878342c1922dbe223bb18b521b0d6c21dd655a61d979b15b0823c
rest-heroes:8ea0337          sha256:2d1aca9454dec5b4cd508b6b61d72c5411efbe79458826fd92ec04753e215c67
rest-villains:8ea0337        sha256:ac7ca03053fd09aebb4a8d8bf851f6eddce181175023ec6f42c3073f9bb37e99
rest-narration:8ea0337       sha256:da43f7def254c5fa536c884d1949f1b0a878bffb06266d34d2e1a14f5ca38fbd
event-statistics:8ea0337     sha256:64b35d4a668c4dca7e8dcf196273cff5b9fdf3503f52c17549c774fd5f3a9cdc
grpc-locations:8ea0337       sha256:d11439741f5ae923565e974db79a66a2492d86790fdc93ccdfe3be11882f3da2

Pulled infrastructure images, RepoDigest:
neo4j:5.26.0                 sha256:5a015e53de1895e7eee1574ae0325cf8c4b89587222778108c594bdd45a474b5
mongo:8.3.8 (fights-db)      sha256:5211c51171f57ae60842b11664bb244628971b3d35325762a97888337b9bb0db
apicurio-registry:3.1.7      sha256:3ff121c9f744d535ef770b80ff95693bc95063295316a5864b56312b6edfb4e2
kafka-native:4.2.0           sha256:777f2dddec6970003f1f27922a8c317d87140567b0537e801d35669ad9a81faf
postgres:18.6 (heroes/villains-db)
                             sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280
mariadb:11.5.2 (locations-db) sha256:2d50fe0f77dac919396091e527e5e148a9de690e58f32875f113bef6506a17f5
otel-collector:0.159.0        sha256:7725a7a10c87d8853208bdd4bb3439ad3c0d7b32b4292b9300ac07c8daba14a2
```

Provider/instrumentation identity: `io.quarkus.platform:quarkus-bom:3.39.1`, uniform across all six
services (`grep quarkus.platform.version */pom.xml` in the pinned upstream checkout) — this bounds
the Quarkus OpenTelemetry extension version by the same content-addressed reasoning the Airflow
section below uses for its image digest: no source-code instrumentation change (I2 spec §16, still
true here), so the platform BOM version is the complete provider identity.

### Window-closing procedure (corrected during this PR)

The originally reported runs recorded `WINDOW_END` immediately after `traffic.sh` and then only
checked that *some* runtime relation existed in `[window_start, window_end]` — a check that can
(and did) pass even when one of the three expected `CALLS` relations lands a few seconds late in the
OpenTelemetry Collector's batch buffer (the "narration-fallback" lag I2.4's dossier already
documents). Run 1 of that version worked around the gap with a post hoc widened `--until` on the
capture call; run 2 used a different, undocumented `+14s` guess. Both produced a correct final
result, but neither followed one committed, reproducible rule — exactly PR #52 review F3's finding.

`runbook.md` phase 9 now closes the window with a bounded, self-terminating poll: it derives the
expected `CALLS` count from `expected.yaml` (not a hand-typed constant), polls
`GET /api/analysis/runtime/confirmed` (spec §43/§47's O2 — declared ∩ observed, the endpoint whose
`status` is actually `"CONFIRMED"`) with a widening `until` up to a 60s bound, and sets `WINDOW_END`
to the timestamp at which the expected count is first reached. Building this fix surfaced a second,
independent bug: an intermediate version of the fix queried `GET /api/runtime/relations` instead
(spec §42's O1, raw "observed" listing) and filtered client-side for `status == "CONFIRMED"` — that
endpoint's `status` field is always the literal string `"OBSERVED"` and never `"CONFIRMED"`, so the
filter matched zero rows every time and the loop only ever failed at its 60s bound. This was caught
live (against a running stack, not by inspection) before either qualifying run below was captured;
`runbook.md`'s own explanatory prose now documents both the original ad hoc-widening problem and
this endpoint bug so neither recurs silently.

Both runs below used the corrected, committed procedure and each closed in single digits of seconds
with no manual intervention — the two originally reported runs (raw commit `9f95d48`, artifacts now
superseded) are not carried forward as evidence; captured facts and comparator output are identical
either way (verified before discarding them), but the runs *reported* here are the ones bound to the
corrected, committed profile per spec §19.

### Run 1

```text
window_start:  2026-09-02T07:08:35Z
window_end:    2026-09-02T07:08:46Z  (closed after 8s, 3/3 CALLS confirmed — no widening needed)
```

Bounded readiness gate passed for every service on the first pass. `POST /api/import` returned
`nodes_written`/`relations_written` of 22/23, 14/16, 8/6, 14/16 for
fights/heroes/narration/villains — identical to the I2.3/I2.4 baseline. `traffic.sh` ran once.

**Comparator result** (`expected.yaml` vs. captured `actual.yaml` — `expected.yaml` declares no
`insufficient_evidence:` entries, so the comparator itself reports `0` for that field; see "Final
dispositions" below for why the overall Quarkus result is not this number alone):

```text
Expected supported facts:      38
Correct:                       38
Missing supported:              0
Incorrect supported:            0
Unsupported constructs:         2
Unresolved identities:          0
Insufficient evidence:           0
Critical semantic errors:        0
```

Identical to the frozen I2.3/I2.4 comparator summary in every classification.

Artifacts: [`artifacts/quarkus-actual.yaml`](artifacts/quarkus-actual.yaml)
(SHA-256 `8baff3a9a9f0480f5f0d2c144008ee4f075d3eda538ed4ac5f171df51b209b1a`),
[`artifacts/quarkus-compare.txt`](artifacts/quarkus-compare.txt)
(SHA-256 `4c34ae89d32209ab178dfc5b72bfd903ce47580c389b6e6381282303b7627309`).

### Run 2 (repeatability)

Full teardown (`docker compose down -v`) after run 1, fresh `NEO4J_PASSWORD`, same unmodified
service images and same pinned AIP image (verified by image ID again before traffic). Import
returned identical counts.

```text
window_start:  2026-09-02T07:10:56Z
window_end:    2026-09-02T07:11:07Z  (closed after 8s, 3/3 CALLS confirmed)
```

```text
Expected supported facts:      38
Correct:                       38
Missing supported:              0
Incorrect supported:            0
Unsupported constructs:         2
Unresolved identities:          0
Insufficient evidence:           0
Critical semantic errors:        0
```

Artifacts: [`artifacts/quarkus-actual-revalidation.yaml`](artifacts/quarkus-actual-revalidation.yaml),
[`artifacts/quarkus-compare-revalidation.txt`](artifacts/quarkus-compare-revalidation.txt).

### Repeatability result

```text
diff quarkus-actual.yaml quarkus-actual-revalidation.yaml         -> byte-identical
diff quarkus-compare.txt quarkus-compare-revalidation.txt         -> byte-identical
SHA-256 (both actual.yaml files):  8baff3a9a9f0480f5f0d2c144008ee4f075d3eda538ed4ac5f171df51b209b1a
SHA-256 (both compare.txt files):  4c34ae89d32209ab178dfc5b72bfd903ce47580c389b6e6381282303b7627309
```

Two independent runs against the literal `9f95d48` candidate, both closed by the same committed,
bounded procedure with no manual per-run adjustment: same images, same profile, same frozen
`expected.yaml`, byte-identical captures, byte-identical comparator output. Spec §20's repeatability
requirement is met in full (stronger than "SHOULD have identical semantic results" — these are
byte-identical, not merely semantically equivalent).

## Apache Airflow

```text
Upstream release:            apache/airflow 3.3.1, tag object 8d7af742565409cf8857c92c1cec98568dae4296
Upstream commit SHA:         3adbbe1c58e4532df1964cb7794805e763816ee8
Upstream image:              apache/airflow:3.3.1
                             @sha256:0c4bcc0370e526de1b7892a3bf4343d260c6c82359c66f77155b53cd773d6339
Profile revision:            docs/real-world-validation/apache-airflow/runtime/ @ 9f95d48 (unchanged)
Ground-truth revision:       docs/real-world-validation/apache-airflow/expected.yaml @ 9f95d48
Comparison-tool revision:    real_world_validation/ @ 9f95d48
Neo4j:                        neo4j:5.26.0
                             @sha256:5a015e53de1895e7eee1574ae0325cf8c4b89587222778108c594bdd45a474b5
Postgres:                    postgres:16.15@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94
Redis:                       redis:7.2-bookworm@sha256:74566c6910d13ae61e7ce73ebd3127438a1fe805b309b097c323142719ec8a5b
otel-collector:               otel/opentelemetry-collector:0.159.0
                             @sha256:7725a7a10c87d8853208bdd4bb3439ad3c0d7b32b4292b9300ac07c8daba14a2
Workers:                     AIRFLOW_WORKERS=2 (both runs — matches I3 spec §9's preferred
                             multiple-runtime-instance configuration)
```

Provider/instrumentation identity — carried forward from the frozen I3 dossier
(`upstream.md`/`results.md`'s "Same AIP candidate, same profile revision" section) rather than
re-queried, because I4.4 uses the exact same content-addressed `apache/airflow:3.3.1` image digest
I3 queried directly (`docker run --rm --entrypoint python3 <digest> -m pip show
apache-airflow-providers-celery celery`): an unchanged digest guarantees byte-identical installed
packages, so re-querying would reproduce the same values, not independently verify them:

```text
apache-airflow-providers-celery:      3.23.1
celery (runtime, not instrumentation): 5.6.3
OpenTelemetry Celery instrumentation: absent from this qualifying native profile (both runs) —
                                       opentelemetry-instrumentation-celery==0.65b0 is the
                                       diagnostic-only package documented in profile.md's "Standard
                                       Celery instrumentation decision" section; it was not
                                       installed/activated in either I4.4 run
```

### Run 1

```text
window_start:  2026-09-02T06:17:52Z
window_end:    2026-09-02T06:18:26Z
```

Bounded readiness gate (apiserver, scheduler, dag-processor, triggerer, both workers, DAG
registration) passed on the first pass. `POST /api/import` returned `nodes_written: 223,
relations_written: 512` — identical to the frozen I3 baseline. `traffic.sh` triggered
`i3_validation` (`dag_run_id=aip-i3-validation`); both tasks reached `success` on `queue=default`,
running on two distinct worker container hostnames (`ddcdfb8f538a`, `c9de510752a7`), directly
exercising the multiple-runtime-instance configuration. The AIP-access-log drain barrier (I3's valid
system-shape-independent drain signal, since `/api/runtime/relations` legitimately stays empty for
Airflow's native task/dagrun spans) confirmed ingestion before capture — this single bounded
count-based check needed no widening in either run, so (unlike Quarkus above) no procedure change
was required here.

```text
Expected supported facts:      9
Correct:                       9
Missing supported:              0
Incorrect supported:            0
Unsupported constructs:         3
Unresolved identities:          2
Insufficient evidence:           1
Critical semantic errors:        0
```

Identical to the frozen I3.3/I3.4 summary in every classification.

Artifacts: [`artifacts/airflow-actual.yaml`](artifacts/airflow-actual.yaml)
(SHA-256 `1d8a0db7741b0f108f4a23c78113e6cfb3466c01a975eac660b5ab2d7c026419`),
[`artifacts/airflow-compare.txt`](artifacts/airflow-compare.txt)
(SHA-256 `bc05e5cbb22a22175e3fdeb3112c40875f61907708a07fbcf35da316c0274d36`).

### Run 2 (repeatability)

Full teardown (`docker compose down -v` — Postgres, Redis, Neo4j, and the named
`airflow-i3-logs`/`-config`/`-plugins` volumes all removed) after run 1, fresh
`NEO4J_PASSWORD`/`FERNET_KEY`, same pinned AIP image (verified again), same unmodified
`apache/airflow:3.3.1` digest. Import returned identical counts. `traffic.sh` ran once; both tasks
succeeded on `queue=default` on worker hostname `d24726a67b91`.

```text
window_start:  2026-09-02T06:21:54Z
window_end:    2026-09-02T06:22:27Z
```

```text
Expected supported facts:      9
Correct:                       9
Missing supported:              0
Incorrect supported:            0
Unsupported constructs:         3
Unresolved identities:          2
Insufficient evidence:           1
Critical semantic errors:        0
```

Artifacts: [`artifacts/airflow-actual-revalidation.yaml`](artifacts/airflow-actual-revalidation.yaml),
[`artifacts/airflow-compare-revalidation.txt`](artifacts/airflow-compare-revalidation.txt).

### Repeatability result

```text
diff airflow-actual.yaml airflow-actual-revalidation.yaml         -> byte-identical
diff airflow-compare.txt airflow-compare-revalidation.txt         -> byte-identical
SHA-256 (both actual.yaml files):  1d8a0db7741b0f108f4a23c78113e6cfb3466c01a975eac660b5ab2d7c026419
SHA-256 (both compare.txt files):  bc05e5cbb22a22175e3fdeb3112c40875f61907708a07fbcf35da316c0274d36
```

Byte-identical captures and comparator output despite the two runs using different worker container
hostnames — expected and correct: the captured scope (`PROVIDES`, `SENDS`, `RECEIVES_FROM`) contains
no fact derived from worker hostname, since Celery sender/consumer identity remains
`INSUFFICIENT_EVIDENCE`/unresolved by design (I4.1's `runtime-role-identity` decision). Spec §20's
repeatability requirement is met in full.

## Final dispositions

No new finding was discovered during this revalidation, and no ledger disposition changed. Every
finding in [`finding-ledger.md`](finding-ledger.md) keeps the disposition I4.1 assigned; nothing here
reopens `hardening.md`'s `NO_CHANGE` record or any decision in `decisions/`.

Two different counts are reported for Quarkus, and (per the frozen dossier's own convention,
`quarkus-super-heroes/results.md`'s "Summary") they measure different things, so neither is reported
alone:

**Comparator result** — `expected.yaml` vs. the captured `actual.yaml` above, via `real_world_
validation compare`. `expected.yaml` declares no `insufficient_evidence:` entries, so the comparator
itself reports `0` for that field:

```text
CORRECT:                 38
UNSUPPORTED:               2
INSUFFICIENT_EVIDENCE:     0
MISSING_SUPPORTED:         0
INCORRECT_SUPPORTED:       0
UNRESOLVED_IDENTITY:       0
Critical semantic errors:  0
```

**Overall Quarkus result** — the comparator result above, plus `qsh-kafka-operation-type-gap`
(`INSUFFICIENT_EVIDENCE`, disposition `DEFER` per `finding-ledger.md`), the finding I2.3 originally
discovered by a separate diagnostic raw-telemetry inspection *after* its own comparator run, not by
the comparator itself, and which I4.1 evaluated cross-system and kept `DEFER` (no messaging
correction was accepted). This is the count spec §5's frozen input table freezes as
`38 CORRECT / 2 UNSUPPORTED / 1 INSUFFICIENT_EVIDENCE`, and it is the number this revalidation
reproduces, unchanged:

```text
CORRECT:                 38
UNSUPPORTED:               2
INSUFFICIENT_EVIDENCE:     1
MISSING_SUPPORTED:         0
INCORRECT_SUPPORTED:       0
UNRESOLVED_IDENTITY:       0
Critical semantic errors:  0
```

Airflow has no such split — its comparator result already includes all three of its frozen
non-`CORRECT` classifications directly (`expected.yaml` declares its own `insufficient_evidence:`
entry), so the single reported summary is the overall result:

```text
Quarkus (overall):  CORRECT 38, UNSUPPORTED 2, INSUFFICIENT_EVIDENCE 1, all other classifications 0
Airflow:            CORRECT 9, UNSUPPORTED 3, UNRESOLVED_IDENTITY 2, INSUFFICIENT_EVIDENCE 1, all other classifications 0
```

Material `INCORRECT_SUPPORTED` findings = 0. Critical semantic errors = 0.

## Known limitations (carried forward, unchanged)

```text
gRPC/protobuf calls (Quarkus)                      — unsupported, DOCUMENT_UNSUPPORTED
Kafka topic/subscription semantics (Quarkus)       — unsupported, DOCUMENT_UNSUPPORTED
messaging.operation.type/legacy attribute gap (Quarkus) — insufficient evidence, DEFER
                                                      (qsh-kafka-operation-type-gap)
PostgreSQL/database dependencies (Airflow)         — unsupported, DOCUMENT_UNSUPPORTED
Airflow Execution API caller identity              — unresolved, DEFER
Airflow runtime-role/Celery messaging identity     — unresolved, DEFER
```

None of these is a material `INCORRECT_SUPPORTED` claim; each is an explicit, bounded limitation
per spec §24's non-blocking outcomes.

## Method note

No production code changed between or during any of the runs in this record. `docs/real-world-
validation/quarkus-super-heroes/runbook.md`'s phase 9 (the Quarkus window-closing procedure) was
corrected as described above — a profile/documentation change, not a production code change — and
both Quarkus runs reported here were captured after that correction, per spec §20 ("if ... profile
... changes afterward, all affected runs SHALL be repeated"). `expected.yaml`, `docker-compose.yml`,
and `traffic.sh` did not change for either system. The only per-run inputs that changed were secrets
(`NEO4J_PASSWORD`, `FERNET_KEY`) generated fresh per spec's clean-state requirement (I1 §29).

Both compose profiles were pointed at the single pre-built `aip-candidate-9f95d48` image via a
local, untracked `docker-compose.override.yml` (`image:` key layered onto the committed `build:` key
so Compose reused the existing tagged image instead of rebuilding) — this override is gitignored
(`.gitignore` already lists `docker-compose.override.yml`) and is not part of this commit; its exact
resolved effect for both profiles is preserved and hashed above ("Effective Compose configuration")
so the pinning claim is auditable rather than only asserted.
