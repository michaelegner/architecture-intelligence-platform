# AIP v0.4.0 — I4 Release Candidate, Publication, and Verification

**Status:** Draft 1 — self-contained implementation contract  
**Target release:** `v0.4.0`  
**Iteration:** I4 — Release Candidate, Publication, and Verification  
**Entry baseline:** `main` after I3 completion  
**Qualified I3 candidate:** `bbde691d5d317ae167394b9871e26c0b2e183b63`  
**Parent release specification:** [`specification.md`](specification.md)  
**Preceding iteration:** [`i3-drift-capability-and-deterministic-qualification.md`](i3-drift-capability-and-deterministic-qualification.md)

---

## 1. Purpose

I1–I3 have completed the architecture-intelligence capability of `v0.4.0`:

```text
ArchitectureIntelligenceService
ArchitectureAnswer<T>
snapshot-bound answers
explicit observation context
evidence/provenance linkage
qualification and limitation semantics
exactly three read-only MCP tools
deterministic three-tool evaluation
frozen Quarkus/Airflow-derived qualification
deterministic hero demo
```

I4 does **not** add another architecture capability.

Its purpose is to convert that qualified capability into an exact, public, independently verifiable release:

```text
I3-qualified capability
        |
        v
candidate preparation
        |
        v
exact source candidate
        |
        v
clean-checkout qualification
        |
        v
v0.4.0-rc.N
        |
        v
published RC image qualification
        |
        v
GO / NO-GO
        |
        v
v0.4.0
        |
        v
published source/image verification
        |
        v
public status closure
```

The governing I4 rule is:

> **Qualify the exact source state intended for release, exercise the actual publication pipeline before GO, publish only the qualified candidate, and then independently verify the artifacts that were actually published.**

A green development branch, an earlier I3 candidate, an unverified local image, or a successful LLM demonstration is not sufficient.

---

## 2. Normative Language and Precedence

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

The parent `v0.4.0` release specification governs whenever this document is silent.

The executable I1–I3 contracts and qualified behavior are frozen input to I4. If I4 cannot complete without changing architecture semantics, answer contracts, snapshot/evidence semantics, MCP tool semantics, or independently authored evaluation ground truth, implementation SHALL stop and record a release blocker rather than silently treating the change as release engineering.

---

## 3. Entry Conditions

I4 starts only after I1, I2, and I3 are complete and merged.

At entry, all of the following SHALL be true:

```text
I1 GO
I2 GO
I3 GO

exactly three public MCP tools
ArchitectureIntelligenceService remains the semantic boundary
all tool operations are read-only
I1 claim identity is preserved by drift
architecture-answer evaluation = PASS
two full clean-state answer passes are semantically identical
frozen Quarkus/Airflow-derived qualification = PASS
hero demo succeeds twice from clean state with byte-identical structuredContent
graph writes through the MCP tool surface = 0
CI = PASS
CodeQL = PASS
dependency audit = PASS
I3 blockers = 0
```

The qualified I3 executable/demo candidate is:

```text
bbde691d5d317ae167394b9871e26c0b2e183b63
```

If an entry condition is false, I4 SHALL return to the responsible I1/I2/I3 increment rather than absorb the defect.

---

## 4. Current Entry Observations

I4 begins with several concrete release-preparation facts that MUST be resolved before candidate freeze.

### 4.1 Active package version

The active repository metadata still reports:

```text
pyproject.toml = 0.3.0
uv.lock root project = 0.3.0
```

The final release candidate MUST identify itself consistently as `0.4.0`.

This is a candidate-changing source modification and SHALL occur before candidate freeze.

### 4.2 Producer identity

The qualified evaluator and production MCP wiring already target:

```text
producer.name    = architecture-intelligence-platform
producer.version = 0.4.0
```

The production Docker workflow supplies:

```text
AIP_BUILD_REVISION=<source SHA>
```

I4 SHALL prove that package version, producer version, and immutable build revision agree in the published artifact.

### 4.3 Changelog

`CHANGELOG.md` currently has an empty `[Unreleased]` section. I4 MUST add the bounded externally meaningful `v0.4.0` release content before final candidate freeze.

### 4.4 Publication pipeline

The current Docker workflow builds and publishes GHCR only on a **published GitHub Release**.

Therefore I4 SHALL publish and qualify an immutable release candidate before final GO so the actual release-triggered container pipeline is exercised.

The first planned tag is:

```text
v0.4.0-rc.1
```

If a candidate-changing blocker is found later, use `v0.4.0-rc.2`, `rc.3`, and so on. Existing RC tags remain immutable historical evidence.

---

## 5. Release Identity

The public identity of `v0.4.0` is:

> **Trusted Architecture Context for Agents**

The release SHALL communicate the bounded capability:

