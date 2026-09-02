# AIP v0.3.0 I5 Specification — Release Qualification

**Status:** Draft 1 — self-contained implementation contract  
**Target release:** `v0.3.0`  
**Iteration:** I5 — Release Qualification  
**Entry baseline:** `v0.3.0-rc.1` after I4 is complete, tagged, and documented  
**Parent release specification:** [`specification.md`](specification.md)  
**Preceding iteration:** [`i4-cross-system-model-hardening.md`](i4-cross-system-model-hardening.md)

---

## 1. Purpose

I1–I4 proved that AIP's supported architecture claims remain materially correct against two
independently authored real systems and that no fundamental Canonical Model redesign is required
before v0.4.

I5 does **not** add architecture intelligence and does **not** reopen model hardening by default.

Its purpose is to qualify the exact source state and public artifacts intended for `v0.3.0`, publish
the release, and verify what an external user can actually consume.

The intended transition is:

```text
I4
real-system candidate qualified
        |
        v
v0.3.0-rc.N
        |
        v
I5
source + artifact qualification
        |
        v
GO / NO-GO
        |
        v
v0.3.0
        |
        v
post-release verification
```

The central I5 rule is:

> **Qualify the exact release that will actually be shipped, then verify the artifacts that were
> actually shipped.**

A green development checkout, an earlier real-system run, or a source-diff equivalence argument is
not sufficient on its own.

---

## 2. Normative Language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD
NOT**, and **MAY** are normative.

Where this specification cites evidence from I4, the cited revision and artifact identity are part of
the requirement. A moving branch name is not an evidence identity.

---

## 3. Release Identity

The release identity remains the one defined by the parent v0.3 specification:

```text
v0.1
architecture intelligence exists

v0.2
architecture intelligence is reproducibly verified

v0.3
architecture intelligence survives real systems
```

The release SHALL communicate that AIP was tested against:

```text
Quarkus Super Heroes
    external reference architecture

Apache Airflow
    real-world OSS software
```

and that the result is deliberately bounded:

```text
supported claims are materially correct
unsupported mechanisms remain explicit
unresolved identity is not guessed
non-observation is not treated as absence
evidence and provenance remain traceable
```

I5 SHALL NOT broaden this identity into complete architecture conformance, production qualification,
or stable public contracts.

---

## 4. Entry Criteria

I5 implementation MUST NOT begin until I4 has completed successfully.

At entry, all of the following SHALL be true:

```text
I4.1-I4.5 complete
v0.3.0-rc.1 exists
v0.3.0-rc.1 resolves to the I4-approvedapproved candidate
I4 cross-system report committed
I4 Definition of Done satisfied
Quarkus and Airflow final-candidate revalidation evidence committed
I4 finding ledger and decision records final
canonical-redesign gate = NO
critical semantic errors = 0
I4 release blockers = 0
v0.2 deterministic evaluation = 10/10 PASS
CI, CodeQL, and dependency audit green at the I4 candidate
public roadmap/status surfaces agree that I4 is complete and I5 is next
RC release-note documentation links resolve
```

The initial I4 handoff identity is:

```text
RC tag:             v0.3.0-rc.1
I4 candidate SHA:   9f95d48046ab1942bb1a77c9a3a887a542120b98
```

I5 SHALL independently verify this mapping. The tag name and a textual claim are not substitutes for
dereferencing the tag.

If any entry condition is false, I5 records `NO-GO` or returns to the named I4 closure task before
proceeding.

---

## 5. Scope

I5 SHALL deliver:

1. Candidate and release-identity audit.
2. Version and lock-file consistency.
3. Final public documentation and changelog.
4. Draft final release notes.
5. Fresh-checkout source qualification.
6. Deterministic synthetic evaluation.
7. Audit of the candidate-bound Quarkus and Airflow evidence.
8. Fresh Quick Start qualification.
9. CI, CodeQL, dependency, and security qualification.
10. Explicit GO/NO-GO bound to one literal commit.
11. Immutable `v0.3.0` tag and GitHub Release.
12. GHCR and tagged-source post-release verification.
13. Post-release evidence and public status closure.

