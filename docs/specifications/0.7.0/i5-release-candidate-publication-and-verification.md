# AIP v0.7.0 I5 — Release Candidate, Publication, and Verification

**Status:** Draft 0.1  
**Increment:** I5 — Release Candidate, Publication, and Verification  
**Entry:** I4 is complete and merged (#558). The [I4 completion record](i4-completion-record.md) records the qualified semantic candidate `c662f3c440733a7b75252ba2466fee14c1c88f4a`, the product-pilot disposition `CONTINUE`, and the reviewed Tyk `MODEL_GAP` scope exclusion. I4 does **not** qualify a later release candidate or authorize publication.  
**Authority:** accepted [v0.7.0 parent specification](specification.md), especially §§26–28 and §32; [I4 completion record](i4-completion-record.md); [I4 → I5 handoff](i4-i5-handoff.md); [ROADMAP](../../../ROADMAP.md); and the repository [release-publication skill](../../../.agents/skills/release-publication/SKILL.md) as procedural guidance only.

## 1. Purpose

I5 turns the completed v0.7 implementation and I4 evidence into **one exact release candidate**, re-freezes release-facing content, independently re-runs the mandatory qualification on that exact SHA, separates technical readiness from publication authority, and—only if authorized—publishes and verifies the exact tagged source and immutable GHCR artifact.

I5 SHALL NOT add:

- new Architecture Intelligence semantics;
- another gateway adapter;
- a Tyk model amendment;
- new Intent or Assessment behavior;
- another public API question or MCP tool;
- a new product pilot;
- F1/F2/F3 optimizations merely because release work touches the same code.

Any such change returns to the owning increment and creates a new candidate after review.

## 2. Terminal outcomes

I5 has four terminal outcomes:

~~~text
RELEASE_READY_NOT_PUBLISHED
  every mandatory technical gate passed on one exact release candidate;
  the owner did not authorize publication;
  no v0.7.0 release/tag/final image is claimed

SHIPPED_VERIFIED
  the owner authorized publication;
  the exact qualified candidate was tagged and published;
  tagged source and immutable GHCR digest passed post-publication verification

NO_GO
  one or more mandatory pre-publication gates failed or remain undispositioned

POST_RELEASE_FAILED
  publication occurred, but mandatory verification of the tag or published artifact failed
~~~

A green PR, a local build, a Git tag, or a successful publication workflow alone is not `SHIPPED_VERIFIED`.

## 3. Frozen I5 decisions

### 3.1 Capability-release path

v0.7.0 uses the repository's **capability-release** path, not the lightweight patch/demo path.

Candidate attempts are labelled `rc.1`, `rc.2`, … in release evidence only. No `v0.7.0-rc.N` Git tag, GitHub prerelease, or prerelease GHCR image is created by default.

The only release tag authorized by this specification is `v0.7.0`, and it may be created only after explicit owner authorization for one technically qualified candidate.

### 3.2 Exact release-candidate identity

For every attempt record:

~~~text
ATTEMPT = rc.N
RELEASE_CANDIDATE_SHA
CANDIDATE_IMAGE_ID_OR_DIGEST
I4_FINAL_REPORT
PREPUBLICATION_EVIDENCE_COMMIT_SHA
PUBLICATION_DECISION_COMMIT_SHA       # if separate
FINAL_TAG_TARGET_SHA                  # if published
FINAL_RELEASE_WORKFLOW_RUN_ID         # if published
FINAL_IMAGE_DIGEST                    # if published
POST_RELEASE_VERIFICATION_COMMIT_SHA  # if published
~~~

`RELEASE_CANDIDATE_SHA` is the merge commit on `main` of the release-preparation PR. Once selected, it is immutable.

Evidence-only readiness/decision/verification records do not move the candidate.

Any change after freeze to production code, public schema, qualification fixtures/oracles, release golden-path executable/profile, package metadata, dependency lock, Dockerfile, publication workflow, or security-relevant behavior creates a **new candidate attempt** and re-runs every affected mandatory gate.

### 3.3 Release-facing content re-freeze

Before candidate freeze, the release-preparation PR SHALL reconcile all release-facing v0.7 content with the I4 handoff.

At minimum:

1. product/package/runtime/MCP/Producer version is `0.7.0`;
2. the release golden path and client/demo documentation advertise **exactly five** read-only MCP tools, including `get_api_consumer_usage`;
3. the release golden path exercises the API-aware Current-State question through the public surface;
4. release notes state that the configured-access implementation is **qualified for APISIX only**;
5. release notes state the Route/Operation and target/Application-Service **mapping dependence**: without an explicit mapping or the frozen exact-match rule the association remains unresolved;
6. known limitations include F1–F3 and any still-applicable #323/security disposition;
7. release notes and CHANGELOG do not overclaim authorization, ownership, Intent, complete consumer population, or production/customer value;
8. the I4 pilot is described only as one bounded session with disposition `CONTINUE`, not user research.

### 3.4 Five-tool golden-path re-freeze

The release golden path SHALL be deliberately re-frozen for v0.7.

It SHALL:

- advertise exactly five read-only MCP tools;
- preserve the existing four tools and their meanings;
- exercise `get_api_consumer_usage` in query mode;
- exercise same-snapshot evidence resolution for the API-aware answer;
- demonstrate an expected unresolved/insufficient case rather than only a happy path;
- run against a pinned APISIX replay state already qualified by I4, not a new hand-authored semantic oracle;
- verify every public answer carries `producer.version = 0.7.0` and `build_revision = RELEASE_CANDIDATE_SHA`.

The golden path is release replay of already-qualified semantics. It MUST NOT invent new expected truth during I5.

### 3.5 Tyk `MODEL_GAP` stays scoped out

The I4 cross-source result remains:

~~~text
Tyk configured-access semantics => MODEL_GAP
v0.7 scope exclusion            => accepted
production gateway source       => APISIX only
~~~

I5 SHALL NOT fix or generalize the configured-access carrier for Tyk.

The first future non-APISIX adapter must first land the reviewed source-neutral amendment identified by I4. v0.7 release content must make the APISIX-only qualification boundary visible.

## 4. Candidate preparation — I5.1

The release-preparation PR SHALL contain every qualification-relevant release change before its merge becomes `RELEASE_CANDIDATE_SHA`.

Minimum content:

1. set version `0.7.0` consistently across active version-bearing surfaces, including `pyproject.toml`, root project version in `uv.lock`, runtime/MCP/Producer version pins, and release-version consistency tests;
2. update the four stale four-tool references identified by the I4 handoff:
   - `examples/release-golden-path/golden_path.py` (`TOOLS`);
   - `examples/mcp-clients/cursor.md`;
   - `examples/mcp-clients/vscode.md`;
   - `examples/runtime-demo/hero-demo.md`;
3. re-freeze the release golden path with the v0.7 API-aware phase (§3.4);
4. create `docs/release-validation/v0.7.0-release-notes.md`;
5. add the v0.7 release section to `CHANGELOG.md`, leaving the release candidate described as candidate-ready rather than already shipped;
6. update the release-validation index;
7. add the APISIX-only qualification statement, mapping-dependence statement, I4 pilot limitation, and known limitations;
8. update any MCP Registry/server metadata that is part of the repository release artifact to version `0.7.0`;
9. make any required release-workflow or security hardening **before** candidate freeze.

The release-preparation PR MUST NOT change I4 truth, expected answers, or replay fixtures merely to make release checks pass.

### Candidate-preparation evidence

Create:

`docs/release-validation/v0.7.0-rc.N-candidate-preparation.md`

It records at least:

- release-preparation PR and resulting merge SHA;
- version-bearing surfaces changed;
- five-tool list;
- golden-path source/profile identities;
- release-note scope and known limitations;
- APISIX-only/Tyk scope statement;
- mapping-dependence statement;
- publication workflow identity;
- security issue dispositions carried into the candidate.

## 5. Exact-candidate qualification — I5.2

Every mandatory qualification command SHALL run from a fresh isolated checkout at exactly `RELEASE_CANDIDATE_SHA` with a clean worktree.

At minimum:

~~~bash
test "$(git rev-parse HEAD)" = "$RELEASE_CANDIDATE_SHA"
test -z "$(git status --porcelain --untracked-files=all)"
~~~

No floating `main`, PR head, older I4 candidate, evidence commit, or later rebuilt image substitutes for the release candidate.

### 5.1 Repository and exact-SHA CI gate

Run the repository gate required by the current repository policy, including:

~~~bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run lint-imports
uv run pytest tests/unit
uv run pytest tests/integration
~~~

Also verify exact-SHA GitHub check-runs for every mandatory CI, CodeQL, dependency/security, and demo job. Missing, skipped, cancelled, or failed mandatory jobs block technical readiness unless the governing repository policy explicitly marks them non-mandatory.

### 5.2 Re-run v0.7 I4 qualification on the release candidate

Run the frozen v0.7 I4 qualification on the exact candidate:

~~~bash
uv run python -m evaluation.i4   --profile v0.7   --candidate-sha "$RELEASE_CANDIDATE_SHA"   --out "$OUT/i4"
~~~

Required:

- `status = PASS`;
- zero oracle mismatch;
- zero raw A/B canonical difference;
- service = REST = negotiated MCP semantically;
- all mandatory v0.7 cases present;
- APISIX replay, revision fencing, evidence resolution and legacy regressions pass;
- required exact-SHA check-runs are present.

I5 does not re-author or mutate the I4 oracle.

### 5.3 Re-run v0.7 API cost evidence

Run the existing v0.7 API-usage cost wrapper on the exact candidate:

~~~bash
uv run python -m evaluation.i4.api_usage_cost_run   --candidate-sha "$RELEASE_CANDIDATE_SHA"   --out "$OUT/api-usage-cost.json"
~~~

This is evidence, not an SLO.

Confirm only that the final candidate does not invalidate the accepted I4 disposition and that F1–F3 remain explicit. I5 does not require optimization before release merely because the known costs are visible.

### 5.4 Candidate image and release golden path

Build one candidate image from the exact SHA with:

~~~text
AIP_BUILD_REVISION = RELEASE_CANDIDATE_SHA
producer.version    = 0.7.0
~~~

Run the re-frozen release golden path against that image.

Required:

- all legacy phases still pass;
- exactly five MCP tools are advertised;
- the API-aware query phase passes;
- same-snapshot evidence drill-down passes;
- at least one expected unresolved/insufficient API-aware case remains explicit;
- every answer reports version `0.7.0` and the exact candidate build revision.

### 5.5 Version and public-surface gate

Verify at the candidate:

- package/runtime/MCP/Producer version = `0.7.0`;
- published v0.7 API-aware schemas match the actual public answer;
- existing v0.5/v0.6 public schemas and legacy tool meanings remain unchanged;
- exactly five MCP tools are advertised in deterministic order;
- `get_api_consumer_usage` request/output schemas match the published v0.7 contracts;
- REST and MCP remain read-only;
- release docs state APISIX-only qualification and mapping dependence;
- no release claim converts configured access or observed usage into authorization, ownership, policy, Intent, or “safe to change”.

### 5.6 Security, SBOM and public-content gate

Before technical `GO`, review:

- exact-SHA CodeQL;
- Semgrep;
- dependency audit;
- candidate-image HIGH/CRITICAL scan including unfixed findings;
- candidate-image SBOM;
- secrets/public-repository-content checks;
- credential/evidence exposure regressions;
- any still-open #323 or successor security finding.

Every new HIGH/CRITICAL or public-evidence exposure requires an explicit owner disposition. An undispositioned release-blocking finding yields `NO_GO`.

If the publication workflow changes during candidate preparation, its release scan/SBOM/digest path is part of the exact candidate and must be re-qualified.

## 6. Technical GO / NO_GO record — I5.3

Create:

`docs/release-validation/v0.7.0-release-readiness.md`

It names exactly one `RELEASE_CANDIDATE_SHA` and records:

- attempt id;
- source and candidate-image identity;
- exact commands and relevant tool/runtime versions;
- repository gate results;
- exact-SHA CI/check-run ids;
- I4 report and artifact digests;
- API cost artifact;
- golden-path result;
- version/schema/five-tool checks;
- security/SBOM findings and dispositions;
- APISIX-only/Tyk scope statement;
- mapping-dependence statement;
- I4 pilot `CONTINUE` carry-forward;
- every skipped, failed or unmeasured item;
- release blockers.

The technical decision is exactly:

~~~text
GO
NO_GO
~~~

`GO` means technically release-ready. It does **not** authorize publication.

If `NO_GO`, write `docs/release-validation/v0.7.0-rc.N-no-go.md` and either prepare a new candidate or return to the increment that owns the defect. Never repair a qualified SHA in place.

## 7. Publication authority — I5.4

After technical `GO`, the repository owner chooses one of:

~~~text
DO_NOT_PUBLISH
AUTHORIZE_V0.7.0_PUBLICATION
~~~

Record the decision in:

`docs/release-validation/v0.7.0-publication-decision.md`

No tag, GitHub Release, or final GHCR image is created before explicit owner authorization for the exact candidate.

If the owner chooses `DO_NOT_PUBLISH`, I5 may close as:

`RELEASE_READY_NOT_PUBLISHED`

and no shipped artifact is implied.

## 8. Publication — I5.5

If publication is authorized:

1. re-confirm the exact candidate and clean tagging state;
2. confirm `v0.7.0` does not already exist;
3. create annotated tag `v0.7.0` directly at `RELEASE_CANDIDATE_SHA`;
4. push the tag;
5. create the GitHub Release from the reviewed v0.7 release notes;
6. record the release workflow run and every attempt;
7. require the publication workflow to build from the tagged commit with `AIP_BUILD_REVISION = RELEASE_CANDIDATE_SHA`;
8. record the immutable GHCR digest as `FINAL_IMAGE_DIGEST`.

The final tag SHALL never point at a readiness, publication-decision, or evidence-only commit.

A failed publication SHALL NOT be “fixed” by moving or recreating the tag. Stop and disposition the failure.

## 9. Post-publication verification — I5.6

Verification targets the **tagged source and immutable published digest**, not a local rebuild.

Create:

`docs/release-validation/v0.7.0-post-release-verification.md`

### 9.1 Release identity

Verify:

- annotated `v0.7.0` dereferences to `RELEASE_CANDIDATE_SHA`;
- GitHub Release is final, not draft/prerelease;
- publication workflow head SHA equals the candidate;
- `FINAL_IMAGE_DIGEST` is immutable and recorded;
- published image reports product version `0.7.0` and full candidate build revision.

### 9.2 Anonymous digest pull

Using an empty/anonymous Docker configuration where practical, pull:

~~~text
ghcr.io/michaelegner/architecture-intelligence-platform@sha256:<FINAL_IMAGE_DIGEST>
~~~

Verify registry/content digest equality.

Mutable `v0.7.0` or `latest` tags alone are not sufficient evidence.

### 9.3 Published-image security and SBOM

Verify publication artifacts are bound to `FINAL_IMAGE_DIGEST`:

- SBOM;
- full HIGH/CRITICAL report;
- code-scanning/tag state;
- owner dispositions;
- zero undispositioned release blocker.

### 9.4 Tagged-source and published-image golden path

From a clean checkout of the tagged source, run the release golden path against the pulled immutable image digest.

Required:

- all legacy phases pass;
- exactly five tools are advertised;
- API-aware query passes;
- same-snapshot evidence drill-down passes;
- unresolved/insufficient behavior remains explicit;
- all answers report version `0.7.0` and `build_revision = RELEASE_CANDIDATE_SHA`.

### 9.5 API-aware published smoke

Against the published image, verify at least one bounded APISIX replay question through:

~~~text
service/REST result
==
negotiated MCP result
~~~

and resolve at least one evidence ref against the same snapshot.

This is a release-artifact smoke over the already-qualified I4 truth, not a new oracle.

### 9.6 Registry and release links

If MCP Registry publication is part of the release workflow, verify the registry lists `0.7.0` as the intended current version.

Verify all links in the GitHub Release body resolve to content that exists at the release tag, except any explicitly documented closure-link step that necessarily targets the post-release closure commit.

## 10. Closure — I5.7

After successful post-publication verification, create the I5 completion record:

`docs/specifications/0.7.0/i5-completion-record.md`

and update the normal release closure surfaces:

- release-validation index;
- README latest release;
- ROADMAP shipped status;
- v0.7 specification/I5 status as appropriate.

The completion record SHALL state one terminal outcome and cite the exact candidate, tag, workflow and digest identities.

## 11. Stop conditions

Before publication, stop the current attempt as `NO_GO` if any of these occur:

- candidate identity is ambiguous or the qualification checkout is dirty;
- mandatory exact-SHA CI/checks are missing or fail;
- I4 qualification is not `PASS`;
- A/B, service, REST or MCP semantics differ;
- the APISIX replay or evidence/snapshot fences regress;
- legacy v0.5/v0.6 tool meanings regress;
- the golden path does not advertise exactly five tools;
- the published v0.7 schema and actual API-aware response diverge;
- release content hides the APISIX-only qualification boundary or mapping dependence;
- version/build identity is inconsistent;
- security/SBOM findings remain undispositioned;
- release notes overclaim authorization, ownership, Intent, complete usage, production capacity, customer value, or pilot evidence.

After publication, any tag/digest/build-revision mismatch, failed anonymous pull, published-image golden-path failure, API-aware published-smoke failure, or final security blocker yields `POST_RELEASE_FAILED`.

## 12. Definition of Done

### Technical readiness

One exact candidate is technically ready only when:

1. release-facing content is re-frozen for v0.7;
2. version `0.7.0` is consistent;
3. exactly five MCP tools are documented and advertised;
4. repository gate and exact-SHA CI/security checks pass;
5. v0.7 I4 qualification passes unchanged on the release candidate;
6. API cost evidence is rerun and accepted limitations remain explicit;
7. candidate image golden path passes, including API-aware query/evidence behavior;
8. public schemas and actual service/REST/MCP surfaces agree;
9. APISIX-only qualification and mapping dependence are explicit;
10. candidate security/SBOM review has no undispositioned blocker;
11. `v0.7.0-release-readiness.md` says `GO`.

### Unpublished success

If technical readiness passes but publication is not authorized:

> **`RELEASE_READY_NOT_PUBLISHED`** — v0.7.0 is technically qualified on the recorded exact candidate, but no release/tag/final image is claimed.

### Published success

If publication is authorized:

> **`SHIPPED_VERIFIED`** — the exact qualified candidate is tagged as v0.7.0, the immutable published image digest identifies that candidate, final security/SBOM evidence is bound to that digest, and the tagged-source/published-image golden path including the API-aware query and evidence drill-down passes.

## 13. Permitted release claim

Only after technical `GO`, and as a shipped claim only after `SHIPPED_VERIFIED`:

> **AIP v0.7.0 adds API-aware Current State for the qualified APISIX source: it deterministically relates configured consumer access to independently observed consumer-attributed usage in an explicit environment and observation window, while preserving unresolved associations, measurement coverage, provenance and same-snapshot evidence. It does not turn configured access or observed usage into authorization, ownership, policy, architectural Intent or proof that a change is safe.**

The release notes SHALL also state:

- the configured-access implementation is qualified for APISIX only;
- associations may require explicit operator mapping when exact reconciliation cannot establish them;
- the product-value pilot disposition `CONTINUE` comes from one bounded session, not user research.