```text
AIP exposes deterministic architecture context
through exactly three read-only MCP tools.

Answers are:
    evidence-backed
    snapshot-bound
    observation-context-bound where runtime-sensitive
    explicitly qualified
    limitation-aware
    machine-readable
    reproducible for fixed inputs
```

The governing principle remains:

> **AIP may help agents reason about architecture, but an agent must never become the source of architectural truth.**

I4 SHALL NOT broaden this into complete architecture conformance, production-safe internet MCP exposure, historical snapshot storage, transitive reasoning, generic graph query, policy enforcement, or stable v1 contracts.

---

## 6. Fixed Scope Budget

I4 is release qualification, not a fourth product-development increment.

| Area | I4 limit |
|---|---|
| New public MCP tools | `0` |
| Public MCP tools after I4 | Exactly `3` |
| New service operations | `0` |
| New Canonical Model entities/relations | `0` |
| New discovery sources | `0` |
| New architecture algorithms | `0` |
| New qualification/status values | `0` |
| New transport | `0` |
| New snapshot model | `0` |
| New observation-context model | `0` |
| LLM dependency for correctness | `0` |
| Fresh Quarkus/Airflow executions | `0` by default |
| Planned initial RC | `v0.4.0-rc.1` |
| Final release | `v0.4.0` |
| Combined qualification record | `1` |

I4 SHALL deliver version/release metadata, exact-candidate qualification, RC publication, published RC qualification, explicit GO/NO-GO, final publication, published-artifact verification, and public status closure.

---

## 7. Explicit Non-Goals

I4 SHALL NOT implement:

```text
new MCP tools/resources/prompts/sessions
authentication or authorization
multi-tenancy
public-internet MCP hardening
generic Cypher or graph access
agent writes
new drift semantics or scoring
transitive dependency traversal
historical snapshots or snapshot diffing
new evidence/status/limitation types
Kubernetes discovery
gRPC/protobuf discovery
new adapters
new runtime-correlation semantics
new real-system ground truth
performance/SLO qualification
v0.9 contract freeze
v1.0 compatibility guarantees
```

A release blocker requiring one of these is a **NO-GO**, not permission to expand I4.

---

## 8. Release Identity and Candidate Terminology

I4 SHALL distinguish:

```text
source candidate
    exact Git commit intended for release

qualification evidence
    tests/evaluations/checks proving that candidate

published source
    immutable Git tag / GitHub source artifact

published container
    GHCR image produced by the release-triggered workflow
```

These identities are related but not interchangeable.

The release is qualified only when:

```text
RC tag -> exact candidate SHA
final v0.4.0 tag -> exact GO candidate SHA
RC image producer.build_revision -> exact candidate SHA
final image producer.build_revision -> exact GO candidate SHA
published package version -> 0.4.0
published producer.version -> 0.4.0
```

Terms:

```text
I3_CANDIDATE_SHA
    bbde691d5d317ae167394b9871e26c0b2e183b63

RELEASE_CANDIDATE_SHA
    literal commit produced by I4 candidate preparation

EVIDENCE_COMMIT_SHA
    optional later documentation/data-only commit recording completed qualification

FINAL_RELEASE_SHA
    RELEASE_CANDIDATE_SHA named by final GO
```

---

## 9. Candidate Freeze and Mutation Policy

Qualification applies only to the literal commit tested.

```text
qualified commit A != later commit B
```

The final `v0.4.0` tag SHALL resolve to the SHA named by final GO.

After candidate freeze, any change to the following creates a new candidate:

```text
production code
contracts/schemas
tests
evaluation code or fixtures
dependencies / lock file
configuration
Dockerfile
GitHub Actions workflows
executable demo/seed code
tracked release documentation intended to be inside the final tag
```

Tags SHALL NOT be moved or overwritten to hide candidate mutation.

Escalation:

```text
release blocker
    -> NO-GO for current candidate
    -> fix
    -> new candidate SHA
    -> new v0.4.0-rc.N
    -> repeat affected gates
    -> new GO / NO-GO
```

### 9.1 Evidence-only commits

A later evidence-only commit MAY advance `main` after candidate freeze to record candidate-bound results.

Allowed examples:

```text
candidate-bound evaluation result
combined GO/NO-GO record
status text recording completed checks
post-release verification evidence
public shipped-status closure
```

Such a commit MUST NOT modify executable code, schemas, evaluation logic/fixtures, tests, Docker/workflow/configuration, dependencies, or executable demo code.

Most importantly:

> **Once `main` contains evidence-only commits after the qualified candidate, release tags MUST be created from the explicit candidate SHA, never ambient `HEAD`.**

---

## 10. Frozen I3 Semantics

I4 SHALL preserve the I3 surface exactly.

### Tools

Exactly:

```text
get_architecture_drift
get_evidence
get_service_dependencies
```

in lexicographic `tools/list` order.

### Drift

For the same service/snapshot/context:

```text
drift.claims
=
dependency.claims filtered to:
    OBSERVED_ONLY
    NOT_OBSERVED_IN_WINDOW
```