I5 MAY fix a release blocker, but every fix follows the candidate-mutation policy in §9.

---

## 6. Non-Goals

The following are outside I5:

```text
new canonical entities or relations
new architecture analyses
new discovery adapters
new runtime-correlation semantics
new evidence or status semantics
new real-system ground truth
broader Quarkus or Airflow scope
messaging-model redesign
database dependency modeling
gRPC/protobuf discovery
Kubernetes discovery
ArchitectureIntelligenceService implementation
MCP tools
agent write capabilities
GraphRAG
policy engine
performance or production qualification
v1.0 contract freeze
```

The v0.4 roadmap update in this iteration is planning context, not a v0.4 implementation contract.

---

## 7. I4 Handoff Inputs

I5 receives the following immutable or revision-bound inputs from I4:

```text
exact candidate SHA and dependency-lock identity
v0.3.0-rc.1 tag identity
Quarkus and Airflow upstream/profile/image/instrumentation identities
four I4.4 revalidation captures and comparator reports
artifact and report SHA-256 values
cross-system finding ledger
decision records and final dispositions
regression map
known limitations
canonical-redesign gate answer
I4 GO/NO-GO record
updated roadmap and public project status
```

Primary evidence locations:

- [`docs/real-world-validation/cross-system/report.md`](../../real-world-validation/cross-system/report.md)
- [`docs/real-world-validation/cross-system/definition-of-done.md`](../../real-world-validation/cross-system/definition-of-done.md)
- [`docs/real-world-validation/cross-system/revalidation.md`](../../real-world-validation/cross-system/revalidation.md)
- [`docs/real-world-validation/cross-system/finding-ledger.md`](../../real-world-validation/cross-system/finding-ledger.md)
- [`docs/real-world-validation/cross-system/regression-map.md`](../../real-world-validation/cross-system/regression-map.md)

I5 SHALL cite exact commits and hashes in its evidence record rather than copying identity blocks
without provenance.

---

## 8. Qualification Principles

### 8.1 Qualification, Not Development

I5 SHALL prefer:

```text
audit
verify
document
fix release blockers
publish
verify publication
```

over:

```text
extend
redesign
generalize
experiment
```

New feature ideas are deferred.

### 8.2 Source and Artifact Qualification Are Distinct

I5 SHALL distinguish:

```text
source qualification
    exact commit
    locked dependencies
    lint/tests/evaluation
    Quick Start

real-system evidence qualification
    exact candidate binding
    frozen profiles and ground truth
    capture/report hashes
    deterministic semantic results

published-artifact qualification
    immutable tag/release
    release-triggered workflow
    GHCR digest
    anonymous pull
    non-root and health/import smoke
    tagged-source verification
```

Passing one layer does not prove the others.

### 8.3 No Hidden Maintainer State

Mandatory procedures SHALL work from clean state without:

```text
uncommitted files
maintainer-local graph state
an existing Neo4j database
private source artifacts
private customer data
manual graph repair
manual Cypher mutation
an OPENAI_API_KEY for deterministic evaluation
cached registry credentials for the anonymous-pull check
```

### 8.4 Evidence Before Assertion

Every release claim SHALL name evidence. Examples:

```text
"tag points to candidate"
    -> dereferenced tag SHA

"CI green"
    -> workflow run IDs + candidate SHA

"real-system results unchanged"
    -> candidate-bound artifact/report hashes

"published image works"
    -> release tag + digest + pull/smoke results
```

Unexecuted checks SHALL be recorded as `NOT_EXECUTED`, never `PASS`.

---

## 9. Candidate Freeze and Mutation Policy

A qualification result applies only to the literal commit tested.

```text
qualified commit A != later commit B
```

The final `v0.3.0` tag SHALL resolve to the commit named by the final GO decision.

After candidate freeze:

- documentation-only evidence committed after the candidate MAY live on `main` without changing the
  executable candidate;
- a release-note edit on GitHub MAY be corrected without moving a source tag;
- any tracked change included in the final source tag creates a different candidate;
- tags SHALL NOT be moved or overwritten to hide a candidate change.

