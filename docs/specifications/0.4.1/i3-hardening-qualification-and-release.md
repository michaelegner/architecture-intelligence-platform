# AIP v0.4.1 — I3 Hardening Qualification and Release

**Status:** Draft 0.1 — self-contained implementation and release contract

**Target release:** `v0.4.1`

**Release increment:** I3 — Hardening Qualification and Release

**Target repository path:** `docs/specifications/0.4.1/i3-hardening-qualification-and-release.md`

**Governing specification:** [`specification.md`](specification.md)

**Entry baseline:** `main` after completed I1 (`c10b89f`, PR #114) and completed I2
(`02ba34f`, PR #117)

**Preceding increment:** [`i2-messaging-semantic-guards.md`](i2-messaging-semantic-guards.md)

**Primary outcome:** AIP commits a reproducible benchmark that makes whole-graph snapshot/read cost
measurable without changing snapshot semantics, then qualifies, publishes, and independently
verifies the exact `v0.4.1` release candidate while preserving every I1/I2 semantic guarantee and
the frozen `v0.4` public architecture-intelligence contract.

---

## 1. Purpose

I1 and I2 are complete and merged:

```text
I1
one declared-versus-observed semantic owner
+ real-Neo4j differential qualification
+ qualification mismatches = 0
+ coverage mismatches = 0

I2
Queue-compatible destination guard
+ safe messaging service-identity guard
+ atomic refusal before semantic artifacts
+ frozen Quarkus/Airflow regressions
```

I3 does not add another architecture capability. It completes the remaining `v0.4.1` release
promise:

```text
merged semantic hardening
        |
        v
committed snapshot/read-cost benchmark
        |
        v
exact candidate qualification
        |
        v
release-candidate publication and artifact qualification
        |
        v
GO / NO-GO
        |
        v
v0.4.1 publication and independent verification
```

I3 SHALL establish this guarantee:

> **The semantic hardening delivered by I1 and I2 is compatible with AIP's shipped `v0.4.0`
> capability, the known whole-graph read cost is reproducibly measurable, and the exact source and
> container artifacts published as `v0.4.1` have been qualified without silently changing snapshot,
> retention, Canonical Model, or public MCP semantics.**

The benchmark is evidence for a later scaling decision. It is not permission to implement that
decision in this patch release.

---

## 2. Normative Language and Precedence

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD
NOT**, and **MAY** are normative.

The parent `v0.4.1` release specification governs whenever this document is silent. The completed I1
and I2 specifications and their completion records are frozen input to I3:

- [`i1-qualification-consistency.md`](i1-qualification-consistency.md)
- [`i1-completion-record.md`](i1-completion-record.md)
- [`i2-messaging-semantic-guards.md`](i2-messaging-semantic-guards.md)
- [`i2-completion-record.md`](i2-completion-record.md)

If this document conflicts with the parent specification or a completed earlier increment,
implementation SHALL stop and resolve the conflict explicitly. I3 MUST NOT silently reinterpret an
earlier GO statement.

Executable tests, machine-readable benchmark output, exact-commit CI results, and published-artifact
verification are the authoritative implementation evidence. A prose claim, development-branch run,
or locally built image is not a substitute.

---

## 3. Entry Conditions

I3 starts only after I1 and I2 are merged and their completion records report GO.

At entry, the following SHALL be independently confirmed from repository state and executable
evidence:

```text
I1 GO
I2 GO

one declared-versus-observed semantic owner
qualification mismatches = 0
coverage mismatches = 0

both messaging guards are production-reachable
either guard refusal creates zero semantic artifacts
valid declared Queue behavior remains supported
valid explicit runtime-only Service behavior remains OBSERVED_ONLY-capable

exactly three read-only MCP tools
schema_version = 0.4
no Topic or Subscription family
messaging operation recognition remains frozen
CI/security/dependency checks for the merged I2 state = PASS
I1 blockers = 0
I2 blockers = 0
```

The I3 entry audit SHALL use the merged `main` commits, not only the pre-merge candidate SHAs named
inside the I1/I2 completion records. A squash merge, documentation-only merge commit, or unrelated
intervening commit does not invalidate the earlier evidence, but the exact merged state still SHALL
pass the affected regression suites before candidate freeze.

If an entry condition is false, the defect SHALL be assigned back to the owning increment. I3 SHALL
not weaken the relevant assertion to make entry appear green.

---

## 4. Scope Budget

I3 is benchmark and release qualification work, not discovery or semantic expansion.

| Area | I3 limit |
|---|---|
| New public MCP tools | `0`; exactly the existing `3` remain |
| New Architecture Intelligence operations | `0` |
| New Canonical Model entities/relations | `0` |
| New discovery sources | `0` |
| Messaging recognition widening | `0` |
| Qualification/status vocabulary changes | `0` |
| Snapshot semantic changes | `0` |
| Fingerprint cache | `0` |
| Evidence retention/compaction | `0` |
| Performance/SLO gate | `0` |
| LLM dependency for correctness | `0` |
| Fresh Quarkus/Airflow live runs | `0` by default |
| Committed benchmark harness | `1` |
| Planned first release candidate | `v0.4.1-rc.1` |
| Final release | `v0.4.1` |

I3 MAY change package/producer version metadata, benchmark-only code, benchmark documentation,
release documentation, and tests required to qualify those changes.

---

## 5. Explicit Non-Goals

I3 SHALL NOT implement:

```text
snapshot fingerprint caching
incremental or rolling snapshot hashes
request-scoped repository optimization
telemetry ingestion lookup optimization
observed-evidence retention, compaction, deletion, or archival
evidence_refs caps or truncation
historical snapshot storage
performance SLOs or latency budgets
production-scale certification
Topic or Subscription
Kafka or Celery support
wider OpenTelemetry messaging attribute recognition
Kubernetes, gRPC, protobuf, or another adapter
AdapterRegistry or SourceDescriptor
new REST or MCP endpoints
new architecture analysis
new qualification or limitation values
LLM-based classification
```

A benchmark result that shows unacceptable cost is evidence for later work, not permission to add an
optimization to I3. A required semantic or production-code correction discovered during I3 creates a
new candidate and reopens the owning qualification gates.

---

## 6. Frozen Semantic Baseline

### 6.1 I1 qualification semantics

I3 SHALL preserve:

```text
CONFIRMED
OBSERVED_ONLY
NOT_OBSERVED_IN_WINDOW
```

and the shared evidence-window/coverage semantics implemented by
`app/qualification/declared_observed.py`.

The real-Neo4j differential fixture SHALL continue to report:

```text
qualification mismatches = 0
coverage mismatches = 0
unexplained differential cases = 0
```

Equivalent effective observation contexts MUST remain equivalent. The documented REST/MCP default
window asymmetry remains intentional.

### 6.2 I2 messaging semantics

I3 SHALL preserve the default-deny destination decision:

```text
deterministic declared Queue match
    -> Queue-compatible unless explicit evidence conflicts

no declared Queue match + explicit queue kind
    -> OBSERVED_ONLY Queue may be valid

no declared Queue match + absent/unknown/topic-like/conflicting kind
    -> refusal; no semantic artifacts
```

`messaging.system`, a destination name, or telemetry existence alone MUST NOT qualify an undeclared
destination as Queue-compatible.

The messaging service decision SHALL continue to preserve distinctive runtime-only service names
while refusing placeholder, conflicting, and ambiguous identities.

### 6.3 Public `v0.4` contract

I3 SHALL preserve:

- exactly `get_architecture_drift`, `get_evidence`, and `get_service_dependencies`;
- read-only MCP behavior and zero graph writes through tool calls;
- the existing `ArchitectureAnswer<T>` envelope family;
- `schema_version = "0.4"`;
- snapshot-bound answers and explicit observation context where required;
- evidence/provenance drill-down and closed schemas;
- direct dependencies only;
- no LLM requirement for deterministic correctness.

Patch version `0.4.1` is producer/build metadata. It MUST NOT cause a `v0.4` schema-directory rename
or a public schema-version bump.

---

## 7. Benchmark Question

The committed benchmark SHALL answer one bounded question:

> **With the requested answer held constant, how does the current cost of snapshot-state reading,
> snapshot fingerprinting, and one representative dependency answer change as unrelated total graph
> size and observed Evidence volume increase?**

The benchmark SHALL expose measurements. It SHALL NOT claim production capacity, extrapolate a safe
maximum landscape, or define an SLO.

The expected mechanism under test is the current implementation:

```text
Architecture Intelligence read
        |
        v
revision fence before
        |
        v
canonical_snapshot_state()
        |
        v
snapshot_fingerprint()
        |
        v
requested answer read/projection
        |
        v
revision fence after
```

The stable-read retry contract remains unchanged.

---

## 8. Benchmark Architecture

The benchmark SHALL have four separable components:

```text
deterministic fixture plan
        |
        v
disposable Neo4j seeding
        |
        v
timed production reads
        |
        v
validated JSON result + human summary
```

The implementation SHOULD live under a dedicated `benchmarks/` package or directory and SHOULD be
invocable with one documented command. It MUST import and exercise production snapshot and service
code rather than copying their algorithms into benchmark-only code.

The default benchmark workflow SHALL use an isolated disposable Neo4j instance, preferably the same
Testcontainers foundation used by integration tests. It MUST NOT assume or mutate the developer's
normal AIP database.

If an optional externally supplied Neo4j URI is supported, the harness MUST:

1. require an explicit destructive/disposable acknowledgement;
2. verify a benchmark-owned marker before cleanup;
3. refuse to clear an unmarked or non-empty user graph by default; and
4. document exactly which data is created and removed.

---

## 9. Deterministic Fixture Model

The benchmark SHALL use a fixed target subgraph whose requested dependency answer has constant
semantic cardinality at every scale point.

Additional scale data SHALL be disconnected from that target answer while remaining part of
`canonical_snapshot_state()`:

```text
fixed target service
    -> fixed dependency
    -> fixed answer size

unrelated synthetic services / operations / relations / evidence
    -> grow total canonical snapshot
    -> do not grow requested answer
```

This separation is REQUIRED. If both whole-graph size and answer size grow together, the benchmark
cannot establish which cost is being measured.

Synthetic observed evidence SHALL follow the production model, including:

- stable canonical entity and relation identifiers;
- `Evidence` with `evidence_type = OBSERVED`;
- deterministic environment and day/window values;
- deterministic evidence IDs consistent with the production per-fact/per-day identity rule;
- relation `evidence_ids` references to existing Evidence nodes;
- deterministic `first_seen`, `last_seen`, and sample trace values where those fields are present;
- no random UUID, wall-clock timestamp, process-dependent hash, or insertion-order dependency in
  structural fixture fields.

The seed plan MUST be inspectable before execution and MUST declare expected structural counts for
each scale point.

---

## 10. Scale Profiles

The harness SHALL define at least two named profiles.

### 10.1 Smoke profile

The smoke profile SHALL be small enough for explicit release qualification and integration testing.
It proves wiring, cleanup, result validation, and determinism; it does not prove scaling shape.

### 10.2 Review-comparable profile

The review-comparable profile SHOULD contain points in the same orders of magnitude as the
post-`v0.4.0` architecture review:

```text
~10^2 total nodes
~5 x 10^3 total nodes
~2 x 10^4 total nodes
~1 x 10^5 total nodes
```

The implementation MAY choose exact fixture dimensions that make deterministic seeding simpler.
For every point, the result SHALL record actual queried graph counts rather than reporting only
planned counts.

Scale points SHALL execute in a documented order. The harness MAY rebuild from clean state per point
or grow one marked disposable graph monotonically, but the selected method MUST be recorded in the
result and MUST NOT leave ambiguity about what each sample measured.

---

## 11. Measurements

At each scale point the benchmark SHALL measure, separately:

1. `canonical_snapshot_state()` plus `snapshot_fingerprint()` using production code; and
2. one end-to-end `get_service_dependencies` request through the production MCP application using
   an independent client boundary.

The second measurement SHALL include the stable-read and snapshot work actually paid by a caller.
A direct helper call MAY be recorded as an additional diagnostic, but it MUST NOT substitute for the
production-wired dependency measurement.

The benchmark SHALL use:

- a documented warm-up policy;
- at least three measured samples per operation and scale point;
- a monotonic high-resolution clock;
- identical request identity, environment, and observation window at every scale point;
- no concurrent writer during timed samples;
- explicit failure if the revision fence moves during a sample beyond production's permitted retry
  behavior.

To remain comparable with the architecture review, the result SHALL record the minimum of the
measured samples. It SHOULD also record every raw sample and median. No single summary number may
replace the raw measured values.

---

## 12. Structural Count Verification

Before timing each point, the harness SHALL query and record at least:

```text
Service nodes
Operation nodes
Queue nodes
Message nodes
Schema nodes
Evidence nodes
all canonical nodes included in snapshot state
canonical relations included in snapshot state
target answer claim count
target answer evidence-reference count
revision fence value
```

The actual structural counts SHALL be compared with the deterministic fixture plan. A mismatch is a
benchmark failure, not a timing sample.

The target answer's semantic content SHALL be canonicalized and compared across scale points. The
following MUST remain equal apart from snapshot identity/build metadata that legitimately reflects
the larger graph:

```text
requested service
observation context
outcome
claim identities
claim qualifications
delivery/destination semantics
limitations
```

If answer cardinality or semantics change as unrelated scale data is added, the benchmark run is
invalid until the fixture isolation defect is fixed.

---

## 13. Machine-Readable Result Contract

Every successful run SHALL emit one UTF-8 JSON document validated against a committed closed schema.
The schema SHALL reject unknown required-structure drift while permitting implementation-defined
metadata only through an explicitly bounded extension object, if one is provided.

The result SHALL contain at least:

```text
schema_version
benchmark_name
benchmark_implementation_version
candidate_sha
dirty_worktree
started_at
completed_at
profile
database_lifecycle
seed_method
warmup_count
sample_count
request
runtime_metadata
scale_points[]
```

Each `scale_points[]` entry SHALL contain:

```text
planned fixture dimensions
actual node counts by label
actual relation counts by type or benchmark-relevant family
actual evidence count
target claim/evidence-reference counts
revision fence value
snapshot/fingerprint raw samples
snapshot/fingerprint minimum and median
dependency-call raw samples
dependency-call minimum and median
snapshot_id consistency within the no-write sample set
model_revision consistency within the no-write sample set
structural_validation = PASS | FAIL
semantic_validation = PASS | FAIL
```

Durations SHALL use one explicit unit in field names or schema definitions. Floating-point timing
values MUST NOT participate in determinism comparisons.

`candidate_sha` SHALL be a full 40-character Git SHA for release evidence. The harness MAY permit
`unknown` only for local development, but a result with unknown candidate identity cannot qualify
I3.

The release-bound result SHALL state whether the worktree was dirty. `dirty_worktree = true` is
release-blocking.

---

## 14. Runtime Metadata

The result SHALL record enough environment context to interpret, not normalize away, timing
differences:

- operating system and architecture;
- CPU model or the strongest portable equivalent available;
- logical CPU count;
- memory total when discoverable without extra privilege;
- Python version;
- Neo4j version and edition;
- container runtime/version when applicable;
- AIP package version and full source SHA;
- warm-up/sample policy;
- whether the run used a local disposable container or explicit external database;
- any benchmark-affecting configuration override.

Absence of an optional host metadata field SHALL be represented explicitly as unavailable. It SHALL
NOT cause the benchmark to invent a value.

The result MUST NOT contain credentials, access tokens, environment-variable dumps, private host
names, raw traces, or user data.

---

## 15. Benchmark Determinism

Two clean smoke runs from the same exact source state SHALL produce identical deterministic
structure after removing only these explicitly variable fields:

```text
started_at / completed_at
timing samples and summaries
ephemeral container identifiers and ports
host/runtime metadata that is inherently execution-specific
snapshot_id only if the recorded database version introduces a justified nondeterministic storage
representation (the preferred and expected result is identical snapshot_id)
```

Fixture IDs, counts, request, answer semantics, profile definition, sample count, and schema version
MUST be identical.

The determinism comparison SHALL be implemented as a testable canonicalization function, not a
manual visual comparison.

Timing equality is neither expected nor asserted.

---

## 16. Interpreting Scaling Shape

The human-readable report SHALL present every scale point and both timed operations. It SHALL show
at least the ratio between adjacent graph sizes and the ratio between adjacent minimum durations.

The conclusion SHALL use bounded language:

```text
observed cost increased with total graph size in this environment
observed cost did not increase monotonically in this run
run was insufficient to determine the expected shape
```

The benchmark MUST NOT automatically claim strict mathematical linearity from four noisy samples.
It MAY report normalized duration per node or a descriptive regression as diagnostic information,
provided the raw data remains primary and no production guarantee is inferred.

There is no maximum-duration pass/fail threshold in `v0.4.1`. A slow but structurally valid run may
qualify the benchmark while strengthening the evidence for later optimization.

---

## 17. Benchmark Test Contract

Automated tests SHALL cover at least:

1. deterministic fixture-plan generation;
2. deterministic canonical IDs and timestamps;
3. JSON-schema acceptance of a complete valid result;
4. JSON-schema refusal of missing required fields, extra closed-schema fields, invalid SHA, invalid
   counts, and non-positive/invalid durations;
5. canonicalization of variable run fields;
6. structural-count mismatch refusal;
7. target-answer semantic mismatch refusal;
8. dirty-worktree and unknown-candidate release refusal;
9. safe database lifecycle/cleanup behavior;
10. one disposable-Neo4j smoke execution through production snapshot code and the production MCP
    dependency path.

The expensive review-comparable profile SHALL NOT run in default unit/integration CI. The small
smoke execution MAY be marked or otherwise separated if its runtime would materially expand the
default suite, but it MUST be run explicitly during exact-candidate qualification.

Mocking may test serialization and failures. It MUST NOT be the only evidence that the benchmark
reaches real Neo4j and production MCP wiring.

---

## 18. ADR 0011 Disposition

I3 SHALL NOT implement ADR 0011's cache or narrow `snapshot_id` semantics.

At I3 entry ADR 0011 is `Proposed`. Its current acceptance condition asks for a committed benchmark
that reproduces the baseline and shows the cache's effect. I3 supplies the committed current-state
baseline but deliberately supplies no cache whose effect could be measured.

Therefore I3 SHALL keep ADR 0011 `Proposed` unless a separately reviewed ADR amendment makes the
benchmark-only evidence sufficient for acceptance without implying that caching shipped.

I3 SHOULD add an implementation/evidence note to ADR 0011 that names:

- the committed benchmark entry point;
- the machine-readable result schema;
- the exact candidate benchmark result;
- the observed scaling-shape conclusion;
- the explicit statement that no cache, lookup optimization, or snapshot semantic change shipped.

It is forbidden to mark ADR 0011 `Accepted` merely because the benchmark exists while leaving its
stated cache-effect condition unsatisfied.

---

## 19. ADR 0012 and Retention Boundary

ADR 0012 remains outside I3. Benchmark fixture cleanup is disposal of synthetic benchmark-owned
data, not a production evidence-retention policy.

I3 SHALL NOT:

```text
delete or compact production observed evidence
cap relation evidence references
change retention configuration or defaults
change past-window qualification
present benchmark cleanup as evidence-retention support
```

The benchmark result MAY quantify Evidence growth as a scaling input. It MUST NOT prescribe a
retention threshold.

---

## 20. Package and Producer Version

Before release-candidate freeze, active metadata SHALL report `0.4.1` consistently:

```text
pyproject.toml project version = 0.4.1
uv.lock root project version = 0.4.1
MCP server version = 0.4.1
ArchitectureAnswer producer.version = 0.4.1
```

The implementation SHALL update all active producer-version call sites, currently including
`app/mcp/server.py` and `app/mcp/wiring.py`, and SHALL add or retain tests preventing disagreement.

The lock-file update SHOULD change only the root project version. Any third-party dependency,
version, source, or hash change is a dependency mutation and SHALL be justified and fully
requalified.

Historical documents retain the versions they describe. The public answer's `schema_version`
remains `0.4`.

For the exact source and container candidate:

```text
producer.name = architecture-intelligence-platform
producer.version = 0.4.1
producer.build_revision = RELEASE_CANDIDATE_SHA
```

`unknown`, an abbreviated SHA, or a SHA different from the qualified candidate is release-blocking.

---

## 21. Candidate Identity and Freeze

I3 SHALL distinguish:

```text
I3_ENTRY_SHA
    merged I1/I2 baseline from which I3 starts

BENCHMARK_IMPLEMENTATION_SHA
    exact code state at which the committed harness first passes its contract

RELEASE_CANDIDATE_SHA
    exact immutable source state intended for v0.4.1

EVIDENCE_COMMIT_SHA
    optional later documentation-only commit recording candidate-bound evidence

FINAL_RELEASE_SHA
    exact SHA named by the final v0.4.1 tag; equal to RELEASE_CANDIDATE_SHA
```

Qualification applies only to the literal commit tested. After candidate freeze, a change to any of
the following creates a new candidate:

```text
production or benchmark code
tests or evaluation fixtures
schemas or contracts
dependencies or lock file
configuration
Dockerfile or workflows
executable demo/seed code
tracked release documentation intended inside the release tag
```

Tags SHALL NOT be moved. A candidate-changing correction requires a new SHA, a new
`v0.4.1-rc.N`, and re-execution of every affected gate.

A later evidence-only commit MAY record completed results without invalidating the candidate. It
MUST NOT change executable or candidate content. Once evidence-only commits exist after the
candidate, every tag/release command SHALL name the explicit candidate SHA rather than ambient
`HEAD`.

---

## 22. Existing Evaluation and Regression Qualification

The exact candidate SHALL pass:

1. all unit tests;
2. all integration tests against real Neo4j where the suite requires it;
3. the I1 differential qualification fixture;
4. all I2 guard-level, composed, and persistence regressions;
5. exact-literal and synthetic-reachability Quarkus/Airflow messaging regressions;
6. the complete 23-scenario Architecture Answers evaluation;
7. two clean-state evaluation runs with semantically identical results;
8. the independent MCP client dependency/drift/evidence golden path;
9. tool discovery proving exactly three tools in the frozen order;
10. the deterministic hero path;
11. schema-generation/frozen-schema checks;
12. the benchmark smoke profile twice from clean state;
13. the review-comparable benchmark profile once for candidate-bound evidence.

Fresh live Quarkus/Airflow execution is not required. Frozen evidence and the I2 exact-shape tests
are the required patch-release regression.

An existing expected answer MAY change only when an explicit I1/I2 semantic correction requires it.
The qualification record SHALL identify each changed expectation and its governing evidence. I3
MUST NOT regenerate expected answers from AIP output.

---

## 23. Benchmark Candidate Evidence

The review-comparable benchmark SHALL run from a clean checkout of `RELEASE_CANDIDATE_SHA` and emit
a candidate-bound JSON result. That result SHALL be validated before any human conclusion is
written.

The committed release evidence SHOULD include:

```text
docs/release-validation/v0.4.1-read-cost-benchmark.json
docs/release-validation/v0.4.1-read-cost-benchmark.md
```

The Markdown record SHALL summarize the machine-readable artifact without replacing it. It SHALL
state:

- exact source SHA;
- benchmark command/profile;
- fixture topology and actual counts;
- environment caveats;
- raw-result artifact hash;
- observed shape for snapshot/fingerprint and end-to-end dependency reads;
- target answer invariance result;
- cleanup result;
- explicit absence of performance/SLO qualification;
- explicit absence of snapshot-cache or retention changes.

If committing the result produces an evidence-only commit after candidate freeze, the record SHALL
name the earlier candidate explicitly and follow §21.

---

## 24. Clean-Checkout Source Qualification

Source qualification SHALL run from a newly created clean checkout or worktree at the exact
candidate SHA. It SHALL not use the developer's mutable working tree or an environment containing
unrecorded source changes.

At minimum it SHALL execute the repository's locked workflow equivalents:

```text
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit
uv run pytest tests/integration
```

It SHALL additionally run the deterministic evaluation, independent MCP golden path if not already
covered by the integration invocation, hero demo qualification, benchmark smoke/reproducibility
runs, and review-comparable benchmark.

The record SHALL capture commands, results, counts, environment, and exact SHA. A local uncommitted
fix or skipped failing test is a NO-GO.

---

## 25. CI, Security, and Dependency Gates

The exact candidate SHALL have completed successful GitHub checks for:

```text
lint + test (every triggered instance)
CodeQL
analyze (actions)
analyze (python)
dependency security scan / pip-audit (every triggered instance)
```

Checks SHALL be queried by exact full commit SHA through the GitHub API. An ambient branch or PR
summary that can omit, combine, or point at another SHA is insufficient evidence.

The source candidate SHALL also pass the existing container build and local smoke path. Security
findings SHALL be recorded and dispositioned. No unreviewed critical finding may remain at GO.

The benchmark MUST NOT introduce unsafe query construction, credentials in output, privileged
containers without justification, or an unguarded graph-clearing command.

---

## 26. Release Documentation

Before candidate freeze, active documentation SHALL agree on the bounded `v0.4.1` release:

```text
README.md where current version/capability is stated
ROADMAP.md
CHANGELOG.md
docs/mcp.md where producer/version behavior is stated
docs/specifications/0.4.1/README.md
docs/specifications/0.4.1/specification.md
this I3 specification
docs/adr/README.md and ADR 0011 status/evidence note
draft v0.4.1 release notes
```

The `docs/specifications/0.4.1/README.md` summary SHALL make the release boundary explicit:

> `v0.4.1` hardens AIP's existing architecture-intelligence semantics before broader discovery. It
> cross-checks declared-versus-observed qualification, guards runtime messaging destination and
> service identity, and commits reproducible evidence of current whole-graph read cost. It adds no
> discovery source, Canonical Model family, or MCP tool.

Release notes SHALL distinguish:

- semantic correctness delivered by I1/I2;
- benchmark evidence delivered by I3;
- intentionally deferred snapshot optimization, retention, Pub/Sub, and broader discovery.

They MUST NOT market `v0.4.1` as Pub/Sub support or performance remediation.

---

## 27. Release Candidate Publication

The first planned release candidate is:

```text
v0.4.1-rc.1
```

The RC tag SHALL resolve to `RELEASE_CANDIDATE_SHA`. Publishing the GitHub prerelease SHALL exercise
the actual release-triggered Docker workflow and publish the correspondingly tagged GHCR image.

Before RC publication, the following SHALL be true:

```text
candidate source qualification = PASS
candidate CI/security/dependency checks = PASS
benchmark smoke reproducibility = PASS
review-comparable benchmark = valid result
I1/I2 semantic regression = PASS
release blockers = 0 or explicitly awaiting published-artifact gates
```

The RC tag is immutable. A candidate-changing failure produces `v0.4.1-rc.2` or later; it does not
move `rc.1`.

---

## 28. Published RC Artifact Qualification

The image pulled by immutable RC tag SHALL be qualified independently of any local source-built
image.

Qualification SHALL establish:

- the expected GHCR repository/tag and immutable digest;
- anonymous/public pull behavior consistent with the repository's release policy;
- non-root runtime behavior;
- health endpoint success;
- deterministic import/seed success;
- exactly three MCP tools;
- the independent dependency -> evidence and drift -> evidence golden paths;
- graph writes through MCP = `0`;
- `producer.version = 0.4.1`;
- `producer.build_revision = RELEASE_CANDIDATE_SHA`;
- image vulnerability scan results retrieved for the correct digest/workflow run and dispositioned.

A locally built image cannot substitute for the release-triggered RC image. A successful image
build cannot substitute for a successful MCP golden path through that pulled image.

The expensive benchmark need not run inside the published image. Its release role is source-bound
measurement evidence, while the image gates prove artifact identity and shipped behavior.

---

## 29. GO / NO-GO Record

Before final publication, one combined record SHALL exist at:

```text
docs/release-validation/v0.4.1-go-no-go.md
```

It SHALL name:

```text
RELEASE_CANDIDATE_SHA
RC tag and tag target
RC image digest
package/producer/build identities
I1/I2 entry evidence
unit/integration/evaluation results
benchmark result and artifact hash
clean-checkout results
CI/CodeQL/dependency results queried by exact SHA
published RC golden-path results
container security findings and dispositions
known limitations
release blockers
owner GO / NO-GO decision and timestamp
```

The technical precondition may report `READY FOR OWNER DECISION`; only the repository owner (or an
explicitly delegated release authority) records final GO.

GO requires `release blockers = 0`. Unsupported Pub/Sub, unchanged whole-graph read cost, and
deferred retention are known limitations, not blockers, because the release does not claim those
capabilities.

---

## 30. Release Blockers

At minimum, any of the following is release-blocking:

```text
I1 qualification or coverage mismatch
I2 guard bypass or semantic artifact from a refused span
regression in a valid declared Queue or explicit runtime-only Service case
Quarkus/Airflow frozen regression failure
new Topic/Subscription or widened messaging recognition
public MCP tool count != 3
graph write reachable through MCP
schema_version != 0.4
package or producer version != 0.4.1
producer.build_revision != exact candidate SHA
dirty or unknown benchmark candidate identity
benchmark structural or target-answer semantic validation failure
benchmark result fails its committed JSON schema
benchmark cannot cleanly execute against disposable Neo4j
clean-checkout test/evaluation failure
required exact-SHA CI/security/dependency check not successful
unreviewed critical security finding
RC tag does not resolve to exact candidate
published RC image cannot be pulled or fails the independent MCP golden path
release documentation claims unsupported capability
```

Absolute timing different from the architecture review is not a blocker. A measured scaling shape
that is worse than expected is not by itself a blocker if the benchmark is correct and the release
claim remains bounded; it is a finding for future work.

---

## 31. Final Publication

After recorded GO:

1. create immutable tag `v0.4.1` at `RELEASE_CANDIDATE_SHA`;
2. publish the GitHub Release using the reviewed release notes;
3. allow the release-triggered workflow to publish `ghcr.io/...:v0.4.1` and update `latest` according
   to existing policy;
4. record the final tag target, release URL, workflow identity, and image digest;
5. do not infer success from the RC artifact after final publication.

The final tag MUST identify the candidate approved in the GO record. Ambient `main`, an evidence-only
commit, or a later documentation update MUST NOT be tagged accidentally.

---

## 32. Post-Release Verification

The published release SHALL be independently verified and recorded at:

```text
docs/release-validation/v0.4.1-post-release-verification.md
```

Verification SHALL include:

- GitHub `v0.4.1` tag and release existence;
- final tag -> exact GO candidate SHA;
- final GHCR tag -> recorded immutable digest;
- public/anonymous image pull;
- non-root runtime and health check;
- import/seed plus independent three-tool MCP golden path;
- `producer.version = 0.4.1` and exact `producer.build_revision`;
- final-image vulnerability result queried against the correct workflow/image identity;
- fresh clone of the `v0.4.1` tag;
- locked dependency install and bounded source smoke from that fresh clone;
- public documentation links and release notes resolve.

RC verification does not substitute for final-artifact verification. Final verification SHALL use
the actual final tag and image.

If post-release verification finds an artifact identity or functional failure, the result SHALL be
recorded immediately. Tags MUST NOT be moved. Remediation uses a new patch release when source or
artifact changes are required.

---

## 33. Public Status Closure

After final verification passes:

- `ROADMAP.md` SHALL mark `v0.4.1` shipped and retain `v0.5.0` as planned;
- `CHANGELOG.md` SHALL contain the dated `0.4.1` entry and a fresh empty `[Unreleased]` section;
- `docs/specifications/0.4.1/README.md` SHALL mark I1, I2, and I3 complete with their exact evidence;
- `docs/release-validation/README.md` SHALL index the benchmark, GO/NO-GO, release notes, and
  post-release verification records;
- ADR 0010 remains `Accepted`;
- ADR 0013 remains `Accepted` and satisfied, not superseded;
- ADR 0011 follows §18 and MUST NOT imply the cache shipped;
- ADR 0012 remains deferred/proposed according to its own record.

The `v0.5.0` roadmap boundary SHALL state that broader messaging recognition and generic Pub/Sub may
proceed only through the I2 guards, and that broader discovery supplies the landscape against which
ADR 0011/0012 implementation can later be qualified.

---

## 34. No-Substitution Rules

The following substitutions are forbidden:

| Required evidence | Forbidden substitute |
|---|---|
| Production snapshot benchmark | copied benchmark algorithm or mocked repository |
| Production MCP dependency timing | direct helper timing only |
| Constant target answer | merely similar answer counts without semantic comparison |
| Actual graph counts | planned/formula counts only |
| Raw samples | one hand-copied summary duration |
| Machine-readable result | prose table only |
| Clean exact candidate | dirty working tree or nearby branch head |
| Exact-SHA CI query | ambient PR check summary |
| Published RC image | locally built image |
| Independent MCP golden path | health check only |
| Final image verification | RC image verification |
| Explicit owner GO | inferred GO from green automation |
| Unsupported boundary | invented placeholder support |

---

## 35. Delivery Slices

I3 SHOULD be delivered in three reviewable slices.

### I3.1 — Reproducible benchmark harness

Deliver:

- deterministic fixture planner/seeder;
- disposable Neo4j lifecycle;
- production snapshot/fingerprint timing;
- production MCP dependency timing;
- JSON schema and human report;
- unit tests and real-Neo4j smoke test;
- benchmark README and safe runbook;
- ADR 0011 evidence note that does not change its status prematurely.

I3.1 SHALL NOT change package version or publish an artifact.

### I3.2 — Candidate preparation and exact qualification

Deliver:

- I1/I2 merged-state entry audit;
- version/producer metadata `0.4.1`;
- changelog, roadmap, specification-directory README, and draft release notes;
- exact candidate freeze;
- clean-checkout full qualification;
- two smoke benchmark runs and one review-comparable run;
- candidate-bound benchmark and qualification records;
- exact-SHA CI/security/dependency evidence.

I3.2 produces `RELEASE_CANDIDATE_SHA`.

### I3.3 — RC, GO, final publication, and closure

Deliver:

- immutable `v0.4.1-rc.N` publication;
- release-triggered RC image qualification;
- combined GO/NO-GO record and explicit owner decision;
- immutable `v0.4.1` publication after GO;
- independent final source/image verification;
- post-release record and public status closure;
- I3 completion record.

If repository policy prefers evidence-only closure in a fourth PR after external publication, I3.3
MAY be split into I3.3 publication/GO and I3.4 post-release closure. The semantic gates and candidate
identity rules do not change.

---

## 36. Expected Repository Surface

The implementation is expected to add or update approximately:

```text
benchmarks/README.md
benchmarks/snapshot_read_cost.py
benchmarks/snapshot_read_cost.schema.json
tests/unit/test_snapshot_read_cost_benchmark.py
tests/integration/test_snapshot_read_cost_benchmark.py

pyproject.toml
uv.lock
app/mcp/server.py
app/mcp/wiring.py
version/producer tests

docs/adr/0011-snapshot-identity-read-cost.md
docs/adr/README.md
docs/specifications/0.4.1/README.md
docs/specifications/0.4.1/i3-completion-record.md
docs/release-validation/v0.4.1-read-cost-benchmark.json
docs/release-validation/v0.4.1-read-cost-benchmark.md
docs/release-validation/v0.4.1-release-notes.md
docs/release-validation/v0.4.1-go-no-go.md
docs/release-validation/v0.4.1-post-release-verification.md
docs/release-validation/README.md
README.md
ROADMAP.md
CHANGELOG.md
docs/mcp.md
```

Exact filenames beneath `benchmarks/` are implementation choices if the resulting entry point,
schema, and evidence remain equally discoverable. Changes to Canonical Model, graph schema,
qualification logic, messaging recognition, or public answer schemas are unexpected and require
explicit review.

---

## 37. Review Invariants

Review SHALL reject an implementation that violates any of these invariants:

```text
R1   Benchmark imports production snapshot/read code; it does not clone the algorithm.
R2   End-to-end timing crosses the production MCP boundary.
R3   Requested answer semantics remain constant across scale points.
R4   Scale growth is present in canonical_snapshot_state.
R5   Seed data and structural expectations are deterministic.
R6   Actual database counts are measured and validated.
R7   Raw timing samples are retained.
R8   Timing values are not treated as deterministic or as an SLO.
R9   Benchmark runs against disposable/explicitly marked data only.
R10  Machine-readable output validates against a committed closed schema.
R11  Release evidence is bound to a clean full candidate SHA.
R12  No snapshot or out-of-band-write semantic changes ship.
R13  No evidence retention behavior changes ship.
R14  I1 mismatch counts remain zero.
R15  I2 refusals remain atomic and default-deny.
R16  Exactly three read-only MCP tools remain.
R17  schema_version remains 0.4 while producer.version becomes 0.4.1.
R18  RC/final tags name the explicit qualified candidate.
R19  Published images prove their source revision through producer metadata.
R20  Final artifact verification is independent of RC/local verification.
```

---

## 38. Definition of Done

### Entry and semantic preservation

```text
[ ] merged I1 and I2 entry state is audited
[ ] qualification mismatches = 0
[ ] coverage mismatches = 0
[ ] messaging guard suites pass
[ ] refused messaging spans create zero semantic artifacts
[ ] exact Quarkus/Airflow regressions pass
[ ] valid Queue and OBSERVED_ONLY service cases pass
```

### Benchmark

```text
[ ] committed benchmark uses production snapshot/fingerprint code
[ ] end-to-end measurement uses production MCP dependency path
[ ] disposable Neo4j lifecycle is safe and documented
[ ] target answer is semantically constant across scale points
[ ] smoke and review-comparable profiles exist
[ ] actual graph/evidence/relation counts are validated
[ ] at least three raw samples per operation/point are emitted
[ ] machine-readable output validates against a closed schema
[ ] two clean smoke runs have identical deterministic structure
[ ] review-comparable result is bound to exact clean candidate SHA
[ ] human record states bounded scaling-shape conclusion and caveats
[ ] no performance threshold or SLO is claimed
```

### Scope and contract preservation

```text
[ ] no snapshot cache or snapshot semantic change exists
[ ] no retention/compaction behavior exists
[ ] no Topic/Subscription or new relation family exists
[ ] messaging recognition is not widened
[ ] no discovery source or adapter seam is added
[ ] exactly three read-only MCP tools remain
[ ] graph writes through MCP = 0
[ ] ArchitectureAnswer schema family is unchanged
[ ] schema_version = 0.4
[ ] package/producer version = 0.4.1
[ ] producer.build_revision = exact candidate SHA
```

### Qualification and publication

```text
[ ] clean-checkout unit/integration suites pass
[ ] 23-scenario evaluation passes twice deterministically
[ ] independent MCP golden paths pass
[ ] hero demo remains semantically valid
[ ] exact-SHA CI/CodeQL/dependency gates pass
[ ] source container smoke passes
[ ] RC tag points to exact candidate
[ ] published RC image passes independent qualification
[ ] security findings are reviewed and dispositioned
[ ] owner records GO with release blockers = 0
[ ] final v0.4.1 tag points to exact GO candidate
[ ] final source and GHCR image are independently re-verified
[ ] roadmap/changelog/specification/release-validation indexes are closed
```

---

## 39. I3 Exit Statement

The canonical I3/release exit statement SHALL have this form:

```text
GO — At <full candidate SHA>, AIP v0.4.1 preserves the shipped v0.4 ArchitectureAnswer schema
family and exactly three read-only MCP tools while completing its semantic hardening: the analysis
and Architecture Intelligence paths remain governed by one declared-versus-observed rule with
qualification mismatches = 0 and coverage mismatches = 0, and runtime messaging still requires
both Queue-compatible destination semantics and safe service identity before producing any
canonical artifact. A committed, disposable, deterministic benchmark reproduces and records the
current relationship between total graph/evidence size and snapshot/dependency read cost without
changing snapshot identity, retention, or public semantics. The exact source candidate, release-
triggered RC image, final v0.4.1 tag, and final GHCR image have passed their required independent
qualification, with producer.version=0.4.1 and producer.build_revision=<full candidate SHA>.
Release blockers = 0.
```

If any clause cannot be supported by executable, candidate-bound, and artifact-bound evidence, I3
is `NO-GO` and `v0.4.1` SHALL not be declared shipped.

---

## 40. Handoff to v0.5.0

I3 completes semantic hardening; it does not consume the broader-discovery work it enables.

```text
v0.4.1
one qualification rule
+ messaging semantic guards
+ reproducible read-cost evidence
+ qualified published artifacts

        |
        v

v0.5.0
real adapter seam
+ broader independently qualified discovery
+ generic Pub/Sub semantics after a new ADR
+ Kubernetes discovery
+ real landscapes for later scaling/retention decisions
```

`v0.5.0` SHALL cite the I2 guards before widening messaging recognition. It SHALL use the I3
benchmark as a reproducible baseline, not as proof that scaling has already been fixed. ADR 0011
implementation and ADR 0012 retention remain separately reviewable semantic work.

---

## 41. References

- [`specification.md`](specification.md) — governing `v0.4.1` release contract
- [`i1-completion-record.md`](i1-completion-record.md) — completed qualification-consistency
  evidence
- [`i2-completion-record.md`](i2-completion-record.md) — completed messaging-guard evidence
- [`../../adr/0010-single-qualification-rule.md`](../../adr/0010-single-qualification-rule.md)
- [`../../adr/0011-snapshot-identity-read-cost.md`](../../adr/0011-snapshot-identity-read-cost.md)
- [`../../adr/0012-observed-evidence-retention.md`](../../adr/0012-observed-evidence-retention.md)
- [`../../adr/0013-no-topic-family-without-guards.md`](../../adr/0013-no-topic-family-without-guards.md)
- [`../../architecture-review-0.4.0.md`](../../architecture-review-0.4.0.md)
- [`../0.4.0/i4-release-candidate-publication-and-verification.md`](../0.4.0/i4-release-candidate-publication-and-verification.md)
- [`../../release-validation/v0.4.0-go-no-go.md`](../../release-validation/v0.4.0-go-no-go.md)
- [`../../release-validation/v0.4.0-post-release-verification.md`](../../release-validation/v0.4.0-post-release-verification.md)