`CONFIRMED` never appears in drift.

### Evidence

Every returned evidence reference resolves through `get_evidence` at the same snapshot or is represented by an explicit limitation/refusal.

### Read-only

```text
MCP graph writes = 0
```

### Hero path

For the frozen demo context:

```text
LegacyPricingService = OBSERVED_ONLY
unused-q = NOT_OBSERVED_IN_WINDOW
ProductService = CONFIRMED and excluded from drift
payment-q = CONFIRMED and excluded from drift
```

I4 verifies these facts; it does not reinterpret them.

---

## 11. Version and Package Metadata

Before release-candidate freeze:

```text
pyproject.toml
    [project].version = "0.4.0"

uv.lock
    root project version = "0.4.0"
```

The version update SHOULD NOT cause unrelated third-party dependency re-resolution.

Default permitted lock change:

```text
architecture-intelligence-platform 0.3.0 -> 0.4.0
```

Any third-party package/version/hash change SHALL be treated as dependency mutation and explicitly justified and requalified.

Historical specifications, changelog entries, and release-validation records retain historical version numbers.

A stale active `0.3.0` version is release-blocking even if MCP answers already advertise `producer.version = 0.4.0`.

---

## 12. Producer Identity Qualification

The exact candidate SHALL prove, through a production-wired MCP answer:

```text
producer.name = architecture-intelligence-platform
producer.version = 0.4.0
producer.build_revision = RELEASE_CANDIDATE_SHA
```

Local source qualification MAY resolve the revision via Git.

Container qualification SHALL resolve it through the workflow-provided `AIP_BUILD_REVISION`.

Release blockers:

```text
build_revision = "unknown"
build_revision != candidate
producer.version != 0.4.0
package version != 0.4.0
```

---

## 13. Frozen JSON Schemas

I4 SHALL preserve:

```text
schemas/architecture_intelligence/v0.4/architecture-answer.schema.json
schemas/architecture_intelligence/v0.4/drift-answer.schema.json
schemas/architecture_intelligence/v0.4/evidence-answer.schema.json
```

Candidate qualification SHALL run the existing schema-drift tests proving committed schemas equal generated schemas.

A schema content change relative to the I3-complete baseline is a release blocker unless it is an explicitly approved correction that reopens the affected earlier gate.

Record candidate hashes for all three schema files.

---

## 14. Public Documentation and Changelog

Before candidate freeze, these active surfaces SHALL agree on the bounded `v0.4.0` capability:

```text
README.md
ROADMAP.md
CHANGELOG.md
docs/mcp.md
docs/specifications/0.4.0/README.md
docs/specifications/0.4.0/specification.md
this I4 specification
draft release notes
```

Pre-publication wording SHALL distinguish capability completion from release publication.

`CHANGELOG.md` SHALL describe externally meaningful outcomes rather than PR numbers, including:

```text
Trusted Architecture Context for Agents
ArchitectureIntelligenceService
ArchitectureAnswer<T>
snapshot-bound current-state answers
explicit observation context
evidence/provenance drill-down
qualification and limitations
three read-only MCP tools
deterministic three-tool evaluation
frozen real-system-derived qualification
deterministic hero demo
no LLM required for tool correctness
```

It SHALL also state the important boundaries:

```text
direct dependencies only
no transitive query
no historical snapshots
no generic graph query
no writes
MCP local/trusted-network posture
pre-1.0 contracts may still change on minor releases
```

The final changelog entry SHALL be:

```text
## [0.4.0] - <actual release date>
```

---

## 15. Release Notes

I4 SHALL prepare final GitHub Release notes before GO.

They SHOULD contain:

```text
pre-1.0 status
Trusted Architecture Context for Agents
three MCP tools and their bounded scopes
candidate SHA
deterministic evaluation result
Quarkus/Airflow-derived qualification summary
hero finding: OrderService -> LegacyPricingService = OBSERVED_ONLY
read-only guarantee
Quick Start / MCP demo links
known limitations
security reporting
license
next roadmap step: v0.5 broader architecture discovery
```

They SHALL NOT claim production-safe public MCP exposure, complete architecture coverage, transitive dependencies, historical architecture state, stable v1 contracts, or agent-generated architecture as truth.

---

## 16. Clean-Checkout Source Qualification

The final source candidate SHALL be qualified from a fresh clone or isolated clean worktree.

Reference flow:

```bash
git clone https://github.com/michaelegner/architecture-intelligence-platform.git
cd architecture-intelligence-platform
git checkout <RELEASE_CANDIDATE_SHA>

test "$(git rev-parse HEAD)" = "<RELEASE_CANDIDATE_SHA>"
test -z "$(git status --porcelain)"

uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit -q
uv run pytest tests/integration -q
uv run python -m evaluation run
uv run python -m evaluation answers --candidate-sha <RELEASE_CANDIDATE_SHA>
uv run --with pip-audit pip-audit
```