If production code, validation code, dependency resolution, configuration, a real-system profile,
ground truth, or comparator changes, all affected I4 gates SHALL reopen.

A source diff, content-equivalence claim, or statement that a change is “only metadata” SHALL NOT
substitute for any candidate-bound run required by the reopened gate.

The escalation path is:

```text
candidate-changing defect
        |
        v
NO-GO
        |
        v
fix on a new commit
        |
        v
new RC tag
        |
        v
repeat affected qualification
        |
        v
new GO / NO-GO
```

The existing `v0.3.0-rc.1` tag remains immutable even if a later RC is required.

---

## 10. Version and Package Metadata

The final source candidate SHALL identify itself consistently as `0.3.0`.

At minimum:

```text
pyproject.toml
    [project].version = "0.3.0"

uv.lock
    root-project version consistent with pyproject.toml
    dependency resolution unchanged unless explicitly justified
```

Active current-version metadata SHALL be `0.3.0`. Historical changelog entries, old specifications,
and prior release-validation records SHALL retain their historical versions.

A package-version mismatch is release-blocking even if only GitHub and GHCR artifacts are published:
the source archive and installed project metadata are public release artifacts.

### 10.1 Current Entry Observation

At specification authoring time, `v0.3.0-rc.1` resolves to the I4 candidate but its
`pyproject.toml` still declares:

```toml
version = "0.2.0"
```

I5 MUST resolve this before final GO. Updating active version metadata changes the source candidate;
it SHALL therefore produce a new candidate and new RC rather than silently promoting the existing
`rc.1` commit as `v0.3.0`.

Because I4's real-system qualification is explicitly literal-candidate-bound, the final candidate
must receive the I4.4 evidence required by the reopened candidate gate. The implementation SHALL not
replace those runs with a source-diff argument.

---

## 11. Semantic Freeze

I5 SHALL NOT intentionally change:

```text
Canonical Model semantics
relation type or direction
identity-resolution behavior
runtime status classification
evidence/provenance preservation
observation-window semantics
coverage qualification
real-system supported scope
comparison classifications
ground-truth expectations
```

A semantic defect discovered during I5 is release-blocking.

Required response:

```text
NO-GO
fix
deterministic regression
affected I4 decision reopened
synthetic and real-system revalidation
new RC
full I5 requalification
```

No known semantic defect may be deferred merely to preserve the release schedule.

---

## 12. Public Documentation

Before final GO, the following active surfaces SHALL agree:

```text
README.md
ROADMAP.md
CHANGELOG.md
docs/specifications/0.3.0/README.md
docs/real-world-validation/cross-system/report.md
GitHub RC release notes
draft v0.3.0 release notes
```

They SHALL distinguish:

```text
I4 complete
I5 in progress / qualified
v0.3.0 not shipped
```

Before publication, none may claim `v0.3.0` is shipped.

After publication, `main` SHALL be updated to distinguish the immutable released tag from later
development.

Documentation links in GitHub Releases SHALL resolve. Where the linked evidence was committed after
the executable candidate, use an immutable documentation commit permalink rather than a tag-scoped
URL to a file absent from that tag.

---

## 13. ROADMAP and v0.4 Planning Baseline

I5 SHALL preserve the release sequence:

```text
v0.3 validation and hardening
  -> v0.4 architecture-intelligence tools
  -> v0.5 broader discovery
  -> v0.9 contract freeze and production qualification
  -> v1.0 stable platform
```

The v0.4 roadmap goal is:

> **Trusted Architecture Context for Agents**

Its planning scope includes:

```text
ArchitectureIntelligenceService
structured evidence-backed result contracts
snapshot and observation-context binding
evidence and provenance linkage
qualification of architectural claims
read-only MCP tools
deterministic tool evaluation
```

The governing principle is:

> **AIP may help agents reason about architecture, but an agent must never become the source of
> architectural truth.**

I5 SHALL record this direction without implementing it or freezing its public contract.

---

## 14. CHANGELOG

Before final publication, `CHANGELOG.md` SHALL contain the complete v0.3 content under
`[Unreleased]`.

It SHOULD describe externally meaningful outcomes:

- independent real-system validation methodology;
- Quarkus Super Heroes and Apache Airflow qualification;
- deterministic supported-scope comparison;
- cross-system finding dispositions;
- zero material `INCORRECT_SUPPORTED` findings;
- no production semantic changes justified by the evidence;
- explicit unsupported, unresolved, and insufficient-evidence boundaries;
- final-candidate repeatability;
- known limitations.

It SHALL describe product evidence and externally relevant behavior, not merely PR numbers.

At publication, the entry SHALL become:

```text
## [0.3.0] - <actual release date>
```

with comparison links updated consistently if the changelog uses them.

---

## 15. Release Notes

I5 SHALL prepare final GitHub Release notes before publication.

They SHOULD contain:

```text
pre-1.0 status
what v0.3 proves
candidate identity
Quarkus result summary
Airflow result summary
cross-system hardening outcome
deterministic evaluation result
how to run AIP / Quick Start
known limitations
documentation links
security reporting link
license
what is next: Trusted Architecture Context for Agents
```

The notes SHALL NOT claim:

```text
complete architecture conformance
all protocols supported
complete runtime coverage
formal proof of correctness
absence of a relation from non-observation
production-grade qualification
stable 1.0 contracts
agent-generated architecture as truth
```

All report and roadmap links SHALL resolve and SHOULD use immutable documentation commit permalinks.

---

## 16. Clean-Checkout Source Qualification

I5 SHALL qualify the final candidate from a fresh clone or isolated worktree with no inherited
development state.

Reference commands:

```bash
git clone https://github.com/michaelegner/architecture-intelligence-platform.git
cd architecture-intelligence-platform
git checkout <final-candidate-sha>

uv sync --locked

uv run ruff check .
uv run ruff format --check .

uv run pytest tests/unit -q
uv run pytest tests/integration -q
uv run python -m evaluation run
uv run --with pip-audit pip-audit
```

Record:

```text
candidate SHA
Python and uv versions
OS/architecture
dependency-lock SHA-256
command lines
exit codes
unit and integration counts
evaluation counters
pip-audit result
start/end timestamps
```

Actual test counts SHALL be recorded but are not permanent release-contract constants.

---

## 17. Deterministic Evaluation Qualification

Run the complete v0.2 evaluator at least twice against clean ephemeral state.

Required result for each run:

```text
Scenarios: 10
Passed: 10
Failed: 0
Missing facts: 0
Unexpected facts: 0
Forbidden facts: 0
Wrong statuses: 0
Evidence errors: 0
RESULT: PASS
```

Required repeatability:

```text
same candidate
same scenarios
same scenario order
same classifications
same mismatch order
same counters
same exit code
```

A byte-identical stdout comparison SHOULD be used after normalizing only fields already documented as
non-semantic and nondeterministic. Any normalization SHALL be disclosed.

Evaluation SHALL work without an LLM API key.

---

## 18. Real-System Evidence Gate

I5 SHALL verify that the final candidate is the candidate bound by the qualifying Quarkus and
Airflow evidence.

### 18.1 Candidate Unchanged

If the final candidate is literally the I4-qualified commit, I5 SHALL NOT repeat the four heavy
real-system runs merely to duplicate I4.4.

Instead it SHALL audit and record:

```text
final candidate SHA == I4.4 candidate SHA
profile/ground-truth/comparator revisions unchanged
dependency-lock identity unchanged
artifact and report hashes resolve
both systems have at least two qualifying runs
semantic counts match the frozen baselines
no I4 finding or limitation was silently removed
```

### 18.2 Candidate Changed

If the final candidate differs, apply I4 §20 and the candidate-mutation policy in §9.

At minimum, the affected real-system runs SHALL be repeated against the literal new candidate. A
package-version correction changes the public source and built artifact identity; under the current
strict no-substitution policy, the final candidate SHALL receive fresh Quarkus and Airflow
revalidation rather than inherit runs bound to `9f95d48`.

Expected unchanged semantic baselines, unless a separately approved semantic correction reopens I4:

