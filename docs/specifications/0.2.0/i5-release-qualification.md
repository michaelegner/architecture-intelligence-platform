# AIP v0.2.0 I5 Specification — Release Qualification

**Status:** Draft 1 — self-contained implementation contract  
**Target release:** `v0.2.0`  
**Iteration:** I5 — Release Qualification  
**Entry baseline:** `v0.2.0-rc.1` after I4 is complete, tagged, and verified  
**Parent release specification:** [`specification.md`](specification.md)  
**Preceding iteration:** [`i4-coverage-hardening.md`](i4-coverage-hardening.md)

---

## 1. Purpose

I1–I4 build and harden the deterministic evaluation capability required by AIP `v0.2.0`.

I5 does **not** add architecture intelligence and does **not** add evaluation semantics.

Its purpose is to prove that the exact source state and public release artifacts intended for
`v0.2.0` satisfy the complete release contract and can be consumed from a clean environment without
hidden maintainer state.

The intended transition is:

```text
I4
release candidate is technically complete
        |
        v
v0.2.0-rc.1
        |
        v
I5
qualify the exact release candidate
        |
        v
GO / NO-GO
        |
        v
v0.2.0
        |
        v
verify the published release artifact
```

The central I5 rule is:

> **Qualify the release that will actually be shipped, then verify the artifact that was actually
> shipped.**

A green development checkout is necessary but not sufficient.

---

## 2. Release Identity

The identity of `v0.2.0` remains the one defined by the parent release specification:

```text
v0.1
architecture intelligence exists

v0.2
architecture intelligence is reproducibly verifiable
```

The final release SHALL demonstrate that, for independently authored controlled architecture
situations:

```text
known declared input
        +
known observed input
        +
observation context
        |
        v
       AIP
        |
        v
canonical architecture facts
        |
        v
independent expected ground truth
        |
        v
deterministic PASS / FAIL
```

I5 SHALL NOT broaden that identity.

---

## 3. Entry Criteria

I5 MUST NOT begin as final-release qualification until I4 has completed successfully.

The expected baseline is:

```text
v0.2.0-rc.1
```

with all mandatory I4 outcomes satisfied.

At entry to I5, the following SHALL be true:

```text
I4 mandatory implementation merged to main
I4 specification Definition of Done satisfied
v0.2.0-rc.1 tag exists
I4 specification index status = Shipped
10 core evaluation scenarios exist
10/10 evaluation suite passes
scenario-schema hardening is complete
reconciliation-fixture hardening is complete
comparison/report ordering is deterministic
unit suite is green
integration suite is green
lint/format is green
CI is green
CodeQL is green
critical semantic errors = 0
```

If `v0.2.0-rc.1` has not yet been tagged, that tagging and its verification remain I4 release
candidate work and SHALL be completed before the final I5 GO/NO-GO process.

The exact `rc.1` commit SHA and release date SHALL be recorded when I5 implementation begins. They
are deliberately not hard-coded into this specification.

---

## 4. Non-Goals

I5 is a qualification and publication iteration.

The following are explicitly outside scope:

```text
new canonical entity types
new canonical relation types
new architecture adapters
new runtime observation semantics
new coverage semantics
new evidence semantics
new evaluation scenarios merely to increase scenario count
new comparison mismatch types
new policy/rules framework
new evaluation metrics
new LLM evaluation
GraphRAG
MCP
Kubernetes discovery
gRPC/protobuf ingestion
Dapr discovery
framework-compatibility experiments
real-system architecture validation
performance/scale benchmarking
architecture trajectories
causal runtime analysis
```

In particular, external validation against independent reference or real-world systems is valuable
for later pre-1.0 qualification, but it is **not** a `v0.2.0` release requirement and SHALL NOT delay
I5.

Optional I4 scenarios such as DLQ directionality or cross-batch HTTP correlation remain optional.
Their absence is not an I5 release blocker.

---

## 5. Qualification Principles

### 5.1 Qualification, Not Development

I5 SHALL prefer:

```text
verify
document
fix regressions
publish
```

over:

```text
extend
redesign
generalize
experiment
```

A new feature discovered during I5 SHALL be deferred.

A defect discovered during I5 MAY be fixed.

---

### 5.2 The Exact Candidate Commit Matters

A qualification result applies only to the commit that was tested.

```text
qualified commit A
        !=
later commit B
```

If any source, dependency lock, configuration, fixture, documentation that affects the release
procedure, or executable code changes after qualification, the relevant qualification steps SHALL
be repeated against the new final candidate.

The final `v0.2.0` tag MUST resolve to the commit recorded in the final GO decision.

---

### 5.3 Source Qualification and Artifact Qualification Are Distinct

I5 SHALL distinguish:

```text
Source qualification
    fresh checkout
    dependencies
    lint
    unit tests
    integration tests
    deterministic evaluation
    Quick Start

Published-artifact qualification
    Git tag/release provenance
    release-triggered container workflow
    GHCR image
    anonymous pull
    non-root execution
    health/import smoke
```

A passing source checkout does not prove that the published image is correct.

A successfully published image does not prove that the evaluation semantics are correct.

Both are required for a complete release evidence trail.

---

### 5.4 No Hidden Maintainer State

Required qualification procedures SHALL be executable from a clean environment without:

```text
an existing Neo4j database
maintainer-local graph state
an OPENAI_API_KEY
private source artifacts
private customer data
uncommitted fixture files
manual graph repair
manual Cypher mutation
```

Docker is an explicit runtime prerequisite where documented.

---

### 5.5 Evidence Before Assertion

Release claims SHALL be backed by recorded evidence.

Examples:

```text
"CI green"
    -> workflow run id + candidate SHA

"10/10 scenarios pass"
    -> captured evaluator output

"deterministic"
    -> repeated run comparison

"published container works"
    -> pulled tag + digest + smoke results
```

The release-validation record is evidence for the release, not a narrative written from memory.

---

## 6. Semantic Freeze

After I4:

```text
semantic/evaluation feature set = frozen for v0.2.0
```

I5 SHALL NOT intentionally alter:

```text
canonical architecture semantics
relation direction semantics
status classification semantics
evidence-preservation semantics
coverage qualification semantics
scenario scope semantics
comparison semantics
ground-truth schema semantics
```

The mandatory I5 changes should primarily be:

```text
version metadata
documentation
release notes
ROADMAP
CHANGELOG
release-validation evidence
small regression fixes if required
```

---

## 7. Defect and RC Escalation Policy

I5 may uncover defects.

They SHALL be classified before deciding whether the existing `rc.1` can be promoted.

### 7.1 Documentation or Metadata Defect

Examples:

```text
stale version string
broken documentation link
incorrect release-note wording
README command typo
missing roadmap status
```

These MAY be fixed without introducing a new RC solely because the text changed, provided the final
candidate is fully requalified.

---

### 7.2 Non-Semantic Implementation Defect

Examples:

```text
release script problem
container packaging issue
startup regression
health endpoint regression
configuration regression
```

Fix the defect and repeat all qualification steps affected by it.

A new RC SHOULD be cut when the fix materially changes the artifact users will run.

---

### 7.3 Semantic Defect

Examples:

```text
invented relation
missing expected relation
wrong direction
wrong provider/consumer resolution
wrong CONFIRMED classification
wrong OBSERVED_ONLY classification
wrong NOT_OBSERVED_IN_WINDOW classification
surviving evidence lost
fact deleted while evidence remains
non-observation interpreted as absence
```

A semantic defect is release-blocking.

Required response:

```text
NO-GO
    |
fix defect
    |
full regression
    |
new release candidate, normally v0.2.0-rc.2
    |
requalify
```

`v0.2.0` SHALL NOT be published directly from an RC with a known semantic defect.

---

## 8. Version and Package Metadata

The final candidate SHALL identify itself consistently as `0.2.0`.

At minimum:

```text
pyproject.toml
    [project].version = "0.2.0"

uv.lock
    regenerated/updated consistently
```