Record:

```text
candidate SHA
Python version
uv version
OS / architecture
pyproject.toml hash
uv.lock hash
schema hashes
command lines and exit codes
unit/integration counts
relation-facts evaluation summary
architecture-answer evaluation summary
semantic run hashes
pip-audit result
```

Actual test counts are evidence, not permanent specification constants.

---

## 17. Deterministic Evaluation Qualification

Both evaluators SHALL remain green.

### Relation-facts evaluator

```bash
uv run python -m evaluation run
```

Expected semantic result:

```text
10/10 PASS
no missing supported facts
no unexpected supported facts
no forbidden facts
no wrong statuses
no evidence errors
```

### Architecture-answer evaluator

```bash
uv run python -m evaluation answers --candidate-sha <RELEASE_CANDIDATE_SHA>
```

Expected:

```text
schema_version = aip-evaluation-result/v2
suite = architecture-answers
result = PASS
run_count = 2
semantic_outputs_identical = true
summary.scenarios = 23
summary.failed = 0
```

Required live invariants:

```text
dependency_to_drift = PASS
drift_to_evidence = PASS
```

Externally qualified gates remain explicitly named rather than fabricated as evaluator-local PASS:

```text
service_to_mcp = QUALIFIED_EXTERNALLY
insufficient_evidence_qualification = QUALIFIED_EXTERNALLY
```

---

## 18. Candidate-Bound Evaluation Artifact

The candidate-bound architecture-answer report necessarily names the candidate it evaluates. Committing that newly generated report would itself create another Git SHA.

I4 SHALL avoid an infinite candidate/report loop:

```text
1. freeze RELEASE_CANDIDATE_SHA
2. clean-checkout that SHA
3. run evaluator with --candidate-sha RELEASE_CANDIDATE_SHA
4. capture generated JSON + SHA-256
5. verify candidate worktree otherwise clean
6. optionally commit the JSON later in an evidence-only commit
7. never move the release tag from RELEASE_CANDIDATE_SHA to that evidence commit
```

If committed later, the qualification record SHALL state explicitly that the report is evidence **about** the release candidate, not the source candidate itself.

---

## 19. Independent-Client and Hero Qualification

The exact candidate SHALL run the existing real HTTP independent-client integration path:

```text
real uvicorn listener
production app wiring
real Neo4j
no in-process ASGI shortcut

tools/list
get_service_dependencies
get_architecture_drift
get_evidence
advertised outputSchema validation
same-snapshot evidence drill-down
direct service == MCP structuredContent where required
graph writes = 0
no OPENAI_API_KEY required
```

I4 SHALL not create a second MCP test framework.

The documented hero demo SHALL also run twice from separate clean states. Compare complete semantic `structuredContent`, not only selected qualifications.

Required stable fields include:

```text
snapshot_id
model_revision
observation_context
claims
claim_id
qualification
coverage
evidence refs
limitations
evidence records
sample_trace_ids
first_seen
last_seen
```

Required hero result:

```text
LegacyPricingService = OBSERVED_ONLY
unused-q = NOT_OBSERVED_IN_WINDOW
ProductService not in drift
payment-q not in drift
```

---

## 20. Frozen Real-System-Derived Qualification

I4 SHALL reuse the deterministic I3 derived fixtures. No fresh heavy Quarkus/Airflow execution is required by default.

Required frozen source blob identities remain:

```text
Quarkus:
    656446cd79c4cefec8f1ac0124fbb6b34e993704

Airflow:
    8891289baa9facaf70a0cc0c6b9b2e0fdd9c838a
```

The exact-candidate architecture-answer evaluator SHALL report both systems PASS.

I4 SHALL preserve:

```text
Quarkus:
    supported confirmed dependencies
    empty drift for the qualified service
    evidence resolves

Airflow:
    zero invented outgoing dependencies for airflow-apiserver
    unsupported/unresolved/insufficient findings remain visible
```

If I4 changes architecture/evaluation semantics or the frozen fixture derivation, the relevant I3 gate reopens.

---

## 21. CI, CodeQL, Dependency, and Source Container Gates

The exact `RELEASE_CANDIDATE_SHA` SHALL have successful candidate-bound GitHub Actions results.

Record:

```text
CI workflow run ID
CodeQL workflow run ID
head SHA
job names
job conclusions
pip-audit result
```

Do not infer candidate success from a later PR-head badge.

Before publishing an RC, also build the exact source candidate locally with:

```text
AIP_BUILD_REVISION = RELEASE_CANDIDATE_SHA
```

Verify:

```text
image builds
container runs non-root
GET /health succeeds
GET /health/neo4j succeeds
POST /api/import succeeds
tools/list returns exactly three tools
producer.version = 0.4.0
producer.build_revision = RELEASE_CANDIDATE_SHA
```

---

## 22. RC Publication