| System | Correct | Unsupported | Unresolved | Insufficient | Incorrect supported |
|---|---:|---:|---:|---:|---:|
| Quarkus Super Heroes | 38 | 2 | 0 | 1 overall | 0 |
| Apache Airflow | 9 | 3 | 2 | 1 | 0 |

Each repeated run SHALL preserve the full I4 identity block and artifact/report hashes.

---

## 19. Fresh Quick Start Qualification

The public Quick Start SHALL be executed from the exact final candidate using only committed
instructions and files.

Reference start:

```bash
cp .env.example .env
docker compose up -d
```

Verify at minimum:

```text
GET /health        -> healthy
GET /health/neo4j  -> healthy
POST /api/import   -> bundled example import succeeds
```

No undocumented edit or maintainer-only secret may be required.

Clean up with:

```bash
docker compose down -v
```

or an equivalent documented command that removes qualification state.

A runtime-demo smoke SHOULD confirm representative `CONFIRMED`, `OBSERVED_ONLY`, and
`NOT_OBSERVED_IN_WINDOW` behavior if the demo remains operationally inexpensive.

---

## 20. CI and Security Qualification

The exact final candidate SHALL have successful required workflows.

Record:

```text
candidate SHA
CI workflow run ID and conclusion
CodeQL workflow run ID and conclusion
dependency-audit job result
actual test counts where exposed
```

Required:

```text
Ruff lint and format       PASS
unit tests                 PASS
integration tests          PASS
pip-audit                  PASS
CodeQL Python              PASS
CodeQL Actions             PASS
no unreviewed release-blocking security finding
```

The release-triggered Docker workflow scans `CRITICAL` and `HIGH` image findings with Trivy. Its
current non-blocking exit policy does not turn findings into approval automatically. I5 SHALL review
the result and record whether any finding is release-blocking.

---

## 21. RC Artifact Qualification

Before final GO, qualify the GHCR image published for the final RC.

Expected image:

```text
ghcr.io/michaelegner/architecture-intelligence-platform:<final-rc-tag>
```

Required checks:

```text
release-triggered Docker workflow succeeded exactly once
tagged image pull succeeds
digest recorded
anonymous pull succeeds
container runs as non-root
GET /health succeeds
GET /health/neo4j succeeds
bundled example import succeeds
Trivy result reviewed
```

The RC tag, workflow run, source SHA, and image digest SHALL form one provenance chain.

If a new RC is required for version consistency, the earlier `rc.1` image remains historical and
SHALL NOT be relabeled as the new candidate.

---

## 22. Release-Validation Record

I5 SHALL create:

```text
docs/release-validation/v0.3.0-go-no-go.md
```

The record SHALL contain at least:

```text
date and environment
repository
final candidate commit SHA
final RC tag and dereferenced SHA
package version
dependency-lock identity
I4 report/revalidation revisions
Quarkus and Airflow artifact/report hashes
real-system candidate-binding result
CI/CodeQL/workflow run IDs and conclusions
pip-audit result
unit and integration results
evaluation results and repeatability
Quick Start results
RC GHCR tag and digest
anonymous pull/non-root/health/import results
Trivy review status
known limitations
critical semantic errors
release blockers
GO / NO-GO
```

Every item SHALL be classified as:

```text
VERIFIED
KNOWN_LIMITATION
NOT_EXECUTED
NOT_APPLICABLE
BLOCKED
```

The document SHALL be committed before the final tag and SHALL name the exact candidate that may be
released.

---

## 23. GO / NO-GO

### 23.1 GO

`GO` requires:

```text
I4 handoff complete
final candidate identity frozen
active package version = 0.3.0
uv.lock consistent
public documentation accurate
release notes prepared and links valid
clean-checkout source qualification passes
unit/integration tests pass
evaluation = 10/10 twice with deterministic result
real-system evidence binds to the final candidate
Quick Start passes
CI and CodeQL green
dependency audit green
RC GHCR artifact verified
no unreviewed release-blocking security issue
critical semantic errors = 0
release blockers = 0
```

The GO statement SHALL name:

```text
final candidate SHA
final RC tag
dependency-lock SHA-256
RC image digest
GO record revision
```