The final release qualification SHALL search active public metadata for stale `0.1.0` release
identity where that value is intended to mean the current package version.

Historical documents, changelog entries, release-validation records, and v0.1 specifications SHALL
remain historical and SHALL NOT be rewritten merely because they contain `0.1.0`.

The rule is:

```text
active current-version metadata -> 0.2.0
historical references            -> preserve history
```

A package-version mismatch is an I5 blocker.

---

## 9. Public Documentation Updates

I5 SHALL bring public documentation into the final `v0.2.0` state.

### 9.1 Root README

The root `README.md` SHALL make the shipped deterministic evaluation capability discoverable.

At minimum it SHOULD include:

```text
deterministic evaluation as a shipped capability
link to evaluation/README.md
one canonical command:
    uv run python -m evaluation run
statement that evaluation does not require an LLM API key
```

The root README SHALL NOT imply that pre-1.0 API/model surfaces are now stable.

---

### 9.2 Evaluation README

`evaluation/README.md` SHALL remain the detailed operational document for the ten-scenario suite.

It SHALL accurately describe:

```text
10 core scenarios
AIP Evaluation — I4 banner
scenario semantics
strict expected.yaml validation
partial-observation behavior
qualitative coverage
reconciliation
deterministic output
clean-checkout commands
actual evaluator exit-code behavior
```

No known incorrect command or exit-code statement may remain in the final release documentation.

---

### 9.3 Specification Index

Before the final tag, the v0.2 specification index SHOULD represent:

```text
I1  Shipped
I2  Shipped
I3  Shipped
I4  Shipped
I5  Implementation complete — release pending
```

or equivalent wording.

After `v0.2.0` is published, the index SHALL be updated on `main` to:

```text
I5  Shipped
```

The final release tag itself may naturally point to the pre-publication status because publication
cannot be recorded as historical fact until after it occurs.

---

### 9.4 ROADMAP

`ROADMAP.md` SHALL no longer describe `v0.2` as planned.

It SHALL mark `v0.2` as shipped and summarize the delivered evaluation capability accurately.

I5 SHALL NOT use the ROADMAP update to define a detailed new `v0.3` implementation contract.

A concise future-direction update is allowed, but detailed `v0.3` commitments belong in the
`v0.3.0` release specification.

---

### 9.5 CHANGELOG

`CHANGELOG.md` SHALL contain a final `0.2.0` entry following the existing Keep a Changelog style.

It SHOULD summarize externally meaningful changes, including:

```text
deterministic evaluation kernel
independent expected.yaml ground truth
10 core scenarios
missing/unexpected/forbidden detection
status/evidence validation
NOT_OBSERVED_IN_WINDOW evaluation
evidence reconciliation evaluation
partial-observation coverage qualification
strict scenario-schema validation
deterministic mismatch/report ordering
local reproducibility
```

The changelog SHALL describe product behavior, not the internal PR sequence.

Exact test counts SHOULD NOT be treated as a permanent changelog contract.

---

## 10. Release Notes

I5 SHALL prepare the GitHub Release notes before the final release is published.

The release notes SHOULD contain:

```text
Project status: Experimental / Alpha or equivalent pre-1.0 wording
License: Apache-2.0

What v0.2 proves
Highlights
How to run the evaluator
Evaluation result
What changed since v0.1.0
Known limitations
Quick Start
Documentation links
Security reporting link
```

The central release statement SHOULD be equivalent to:

> AIP v0.2.0 adds a deterministic evaluation suite that verifies the architecture intelligence
> introduced in v0.1 against independently authored ground truth.

The release notes SHALL NOT claim:

```text
1.0 API stability
complete architecture conformance
formal proof of correctness
complete runtime observation coverage
absence of a relation from non-observation
production readiness of every pre-1.0 surface
```

---

## 11. Clean-Checkout Source Qualification

I5 SHALL perform final source qualification from a fresh checkout of the exact release-candidate
commit.

Do not qualify an existing development worktree containing caches, local environment files, or
uncommitted changes.

Reference procedure:

```bash
git clone https://github.com/michaelegner/architecture-intelligence-platform.git
cd architecture-intelligence-platform
git checkout <candidate-sha>

uv sync --locked

uv run ruff check .
uv run ruff format --check .

uv run pytest tests/unit
uv run pytest tests/integration

uv run python -m evaluation run
```

Required environment:

```text
supported Python as defined by pyproject.toml / uv
Docker available
no separately running Neo4j required
no OPENAI_API_KEY required for evaluation
```

`uv sync --locked` is preferred for release qualification because it proves the committed lock file
is internally consistent.

The actual unit and integration test counts SHALL be recorded in the qualification evidence but are
not normative fixed numbers.

---

## 12. Deterministic Evaluation Qualification

The complete evaluator SHALL be run against the exact release candidate.

Required result:

```text
AIP Evaluation — I4

[PASS] 01-rest-confirmed
[PASS] 02-rest-observed-only
[PASS] 03-async-confirmed
[PASS] 04-orphan-messaging
[PASS] 05-mixed-rest-async
[PASS] 06-request-response-queue-pair
[PASS] 07-not-observed-in-window
[PASS] 08-evidence-reconciliation
[PASS] 09-partial-observation
[PASS] 10-declared-rest-relation

Scenarios: 10
Passed:    10
Failed:    0

RESULT: PASS
```

All failure counters SHALL be zero.

The evaluator SHALL be run at least twice against clean ephemeral evaluation state.

Required property:

```text
same candidate
same scenarios
same PASS/FAIL result
same scenario ordering
same mismatch ordering
same counters
```

A byte-for-byte stdout comparison SHOULD be used.

Example:

```bash
uv run python -m evaluation run > /tmp/aip-eval-1.txt
uv run python -m evaluation run > /tmp/aip-eval-2.txt
diff -u /tmp/aip-eval-1.txt /tmp/aip-eval-2.txt
```

Expected:

```text
diff output = empty
```

Each run SHALL use the normal evaluator path and its fresh Testcontainers Neo4j state.

---

## 13. Evaluation Failure Semantics

For final qualification:

```text
exit 0
    full requested evaluation passed

exit 1
    one or more semantic evaluation failures

exit 2
    known invalid evaluator/scenario configuration
```

Unexpected programmer or infrastructure exceptions are not required to be normalized into exit code
`2`; they may terminate with a traceback and are themselves a failed qualification run.

The release evidence SHALL record the actual command result, not infer success from partial output.

---

## 14. Fresh Quick Start Qualification

The public Quick Start SHALL be exercised from a fresh clone of the final candidate.

Reference procedure:

```bash
cp .env.example .env
docker compose up -d
```

Then verify at minimum:

```text
GET /health
    -> healthy

GET /health/neo4j
    -> healthy

POST /api/import
    -> succeeds against the bundled example architecture
```

The procedure SHALL use only files and instructions present in the repository.

No manual edit not documented in the public Quick Start may be required.

After verification:

```bash
docker compose down -v
```

or equivalent cleanup SHALL remove the temporary qualification environment.

---

## 15. Runtime Demo Regression Smoke

Because `v0.2.0` does not change the product's runtime architecture semantics, I5 does not need to
repeat the entire v0.1 runtime-validation campaign.

However, a final runtime-demo smoke SHOULD be run if it remains inexpensive.

At minimum it SHOULD confirm that the existing demo still exposes representative:

```text
CONFIRMED
OBSERVED_ONLY
NOT_OBSERVED_IN_WINDOW
```

behavior and that the evaluator work has not broken normal application startup/import/runtime APIs.

A runtime-demo failure caused by a `v0.2` regression is release-blocking.

---

## 16. CI Qualification

The final candidate commit on `main` SHALL have successful GitHub Actions results for the project's
required workflows.

At minimum:

```text
CI
    lint + test                  PASS
    dependency security scan    PASS

CodeQL                          PASS
```

The release evidence SHALL record:

```text
candidate SHA
workflow run IDs
workflow conclusions
actual test counts from CI
```

The final release SHALL NOT rely only on PR checks for an earlier commit.