After source qualification succeeds, publish an immutable prerelease.

Initial planned tag:

```text
v0.4.0-rc.1
```

The tag SHALL point explicitly to `RELEASE_CANDIDATE_SHA`, not current `main`.

Reference sequence:

```bash
git tag v0.4.0-rc.1 <RELEASE_CANDIDATE_SHA>
git push origin v0.4.0-rc.1

gh release create v0.4.0-rc.1 \
  --verify-tag \
  --prerelease \
  --title "v0.4.0-rc.1" \
  --notes-file <prepared-rc-notes>
```

Verify before publication:

```bash
git rev-parse v0.4.0-rc.1^{commit}
```

Existing RC tags remain immutable. A candidate-changing fix gets a new RC number.

---

## 23. Release-Triggered RC Image Qualification

Publishing the RC SHALL trigger the Docker workflow exactly once.

Verify:

```text
event = release
release tag = v0.4.0-rc.N
source SHA corresponds to RELEASE_CANDIDATE_SHA
build, scan, and push = success
```

Record:

```text
RC tag
candidate SHA
workflow run ID
GHCR image name
immutable image digest
platform(s)
container user
```

The RC image SHALL expose through a real MCP answer:

```text
producer.version = 0.4.0
producer.build_revision = RELEASE_CANDIDATE_SHA
```

A published image reporting `unknown` or a different SHA is release-blocking.

The image SHALL also be publicly/independently pullable without relying on maintainer credentials.

---

## 24. Published RC MCP Golden Path

The published RC image SHALL complete one external MCP golden path over ordinary HTTP/JSON-RPC, with no `app.*` imports in the client.

Required path:

```text
1. start published RC image with clean Neo4j
2. GET /health
3. GET /health/neo4j
4. POST /api/import
5. seed deterministic frozen telemetry
6. tools/list
7. get_service_dependencies
8. get_architecture_drift
9. get_evidence using the same snapshot
10. inspect producer version/build revision
```

Tool discovery SHALL return exactly:

```text
get_architecture_drift
get_evidence
get_service_dependencies
```

Drift SHALL include:

```text
LegacyPricingService = OBSERVED_ONLY
unused-q = NOT_OBSERVED_IN_WINDOW
```

and exclude confirmed `ProductService` / `payment-q` claims.

Every top-level drift evidence reference SHALL resolve via `get_evidence` at the exact same snapshot.

The smoke SHOULD reuse the committed deterministic hero seed semantics: fixed timestamp, fixed trace/span IDs, fixed duration jitter, fixed observation window, clean graph state.

---

## 25. Trivy / Container Security Review

The Docker workflow's Trivy step is intentionally non-blocking at process exit.

Therefore:

```text
workflow success != automatic security approval
```

I4 SHALL review the RC scan and record:

```text
workflow run
Trivy step status
SARIF upload status
CRITICAL/HIGH findings
release-blocking disposition
```

Required before GO:

```text
known critical release-blocking security findings = 0
unreviewed release-blocking image findings = 0
```

Accepted base-image findings require explicit disposition.

---

## 26. Release Blockers

Any of the following blocks `v0.4.0`.

### Semantic integrity

```text
unexpected architecture claim
wrong qualification
dropped limitation
broken evidence reference
snapshot/context substitution
guessed unresolved identity
non-observation represented as absence
MCP/direct-service semantic disagreement
```

### Scope and safety

```text
MCP adapter graph logic/direct graph access
generic query exposure
write-capable tool
LLM required for correctness
fourth public tool
second transport
new unqualified model/discovery semantics
```

### Determinism and usability

```text
derived expected ground truth
evaluation mismatch
repeat-run semantic difference
independent-client failure
evidence drill-down failure
hero clean-state failure
published RC MCP golden-path failure
```

### Release quality

```text
package/lock version mismatch
candidate changes after qualification
CI/CodeQL/pip-audit failure
published image provenance mismatch
published RC not publicly pullable
published RC MCP smoke failure
unreviewed critical security issue
```

Targets:

```text
Incorrect supported architecture claims = 0
Unexpected tool claims = 0
Broken evidence references = 0
Write-capable MCP operations = 0
Release blockers = 0
```

---

## 27. Combined GO / NO-GO Record

I4 SHALL maintain one combined release qualification record:

```text
docs/release-validation/v0.4.0-go-no-go.md
```

It SHALL contain at least:

```text
release identity
entry/I3 handoff identities
release candidate SHA
version/lock audit
schema hashes
clean-checkout results
test counts
both evaluator results
architecture-answer report hash
cross-tool invariants
real-system-derived qualification
hero two-run result
CI / CodeQL run IDs
pip-audit result
RC tag -> candidate mapping
RC Docker workflow run
RC image digest
public pull result
published RC MCP smoke
producer version/build revision
Trivy review
known limitations
blocker table
GO / NO-GO
```

