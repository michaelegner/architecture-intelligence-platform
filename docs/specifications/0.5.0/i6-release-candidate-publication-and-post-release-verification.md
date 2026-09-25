# AIP v0.5.0 I6 — Release Candidate, Publication, and Post-Release Verification

**Status:** Draft 0.1  
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

A production-semantic defect found in I6 produces `NO_GO` and a return to the owning increment rather than an opportunistic release-time fix.

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

### 4.1 Tag identity

The final `v0.5.0` tag SHALL point directly to `RELEASE_CANDIDATE_SHA`.

It SHALL NOT point to an evidence commit, decision commit, closure commit, or whatever `main` happens to contain at publication time.

### 4.2 Build identity

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

At minimum:

~~~text
pyproject.toml [project].version
uv.lock root project version
app.version.package_version()
MCP server advertised version
production Producer.version
Architecture Answer evaluator Producer.version
tests/unit/test_release_version_consistency.py
version-bearing expected evaluation fixtures
~~~

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

The profile MAY reuse and compose existing I1–I4 fixtures. It SHALL NOT add an unqualified semantic expectation.

The profile SHALL have:

- a deterministic content digest;
- frozen expected outputs;
- a documented import order;
- a fixed observation window where runtime evidence is used;
- no dependency on an LLM or external network service.

The same logical profile SHALL run against both the local candidate image and the anonymously pulled final published image.

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

Run twice from the same absolute clean-checkout location:

~~~bash
uv run python -m evaluation answers \
  --candidate-sha "$RELEASE_CANDIDATE_SHA"
~~~

Required result:

~~~text
23/23 PASS
two result files byte-identical
semantic mismatches = 0
~~~

The committed release evaluation report SHALL be refreshed for the release candidate and SHALL identify `RELEASE_CANDIDATE_SHA`, not the old I5 candidate.

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
- candidate image HIGH/CRITICAL findings SHALL be reviewed;
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

That evidence commit becomes `EVIDENCE_COMMIT_SHA`.

It SHALL record at least:

- `I5_QUALIFIED_SEMANTIC_SHA`;
- `I5_COMPLETION_SHA`;
- `RELEASE_CANDIDATE_SHA`;
- clean-checkout proof;
- package/version identities;
- dependency-lock SHA-256;
- schema/tree identities;
- adapter/rule versions;
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

The decision SHALL apply to the exact `RELEASE_CANDIDATE_SHA`.

`PENDING` yields `AWAITING_PUBLICATION_DECISION` and is non-terminal.

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

The immutable `v0.5.0` tag SHALL be created directly at `RELEASE_CANDIDATE_SHA`.

After creation:

~~~bash
git rev-list -n1 v0.5.0
~~~

MUST equal `RELEASE_CANDIDATE_SHA`.

The public release body SHALL use a pre-reviewed, public-only rendered release note and contain no unresolved placeholders or internal drafting instructions.

The release-triggered Docker workflow SHALL execute exactly once for the publication event. Every workflow attempt SHALL be recorded, including failed or retried attempts.

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

- release-workflow Trivy result;
- correctly ref-scoped GitHub code-scanning query;
- final-image SBOM;
- review of all HIGH/CRITICAL findings;
- zero unresolved release-blocking findings.

Queries SHALL be scoped to:

~~~text
refs/tags/v0.5.0
~~~

A default-branch-only code-scanning query is insufficient.

Candidate-image security evidence MAY be referenced for comparison, but SHALL NOT substitute for the final-image disposition.

---

## 20. Published-Image Golden Path

The final image SHALL be pulled anonymously by immutable digest.

A local rebuild SHALL NOT substitute.

From clean state, verify:

~~~text
pulled digest == FINAL_IMAGE_DIGEST
process runs non-root
GET /health succeeds
GET /health/neo4j succeeds

producer.version == 0.5.0
producer.build_revision == RELEASE_CANDIDATE_SHA
schema_version == 0.5

fixture import is COMPLETE
expected OpenAPI facts exist
expected AsyncAPI Queue facts exist
expected Topic/Subscription facts exist
expected Kubernetes infrastructure facts exist
expected DEPLOYED_AS outcome exists
runtime observation qualification exists

unresolved case remains unresolved
conflicting case emits no guessed association
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
post-run source inventory remains COMPLETE
~~~

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
release golden-path profile present
exactly three MCP tools
~~~

Run at least:

~~~bash
uv run pytest tests/unit/test_release_version_consistency.py -q
uv run python -m evaluation answers \
  --candidate-sha "$RELEASE_CANDIDATE_SHA"
~~~

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

### Slice 1 — Entry Audit and Candidate Preparation

Deliver:

~~~text
I5 handoff audit
0.5.0 version consistency
release-version tests/fixtures
release golden-path profile/harness
release notes
CHANGELOG release content
release workflow/SBOM/provenance preparation if required
~~~

Exit:

~~~text
candidate-preparation PR merged
RELEASE_CANDIDATE_SHA frozen
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
Architecture Answer evaluation twice
candidate image
candidate security
candidate golden path
CI/CodeQL
~~~

Publish `docs/release-validation/v0.5.0-release-readiness.md`.

Exit: `RELEASE_READY` or `NO_GO`.

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
16. public release notes materially overclaim qualified behavior.

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
candidate golden path PASS
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
  mandatory pre-publication gate failed

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
  v0.5.0-release-readiness.md
  v0.5.0-publication-decision.md
  v0.5.0-unpublished-closure.md              # only if NOT_GRANTED
  v0.5.0-post-release-verification.md        # only if publication occurs
~~~

Raw candidate and final-artifact evidence MAY be stored under:

~~~text
docs/release-validation/v0.5.0-artifacts/
~~~

No raw secret, token, password, credential, or unredacted sensitive environment value may be committed.

---

## 30. Completion Record

`i6-completion-record.md` SHALL state:

- terminal outcome;
- I5 semantic baseline;
- I5 completion identity;
- release candidate identity;
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
- [ ] Exact-candidate evaluation is rerun twice.
- [ ] Publication requires explicit owner authorization.
- [ ] `RELEASE_READY_NOT_PUBLISHED` and `SHIPPED_VERIFIED` remain distinct.
- [ ] The final GHCR digest is independently verified; no local/RC image substitutes.
- [ ] Final security/SBOM disposition is bound to the published digest/workflow.
- [ ] Final artifact verifies `producer.version = 0.5.0` and `producer.build_revision = RELEASE_CANDIDATE_SHA`.
- [ ] No v0.6 locality or Intent semantics enter I6.