### 23.2 NO-GO

Any mandatory failure produces `NO-GO`, including:

```text
package or tag identity mismatch
candidate changed after qualification
real-system evidence bound to a different required candidate
material INCORRECT_SUPPORTED finding
critical semantic error
synthetic evaluation failure
nondeterministic qualifying result
broken clean checkout or Quick Start
red required CI, CodeQL, or dependency audit
unreviewed release-blocking vulnerability
broken release-note evidence link
public status contradiction
ambiguous release provenance
```

NO-GO SHALL name the failed gate and required re-entry point.

---

## 24. Final Tag and GitHub Release

After GO, create annotated tag `v0.3.0` at the exact approved candidate.

Conceptual sequence:

```text
final RC -> exact candidate SHA
        |
        v
GO record names same SHA
        |
        v
create annotated v0.3.0 tag at same SHA
        |
        v
verify dereferenced tag SHA
        |
        v
publish GitHub Release using reviewed notes
        |
        v
release event triggers Docker workflow
```

Representative commands:

```bash
git tag -a v0.3.0 <candidate-sha> \
  -m "AIP v0.3.0 — real-world validation and cross-system hardening"
git push origin v0.3.0

gh release create v0.3.0 \
  --verify-tag \
  --title "v0.3.0" \
  --notes-file docs/release-validation/v0.3.0-release-notes.md
```

Equivalent tooling is acceptable.

Required properties:

```text
tag resolves to GO candidate
tag is not moved after publication
release uses exact tag
release notes use valid evidence links
exactly one intended publication workflow runs
```

---

## 25. Published GHCR Artifact Verification

After the final release workflow completes, verify:

```text
ghcr.io/michaelegner/architecture-intelligence-platform:v0.3.0
ghcr.io/michaelegner/architecture-intelligence-platform:latest
```

Required:

```text
v0.3.0 pull succeeds
digest recorded
anonymous pull succeeds
container runs as non-root
health succeeds
Neo4j health succeeds
bundled example import succeeds
digest(v0.3.0) == digest(latest)
release workflow completed successfully exactly once
Trivy result reviewed
```

The final image digest MAY differ from the RC digest because the existing release workflow rebuilds
on publication. The source SHA and workflow provenance SHALL therefore be recorded, and the final
artifact itself SHALL receive the smoke checks above.

---

## 26. Tagged-Source Verification

Clone the public final tag from a clean directory:

```bash
git clone --branch v0.3.0 --depth 1 \
  https://github.com/michaelegner/architecture-intelligence-platform.git
cd architecture-intelligence-platform

uv sync --locked
uv run python -m evaluation run
```

Required:

```text
checked-out commit == GO candidate
package version == 0.3.0
locked sync succeeds
evaluation == 10/10 PASS
```

If this fails, the tag SHALL NOT be moved. Record the defect and publish a corrected follow-up
release using immutable-release practice.

---

## 27. Post-Release Verification and Closure

After publication, create:

```text
docs/release-validation/v0.3.0-post-release-verification.md
```

It SHALL record:

```text
release URL
tag SHA
GitHub Release publication time
Docker workflow run ID/result
GHCR v0.3.0 digest
latest digest and equality result
anonymous pull
non-root
health/Neo4j/import smoke
tagged-source version/evaluation result
Trivy review
known post-release issue, if any
```

Then update `main`:

- mark v0.3 and I5 shipped in `ROADMAP.md`;
- mark I5 shipped in the v0.3 specification index;
- finalize and date the `CHANGELOG.md` entry;
- update root README project status;
- add both v0.3 evidence records to `docs/release-validation/README.md`;
- replace moving release-note evidence links with immutable documentation commit permalinks;
- preserve the v0.4 **Trusted Architecture Context for Agents** roadmap direction.

The historical `v0.3.0` tag remains immutable and may naturally contain pre-publication status
wording. Post-release state belongs on `main`.

---

## 28. Known Limitations

I5 SHALL carry forward, without softening, the accepted v0.3 limitations:

```text
gRPC/protobuf calls unsupported
Kafka topic/subscription semantics unsupported
legacy messaging-operation attribute gap deferred
PostgreSQL/database dependencies unsupported
Airflow Execution API caller identity unresolved
Airflow runtime-role identity unresolved
Celery messaging identity/semantic-convention gaps deferred
pre-1.0 Canonical Model, REST, graph, adapter, and config contracts not stable
```

Known limitations are acceptable when explicit and bounded. They are not permission to hide an
incorrect supported claim.

---

## 29. Release Blockers

The following block `v0.3.0`.

### Identity and Provenance

```text
active package version is not 0.3.0
uv.lock inconsistent with project metadata
final tag differs from GO candidate
candidate changed after qualification
RC or release provenance ambiguous
release evidence links broken or materially stale
```

### Semantic and Real-System

```text
material INCORRECT_SUPPORTED finding
wrong relation direction, identity, runtime status, or evidence
unsupported mechanism represented as supported
ground truth derived from AIP output
unresolved fundamental redesign required before v0.4
required Quarkus or Airflow evidence bound to another candidate
real-system revalidation failure after a reopened gate
```

### Regression and Operations

```text
evaluation below 10/10
nondeterministic qualifying result
fresh checkout cannot qualify
Quick Start fails
required CI, CodeQL, or dependency audit fails
RC or final GHCR artifact cannot be pulled
anonymous pull fails
container unexpectedly runs as root
health/Neo4j/import smoke fails
unexpected duplicate publication workflows
unreviewed release-blocking vulnerability
```

Targets:

```text
Critical semantic errors = 0
Release blockers = 0
```

---

## 30. Non-Blocking Items

The following do not block v0.3 merely because they remain absent:

```text
gRPC/protobuf adapter
database relation family
topic/subscription model
complete Airflow role identity
complete telemetry coverage
Kubernetes discovery
ArchitectureIntelligenceService
MCP tools
agent integration
GraphRAG
performance benchmark history
production-support certification
1.0 compatibility promises
```

They remain later-release work unless they expose a false supported claim inside v0.3's frozen scope.

---

## 31. Suggested Delivery Split

### I5.1 — Candidate Identity, Metadata, and Release Preparation

Deliver:

```text
entry audit
package-version and uv.lock consistency
final candidate/RC decision
public documentation review
CHANGELOG preparation
draft v0.3.0 release notes
valid immutable evidence-link plan
```

Exit:

```text
one candidate and RC identity selected
active metadata consistent
no unresolved release-preparation blocker
```

If the candidate changes, create the new RC and reopen affected I4 gates before I5.2.

### I5.2 — Final Qualification and GO/NO-GO

Deliver:

```text
fresh-checkout source qualification
unit/integration/evaluation evidence
evaluation repeatability
real-system candidate-binding audit or required reruns
Quick Start qualification
CI/CodeQL/pip-audit evidence
RC GHCR artifact verification
docs/release-validation/v0.3.0-go-no-go.md
```

Exit:

```text
GO names exact candidate and RC
critical semantic errors = 0
release blockers = 0
```

No source change may occur after GO without invalidating it.

### I5.3 — Publish and Verify

Actions:

```text
create immutable v0.3.0 tag
publish GitHub Release
verify one Docker publication workflow
verify GHCR v0.3.0/latest
verify anonymous pull and non-root execution
verify health/Neo4j/import
verify tagged-source version and evaluation
```

Publication is an explicitly confirmed release action, not an incidental side effect of a
documentation PR.

### I5.4 — Post-Release Evidence and Status Closure

Deliver:

```text
docs/release-validation/v0.3.0-post-release-verification.md
release-validation index update
ROADMAP v0.3/I5 -> shipped
README project status
dated CHANGELOG entry
v0.3 specification index -> shipped
immutable release-note evidence links
```

---

## 32. Definition of Done

### Entry and Identity

- [ ] I4 is complete.
- [ ] Final RC tag resolves to the recorded candidate.
- [ ] Candidate SHA and dependency-lock identity are recorded.
- [ ] No mutable branch name substitutes for candidate identity.

### Version and Documentation

