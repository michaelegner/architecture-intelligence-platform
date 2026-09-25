# AIP v0.5.0 I6 — Release Candidate, Publication, and Post-Release Verification

**Status:** Draft 0.3  
**Target release:** `v0.5.0`  
**Increment:** I6 — Release Candidate, Publication, and Post-Release Verification  
**Parent:** [`specification.md`](specification.md), especially §§23–31 and §33  
**Entry baseline:** I5 completion merge `1ebca5e96a24156179f0a57b5abbdfe9b51c1ee7` (#258)  
**I5 qualified semantic baseline:** `aa04a150965924bd23ecf0125bcf7095a3cf72d9`  
**I5 status:** `FINAL_CANDIDATE_QUALIFIED`  
**Dependencies:** I1–I5 complete; I4 disposition `GO`  
**Exit:** exactly one terminal outcome: `RELEASE_READY_NOT_PUBLISHED`, `SHIPPED_VERIFIED`, `NO_GO`, or `POST_RELEASE_FAILED`

---

## 1. Purpose

I6 turns the I5-qualified v0.5 semantics into one exact release candidate and then keeps four decisions distinct:

1. technical release readiness;
2. authorization to publish;
3. publication itself; and
4. verification of the actual published artifacts.

I6 SHALL NOT reinterpret or extend v0.5 architecture semantics.

The release identity chain is:

~~~text
I5 qualified semantic baseline
    -> release-preparation changes
    -> RELEASE_CANDIDATE_SHA
    -> pre-publication evidence
    -> publication decision
    -> v0.5.0 tag
    -> GitHub Release
    -> release workflow
    -> published GHCR digest
    -> published-artifact verification
    -> terminal closure
~~~

A locally qualified image is not a published artifact. A Git tag alone is not a release. A successful publication workflow alone is not post-release verification.

---

## 2. Inherited I5 Evidence

I6 inherits, but SHALL NOT silently rewrite, the I5 completion record.

~~~text
I5_QUALIFIED_SEMANTIC_SHA =
aa04a150965924bd23ecf0125bcf7095a3cf72d9

I5_COMPLETION_SHA =
1ebca5e96a24156179f0a57b5abbdfe9b51c1ee7
~~~

I5 established at its qualified semantic baseline:

- Quarkus Super Heroes: 45/45 supported facts `CORRECT`;
- Apache Airflow: 9/9 `CORRECT`;
- zero incorrect supported facts;
- all 9 lifecycle steps on both targets passing;
- public REST / `ArchitectureIntelligenceService` / negotiated-MCP parity;
- zero public-read graph writes;
- 23/23 Architecture Answer evaluation scenarios;
- two byte-identical evaluation runs;
- all I5 findings F1–F8 assigned exactly one disposition.

I6 SHALL carry the known limitations without representing them as newly fixed, including F3, F4, F5 and F8. In particular, F5 and F8 SHALL NOT be opportunistically changed inside a frozen I6 candidate. A production change to either creates a new semantic candidate and reopens the appropriate qualification gates.

---

## 3. Scope

### 3.1 In scope

I6 SHALL:

1. audit the I5 handoff;
2. prepare the release version and release metadata;
3. freeze a deterministic v0.5 release golden-path profile;
4. freeze one exact `RELEASE_CANDIDATE_SHA`;
5. qualify that exact candidate from a clean checkout;
6. record candidate, evidence, decision, tag, workflow and artifact identities separately;
7. produce `RELEASE_READY` or `NO_GO`;
8. obtain an explicit repository-owner publication disposition;
9. if authorized, publish exactly the qualified candidate as `v0.5.0`;
10. independently verify the actual published source and GHCR artifact;
11. bind final security/SBOM evidence to the published digest and workflow;
12. record an unpublished or published terminal closure.

### 3.2 Out of scope

I6 SHALL NOT:

~~~text
change Canonical Model semantics
add or alter source adapters
add a discovery-source family
change identity or reconciliation rules
change Queue / Topic / Subscription meaning
add a fourth MCP tool
re-open I4 semantic decisions
fix F5/F8 as product changes
introduce v0.6 locality semantics
introduce Architecture Intent
use a local or RC image as evidence for the final published image
~~~

A production-semantic defect found in I6 produces a candidate-level `NO_GO` (§4.1) and a return to the owning increment rather than an opportunistic release-time fix.

---

## 4. Release Identity Model

I6 SHALL keep these identities distinct:

~~~text
I5_QUALIFIED_SEMANTIC_SHA
I5_COMPLETION_SHA
RELEASE_CANDIDATE_SHA
EVIDENCE_COMMIT_SHA
DECISION_COMMIT_SHA
UNPUBLISHED_CLOSURE_COMMIT_SHA, when applicable
POST_RELEASE_COMMIT_SHA, when applicable
FINAL_TAG_TARGET_SHA, when applicable
FINAL_IMAGE_DIGEST, when applicable
FINAL_RELEASE_WORKFLOW_RUN_ID, when applicable
~~~

The identities SHALL NOT be collapsed merely because two happen to identify equivalent content.

Each `*_COMMIT_SHA` and `RELEASE_CANDIDATE_SHA` is the **merge commit on `main`** of the PR that
carries the corresponding change or record. It is read from git after the merge, never typed from
expectation.

No record embeds its own commit SHA. Each record's commit identity is cited by the next record in the
chain. The publication decision cites `EVIDENCE_COMMIT_SHA`. The closure record and the completion
record cite `DECISION_COMMIT_SHA`. The completion record cites `UNPUBLISHED_CLOSURE_COMMIT_SHA` or
`POST_RELEASE_COMMIT_SHA`.

### 4.1 Candidate attempts and `NO_GO` scope

I6 MAY need more than one candidate. Candidate attempts are numbered `rc.1`, `rc.2`, … in freeze
order. The attempt number is a record label only. No `-rc.N` Git tag, GitHub Release or GHCR image
is published for a candidate attempt.

A failed mandatory pre-publication gate yields `NO_GO` **for that candidate attempt**. This is
recorded in `docs/release-validation/v0.5.0-rc.N-no-go.md` (§29) and is terminal for that SHA: the
SHA can never become `RELEASE_READY`.

After a candidate-level `NO_GO`, exactly one of the following applies:
- **The defect is within §9's allowed release-preparation scope.** A corrected candidate-preparation
  PR freezes the next attempt `rc.N+1`, and Slice 2 restarts in full against it.
- **The defect is semantic (§3.2).** I6 returns to the owning increment. The next candidate is
  frozen only after that increment's affected gates re-close.
- **The repository owner ends the v0.5.0 cycle.** The release-level terminal outcome is then
  `NO_GO`, and the completion record says so.

Parent §27's terminal `NO_GO` is this release-level outcome. A candidate-level `NO_GO` alone does
not end I6.

### 4.2 Tag identity

The final `v0.5.0` tag SHALL point directly to `RELEASE_CANDIDATE_SHA`.

It SHALL NOT point to an evidence commit, decision commit, closure commit, or whatever `main` happens to contain at publication time.

### 4.3 Build identity

Every candidate or release image SHALL expose:

~~~text
producer.version        = "0.5.0"
producer.build_revision = RELEASE_CANDIDATE_SHA
~~~

`producer.build_revision` SHALL contain the full 40-character SHA.

The public Architecture Answer remains:

~~~text
schema_version = "0.5"
~~~

Product version and public schema version are different concepts.

---

## 5. Entry Audit

Before any release-preparation mutation, I6 SHALL verify:

~~~text
main contains I5 completion merge 1ebca5e...
I5 completion state = FINAL_CANDIDATE_QUALIFIED
I5 semantic baseline = aa04a15...
no post-I5 production-semantic mutation exists
working tree is clean
I1/I2/I3/I4/I5 completion records exist
I4 disposition = GO
I5 finding ledger has no unresolved material supported mismatch
~~~

If `main` contains a production or qualification-relevant semantic change after I5, I6 SHALL stop for review.

Docs/evidence-only I5 completion records do not invalidate the qualified semantic baseline.

---

## 6. Candidate Preparation

I6 candidate preparation intentionally creates a new candidate after I5.

At I6 entry, the project version remains `0.4.2`. That is not an I5 defect: release versioning belongs to I6.

Before `RELEASE_CANDIDATE_SHA` is frozen, all active version-bearing surfaces SHALL be made consistent with `0.5.0`.

`pyproject.toml` is the single source of the product version. `app.version.package_version()` reads
it at runtime. The MCP server's advertised version, the production `Producer.version` and the
Architecture Answer evaluator's `Producer.version` all derive from `package_version()`, so they are
verified (§10.2), not edited.

The edited surfaces are:

~~~text
pyproject.toml [project].version                      0.4.2 -> 0.5.0
uv.lock root project version                          via `uv lock`
tests/unit/test_release_version_consistency.py        _RELEASE_VERSION
evaluation/architecture_answers/scenarios/*/expected_answer.json
                                                      producer.version only
~~~

If candidate preparation finds another hand-maintained version literal, that is a
`RELEASE_BLOCKER` (§14). The fix routes that literal through `package_version()`; the literal is
not merely updated.

`schema_version` remains `"0.5"`.

Version-only evaluation updates MAY change `producer.version` from `0.4.2` to `0.5.0`. They SHALL NOT change claim identities, qualifications, evidence, snapshots, limitations, canonical meaning, or expected architecture facts.

Running:

~~~bash
uv lock
~~~

after the version update SHOULD change only the root-project version. Any third-party dependency name, version, source, or hash mutation requires explicit review before candidate freeze.

### 6.1 Release documentation

Before candidate freeze:

- `CHANGELOG.md` SHALL contain the externally meaningful v0.5.0 content under `[Unreleased]`;
- `docs/release-validation/v0.5.0-release-notes.md` SHALL exist;
- release notes SHALL describe only qualified capabilities;
- unsupported, unresolved, deferred and fixture-only behavior SHALL remain explicit;
- release notes SHALL not call v0.5.0 shipped before publication;
- no public release-note source may contain unresolved placeholders, local scratch paths, internal execution instructions, or maintainer-only draft prose.

The dated `[0.5.0]` changelog heading belongs to publication/status closure and SHALL NOT move the immutable release tag.

---

## 7. Release Golden-Path Profile

I6 SHALL freeze one deterministic release profile before candidate freeze.

It SHALL compose already-qualified v0.5 mechanisms rather than inventing new architecture facts.

It SHALL cover at least:

~~~text
OpenAPI declaration
AsyncAPI Queue
AsyncAPI Topic
explicit Subscription
Kubernetes offline discovery
Service <-> Workload reconciliation
deterministic OTel observation
positive declared identity
positive configured or observed runtime identity
one unresolved identity case
one conflicting identity case
COMPLETE source inventory
evidence drill-down
REST Architecture Knowledge read
negotiated MCP initialization
tools/list
get_service_dependencies
get_architecture_drift
get_evidence
disconnect / reconnect
zero writes through public reads
~~~

Because I4 completed as `GO`, Topic/Subscription behavior is mandatory in this release profile.

### 7.1 Phased composition

No single existing fixture covers this list, and the fixtures cannot share one graph:

- The I3 cross-source fixture has exactly one Workload. Its positive case (agreeing mapping) and its
  `CONFLICT` case (conflicting mapping) are mutually exclusive on that Workload.
- `sources.service_workload_mapping` is one path, loaded at startup.
- The runtime-demo oracle `examples/runtime-demo/fixture-state.json` compares whole-graph counts and
  the whole-graph snapshot id, so it holds only in a graph containing the demo alone.

The golden path is therefore a fixed sequence of **phases**. Each phase starts from a clean graph,
meaning a fresh Compose project and a fresh Neo4j volume, and has its own AIP configuration. Each
phase reproduces one already-qualified component setup through public interfaces only:
- configured sources plus `POST /api/import`;
- OTLP through the pinned collector;
- REST;
- negotiated MCP.

| Phase | Component inputs | Covers | Oracle |
|---|---|---|---|
| `demo` | `examples/`, `seed_frozen_evidence.py`, environment `demo` | OpenAPI, AsyncAPI Queue, deterministic OTel, positive declared identity, COMPLETE inventory, the full §20 REST and MCP workflow | `fixture-state.json` via `check_fixture_state.py`, plus the import report |
| `pubsub` | `tests/fixtures/pubsub/google-pubsub/declarations/` (unmodified), with its `spans.yaml` transcribed to OTLP | AsyncAPI Topic, explicit Subscriptions, Pub/Sub observation | the fixture's `expected.yaml` |
| `k8s-agree` | the I2 capture (unmodified), `service-workload-mapping-agree.yaml` (unmodified), a transcribed `service:runtime-demo` declaration and OTLP span | Kubernetes offline discovery; `RESOLVED_EXPLICIT` supported by all three paths | `test_i3_cross_source_qualification.py`, all-paths-agree case |
| `k8s-conflict` | the I2 capture, `service-workload-mapping-conflict.yaml` (unmodified), transcribed `service:runtime-demo` and `service:runtime-demo-alt` declarations, no span | the conflicting-identity case | the same test, Path A vs Path B case |
| `k8s-unresolved` | the I2 capture, a transcribed `service:runtime-demo` declaration, and a transcription of the two-absent-target mapping `_TWO_ABSENT_TARGET_MAPPINGS`; no span | the unresolved-identity case | `test_i5_qualification_tooling.py`, `test_two_same_service_unresolved_groups_are_captured_and_compared_one_to_one` |

The rules for expectations:
- Every expected fact SHALL be derived from a component's existing frozen expectation (its
  qualification test, fixture `expected.yaml`, or frozen oracle) and SHALL cite that source by
  path and line.
- `k8s-unresolved` uses the only frozen `UNRESOLVED` expectation that goes through the public
  Service-scoped projection (I3 §13.4). Rule-level tests that call the resolver directly are not
  enough, because an `UNRESOLVED` resolution is public only when it names the requested, declared
  Service. That frozen expectation is two `UNRESOLVED` resolutions for `service:runtime-demo`, each
  with a null Service and Workload, with distinct resolution ids.
- A phase SHALL NOT expect a fact its cited component does not freeze. Where the component asserts
  over the whole graph, the phase expectation is scoped to the entities that component declares.
- Identity-bearing values are not frozen, except where the component oracle already freezes them.
  These include claim ids, evidence ids, and snapshot ids that depend on configured source ids or
  absolute paths. The demo phase's `expected_snapshot_id` is the only such exception. Expectations
  are statuses, qualifications, shapes, names and counts.
- The complete expected output SHALL be frozen and merged (Slice 1a) **before** the harness first
  runs against any image, whether a development build or a candidate. Expectations SHALL NOT be
  captured from, or edited to match, any image's output. That would repeat the prohibition in I5
  §19 item 5.

### 7.2 Transcribed inputs

Some component inputs exist only inside a test:
- the I3 tests declare their Services in memory and build `RuntimeSpan` objects in Python;
- the I5 tooling test's absent-target mapping is an inline YAML string;
- the Pub/Sub `spans.yaml` uses a test-only format.

A running container needs files, so such inputs MAY be **transcribed**. A transcription SHALL:
1. be derived mechanically from the component test's own input, with nothing added or changed;
2. live under `examples/release-golden-path/profile/<phase>/`, never inside the component fixture;
3. be disclosed as a transcription in the profile README, naming its source test and lines;
4. be pinned by a unit test that proves equivalence through production code:
   - **Service declaration.** An OpenAPI document with `x-aip-service-id`, the test's `info.title`
     and `info.version`, and `paths: {}`. The real OpenAPI adapter SHALL emit exactly the
     test's Service (`id`, `name`, `version`) and no other entity or relation.
   - **Mapping document.** The inline YAML is written out byte for byte. The unit test SHALL
     compare the file's bytes with the test constant.
   - **OTLP payload.** OTLP/HTTP JSON, which the pinned collector accepts and forwards to AIP as
     protobuf. Parsing it into an `ExportTraceServiceRequest`, serializing it, and decoding it with
     `app/telemetry/otlp_receiver.py`'s `decode_export_request` SHALL yield the same `RuntimeSpan`
     fields the component test builds.

A transcription that cannot be proven equivalent is a stop condition (§26).

### 7.3 Named cases and "COMPLETE"

- **Unresolved identity.** An I3 `DEPLOYED_AS` resolution of `UNRESOLVED` (phase `k8s-unresolved`).
- **Conflicting identity.** An I3 `DEPLOYED_AS` resolution of `CONFLICT`, with no guessed
  association (phase `k8s-conflict`). This is not an I1 source-level `REJECTED_CONFLICT`: every
  profile source SHALL be accepted, as its component expects.
- **"COMPLETE".** In every phase, both of the following SHALL hold:
  1. every source-inventory run reports I1 inventory status `COMPLETE`;
  2. the phase oracle reports zero mismatches against the frozen expected output.

  The demo phase MAY use `examples/runtime-demo/check_fixture_state.py` as its oracle, because its
  graph holds the demo alone. The other phases' checks are part of the §7.4 harness.
- **Full workflow placement.** The complete §20 REST and negotiated-MCP workflow runs in the `demo`
  phase: initialize, `tools/list`, all three tools, evidence drill-down, disconnect and reconnect,
  and a revision fence before and after.
  - The `pubsub` phase repeats REST, `tools/list` and the three tools for its publisher.
  - Each `k8s-*` phase reads its resolution through REST
    `GET /api/services/{id}/deployments` and MCP `get_service_dependencies`.
  - Every phase verifies zero writes through public reads.

### 7.4 Location and command

The profile and its harness live in:

~~~text
examples/release-golden-path/
  README.md          phases, import order, observation windows, component provenance,
                     transcription disclosure
  profile/<phase>/   per-phase AIP config, mount list, transcriptions
  expected.json      frozen expected output, keyed by phase (§7.1)
  SHA256SUMS         digests of profile/, expected.json and every referenced component file
  run.sh             the only entry point (Slice 1b)
~~~

`examples/release-golden-path/` sits inside the bundled `examples` source root. The filesystem
discoverer treats every direct subdirectory of that root as a service directory. So no discoverer
candidate filename (`openapi.yaml`, `asyncapi.yaml`, `architecture.yaml`, …) may appear directly
in `examples/release-golden-path/`. A unit test SHALL prove that the bundled-examples discovery
result is unchanged.

It is run as:

~~~bash
examples/release-golden-path/run.sh <IMAGE_REF> <OUT_DIR>
~~~

`IMAGE_REF` is either the local candidate image or `ghcr.io/...@sha256:<digest>`.

Every Compose invocation SHALL use the frozen invocation from the I5 profiles: `-p`,
`--project-directory`, `-f`, and `--env-file /dev/null`. Only `:?` interpolation is allowed.

The harness SHALL:
- verify the running container's image id against `IMAGE_REF`;
- verify its `producer.build_revision`;
- write every §20 check result to `OUT_DIR`;
- exit non-zero on any failed check.

The profile SHALL have no dependency on an LLM or an external network service, apart from the
image pull.

The same profile and command SHALL run against both the local candidate image and the anonymously
pulled final image. For the final image, `run.sh` is taken from the tagged-source clone (§21), not
from a working checkout.

---

## 8. Candidate Freeze

The merge commit of the candidate-preparation PR SHALL become:

~~~text
RELEASE_CANDIDATE_SHA
~~~

Candidate preparation MAY contain:

- `0.5.0` version-consistency changes;
- producer-version-only evaluation fixture changes;
- release documentation;
- the release golden-path harness/profile;
- release-workflow, SBOM or provenance hardening required by this specification;
- tests for those release mechanics.

It SHALL contain these release-workflow changes. The release event runs the workflow file **at the
tagged commit**, so a workflow change merged after freeze cannot affect this release without a new
candidate.

~~~text
.github/workflows/docker.yml:
  generate a final-image SBOM (SPDX or CycloneDX) for the pushed digest,
    and retain it as a workflow artifact
  scan the pushed image by digest (image@sha256:...), not by the mutable tag
  record the scanned digest in the job summary
  retain a full Trivy HIGH/CRITICAL report that includes unfixed findings
    (ignore-unfixed: false), as a workflow artifact
~~~

The SARIF upload MAY keep its current non-blocking behavior. The release-blocking decision is the
§19 human disposition, not the scanner's exit code.

The tool and command chosen for each item SHALL be named in the candidate-preparation PR and
recorded in §13.

Changes to `Dockerfile` or its base-image pin are allowed only when a §12 finding requires them.
Such a change is qualification-relevant: the candidate image, the §12 security gate and the golden
path run against the new image, and the diff SHALL be listed in §13.

After that merge, `RELEASE_CANDIDATE_SHA` is immutable.

Any executable or qualification-relevant change after freeze creates a new candidate. Evidence-only and decision-only commits SHALL NOT move the candidate.

---

## 9. Candidate Mutation Policy Relative to I5

I6 does not blindly inherit I5 qualification after candidate preparation.

Allowed release-preparation mutations include:

~~~text
0.4.2 -> 0.5.0 package/producer metadata
release-version tests
producer.version-only expected-answer changes
release notes / changelog
release golden-path harness composed from already-qualified fixtures
release workflow / SBOM / provenance mechanics
Dockerfile / base-image pin, only per §8
~~~

If the diff from `I5_QUALIFIED_SEMANTIC_SHA` changes any of the following semantically, I6 SHALL stop and return to I5:

~~~text
Canonical Model behavior
ingestion/adaptation semantics
source identity or lifecycle semantics
Architecture Intelligence semantics
public schema meaning
reconciliation semantics
qualification semantics
I5 frozen real-system inputs
I5 expected architecture facts
~~~

A file path alone is not the decision criterion; semantic effect is.

---

## 10. Exact-Candidate Pre-Publication Qualification

All qualification commands SHALL run from a fresh isolated checkout of `RELEASE_CANDIDATE_SHA`.

Minimum preflight:

~~~bash
test "$(git rev-parse HEAD)" = "$RELEASE_CANDIDATE_SHA"
test -z "$(git status --porcelain)"
~~~

### 10.1 Source qualification

The candidate SHALL pass:

~~~bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit -q
uv run pytest tests/integration -q
uv run --with pip-audit pip-audit
~~~

The evidence record SHALL capture exit codes and summary output.

### 10.2 Version consistency

Qualification SHALL prove:

~~~text
pyproject version = 0.5.0
uv.lock root version = 0.5.0
package_version() = 0.5.0
MCP server version = 0.5.0
Producer.version = 0.5.0
evaluation Producer.version = 0.5.0
schema_version = 0.5
~~~

### 10.3 Architecture Answer evaluation

A full `answers` run overwrites the committed report
`evaluation/architecture_answers/results/architecture-answers-evaluation-result.json`. So each run's
output SHALL be copied out of the checkout before the next run, and the checkout SHALL be restored
afterwards. Run twice from the same absolute clean-checkout location:

~~~bash
R=evaluation/architecture_answers/results/architecture-answers-evaluation-result.json
for n in 1 2; do
  uv run python -m evaluation answers --candidate-sha "$RELEASE_CANDIDATE_SHA"
  cp "$R" "$EVIDENCE_DIR/evaluation-run-$n.json"
  git checkout -- "$R"
done
cmp "$EVIDENCE_DIR/evaluation-run-1.json" "$EVIDENCE_DIR/evaluation-run-2.json"
test -z "$(git status --porcelain)"
~~~

Required result:

~~~text
23/23 PASS in each run
evaluation-run-1.json and evaluation-run-2.json byte-identical (cmp exit 0)
each report: result = PASS, semantic_outputs_identical = true
semantic mismatches = 0
checkout clean after the runs
~~~

The two outer runs are the parent §24 `repeatability = PASS` evidence. The report's internal `run_count: 2`
comparison is also required, but it does not replace them.

#### Report refresh is evidence, not candidate content

The committed report records `candidate_sha`, so a report naming `RELEASE_CANDIDATE_SHA` cannot be
part of that candidate. It would be self-referential.

The refreshed report SHALL therefore be `evaluation-run-1.json`, committed to that path in the
§13 evidence PR. This one path is classified as **evidence-only** for §8 and §9. Committing it does
not move the candidate, even though it sits outside `docs/`. No other change under `evaluation/`
has this status.

The `v0.5.0` tag therefore carries the pre-refresh report, which names `a906a58…` (last refreshed
in v0.4.0). The release notes and §13 SHALL state this. The refreshed report on `main` is the
release evidence.

### 10.4 I1–I4 capability gates

The exact candidate SHALL demonstrate through the full suites and named qualification tests:

~~~text
source-adapter conformance
OpenAPI/AsyncAPI supported corpus
inventory / scope / tombstone / discovery-failure safety
reimport / conflict / atomicity
Kubernetes offline discovery
runtime Service/Workload reconciliation
Pub/Sub positive and negative cases
public schema freeze
exactly three MCP tools
read-only invariants
REST / service / negotiated-MCP parity
~~~

### 10.5 I5 inheritance gate

I6 SHALL record that the release-preparation diff introduces no architecture-semantic change relative to the I5 qualified baseline.

If that gate holds, full live Quarkus/Airflow reruns are not required merely because release metadata changed.

If it does not hold, the affected I5 qualification SHALL be rerun before I6 continues.

### 10.6 Repository and documentation hygiene

Parent §24 requires a repository and documentation hygiene gate. At the candidate:

~~~bash
docker run --rm -v "$PWD:/repo:ro" zricethezav/gitleaks:<pinned digest> \
  detect --source=/repo --no-git -v
~~~

Every gitleaks hit SHALL be dispositioned in §13, either as a real finding or as a false positive
with a reason.

The checks of [`public-repository-content-gate.md`](../../release-validation/public-repository-content-gate.md)
SHALL be re-applied to the diff from the `v0.4.2` tag to `RELEASE_CANDIDATE_SHA`. They cover
secrets, private paths, and internal or maintainer-only content.

Every relative link in `README.md`, `CHANGELOG.md`, `docs/**/*.md` and the release notes SHALL
resolve **in the git index** at the candidate. A file present only on disk, or a git symlink that
GitHub's blob view does not follow, fails the check.

### 10.7 Kubernetes mode

v0.5.0 releases Kubernetes discovery as `OFFLINE_ONLY`, per the I2 decision. Parent §29's
live-RBAC, denied-verb and denied-scope qualification therefore does not apply and is not claimed.

The §29 offline obligations are covered by the §10.4 suites:
- failed and partial frozen-input scenarios;
- inventory scenarios;
- no kubeconfig loading, live client or cluster write.

The release notes and §13 SHALL state `OFFLINE_ONLY`.

---

## 11. Candidate Image Qualification

Build a fresh candidate image from the exact SHA:

~~~bash
docker build --no-cache \
  --build-arg AIP_BUILD_REVISION="$RELEASE_CANDIDATE_SHA" \
  -t aip-v0.5.0-candidate:"$RELEASE_CANDIDATE_SHA" .
~~~

Record:

~~~text
image id
resolved base-image identities
candidate SHA
package version
producer.version
producer.build_revision
non-root runtime identity
~~~

The release golden path SHALL pass against this image from clean Neo4j/source state.

Candidate-image success contributes to `RELEASE_READY` but SHALL NOT substitute for final published-artifact verification.

---

## 12. Candidate Security Gate

Before `RELEASE_READY`:

- dependency audit SHALL pass or every finding SHALL have an explicit disposition;
- CodeQL for the exact candidate SHALL be green;
- candidate image HIGH/CRITICAL findings SHALL be reviewed. They are produced with the same Trivy
  version and settings as the release workflow (§8), including unfixed findings:

  ~~~bash
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    aquasec/trivy:<the Trivy version the pinned trivy-action runs, recorded in §13> image \
    --severity HIGH,CRITICAL --ignore-unfixed=false --format json \
    aip-v0.5.0-candidate:"$RELEASE_CANDIDATE_SHA"
  ~~~
- secrets or credentials SHALL not appear in release records;
- the image SHALL execute as the intended non-root user;
- the release workflow SHALL remain least privilege;
- no unresolved release-blocking security finding may remain.

The security record SHALL distinguish:

~~~text
candidate-source findings
candidate-image findings
final published-image findings
~~~

Only the final category can satisfy `SHIPPED_VERIFIED`.

---

## 13. Pre-Publication Evidence Record

The exact-candidate evidence SHALL be committed as:

~~~text
docs/release-validation/v0.5.0-release-readiness.md
~~~

The merge commit of the PR carrying it, together with the refreshed evaluation report (§10.3),
becomes `EVIDENCE_COMMIT_SHA`. Per §4, the record does not embed that SHA.

It SHALL record at least:

- `I5_QUALIFIED_SEMANTIC_SHA`;
- `I5_COMPLETION_SHA`;
- `RELEASE_CANDIDATE_SHA` and its attempt label `rc.N`;
- clean-checkout proof;
- package/version identities;
- dependency-lock SHA-256;
- schema/tree identities;
- the Canonical Model version and the snapshot canonicalization version;
- adapter/rule versions;
- fixture identities: the `coverage-matrix.md` fixture pins, the evaluation-scenario digest and the
  golden-path profile's `SHA256SUMS` digest;
- the tools and pinned versions used for the SBOM, the image scan and gitleaks;
- the §10.6 hygiene result and the §10.7 `OFFLINE_ONLY` statement;
- any `Dockerfile` or base-image diff (§8);
- evaluation digest and byte-identity evidence;
- unit/integration results;
- exact candidate CI check-runs;
- candidate image id;
- candidate golden-path result;
- security disposition;
- known limitations;
- release blocker count.

Required technical result:

~~~text
semantic mismatches = 0
unexpected canonical facts = 0
guessed identities = 0
unresolved release blockers = 0
repeatability = PASS
producer.build_revision = RELEASE_CANDIDATE_SHA
~~~

If all mandatory gates pass:

~~~text
technical state = RELEASE_READY
~~~

`RELEASE_READY` is not publication authorization.

---

## 14. Findings and Release Blockers

I6 findings use:

~~~text
RELEASE_BLOCKER
KNOWN_LIMITATION
NO_CHANGE
RETURN_TO_I5
~~~

A finding is release-blocking when it can affect candidate identity, version identity, shipped supported semantics, the public contract, artifact integrity, security, reproducibility, or the published golden path.

Mandatory blockers include:

~~~text
version surfaces disagree
tag would not point at RELEASE_CANDIDATE_SHA
dirty qualification checkout
dependency lock drift
schema drift
semantic evaluation difference
public adapter mismatch
fourth MCP tool
graph write through public reads
producer.build_revision mismatch
unreviewed release-relevant HIGH/CRITICAL final-image finding
published digest cannot be established
anonymous digest pull fails
published golden path fails
release body materially overclaims qualified behavior
~~~

F5 and F8 remain known I5 limitations unless new evidence shows material release impact.

---

## 15. Publication Decision

After `RELEASE_READY`, the repository owner SHALL explicitly record exactly one publication disposition:

~~~text
GRANTED
NOT_GRANTED
PENDING
~~~

The decision SHALL name both:

~~~text
RELEASE_CANDIDATE_SHA   the candidate it applies to
EVIDENCE_COMMIT_SHA     the readiness evidence it relied on
~~~

A decision that names neither, or names a different candidate or evidence commit, is not a
publication disposition for this candidate.

`PENDING` yields `AWAITING_PUBLICATION_DECISION` and is non-terminal. Recording `PENDING` is
optional.

A later `GRANTED` or `NOT_GRANTED` SHALL be a new decision PR that updates the same file. Its merge
commit alone is `DECISION_COMMIT_SHA`. An earlier `PENDING` merge, if any, is kept as history and is
not a decision identity.

`NOT_GRANTED` proceeds to unpublished closure.

`GRANTED` authorizes publication of exactly the qualified candidate.

The decision SHALL be recorded separately from technical evidence in:

~~~text
docs/release-validation/v0.5.0-publication-decision.md
~~~

Its merge commit becomes `DECISION_COMMIT_SHA`.

No agent or automation may infer authorization merely because technical gates are green.

---

## 16. Unpublished Closure

For `NOT_GRANTED`, create:

~~~text
docs/release-validation/v0.5.0-unpublished-closure.md
~~~

It SHALL state:

~~~text
technical state = RELEASE_READY
publication authorization = NOT_GRANTED
v0.5.0 tag = absent
v0.5.0 GitHub Release = absent
public v0.5.0 artifact = not claimed
~~~

Its merge commit becomes `UNPUBLISHED_CLOSURE_COMMIT_SHA`.

Terminal result:

~~~text
RELEASE_READY_NOT_PUBLISHED
~~~

Permitted statement:

> The AIP v0.5.0 candidate completed all mandatory technical qualification gates and is release ready, but publication was not authorized and no public v0.5.0 release is claimed.

---

## 17. Publication Procedure

Publication occurs only after `GRANTED`.

Immediately before publication re-check:

~~~text
RELEASE_CANDIDATE_SHA unchanged
release readiness still applies
no later commit is being substituted
v0.5.0 tag absent
no existing v0.5.0 GitHub Release
~~~

The immutable `v0.5.0` tag SHALL be created directly at `RELEASE_CANDIDATE_SHA`. It is pushed
before the GitHub Release is published:

~~~bash
git tag -a v0.5.0 "$RELEASE_CANDIDATE_SHA" -m "AIP v0.5.0"
git push origin v0.5.0
gh release create v0.5.0 --verify-tag --title "AIP v0.5.0" \
  --notes-file <rendered public release note>
~~~

After creation:

~~~bash
git rev-list -n1 v0.5.0
~~~

MUST equal `RELEASE_CANDIDATE_SHA`.

The public release body SHALL use a pre-reviewed, public-only rendered release note and contain no unresolved placeholders or internal drafting instructions.

### 17.1 Workflow runs and attempts

Publishing the GitHub Release triggers exactly one `docker.yml` run (`release: published`). The
workflow has no `workflow_dispatch` trigger, and I6 SHALL NOT start another run by any other means.

That one run MAY have several attempts, through GitHub's "re-run jobs" on the same run id. Every
attempt SHALL be recorded, including failed ones, with:
- its attempt number;
- its conclusion;
- the digest it pushed, if any.

`FINAL_RELEASE_WORKFLOW_RUN_ID` is the run id plus the attempt number whose digest becomes
`FINAL_IMAGE_DIGEST`.

### 17.2 Failure before a final digest exists

Suppose the tag and the GitHub Release exist, but no attempt produces a digest that can be verified
under §18. Publication has then occurred without a verifiable artifact, and the outcome is
`POST_RELEASE_FAILED`.

The tag SHALL NOT be moved or re-pointed. Deleting and re-creating the `v0.5.0` release or tag is a
new publication. It requires a new, separately recorded owner authorization and a spec amendment.

---

## 18. Final Artifact Identity

After the release workflow succeeds, record:

~~~text
FINAL_RELEASE_WORKFLOW_RUN_ID
FINAL_IMAGE_DIGEST
~~~

The verification identity is the immutable digest, not a mutable tag.

All subsequent final-image checks SHALL use the immutable digest.

---

## 19. Final SBOM and Security Disposition

`SHIPPED_VERIFIED` requires security evidence generated or resolved specifically for:

~~~text
FINAL_IMAGE_DIGEST
FINAL_RELEASE_WORKFLOW_RUN_ID
~~~

The record SHALL include:

- the release workflow's full Trivy report (§8), including unfixed findings, whose recorded scanned
  digest SHALL equal `FINAL_IMAGE_DIGEST`;
- a correctly ref-scoped GitHub code-scanning query for the Trivy SARIF upload;
- the final-image SBOM from the same workflow attempt, whose subject digest SHALL equal
  `FINAL_IMAGE_DIGEST`;
- review of all HIGH/CRITICAL findings;
- zero unresolved release-blocking findings.

A scan or SBOM that names only the mutable `v0.5.0` or `latest` tag does not satisfy this section.

The code-scanning query SHALL be scoped to:

~~~text
refs/tags/v0.5.0
~~~

A default-branch-only code-scanning query is insufficient.

The only alerts on that ref are the release workflow's Trivy upload. CodeQL runs on pushes to
`main`, pull requests and a schedule, never on tags. So source CodeQL is established for the exact
candidate SHA in §12 and is not re-queried on the tag ref.

Candidate-image security evidence MAY be referenced for comparison, but SHALL NOT substitute for the final-image disposition.

---

## 20. Published-Image Golden Path

The final image SHALL be pulled anonymously by immutable digest.

A local rebuild SHALL NOT substitute.

From clean state, run `examples/release-golden-path/run.sh` from the tagged-source clone (§7.4,
§21) against `ghcr.io/...@sha256:<FINAL_IMAGE_DIGEST>`, and verify:

~~~text
pulled digest == FINAL_IMAGE_DIGEST
process runs non-root
GET /health succeeds
GET /health/neo4j succeeds

producer.version == 0.5.0
producer.build_revision == RELEASE_CANDIDATE_SHA
schema_version == 0.5

every phase is COMPLETE (both conditions of §7.3)
expected OpenAPI facts exist
expected AsyncAPI Queue facts exist
expected Topic/Subscription facts exist
expected Kubernetes infrastructure facts exist
expected DEPLOYED_AS outcome exists
runtime observation qualification exists

unresolved case remains UNRESOLVED
conflicting case remains CONFLICT with no guessed association
unsupported cases remain explicit

evidence drill-down resolves
same-snapshot continuity holds

REST workflow succeeds
negotiated MCP initialize succeeds
tools/list returns exactly:
  get_architecture_drift
  get_evidence
  get_service_dependencies

MCP dependency/drift/evidence workflow succeeds
disconnect/reconnect succeeds
public reads cause zero graph writes
every phase remains COMPLETE after its reads (§7.3)
~~~

These checks are distributed across the §7.1 phases as §7.3 places them. Each check passes only in
the phase that covers it, and every phase SHALL pass.

The final golden-path output SHALL be retained as release evidence.

---

## 21. Tagged-Source Verification

Independently clone the published tag:

~~~bash
git clone --branch v0.5.0 --depth 1 \
  https://github.com/michaelegner/architecture-intelligence-platform.git \
  <fresh-directory>
~~~

Verify:

~~~text
HEAD = RELEASE_CANDIDATE_SHA
working tree clean
package version = 0.5.0
uv sync --locked succeeds
release schemas present
release golden-path profile present and matching its SHA256SUMS (§7.4)
exactly three MCP tools
~~~

Run at least:

~~~bash
uv run pytest tests/unit/test_release_version_consistency.py -q
uv run python -m evaluation answers \
  --candidate-sha "$RELEASE_CANDIDATE_SHA"
~~~

The `answers` run overwrites the committed report in the clone. As stated in §10.3, the committed
report at the tag is the pre-refresh one; that is expected and is not a finding.

This is identity verification, not a substitute for full pre-publication source qualification.

---

## 22. GitHub Release Verification

After publication verify:

~~~text
tag = v0.5.0
tag target = RELEASE_CANDIDATE_SHA
release not draft
release body contains no internal/draft text
release body contains no unresolved placeholders
capability claims match the completion record
known limitations are not contradicted
evidence/documentation links resolve
~~~

Qualification evidence links SHOULD use immutable tag or commit identities rather than mutable `main` links.

---

## 23. Post-Release Closure

Record final verification in:

~~~text
docs/release-validation/v0.5.0-post-release-verification.md
~~~

It SHALL contain:

- candidate SHA;
- evidence commit SHA;
- decision commit SHA;
- final tag target;
- GitHub Release identity/time;
- all release workflow attempts;
- final image digest;
- SBOM identity;
- final security disposition;
- anonymous digest-pull evidence;
- build revision;
- published-image golden path;
- tagged-source verification;
- release-body verification;
- known limitations;
- post-release blocker count.

Its merge commit becomes `POST_RELEASE_COMMIT_SHA`.

Successful terminal state:

~~~text
SHIPPED_VERIFIED
~~~

Failure after publication produces:

~~~text
POST_RELEASE_FAILED
~~~

A published release SHALL NOT be called `SHIPPED_VERIFIED` while final-artifact verification is incomplete.

---

## 24. Documentation Status Closure

After successful publication verification:

- `ROADMAP.md` may mark v0.5 as shipped;
- `CHANGELOG.md` moves the prepared release content from `[Unreleased]` to `[0.5.0] - <publication date>`;
- the v0.5 specification index records I6 complete;
- release-validation documentation links to the post-release record.

These status-closure commits occur after the immutable release candidate and SHALL NOT move the `v0.5.0` tag.

Public GitHub Release links intended to point at shipped-state documentation MAY be updated after the closure commit without changing tag or artifact identity.

---

## 25. Implementation Slices

### Slice 1a — Entry Audit and Golden-Path Profile Freeze

Deliver, in one PR:

~~~text
I5 handoff audit (§5)
examples/release-golden-path/ README.md, profile/<phase>/, expected.json, SHA256SUMS (§7)
the per-fact source citations required by §7.1
the §7.2 transcriptions and their equivalence unit tests
the §7.4 discovery-unchanged guard test
~~~

No harness execution happens in this slice. Exit: the owner's merge freezes the profile.

### Slice 1b — Candidate Preparation

Deliver:

~~~text
0.5.0 version consistency (§6)
release-version tests/fixtures
examples/release-golden-path/run.sh and its per-phase checks (§7.3, §7.4)
release notes and CHANGELOG release content (§6.1), including the OFFLINE_ONLY
  and pre-refresh-report statements (§10.3, §10.7)
docker.yml SBOM / digest-scan / full-report changes (§8), mandatory
~~~

If the harness disagrees with the frozen `expected.json`, that is a finding. It is resolved under §14,
never by editing `expected.json` inside this slice.

Exit:

~~~text
candidate-preparation PR merged
RELEASE_CANDIDATE_SHA frozen as attempt rc.N
~~~

### Slice 2 — Exact-Candidate Qualification

Against only `RELEASE_CANDIDATE_SHA`:

~~~text
clean checkout
locked install
lint/format
unit/integration
dependency audit
version consistency
schemas
Architecture Answer evaluation twice (§10.3)
repository/documentation hygiene (§10.6)
candidate image
candidate security
candidate golden path
CI/CodeQL
~~~

On success, publish `docs/release-validation/v0.5.0-release-readiness.md` together with the
refreshed evaluation report (§10.3, §13). On failure, publish `v0.5.0-rc.N-no-go.md` and proceed
per §4.1.

Exit: `RELEASE_READY`, or a candidate-level `NO_GO` (§4.1).

### Slice 3 — Publication Decision

Repository owner records `GRANTED`, `NOT_GRANTED`, or `PENDING`.

Exit: `AWAITING_PUBLICATION_DECISION`, Slice 4A, or Slice 4B.

### Slice 4A — Unpublished Closure

Only when authorization is `NOT_GRANTED`.

Exit: `RELEASE_READY_NOT_PUBLISHED`.

### Slice 4B — Publication

Only when authorization is `GRANTED`.

Deliver:

~~~text
v0.5.0 tag at RELEASE_CANDIDATE_SHA
GitHub Release
release workflow
published GHCR digest
~~~

No terminal success is claimed yet.

### Slice 5 — Published-Artifact Verification and Closure

Verify the actual final source, artifact and security state.

Exit: `SHIPPED_VERIFIED` or `POST_RELEASE_FAILED`.

---

## 26. Stop Conditions

I6 SHALL stop and require review if:

1. `main` contains a post-I5 semantic mutation before candidate preparation;
2. version synchronization changes dependency resolution unexpectedly;
3. a new semantic fixture or expected architecture fact becomes necessary;
4. any I1–I5 semantic rule would need changing;
5. an I5 deferred finding is proposed as an opportunistic product fix;
6. candidate SHA changes after qualification begins;
7. evaluation runs are not byte-identical;
8. supported semantic output differs from I5 for a reason other than approved release metadata;
9. candidate image reports the wrong build revision;
10. publication is requested without explicit owner authorization;
11. tag target differs from candidate;
12. final artifact cannot be tied to the release workflow;
13. final artifact security findings lack disposition;
14. anonymous pull by digest fails;
15. published golden path fails;
16. public release notes materially overclaim qualified behavior;
17. a golden-path phase would need a component fixture edited, or a fact its component does not
    freeze (§7.1); a transcription cannot be proven equivalent (§7.2); or the harness disagrees
    with the frozen `expected.json`;
18. the release workflow's SBOM or scan cannot be tied to `FINAL_IMAGE_DIGEST` (§19);
19. the tag or GitHub Release would have to be deleted, moved or re-created (§17.2).

---

## 27. Definition of Done

### 27.1 Technical readiness

`RELEASE_READY` requires:

~~~text
exact RELEASE_CANDIDATE_SHA frozen
version surfaces = 0.5.0
schema_version = 0.5
clean exact-candidate qualification PASS
full unit/integration PASS
CI and CodeQL PASS
dependency/security candidate gates PASS
Architecture Answer evaluation 23/23 PASS
two evaluation runs byte-identical
repository/documentation hygiene PASS
candidate golden path PASS against the frozen expected.json
semantic differences from I5 limited to approved release metadata/harness changes
unresolved release blockers = 0
EVIDENCE_COMMIT_SHA recorded
~~~

### 27.2 Unpublished success

`RELEASE_READY_NOT_PUBLISHED` additionally requires:

~~~text
publication authorization = NOT_GRANTED
no v0.5.0 tag/release claimed
unpublished closure committed
~~~

### 27.3 Published success

`SHIPPED_VERIFIED` additionally requires:

~~~text
publication authorization = GRANTED
v0.5.0 tag -> RELEASE_CANDIDATE_SHA
GitHub Release published
release workflow identity recorded
FINAL_IMAGE_DIGEST recorded
SBOM/security disposition bound to final digest
anonymous pull by digest PASS
producer.version = 0.5.0
producer.build_revision = RELEASE_CANDIDATE_SHA
published-image golden path PASS
tagged-source verification PASS
GitHub Release verification PASS
post-release blockers = 0
POST_RELEASE_COMMIT_SHA recorded
~~~

---

## 28. Terminal Outcomes

~~~text
NO_GO
  release-level (§4.1): the owner ended the v0.5.0 cycle after a
  candidate-level NO_GO; a candidate-level NO_GO alone is not terminal

AWAITING_PUBLICATION_DECISION
  technically ready; owner decision pending
  non-terminal

RELEASE_READY_NOT_PUBLISHED
  technically ready
  publication explicitly not granted
  unpublished closure committed

POST_RELEASE_FAILED
  publication occurred
  one or more mandatory final-artifact verification gates failed

SHIPPED_VERIFIED
  publication authorized
  exact candidate published
  exact final artifacts independently verified
  final security disposition complete
  post-release closure committed
~~~

Only `SHIPPED_VERIFIED` permits the statement that `v0.5.0` shipped and was post-release verified.

---

## 29. Evidence Files

Normative filenames:

~~~text
docs/specifications/0.5.0/
  i6-release-candidate-publication-and-post-release-verification.md
  i6-completion-record.md

docs/release-validation/
  v0.5.0-release-notes.md
  v0.5.0-rc.N-no-go.md                       # one per candidate-level NO_GO (§4.1)
  v0.5.0-release-readiness.md                # the candidate that reaches RELEASE_READY
  v0.5.0-publication-decision.md
  v0.5.0-unpublished-closure.md              # only if NOT_GRANTED
  v0.5.0-post-release-verification.md        # only if publication occurs
~~~

Raw candidate and final-artifact evidence MAY be stored under:

~~~text
docs/release-validation/v0.5.0-artifacts/
~~~

Also normative:

~~~text
examples/release-golden-path/                # the §7 profile and harness
evaluation/architecture_answers/results/architecture-answers-evaluation-result.json
                                             # refreshed in the evidence PR only (§10.3)
~~~

`.gitignore` excludes `*.log`. Every cited evidence file SHALL be verified against the git index,
not the disk. A log that must be retained is force-added after a secret scan.

No raw secret, token, password, credential, or unredacted sensitive environment value may be committed.

---

## 30. Completion Record

`i6-completion-record.md` SHALL state:

- terminal outcome;
- I5 semantic baseline;
- I5 completion identity;
- release candidate identity, and every earlier candidate attempt with its `NO_GO` record;
- evidence and decision identities;
- publication authorization;
- tag identity where applicable;
- release workflow identity where applicable;
- final image digest where applicable;
- final SBOM/security status where applicable;
- known limitations;
- exact public claim allowed by the terminal state.

For a published release the final statement SHALL be equivalent to:

> AIP v0.5.0 is `SHIPPED_VERIFIED`: the exact qualified release candidate was published, the tagged source and final GHCR artifact identify that candidate, the final artifact passed the v0.5 golden path and security disposition, and every known unsupported, unresolved, deferred, or coverage-limited case remains explicit.

For an unpublished technical success:

> AIP v0.5.0 is `RELEASE_READY_NOT_PUBLISHED`: all mandatory technical gates passed for the exact candidate, but publication was not authorized and no public v0.5.0 release is claimed.

---

## 31. Relationship to v0.6

I6 closes the v0.5 release line.

It SHALL NOT use release qualification to introduce the next architecture-intelligence dimension.

~~~text
placement context retained in v0.5
    != locality-qualified Current State

Current State evidence
    != Architecture Intent
~~~

Locality-aware Current State remains v0.6.

Any v0.6 implementation begins only after the v0.5 terminal outcome is recorded.

---

## 32. Review Checklist

Before accepting this specification:

- [ ] I5 `FINAL_CANDIDATE_QUALIFIED` is semantic input, not automatic release authorization.
- [ ] The `0.4.2 -> 0.5.0` version mutation occurs before release-candidate freeze.
- [ ] `schema_version` remains `"0.5"`.
- [ ] Candidate, evidence, decision, closure, tag, workflow and image identities are distinct.
- [ ] The tag points to the candidate, never an evidence or decision commit.
- [ ] Candidate preparation cannot silently alter I1–I5 semantics.
- [ ] I4 `GO` means Pub/Sub is present in the final golden path.
- [ ] F5/F8 remain explicit limitations, not hidden release-time fixes.
- [ ] Exact-candidate evaluation is rerun twice, with byte-identical copied outputs and a clean
      checkout afterwards. The refreshed report is evidence-only and lands after the candidate.
- [ ] A candidate-level `NO_GO` differs from the release-level terminal `NO_GO` (§4.1).
- [ ] The golden-path `expected.json` is derived from component fixtures and frozen before the
      harness first runs (§7.1, Slice 1a).
- [ ] The golden path is phased, one clean graph per phase. Transcribed inputs are proven
      equivalent, and every phase expectation, including `k8s-unresolved`, cites a frozen
      public-projection assertion (§7.1, §7.2).
- [ ] The release workflow at the candidate produces a digest-bound SBOM and a full scan report (§8).
- [ ] Parent §24 hygiene (§10.6) and `OFFLINE_ONLY` (§10.7) are covered.
- [ ] The decision names both the candidate and the evidence commit (§15).
- [ ] No record embeds its own commit SHA (§4).
- [ ] Publication requires explicit owner authorization.
- [ ] `RELEASE_READY_NOT_PUBLISHED` and `SHIPPED_VERIFIED` remain distinct.
- [ ] The final GHCR digest is independently verified; no local/RC image substitutes.
- [ ] Final security/SBOM disposition is bound to the published digest/workflow.
- [ ] Final artifact verifies `producer.version = 0.5.0` and `producer.build_revision = RELEASE_CANDIDATE_SHA`.
- [ ] No v0.6 locality or Intent semantics enter I6.