After final publication, append final published-artifact verification to the same record rather than creating another large dossier.

Unexecuted mandatory checks are `NOT_EXECUTED`, never `PASS`.

---

## 28. GO Decision

Final GO is allowed only when:

```text
candidate frozen
package version = 0.4.0
uv.lock root version = 0.4.0
schemas qualified
unit/integration tests PASS
relation-facts evaluator PASS
architecture-answer evaluator PASS
two answer passes identical
cross-tool invariants qualified
Quarkus/Airflow-derived qualification PASS
hero deterministic
CI PASS
CodeQL PASS
pip-audit PASS
RC tag -> exact candidate
RC Docker workflow PASS
RC image publicly pullable
RC image non-root
RC producer build revision = exact candidate
published RC MCP golden path PASS
Trivy reviewed
release blockers = 0
```

Successful GO SHALL be equivalent in meaning to:

```text
GO — At <RELEASE_CANDIDATE_SHA>, AIP v0.4.0 is qualified as Trusted Architecture Context for Agents.
The exact candidate exposes exactly three read-only MCP 2026-07-28 tools through
ArchitectureIntelligenceService; answers are snapshot-bound, evidence-backed and explicitly
qualified; deterministic synthetic and frozen real-system-derived qualification passes; the hero
demo is reproducible; CI, CodeQL and dependency audit pass; and the release-triggered v0.4.0-rc.N
GHCR image is publicly pullable and completes the independent dependency/drift/evidence MCP golden
path with producer.version=0.4.0 and producer.build_revision=<RELEASE_CANDIDATE_SHA>. Release
blockers = 0.
```

or:

```text
NO-GO — v0.4.0 publication is blocked by <named blocker>; return to <named task>.
```

GO SHALL name the full 40-character SHA.

---

## 29. Final Publication

After GO, create the final tag explicitly at the GO candidate:

```bash
git tag v0.4.0 <RELEASE_CANDIDATE_SHA>
git push origin v0.4.0
```

Verify:

```bash
git rev-parse v0.4.0^{commit}
```

If `main` has advanced to evidence-only commits, `v0.4.0` MUST NOT point to ambient `main HEAD` unless it literally equals the GO candidate and that equality was checked.

Publish the GitHub Release from the immutable tag.

The final release SHALL trigger the Docker workflow exactly once.

Because the current Docker build uses moving base-image references, the final image digest is **not required** to equal the RC digest. What is required is the same exact release source SHA, correct embedded build revision, successful final artifact smoke, and reviewed security scan.

---

## 30. Final Published-Artifact Verification

After publication, independently verify both source and image.

### Tagged source

```bash
git clone https://github.com/michaelegner/architecture-intelligence-platform.git
cd architecture-intelligence-platform
git checkout v0.4.0

test "$(git rev-parse HEAD)" = "<GO_SHA>"
```

Verify:

```text
package version = 0.4.0
uv.lock root version = 0.4.0
three v0.4 schemas present
docs/mcp.md present
hero demo present
exactly three MCP tools registered
```

### Final image

Pull publicly:

```bash
docker pull ghcr.io/michaelegner/architecture-intelligence-platform:v0.4.0
```

Record:

```text
final digest
platform
container user
release workflow run ID
```

Immediately after final publication, the current workflow is expected to make:

```text
digest(v0.4.0) == digest(latest)
```

Verify rather than assume it.

### Final MCP smoke

Repeat the published-image golden path against the final tag:

```text
health
Neo4j health
import
frozen telemetry seed
tools/list
get_service_dependencies
get_architecture_drift
get_evidence
same-snapshot evidence drill-down
```

Required:

```text
producer.version = 0.4.0
producer.build_revision = GO SHA
exactly three tools
LegacyPricingService = OBSERVED_ONLY
unused-q = NOT_OBSERVED_IN_WINDOW
missing hero evidence refs = 0
```

This final smoke is mandatory even when the RC image passed.

---

## 31. Post-Release Failure Policy

Published artifacts are immutable historical evidence.

I4 SHALL NOT repair a failed final release by moving or overwriting `v0.4.0`.

If post-release verification finds a material defect:

```text
record post-release verification = FAIL
do not claim v0.4.0 fully qualified
open a release blocker
fix on a new commit
publish an appropriate follow-up release (normally v0.4.1)
```

Do not rewrite history to conceal a failed artifact.

---

## 32. Public Status Closure

After successful final source/image verification, update active `main` documentation.

At minimum:

```text
ROADMAP.md
    v0.4 -> shipped

docs/specifications/0.4.0/README.md
    I4 -> GO / shipped
    exact release candidate and final tag identity

CHANGELOG.md
    final v0.4.0 links/status

docs/release-validation/v0.4.0-go-no-go.md
    final publication/verification appended
```

This closure commit is release evidence and project-status documentation. It MUST NOT retroactively become the `v0.4.0` source tag.

---

## 33. Roadmap Boundary After `v0.4.0`