- [ ] `pyproject.toml` version is `0.3.0`.
- [ ] `uv.lock` is consistent.
- [ ] README, ROADMAP, CHANGELOG, specification index, and release notes agree.
- [ ] v0.4 is described as **Trusted Architecture Context for Agents**.
- [ ] Release-note evidence links resolve.
- [ ] Known limitations remain explicit.

### Source and Regression

- [ ] Fresh checkout of the final candidate performed.
- [ ] `uv sync --locked` succeeds.
- [ ] Ruff lint and format pass.
- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] Evaluation passes 10/10 twice.
- [ ] Repeated evaluation result is deterministic.
- [ ] Evaluation requires no LLM API key.

### Real-System Evidence

- [ ] Quarkus and Airflow evidence binds to the final candidate.
- [ ] All qualifying artifact/report hashes resolve.
- [ ] Baseline semantic counts remain accepted.
- [ ] Any candidate change triggered the required I4 revalidation.
- [ ] Material `INCORRECT_SUPPORTED` findings = `0`.
- [ ] Critical semantic errors = `0`.

### Usage, CI, and Security

- [ ] Fresh Quick Start succeeds.
- [ ] Health, Neo4j health, and example import succeed.
- [ ] CI is green on the final candidate.
- [ ] CodeQL is green.
- [ ] Dependency audit is green.
- [ ] No unreviewed release-blocking security issue exists.
- [ ] Final RC GHCR artifact is verified.

### Decision and Publication

- [ ] `v0.3.0-go-no-go.md` names the exact candidate.
- [ ] Explicit decision = `GO`.
- [ ] Release blockers = `0`.
- [ ] `v0.3.0` tag resolves to the GO candidate.
- [ ] GitHub Release is published.
- [ ] Exactly one intended Docker workflow succeeds.

### Published Artifact and Closure

- [ ] GHCR `v0.3.0` and `latest` digests are recorded and equal.
- [ ] Anonymous pull succeeds.
- [ ] Published image runs as non-root.
- [ ] Health, Neo4j health, and import smoke pass.
- [ ] Tagged source reports version `0.3.0` and evaluates 10/10.
- [ ] Trivy result is reviewed.
- [ ] Post-release verification is committed.
- [ ] README, ROADMAP, CHANGELOG, specification index, and release-validation index are closed.
- [ ] Release-note evidence links use immutable documentation references.

---

## 33. Exit State

I5 is complete when:

```text
final candidate identity is unambiguous
active version metadata = 0.3.0
all mandatory source and artifact gates pass
real-system evidence binds to the released candidate
critical semantic errors = 0
release blockers = 0
v0.3.0 tag identifies the GO candidate
GitHub Release and GHCR image are verified
post-release evidence is committed
public status marks v0.3 shipped
```

The final release statement SHALL be:

```text
GO — publish v0.3.0 from <exact candidate SHA>
```

or:

```text
NO-GO — return to <named I5/I4 work package>
```

---

## 34. Relationship to v0.4

I5 closes validation of the semantic core. It does not implement the tool layer.

The next planned release is:

```text
v0.4 — Architecture Intelligence Tools
Goal: Trusted Architecture Context for Agents
```

v0.4 will expose snapshot-bound, evidence-qualified, auditable architecture answers through
structured contracts and read-only tools.

The boundary is non-negotiable:

> **An agent may consume and reason over AIP evidence, but it must never become the source of
> architectural truth.**

This preserves the sequencing principle:

```text
validate the semantic core first
expose trusted context second
broaden discovery third
freeze public contracts last
```

---

## 35. Summary

```text
I4 evidence + immutable RC
        |
        v
identity and version audit
        |
        v
exact final candidate
        |
        v
source + synthetic + real-system evidence qualification
        |
        v
GO / NO-GO
        |
        v
v0.3.0 release
        |
        v
published source and GHCR verification
        |
        v
Trusted Architecture Context for Agents in v0.4
```

The governing rule remains:

```text
correct but incomplete
        >
complete-looking but wrong
```

I5 succeeds when the public `v0.3.0` release has one auditable identity and every important claim
can be traced to the exact source, evidence, workflow, and artifact that supports it.
