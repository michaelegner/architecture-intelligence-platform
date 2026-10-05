# AIP v0.6.0 I6 — Release Candidate, Publication, and Verification

**Status:** Proposed — revision 0.1, for owner review. This specification freezes I6 release-process decisions; it does not claim that a v0.6.0 release candidate has been prepared, technically qualified, authorized for publication, published or verified.  
**Increment:** I6 — Release Candidate, Publication, and Verification.  
**Entry:** I5 is complete and merged. The [I5 completion record](i5-completion-record.md) records `TECHNICAL_QUALIFICATION_COMPLETE` for the bounded I5 scope and a product pilot disposition of `NOT_RUN`. I5 does **not** qualify a later I6 candidate or authorize publication.  
**Authority:** accepted [v0.6.0 parent specification](specification.md), especially §§26–31 and §33; [I5 completion record](i5-completion-record.md); [I4 completion record](i4-completion-record.md); [I3 completion record](i3-completion-record.md); [I2 decision record D16](i2-decision-record.md#d16--the-default-flip-is-deferred-added-in-i25c-amends-d1); [ROADMAP](../../../ROADMAP.md); and the proven [v0.5.0 I6 process](../0.5.0/i6-release-candidate-publication-and-post-release-verification.md) as process precedent only.

## 1. Purpose and terminal outcomes

I6 turns the completed v0.6 implementation and evidence into **one exact final release candidate**, independently re-runs the mandatory qualification on that SHA, separates technical readiness from publication authority, and—only if authorized—publishes and verifies the exact tagged source and GHCR artifact.

I6 SHALL NOT add architecture semantics, another locality dimension, another source family, Intent, causal/path reasoning, Workload-level absence semantics, a fifth MCP tool, historical snapshots, retention/compaction, or a product-pilot result.

The only terminal outcomes are:

```text
RELEASE_READY_NOT_PUBLISHED
  all mandatory technical gates passed on the exact candidate;
  the owner did not authorize publication;
  no v0.6.0 tag/GitHub Release/final image is claimed

SHIPPED_VERIFIED
  the owner authorized publication;
  the exact qualified candidate was tagged and published;
  tagged source and final GHCR digest passed post-publication verification

NO_GO
  one or more mandatory pre-publication gates failed or remain undispositioned

POST_RELEASE_FAILED
  publication occurred, but mandatory verification of the tagged/published artifact failed
```

A green PR or locally built image is not a release. A Git tag alone is not a release. A successful publication workflow alone is not `SHIPPED_VERIFIED`.

## 2. Frozen I6 decisions

I6 revision 0.1 freezes the following decisions before candidate preparation.

### 2.1 Candidate attempts and RC tags

Candidate attempts are labelled `rc.1`, `rc.2`, … **in release evidence only**.

No `v0.6.0-rc.N` Git tag, GitHub prerelease or GHCR prerelease image is created by default. The only release tag authorized by this specification is the final `v0.6.0` tag, and it may be created only after the repository owner explicitly authorizes publication of a technically qualified candidate.

If an external prerelease artifact becomes necessary, amend this specification before creating one.

### 2.2 Scoped-evidence default

The release candidate SHALL change `telemetry.scoped-evidence.enabled` from default `false` to default **`true`**.

This is the reviewed D16 default flip deferred from I2/I3. It does **not** change v0.5 unscoped dependency semantics and does not make missing local evidence positive. It enables the already-qualified v2 ingestion path when admissible CLIENT caller identity is present.

Migration rule:

- an existing configuration that omits `telemetry.scoped-evidence` adopts the new v0.6 default and may begin writing the isolated v2/transition state when qualifying telemetry arrives;
- an operator who requires the legacy v0.5 ingestion behavior SHALL explicitly set `telemetry.scoped-evidence.enabled: false`;
- documentation and release notes SHALL state this clearly;
- the v0.5 no-v2 canonical snapshot/fingerprint pins remain byte-identical because operational `ScopedEvidence*` nodes are not unconditional canonical-state inputs.

### 2.3 Golden-path re-freeze

The v0.6 release golden path SHALL be re-frozen deliberately, not silently patched.

It SHALL:

1. advertise exactly **four** read-only MCP tools, including `get_service_dependencies_by_locality`;
2. update the pinned example/client documentation which still says “three tools”;
3. exercise the default-on scoped-evidence configuration;
4. deliberately re-pin the runtime-demo whole-graph node-count oracle to include the two expected internal `ScopedEvidence*` operational nodes created by the default-on transition path; do **not** generically exclude internal nodes merely to preserve the old count;
5. retain the original v0.5/no-v2 canonical snapshot ID and answer semantics;
6. add a **locality phase** using the immutable actual I5 controlled reference and adopted oracle, so the release image proves:
   - caller-locality enumeration without supplied Workload IDs,
   - W1/pricing `CONFIRMED` and W2/legacy-pricing `OBSERVED_ONLY` under C1,
   - same-snapshot scoped evidence drill-down,
   - selected-locality comparison,
   - C2 unresolved P1 / preserved P2,
   - stale C1 refusal,
   - no target-locality, local-absence or global/exclusive-use inference.

The locality phase is a release replay of already-qualified evidence, not a new capture or a new oracle.

### 2.4 ROADMAP reconciliation

Before candidate freeze, update the v0.6 ROADMAP entry to match the accepted release scope.

The v0.6 minimum shipped locality surface is:

- environment;
- whole-UTC-day observation context;
- evidenced caller cluster identity;
- namespace;
- exact captured Workload identity through CLIENT Pod UID → Kubernetes owner chain;
- bounded direct HTTP `CALLS` only.

The ROADMAP SHALL explicitly mark **region, tenant, service-version locality and messaging locality as deferred/unassigned candidates**. Do not assign them to v0.7 or v0.8 by implication; those releases retain their own Current-State/API and later Intent/Assessment boundaries.

### 2.5 Public versioning

Candidate preparation SHALL set the product version to `0.6.0` consistently across all active version-bearing surfaces.

- `pyproject.toml [project].version = 0.6.0`;
- root project version in `uv.lock = 0.6.0`;
- runtime package version, Producer version and MCP advertised server version = `0.6.0`;
- release-version consistency tests pin `0.6.0`.

Public contract versions remain intentionally split:

- legacy ArchitectureAnswer and the original three tools keep public schema version `0.5` and their existing meanings;
- the new locality request/answer remains the published locality-specific `0.6` schema;
- product version and public schema version are not interchangeable.

### 2.6 Known issue #323

[#323](https://github.com/michaelegner/architecture-intelligence-platform/issues/323), the legacy natural-language path exposure of Kubernetes-sourced Evidence, MUST receive an explicit owner security/release disposition before candidate freeze.

Allowed dispositions are:

- **FIX_BEFORE_RELEASE** — fix it, add the acceptance regression, and create a new candidate followed by all affected and mandatory qualification; or
- **KNOWN_LIMITATION_ACCEPTED_FOR_V0.6.0** — record why the legacy NL path exposure is bounded/non-blocking for this pre-1.0 release, identify the owner, include it in release notes/security evidence, and carry the issue open.

It may not remain an unmentioned open finding in a technical `GO` record.

The I5 `NOT_RUN` product pilot remains a separate product-value gap carried to the v1.0-rc stable-contract admission ledger; it does not silently become a v0.6 technical release blocker.

## 3. Release identity model

For each attempt record:

```text
ATTEMPT = rc.N
RELEASE_CANDIDATE_SHA
CANDIDATE_IMAGE_ID_OR_DIGEST
I4_FINAL_REPORT
I5_FINAL_REPORT
PREPUBLICATION_EVIDENCE_COMMIT_SHA
PUBLICATION_DECISION_COMMIT_SHA       # if decision is committed separately
FINAL_TAG_TARGET_SHA                  # if published
FINAL_RELEASE_WORKFLOW_RUN_ID         # if published
FINAL_IMAGE_DIGEST                    # if published
POST_RELEASE_VERIFICATION_COMMIT_SHA  # if published
```

`RELEASE_CANDIDATE_SHA` is the merge commit on `main` of the candidate-preparation PR. After freeze it is immutable.

Evidence-only records, qualification reports and owner-decision commits do not move the candidate. Any change to production code, schema, fixture/oracle, default configuration, release golden-path executable/profile, packaging, dependency lock, Dockerfile, release workflow or security behavior after freeze creates a **new candidate attempt**.

A candidate-level `NO_GO` is permanent for that SHA.

## 4. Candidate preparation (I6.1)

The candidate-preparation PR SHALL contain all qualification-relevant release changes before its merge becomes `RELEASE_CANDIDATE_SHA`.

Minimum content:

1. product version `0.6.0` and lock/version-test consistency;
2. D16 default flip to `true` plus migration/configuration documentation;
3. four-tool release golden-path re-freeze and new locality phase;
4. deliberate runtime-demo node-count re-pin;
5. ROADMAP v0.6 narrowed-scope/deferred-dimension reconciliation;
6. v0.6.0 release notes and `CHANGELOG.md` release section, written as candidate-ready but not “shipped”;
7. release documentation/examples for the locality request, evidence mode, completeness/coverage and C1→C2 limitation;
8. confirmation that `schemas/architecture_intelligence/v0.6/*` are the published locality schemas and legacy v0.5 schemas remain intact;
9. any required release-workflow/security hardening **before** tag publication;
10. an explicit #323 disposition or the reviewed fix.

Candidate preparation MUST NOT rewrite the adopted I5 oracle or actual capture to match output.

### Candidate evidence file

Create:

`docs/release-validation/v0.6.0-rc.N-candidate-preparation.md`

It records:

- exact candidate-preparation PR and merge SHA;
- changed version-bearing surfaces;
- ROADMAP before/after scope;
- D16/default migration decision;
- golden-path file/profile checksums;
- four-tool list;
- locality-phase source/oracle identities;
- release-workflow identity;
- #323 disposition;
- known limitations and deferred product pilot.

## 5. Exact-candidate qualification (I6.2)

Every mandatory command SHALL run from a fresh isolated checkout at exactly `RELEASE_CANDIDATE_SHA` with a clean worktree.

At minimum assert:

```bash
test "$(git rev-parse HEAD)" = "$RELEASE_CANDIDATE_SHA"
test -z "$(git status --porcelain --untracked-files=all)"
```

No floating `main`, dirty worktree, evidence commit, rebuilt later image or older I4/I5 candidate substitutes for this SHA.

### 5.1 Repository and CI gate

Run the repository gate in order:

```bash
uv run ruff format .
uv run ruff check .
uv run pyright
uv run lint-imports
uv run pytest tests/unit
uv run pytest tests/integration
```

The formatting command must leave the clean candidate unchanged. Verify exact-SHA CI/check runs for all mandatory CI and CodeQL jobs; missing, skipped or failed mandatory jobs block qualification.

### 5.2 I4 deterministic semantic qualification

Run the I4 independent two-process/fresh-Neo4j qualification on the final candidate:

```bash
uv run python -m evaluation.i4 \
  --candidate-sha "$RELEASE_CANDIDATE_SHA" \
  --out "$OUT/i4"
```

Required result: `status = PASS`, zero oracle mismatch, zero raw canonical A/B difference, zero service/REST/MCP semantic difference, all required I4 cases and mandatory exact-SHA CI checks present.

Re-run the I4 growth/churn/locality benchmarks against the same candidate using their explicit candidate parameters. The owner SHALL confirm that the already-accepted bounded I4 cost disposition is not invalidated by the final-candidate measurements. This remains a bounded qualification, not a production SLO.

### 5.3 Actual I5 controlled-reference qualification

Use the unchanged adopted oracle carried by merge `c5bc7cb58d4d6efef80b744347c51f36d14b6356` and the immutable I5.1 capture.

```bash
uv run python -m evaluation.i5.qualify run \
  --candidate "$RELEASE_CANDIDATE_SHA" \
  --expectation-commit c5bc7cb58d4d6efef80b744347c51f36d14b6356 \
  --output "$OUT/i5-actual"
```

Required result:

- both clean workers `CORRECT`;
- all 17 public-contract cases per run;
- exactly the complete canonical artifact set;
- raw A/B byte equality;
- service/REST/negotiated-MCP semantic equality;
- 52/52 recorded replay requests accepted by Collector and AIP in each worker;
- C1/C2 truth unchanged;
- no oracle/source hash mutation.

### 5.4 Full Quarkus and Airflow revalidation

Re-run the **full pinned v0.5 Quarkus Super Heroes and Apache Airflow procedures** from the I5.3 retained scripts/evidence on the same `RELEASE_CANDIDATE_SHA`.

Do not replace them with bundled synthetic scenarios.

Required outcomes preserve the I5.3 truth:

- Quarkus: all supported facts remain correct, forbidden facts absent, original unsupported constructs preserved, no fabricated caller-locality facts;
- Airflow: supported facts remain correct, forbidden facts absent, original unsupported/unresolved/insufficient-evidence cases preserved;
- source modes remain unchanged;
- public direct service, REST and negotiated MCP reads agree;
- read paths write zero graph state;
- locality query correctly abstains on both systems because they lack the required scoped-v2 caller evidence.

Any material mismatch is a candidate-level `NO_GO`.

### 5.5 v0.5.1 task-led demo regression

Re-run the original Quarkus developer demo against the exact candidate and verify:

- original no-v2 snapshot pin unchanged;
- dependency/drift/evidence answers remain correct;
- ordinary locality query abstains;
- four tools are advertised;
- no scoped-v2 key is fabricated;
- the demo remains runnable without an LLM for correctness.

### 5.6 Candidate release golden path

Build one candidate image from the exact SHA with:

```text
AIP_BUILD_REVISION = RELEASE_CANDIDATE_SHA
producer.version    = 0.6.0
```

Run the re-frozen release golden path against that image.

The profile SHALL pass all existing v0.5 phases plus the new locality phase. Every answer must carry the candidate build revision. The locality phase must demonstrate same-snapshot query→evidence behavior and C1/C2 refusal semantics under the v0.6 schema.

### 5.7 Version, schema and migration gate

Verify at the candidate:

- package/MCP/Producer version = `0.6.0`;
- legacy public schema version remains `0.5`;
- locality request/answer validate against published `v0.6` JSON Schemas;
- exactly four MCP tools are advertised in deterministic order;
- no fifth tool or hidden schema widening;
- D16 default is true;
- explicit `enabled: false` preserves legacy v1-only ingestion behavior;
- no-v2 canonical snapshot/golden pins remain unchanged;
- migration docs explain the default change and the v1/v2 coexistence/transition ledger.

### 5.8 Security and SBOM gate

Pre-publication security review includes:

- exact-SHA CodeQL;
- Semgrep;
- `pip-audit`;
- container HIGH/CRITICAL scan including unfixed findings;
- candidate-image SBOM;
- dependency/lock review since v0.5.1;
- secrets/public-repository-content checks;
- #323 disposition;
- any new locality evidence/ref exposure check.

Every HIGH/CRITICAL, public-evidence exposure or other security finding gets an explicit disposition tied to the exact candidate/image. An undispositioned release-blocking finding yields `NO_GO`.

The existing digest-bound `.github/workflows/docker.yml` publication scan/SBOM path SHALL remain functional; if modified, the workflow change belongs in candidate preparation and creates a new candidate.

## 6. Technical GO/NO_GO record

Create:

`docs/release-validation/v0.6.0-release-readiness.md`

This evidence-only record names one exact `RELEASE_CANDIDATE_SHA` and contains:

- candidate attempt;
- source and candidate-image identity;
- exact commands and environment/tool versions;
- I4 report/artifact digests;
- I5 actual-reference report/artifact digests;
- full Quarkus/Airflow results;
- demo/golden-path results;
- version/schema/default/migration checks;
- exact-SHA CI/check-run IDs;
- candidate SBOM/security findings and owner dispositions;
- #323 disposition;
- ROADMAP reconciliation;
- product pilot `NOT_RUN` carry-forward;
- every skipped/failed/unmeasured item;
- release blockers.

The technical decision is exactly `GO` or `NO_GO`.

`GO` means **technically release-ready**, not publication-authorized.

If `NO_GO`, write `docs/release-validation/v0.6.0-rc.N-no-go.md` and either prepare a new candidate or return to the owning semantic increment. Never repair a qualified SHA in place.

## 7. Publication authority (I6.3)

After a technical `GO`, the repository owner chooses one of:

- **DO_NOT_PUBLISH** → terminal `RELEASE_READY_NOT_PUBLISHED`; or
- **AUTHORIZE_V0.6.0_PUBLICATION** → publication may proceed for exactly that candidate.

Record the decision in:

`docs/release-validation/v0.6.0-publication-decision.md`

No tag, GitHub Release or final GHCR image is created before explicit authorization.

For an unpublished closure, create `docs/specifications/0.6.0/i6-completion-record.md` with `RELEASE_READY_NOT_PUBLISHED` and stop. No final artifact is implied.

## 8. Publication procedure (I6.4)

If authorized:

1. confirm clean local/tagging state and `HEAD == RELEASE_CANDIDATE_SHA`;
2. create annotated tag `v0.6.0` directly at `RELEASE_CANDIDATE_SHA`;
3. push that tag;
4. create the GitHub Release from the reviewed `docs/release-validation/v0.6.0-release-notes.md` using the existing tag;
5. record the release workflow run and every attempt;
6. require the release workflow to build from the tagged commit with `AIP_BUILD_REVISION = RELEASE_CANDIDATE_SHA`;
7. record the immutable pushed GHCR digest.

The final tag SHALL never point at an evidence/decision commit.

If publication fails before a usable final digest exists, stop and disposition the workflow failure. Do not retag a different SHA under `v0.6.0`.

## 9. Published-artifact verification (I6.5)

Verification targets the **published digest and tagged source**, not a local rebuild.

Create:

`docs/release-validation/v0.6.0-post-release-verification.md`

Required checks:

### 9.1 Identity

- annotated `v0.6.0` tag dereferences to `RELEASE_CANDIDATE_SHA`;
- GitHub Release is final, not draft/prerelease;
- publication workflow head SHA equals candidate;
- `FINAL_IMAGE_DIGEST` is recorded and syntactically immutable;
- image labels/environment expose product version `0.6.0` and full candidate build revision.

### 9.2 Anonymous immutable pull

Remove GHCR credentials/cached target where practical and anonymously pull:

`ghcr.io/michaelegner/architecture-intelligence-platform@sha256:<FINAL_IMAGE_DIGEST>`

Verify registry/content digest equality. Mutable `v0.6.0` or `latest` tags are not sufficient evidence.

### 9.3 Final security/SBOM evidence

From the publication workflow:

- bind SBOM to `FINAL_IMAGE_DIGEST`;
- bind the full HIGH/CRITICAL report to the same digest;
- compare candidate and final-artifact security findings;
- record code-scanning/tag state and owner dispositions;
- require zero undispositioned release-blocking finding.

### 9.4 Tagged-source verification

Fresh-clone the `v0.6.0` tag and verify:

- `HEAD == RELEASE_CANDIDATE_SHA`;
- product version `0.6.0`;
- public schemas and golden-path checksums;
- exact four-tool contract;
- ROADMAP narrowed/deferred scope;
- release notes;
- release workflow definition;
- version-consistency test.

### 9.5 Published-image golden path

From the tagged-source clone, run the same re-frozen golden-path command against **only** `FINAL_IMAGE_DIGEST`.

All legacy phases and the locality phase must pass. Specifically re-execute from the published image:

- one C1 locality enumeration;
- one selected-locality comparison;
- one same-snapshot scoped evidence drill-down;
- one C2 unresolved/stale-boundary check.

The returned Producer build revision must equal `RELEASE_CANDIDATE_SHA`; locality answers validate against the v0.6 schema.

### 9.6 Final release content

Verify release body/notes accurately state:

- bounded direct HTTP caller-locality capability;
- initial supported dimensions;
- region/tenant/service-version/messaging locality deferred/unassigned;
- no local absence/target-locality/global-exclusivity/causal-path claim;
- D16 default-on migration;
- actual controlled capture versus synthetic/real-system evidence distinction;
- I4 measured-cost/production-capacity limitation;
- product pilot `NOT_RUN` and v1.0-rc carry-forward;
- #323 disposition;
- all other material unsupported/unresolved limitations.

## 10. Documentation and ROADMAP closure

Candidate preparation updates scope, migration and release notes before freeze.

After the terminal outcome:

- if `SHIPPED_VERIFIED`, update ROADMAP v0.6 status to shipped with tag/date and link the post-release verification;
- if `RELEASE_READY_NOT_PUBLISHED`, do not call v0.6 shipped; link the readiness record/terminal disposition instead;
- if `NO_GO` or `POST_RELEASE_FAILED`, record the failure and do not advance the roadmap as shipped.

No documentation-only status update may rewrite the immutable tag target.

## 11. Execution slices

| Slice | Work | Exit evidence |
|---|---|---|
| **I6.1 — Candidate preparation** | version 0.6.0; D16 default-on; golden path re-freeze/four tools/locality phase; ROADMAP scope reconciliation; release notes; #323 disposition | `v0.6.0-rc.N-candidate-preparation.md` and one immutable `RELEASE_CANDIDATE_SHA` |
| **I6.2 — Exact-candidate qualification** | full repo gate, I4, I5 actual A/B, full Quarkus/Airflow, demo, candidate golden path, version/schema/security/SBOM | `v0.6.0-release-readiness.md` with `GO` or candidate-level `NO_GO` |
| **I6.3 — Owner publication decision** | separate technical result from authorization | `v0.6.0-publication-decision.md`; either unpublished closure or authorization |
| **I6.4 — Publication** | final tag, GitHub Release, release workflow, immutable GHCR digest | tag/release/workflow/digest identities |
| **I6.5 — Published verification and closure** | anonymous digest pull, final SBOM/security, tagged source, published-image golden path/locality drill-down | `v0.6.0-post-release-verification.md` + I6 completion record |

## 12. Stop conditions

Stop and mark the current attempt `NO_GO` if any of the following occurs before publication:

- final candidate identity is ambiguous or dirty;
- mandatory exact-SHA CI is missing/failed;
- I4 or I5 A/B differs, oracle mismatch occurs, or required case is skipped;
- Quarkus/Airflow supported truth changes or a preserved limitation is incorrectly “resolved”;
- no-v2 snapshot compatibility breaks;
- service/REST/MCP locality semantics differ;
- golden path does not advertise exactly four tools;
- D16 default-on behavior is not deliberately reflected in the golden oracle;
- the published v0.6 schema and actual response diverge;
- a new locality/ref exposure is found;
- #323 has no explicit release disposition;
- security/SBOM findings are undispositioned;
- version, tag, candidate or image build identity disagrees;
- release notes overclaim locality, production capacity, customer value or pilot evidence.

After publication, any tag/digest/build-revision mismatch, failed anonymous pull, published-image golden-path failure, or final security blocker yields `POST_RELEASE_FAILED`.

## 13. Definition of Done

### Technical readiness

A candidate is technically ready only when all of these hold on **one exact SHA**:

1. version 0.6.0, ROADMAP scope, D16 migration and four-tool contract are frozen;
2. repository gate and mandatory exact-SHA CI/CodeQL pass;
3. I4 independent qualification passes twice from clean state with byte-identical semantics;
4. final-candidate growth/churn evidence is re-run and dispositioned;
5. actual I5 reference passes two clean A/B workers unchanged;
6. full Quarkus and Airflow qualification remains truthful;
7. original Quarkus no-v2 demo remains compatible;
8. candidate golden path passes, including the new locality phase;
9. schemas/version/default migration checks pass;
10. candidate security/SBOM review has no undispositioned release blocker;
11. #323 has an explicit release disposition;
12. `v0.6.0-release-readiness.md` says `GO`.

### Unpublished success

If technical readiness passes but publication is not authorized:

> **`RELEASE_READY_NOT_PUBLISHED`** — AIP v0.6.0 is technically qualified on the recorded exact candidate, but no release/tag/final image is claimed.

### Published success

If publication is authorized:

> **`SHIPPED_VERIFIED`** — the exact qualified candidate is tagged as v0.6.0, the published GHCR digest identifies that candidate, final SBOM/security evidence is bound to that digest, and the tagged-source/published-image golden path—including locality query and same-snapshot evidence drill-down—passes independently.

## 14. Permitted release claim

Only after technical qualification, and as a shipped claim only after `SHIPPED_VERIFIED`:

> **AIP v0.6.0 discovers bounded evidenced caller localities, establishes supported direct HTTP `CALLS` within their admitted UTC-day observation contexts, and deterministically compares qualified local Current-State results without inventing global truths, negative dependencies, Intent or causal flows. The initial locality-qualified relation/dimension surface is explicitly narrower than the full roadmap candidates.**

The product pilot remains `NOT_RUN`. I6 does not turn technical qualification into evidence of customer value or v1.0 stable-contract readiness.