I4 SHALL preserve the established sequence:

```text
v0.4
    trusted architecture context for agents
        |
        v
v0.5
    broader architecture discovery
        |
        v
v0.9
    contract freeze / production qualification
        |
        v
v1.0
    stable platform
```

The immediate next planned release remains `v0.5 — Broader Architecture Discovery`, including candidates such as Kubernetes discovery, additional source adapters, and deeper runtime discovery.

Those are not I4 work.

---

## 34. No-Substitution Rules

The following substitutions are forbidden:

```text
local Docker image
    != published RC/final image

branch head
    != exact candidate SHA

PR checks
    != candidate-bound checks

RC image
    != final image

I3 evaluation artifact
    != final-candidate evaluator run

selected hero fields equal
    != full structuredContent deterministic

GitHub Release text says tag X
    != dereferenced tag X

workflow success
    != Trivy finding review

source diff looks harmless
    != required reopened qualification
```

These are release-integrity requirements, not ceremony.

---

## 35. Suggested Delivery Split

I4 SHOULD be implemented as four small increments.

### I4.1 — Candidate Preparation and Freeze

Deliver:

```text
version 0.4.0 in pyproject.toml
uv.lock root version 0.4.0
final changelog content
release-notes draft
README/ROADMAP/spec-index candidate consistency
schema freeze audit
exact candidate SHA
```

Exit:

> A literal source commit contains the exact code, contracts, package identity, and public release content intended for `v0.4.0`.

Suggested branch:

```text
release/v0.4.0-candidate
```

### I4.2 — Exact-Candidate and RC Qualification

Deliver:

```text
clean-checkout source qualification
unit/integration tests
both evaluators
candidate-bound machine-readable evidence
hero demo twice
CI/CodeQL/pip-audit
local container smoke
v0.4.0-rc.N
published RC image
public pull
published RC MCP golden path
Trivy review
combined GO/NO-GO record
```

Exit:

> The exact candidate and the actual release-triggered RC artifact both satisfy the release contract.

### I4.3 — GO and Final Publication

Deliver:

```text
release blocker assessment
explicit GO
v0.4.0 tag at exact GO candidate
GitHub Release
final release-triggered Docker workflow
```

Exit:

> The immutable final release points to the exact candidate that received GO.

### I4.4 — Published-Artifact Verification and Public Closure

Deliver:

```text
final tagged-source verification
final GHCR public pull
final image digest
final MCP dependency/drift/evidence smoke
producer build-revision verification
final Trivy/security review
latest-tag verification
GO record post-release section
ROADMAP/status closure
```

Exit:

> A new external user can consume the published source/image and complete the documented MCP golden path.

---

## 36. Candidate-Change Impact Matrix

| Change | New candidate? | Minimum reopened gates |
|---|---:|---|
| `app/**` | Yes | full source/evaluation/integration/RC image |
| `schemas/**` | Yes | schema/evaluation/MCP/RC image |
| evaluation code/fixtures | Yes | full affected evaluation |
| tests | Yes | source qualification + affected gate |
| `pyproject.toml` / `uv.lock` | Yes | locked install, tests, evaluations, pip-audit, container/RC |
| `Dockerfile` | Yes | local/RC image + security + affected tests |
| workflow files | Yes | workflow-specific qualification + new RC |
| `config*.yaml` | Yes | config/integration/container/MCP |
| executable demo/seed | Yes | hero determinism + container/RC smoke |
| release docs intended inside tag | Yes | doc/link audit + new source identity |
| evidence-only GO record after freeze | No, if not tagged | verify explicit tag SHA |
| post-release shipped-status docs | No, if not tagged | link/status audit |

When uncertain, treat the change as candidate-changing.

---

## 37. Definition of Done

### Candidate

- [ ] Active project version is `0.4.0`.
- [ ] `uv.lock` is consistent.
- [ ] No unintended dependency re-resolution occurred.
- [ ] Candidate SHA is explicit.
- [ ] Candidate tree contains final intended release content and is clean.

### Contracts and semantics

- [ ] Exactly three MCP tools exist.
- [ ] No public contract changed in I4.
- [ ] Three committed JSON schemas match generated schemas.
- [ ] `ArchitectureIntelligenceService` remains the semantic entry point.
- [ ] MCP adapters remain read-only.
- [ ] No generic graph access exists.
- [ ] Producer identity is `0.4.0` + exact candidate revision.

### Deterministic qualification

- [ ] Relation-facts evaluator passes.
- [ ] Architecture-answer evaluator passes all 23 scenarios.
- [ ] Two full answer passes are semantically identical.
- [ ] Dependency→drift and drift→evidence invariants pass.
- [ ] Service→MCP parity remains qualified.
- [ ] Insufficient-evidence behavior remains qualified.
- [ ] Frozen Quarkus/Airflow-derived scenarios pass.
- [ ] Hero demo produces byte-identical full semantic responses twice from clean state.