If the candidate commit differs from the reviewed PR head because of merge mechanics or final release
metadata changes, qualification SHALL refer to the resulting candidate commit.

---

## 17. Security Qualification

I5 is not a new security-feature iteration, but existing security gates SHALL remain healthy.

Required:

```text
pip-audit job passes
CodeQL workflow passes
no known unreviewed release-blocking security finding
```

The release-triggered container workflow performs Trivy scanning of `CRITICAL`/`HIGH` findings and
uploads SARIF.

Because the existing workflow intentionally treats Trivy findings as reviewable rather than a hard
exit-code gate, I5 requires:

```text
no unreviewed critical/high release finding
```

rather than:

```text
zero findings under all circumstances
```

A known exploitable release-blocking issue SHALL result in NO-GO.

---

## 18. Release Validation Record

I5 SHALL create a release-validation record under:

```text
docs/release-validation/
```

Recommended pre-release file:

```text
v0.2.0-go-no-go.md
```

It SHALL record at least:

```text
date
repository
candidate commit SHA
rc.1 tag/commit
package version
CI workflow run IDs/results
CodeQL result
pip-audit result
unit test count/result
integration test count/result
evaluation result 10/10
repeated-run determinism result
Quick Start result
runtime-demo smoke result if performed
known limitations
known critical semantic errors
release blockers
GO / NO-GO decision
```

The evidence document SHALL distinguish:

```text
verified fact
known limitation
not executed
not applicable
```

It SHALL NOT report an unexecuted check as PASS.

---

## 19. GO / NO-GO Decision

A final explicit decision is required.

### 19.1 GO

`GO` requires all mandatory conditions:

```text
candidate identity frozen
package version = 0.2.0
public docs accurate
CHANGELOG updated
ROADMAP updated
I4 = Shipped
I5 pre-release state documented

clean-checkout dependency sync passes
ruff check passes
ruff format check passes
all unit tests pass
all integration tests pass
10/10 evaluator passes
repeated evaluator output is deterministic

Quick Start works
CI green on candidate
CodeQL green
pip-audit green
no unreviewed release-blocking security issue

critical semantic errors = 0
release blockers = 0
```

The GO record SHALL name the exact commit that may be tagged.

---

### 19.2 NO-GO

Any of the following requires NO-GO:

```text
evaluation < 10/10
known critical semantic error
nondeterministic result for identical semantic input
candidate package-version mismatch
broken clean checkout
broken documented Quick Start
required CI failure
CodeQL failure
dependency audit failure
unreviewed release-blocking security issue
release documentation materially contradicts behavior
candidate commit changed after qualification
```

NO-GO is not a failure of the process.

It is the mechanism that prevents an unqualified candidate from becoming the public release.

---

## 20. Final Tag and GitHub Release

After GO, create `v0.2.0` from the exact approved candidate commit.

The release tag MUST NOT be moved after publication.

An annotated tag SHOULD be used for provenance consistency with the v0.2 pre-release process.

Recommended conceptual sequence:

```text
main @ qualified candidate SHA
        |
        v
create v0.2.0 tag
        |
        v
verify tag -> exact candidate SHA
        |
        v
publish GitHub Release using prepared release notes
        |
        v
release event triggers Docker workflow
```

If using the GitHub CLI, a safe pattern is:

```bash
git tag -a v0.2.0 <candidate-sha> -m "AIP v0.2.0 — deterministic evaluation suite"
git push origin v0.2.0

gh release create v0.2.0 \
  --verify-tag \
  --title "v0.2.0" \
  --notes-file <release-notes-file>
```

Equivalent tooling is acceptable.

The important properties are:

```text
tag exists before release publication
tag resolves to approved candidate
release uses that exact tag
tag is immutable after publication
```

---

## 21. Release Workflow Provenance

The existing Docker publication workflow is triggered by:

```text
GitHub Release -> published
```

The final release SHALL verify that the release produces exactly the intended publication workflow.

Record:

```text
v0.2.0 tag SHA
GitHub Release URL
Docker workflow run ID
workflow conclusion
GHCR image digest
```

Unexpected duplicate publication runs SHALL be investigated before declaring post-release
verification complete.

---

## 22. Published GHCR Artifact Verification

After the GitHub Release publishes the image, verify the actual tagged artifact a user can pull.

Expected image:

```text
ghcr.io/michaelegner/architecture-intelligence-platform:v0.2.0
```

Required checks:

```text
tagged pull succeeds
digest is recorded
image is publicly pullable without registry credentials
container runs as non-root
basic health succeeds
Neo4j health succeeds
bundled example import succeeds
```

A representative verification sequence MAY include:

```bash
docker pull ghcr.io/michaelegner/architecture-intelligence-platform:v0.2.0

docker logout ghcr.io || true
docker image rm ghcr.io/michaelegner/architecture-intelligence-platform:v0.2.0
docker pull ghcr.io/michaelegner/architecture-intelligence-platform:v0.2.0
```

The second pull demonstrates that public distribution does not depend on cached credentials.

Against the running pulled artifact, verify:

```text
whoami -> app
uid != 0

GET /health       -> healthy
GET /health/neo4j -> healthy
POST /api/import  -> succeeds
```

The exact isolated-container/network commands may reuse the established v0.1 release-validation
procedure.

---

## 23. `latest` Tag Consistency

If the release workflow publishes both:

```text
:v0.2.0
:latest
```

then post-release verification SHALL confirm that both resolve to the expected release artifact
digest.

Required property:

```text
digest(v0.2.0) == digest(latest)
```

at the time of release verification.

If they differ unexpectedly, post-release verification is incomplete until the reason is understood.

---

## 24. Post-Release Source Verification

A post-release source check SHOULD clone the public release tag itself rather than relying solely on
the pre-tag worktree:

```bash
git clone --branch v0.2.0 --depth 1 \
  https://github.com/michaelegner/architecture-intelligence-platform.git
cd architecture-intelligence-platform

uv sync --locked
uv run python -m evaluation run
```

Expected:

```text
10/10 PASS
```

This provides a final independent confirmation that:

```text
published source tag
    =
qualified source state
```

If this check fails, the tag MUST NOT be silently moved.

Record the defect and publish a corrected follow-up release according to normal immutable-release
practice.

---

## 25. Post-Release Verification Record

The published artifact verification SHALL be recorded.

Recommended file:

```text
docs/release-validation/v0.2.0-post-release-verification.md
```

or a clearly separated post-release section in the GO/NO-GO record.

It SHOULD record:

```text
release URL
tag SHA
Docker workflow run
GHCR digest
v0.2.0/latest digest comparison
anonymous pull result
non-root result
health result
import result
tagged-source evaluation result
Trivy review status
```

This record may be committed to `main` after the release tag because the evidence does not exist
until publication has occurred.

The historical `v0.2.0` tag SHALL remain immutable.

---

## 26. Known Limitations

I5 SHALL carry forward genuine pre-1.0 limitations rather than hiding them.

At minimum, release documentation SHALL continue to make clear that pre-1.0 surfaces such as the
following are not yet guaranteed stable:

```text
Canonical Model
REST API surface
Graph Schema
Adapter SPI
configuration format
```

The final release MAY also document:

```text
no Kubernetes/cloud discovery
no gRPC/protobuf adapter
no GraphRAG
no broad real-system validation yet
natural-language query requires an LLM provider key
deterministic evaluation does not require an LLM key
```

Known limitations are acceptable when they do not contradict the release contract.

---

## 27. Release Blockers

The following are release-blocking for `v0.2.0`.

### Semantic

```text
invented architecture dependency
missing expected dependency
wrong canonical identity
wrong direction
wrong provider resolution
wrong sender/consumer resolution
wrong CONFIRMED
wrong OBSERVED_ONLY
wrong NOT_OBSERVED_IN_WINDOW
out-of-window evidence treated as in-window
non-observation interpreted as absence
surviving evidence lost
fact deleted while evidence remains
partial observation collapses or deletes facts
evaluator independently reimplements coverage classification
```

### Evaluation / Reproducibility