### Candidate quality

- [ ] Unit/integration tests pass.
- [ ] Ruff lint/format checks pass.
- [ ] CI passes on exact candidate.
- [ ] CodeQL passes on exact candidate.
- [ ] pip-audit passes on exact candidate.
- [ ] Local candidate image builds/runs non-root.

### RC artifact

- [ ] `v0.4.0-rc.N` points to exact candidate.
- [ ] RC Docker workflow succeeds exactly once.
- [ ] RC image digest recorded.
- [ ] RC image publicly pullable and non-root.
- [ ] RC producer version/build revision matches candidate.
- [ ] RC `tools/list` returns exactly three tools.
- [ ] RC dependency/drift/evidence golden path succeeds.
- [ ] RC Trivy result reviewed.
- [ ] Release blockers = `0`.

### Final publication

- [ ] Explicit GO names exact candidate.
- [ ] `v0.4.0` tag points to exact GO candidate.
- [ ] Final GitHub Release is published from that tag.
- [ ] Final Docker workflow succeeds.

### Published artifact verification

- [ ] Tagged source resolves to GO SHA and package version `0.4.0`.
- [ ] Final GHCR image publicly pullable; digest recorded; runs non-root.
- [ ] Final MCP producer revision equals GO SHA.
- [ ] Final three-tool golden path and same-snapshot evidence drill-down succeed.
- [ ] `latest` resolves to the final release image.
- [ ] Final security scan reviewed.
- [ ] Combined release record complete.
- [ ] Public roadmap/status says `v0.4` shipped.
- [ ] Post-release blockers = `0`.

---

## 38. Final Release Statement

After successful post-release verification, public closure SHALL be equivalent in meaning to:

```text
SHIPPED — v0.4.0 at <GO_SHA> delivers Trusted Architecture Context for Agents through exactly three
read-only MCP 2026-07-28 tools. The published source and GHCR image identify the same immutable
source revision, expose snapshot-bound evidence-qualified architecture answers, and complete the
independent dependency/drift/evidence golden path. Deterministic synthetic and frozen real-system-
derived qualification passes, the hero demo is reproducible from clean state, and release blockers
and post-release blockers are both 0.
```

---

## 39. Expected Repository Touch Points

Likely I4.1 candidate-preparation changes:

```text
pyproject.toml
uv.lock
CHANGELOG.md
ROADMAP.md
README.md
docs/specifications/0.4.0/README.md
possibly docs/release-validation/v0.4.0-release-notes.md
```

Likely I4.2 evidence-only changes after freeze:

```text
docs/release-validation/v0.4.0-go-no-go.md
evaluation/architecture_answers/results/architecture-answers-evaluation-result.json
```

Likely I4.4 post-release status changes:

```text
ROADMAP.md
docs/specifications/0.4.0/README.md
CHANGELOG.md
docs/release-validation/v0.4.0-go-no-go.md
```

Production `app/**`, schemas, tests, evaluation logic, and workflow code SHOULD remain untouched unless a release blocker is discovered.

---

## 40. References

- `ROADMAP.md`
- `CHANGELOG.md`
- `docs/specifications/0.4.0/specification.md`
- `docs/specifications/0.4.0/README.md`
- `docs/specifications/0.4.0/i1-service-contract-and-dependency-vertical-slice.md`
- `docs/specifications/0.4.0/i2-mcp-vertical-slice-and-evidence-drill-down.md`
- `docs/specifications/0.4.0/i3-drift-capability-and-deterministic-qualification.md`
- `docs/mcp.md`
- `examples/runtime-demo/hero-demo.md`
- `evaluation/README.md`
- `docs/specifications/0.3.0/i5-release-qualification.md`
- `docs/release-validation/v0.3.0-go-no-go.md`
- `docs/release-validation/v0.3.0-post-release-verification.md`
- `.github/workflows/ci.yml`
- `.github/workflows/codeql.yml`
- `.github/workflows/docker.yml`
- `Dockerfile`

---

## 41. Summary

I4 is deliberately a release-integrity increment. It does not make AIP smarter.

It proves that the architecture intelligence already qualified in I1–I3 is the exact architecture intelligence an external user receives from the published `v0.4.0` artifact.

The release succeeds when all of the following are simultaneously true:

```text
one exact source candidate
version = 0.4.0
exactly three read-only MCP tools
deterministic qualified architecture answers
snapshot-bound evidence drill-down
no architecture writes
synthetic evaluation PASS
frozen real-system-derived qualification PASS
hero demo reproducible
candidate CI/security gates PASS
published RC artifact PASS
explicit GO
v0.4.0 tag -> exact GO SHA
final published source PASS
final published GHCR image PASS
independent MCP dependency/drift/evidence golden path PASS
release blockers = 0
post-release blockers = 0
```

That is the complete `v0.4.0` release boundary.