```text
one or more core scenarios fail
unexpected in-scope fact is silently accepted
known invalid scenario input is silently accepted
same semantic input produces nondeterministic result
fresh checkout cannot run the suite
evaluation requires an LLM API key
```

### Packaging / Publication

```text
current package metadata not 0.2.0
lock file inconsistent
Quick Start broken
tag does not resolve to qualified commit
release provenance ambiguous
required publication workflow fails
published GHCR image cannot be pulled publicly
published image unexpectedly runs as root
published image fails health/import smoke
```

### Security

```text
required CodeQL failure
dependency audit failure
known unreviewed release-blocking vulnerability
```

Target:

```text
Release blockers = 0
Critical semantic errors = 0
```

---

## 28. Non-Blocking Items

The following SHALL NOT block `v0.2.0` merely because they are absent:

```text
DLQ evaluation scenario
cross-batch correlation evaluation scenario
numeric coverage score
performance benchmark history
Kubernetes discovery
new adapter families
MCP tools
GraphRAG
Architecture Copilot
real-world validation against external systems
1.0 compatibility guarantees
```

They belong to later releases or later pre-1.0 qualification.

---

## 29. Suggested I5 Delivery Split

I5 should continue the project's short-lived task-branch / focused-PR workflow.

A practical split is:

### I5.1 — Release Metadata and Public Documentation

Deliver:

```text
pyproject version -> 0.2.0
uv.lock consistency
root README evaluation visibility
CHANGELOG 0.2.0 entry
ROADMAP v0.2 -> shipped
v0.2 specification index pre-release state
draft GitHub release notes
```

Suggested branch:

```text
docs/v0.2-i5-release-metadata
```

Exit condition:

```text
public source tree describes the candidate accurately
no new architecture semantics
CI green
```

---

### I5.2 — Final Qualification and GO/NO-GO

Deliver:

```text
fresh-checkout qualification
unit/integration evidence
10/10 evaluation evidence
repeated-run determinism evidence
Quick Start evidence
optional runtime-demo smoke
CI/CodeQL/pip-audit evidence
known-limitations review
docs/release-validation/v0.2.0-go-no-go.md
```

Suggested branch:

```text
docs/v0.2-i5-release-qualification
```

Exit condition:

```text
GO decision names exact final candidate SHA
release blockers = 0
critical semantic errors = 0
```

No code should be changed after this GO without invalidating the decision and triggering
requalification.

---

### I5.3 — Publish and Verify

This step begins only after the GO commit is merged.

Actions:

```text
tag v0.2.0
publish GitHub Release
wait for Docker publication workflow
verify release provenance
pull final GHCR artifact
verify anonymous pull
verify non-root
verify health/import
verify tag source 10/10
record post-release evidence
mark I5 Shipped on main
```

The publication itself is not a normal implementation PR.

The post-release evidence/status update MAY be delivered as a small documentation PR after the tag is
immutable.

---

## 30. Final Definition of Done

I5 is complete when every mandatory item below is true.

### Entry / freeze

- [ ] `v0.2.0-rc.1` exists and is verified.
- [ ] I4 is marked `Shipped`.
- [ ] No new architecture semantics are introduced in I5.
- [ ] Any post-RC semantic defect has been fixed and requalified through an appropriate new RC.

### Version / docs

- [ ] `pyproject.toml` version is `0.2.0`.
- [ ] `uv.lock` is consistent.
- [ ] Root README exposes the deterministic evaluation capability.
- [ ] `evaluation/README.md` is factually correct.
- [ ] `CHANGELOG.md` contains the `0.2.0` release entry.
- [ ] `ROADMAP.md` marks `v0.2` shipped.
- [ ] Release notes are prepared.
- [ ] Pre-1.0 limitations remain explicit.

### Source qualification

- [ ] Fresh checkout performed from exact candidate SHA.
- [ ] `uv sync --locked` succeeds.
- [ ] Ruff check passes.
- [ ] Ruff format check passes.
- [ ] All unit tests pass.
- [ ] All integration tests pass.
- [ ] Evaluation suite passes `10/10`.
- [ ] Evaluation run repeated against clean state.
- [ ] Repeated output is deterministic.
- [ ] Evaluation works without an LLM API key.

### Public usage

- [ ] Fresh Quick Start works without undocumented edits.
- [ ] `/health` succeeds.
- [ ] `/health/neo4j` succeeds.
- [ ] Bundled example import succeeds.
- [ ] Runtime-demo regression smoke passes if executed.

### CI / security

- [ ] CI is green on the final candidate commit.
- [ ] CodeQL is green.
- [ ] Dependency security scan is green.
- [ ] No unreviewed release-blocking security issue exists.
- [ ] Critical semantic errors = `0`.

### Decision / publication

- [ ] `v0.2.0-go-no-go.md` records the exact candidate.
- [ ] Explicit decision = `GO`.
- [ ] `v0.2.0` tag points to that exact commit.
- [ ] GitHub Release is published.
- [ ] Exactly the expected Docker publication workflow completes successfully.

### Published artifact

- [ ] GHCR `v0.2.0` image pull succeeds.
- [ ] GHCR image digest is recorded.
- [ ] Anonymous pull succeeds.
- [ ] Published image runs as non-root.
- [ ] Published image health succeeds.
- [ ] Published image Neo4j health succeeds.
- [ ] Published image import succeeds.
- [ ] `v0.2.0` and `latest` resolve consistently.
- [ ] Tagged source evaluates `10/10`.
- [ ] Post-release verification evidence is recorded.
- [ ] I5 status is updated to `Shipped` on `main`.

---

## 31. Final Release Criteria

`v0.2.0` may be published when the pre-release qualification state is:

```text
Core scenarios:             10
Passed:                     10
Failed:                      0

Critical semantic errors:   0
Release blockers:            0

unit tests:                  green
integration tests:           green
lint/format:                 green
determinism:                 verified
Quick Start:                 verified
CI:                          green
CodeQL:                      green
dependency audit:            green

candidate commit:            frozen
GO / NO-GO:                  GO
```

Post-publication verification SHALL then confirm:

```text
tag provenance:              verified
Docker workflow:             success
GHCR artifact:               verified
anonymous pull:              verified
non-root execution:          verified
health/import smoke:         verified
tagged source evaluation:    10/10
```

---

## 32. Expected Final Repository State

After I5 and post-release documentation:

```text
docs/specifications/0.2.0/
├── README.md
├── specification.md
├── i1-evaluation-kernel.md
├── i2-topology-directionality.md
├── i3-evidence-runtime-semantics.md
├── i4-coverage-hardening.md
├── i5-release-qualification.md
└── git-workflow.md
```

and release evidence includes:

```text
docs/release-validation/
├── ...
├── v0.2.0-go-no-go.md
└── v0.2.0-post-release-verification.md
```

The specification index final state is:

```text
I1  Shipped
I2  Shipped
I3  Shipped
I4  Shipped
I5  Shipped
```

---

## 33. Relationship to Later Releases

I5 closes `v0.2.0`; it does not define the next architecture dimension.

After `v0.2.0`:

```text
v0.2
architecture intelligence is reproducibly verifiable

next release
may build on that verified core
```

Later work may include architecture-intelligence service/tool boundaries, additional discovery
sources, MCP integration, broader runtime analysis, GraphRAG, or other roadmap items.

Those capabilities SHALL receive their own release specification rather than being appended to I5.

Likewise, independent external-reference and real-world-system validation should be treated as a
separate pre-1.0 qualification track, not retroactively added to the `v0.2.0` contract.

---

## 34. Summary

I5 converts the I4 release candidate into a qualified public `v0.2.0` release.

It deliberately introduces no new architecture semantics.

```text
I4
technical RC completeness

        +

I5
exact candidate qualification
public documentation
release provenance
artifact verification

        =

v0.2.0
reproducibly verified architecture intelligence
```

The core rule remains:

> **Do not ship because the implementation looks finished. Ship because the exact candidate and the
> exact published artifact have been verified against the release contract.**
