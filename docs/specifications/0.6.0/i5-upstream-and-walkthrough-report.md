# I5.3 upstream qualification and walkthrough

**Result: CORRECT for the bounded I5.3 scope.** Governing: merged I5 revision 0.1 §§5–6 and §8 I5.3, accepted parent specification, unchanged v0.5 upstream dossiers and v0.5.1 demo pins. No production code, public API, schema, default, original dossier or golden-path pin changed.

## Candidate and evidence

Qualified executable candidate: `8df3d118a967a650cbc5b3c6fa40db0e2adaa3eb`. Both full upstream runs, controlled-reference A/B and the isolated demo use this explicit build revision. Later walkthrough/report/archive commits are documentation and evidence; they do not claim a new qualified executable candidate.

[Raw archive](i5-qualification-artifacts/i5.3-upstream-and-demo.tar.gz), [per-file manifest](i5-qualification-artifacts/i5.3-artifact-manifest.json) and [checksums](i5-qualification-artifacts/SHA256SUMS) retain source/configuration hashes, candidate and image identities, full-run scripts/logs, original comparator inputs/results, observation windows, service/REST/negotiated MCP transcripts, read-only graph checks, actual-reference process/container identities and mandatory-gate logs/JUnit. Archive SHA-256: `47819d9c95efb3decea08882a2338af52a464a42bb86b03631c4f4493cefea32`.

Original actual-reference expectation commit: `e48cae8f9842bd197061ba1b2c38ccd78f67b608`. Its byte-identical squash-merge carrier `c5bc7cb58d4d6efef80b744347c51f36d14b6356` is the ancestry-verifiable expectation argument for the unchanged runner. This is not a new adoption or rewritten oracle; Michael's original pre-evaluation adoption remains authoritative.

## Dispositions

| Run | Result and retained limitations |
| --- | --- |
| Full pinned Quarkus | 45 supported facts correct, 0 missing/incorrect; all 4 forbidden facts absent; 0 critical semantic errors. Original 3 unsupported constructs remain. Six upstream services rebuilt from the original pin with frozen builder/base recipes; fixed image identities verified before traffic. `DECLARED_MANIFEST` stays declaration-only; no scoped Pod evidence or fabricated local calls. |
| Full pinned Airflow | 9 supported facts correct, 0 missing/incorrect; both forbidden facts absent; 0 critical semantic errors. Original 3 unsupported constructs, 2 unresolved identities and 1 insufficient-evidence case remain. Native traffic and two workers executed; no fabricated role Services, application dependencies or messaging entities. |
| Upstream public reads | Dependencies/drift agree across direct service, REST and initialized negotiated MCP on each run. Quarkus's 8 refs resolve at the same snapshot; Airflow carries none. Whole-graph before/after checks match: zero writes. Both genuinely lack local observations and return no positive locality with coverage unavailable. Four-tool listing follows the frozen v0.6 I3 contract; existing three-tool semantics remain compatible. |
| Actual controlled reference | Both fresh processes pass the adopted oracle; 70 raw canonical artifacts match. C1 establishes W1/pricing confirmed and W2/legacy-pricing observed-only. C2 retains unresolved P1, eligible P2 and stale-read refusal; no reassignment or invented absence. Original 52-request recording is replayed once per run. |
| Task-led demo | Original no-v2 snapshot `aip:snapshot:v1:dc21e13dcf235b7526433318104531fc1edd944359a6a12b05d4843e4f4120fc` unchanged; pinned answer checks and same-snapshot evidence pass. Ordinary HTTP locality query abstains with complete inventory and unavailable local coverage. No v2 canonical keys exist. The demo's operator messaging overlay remains distinct from upstream truth and actual-reference traffic. |

No missing supported positive, source-mode drift, reference leak, adapter disagreement, nondeterminism or critical semantic defect remains in these runs. Unsupported/identity/evidence gaps are preserved, not cleared. Synthetic pagination/cap coverage remains synthetic; the actual reference's stale cursor is a protocol-generated negative control.

## Walkthrough and validation

The main Quarkus entry point links the [companion walkthrough](../../real-world-validation/v0.6.0/locality-walkthrough.md). It reuses existing commands and generated transcripts: Quarkus before a service edit, separately labelled actual C1 discovery without Workload IDs, selected comparison/evidence, C2 promotion limits and honest abstention. No new launcher or test framework. Replay requires no live cluster, upstream build, Kafka or LLM after dependencies/build images are available.

Required local gate: Ruff format/check, Pyright and all 8 import contracts passed; **3,485 unit tests passed; 803 integration tests passed, 1 skipped**. The suite skipped the fixed-name demo because the owner's existing stopped project existed. An isolated explicit-candidate demo was run successfully instead; the owner's project was untouched. Required CI identity/status will be retained in the PR. No new tests were added.

## Reconciliation against the retained plan

**Completed:** fresh worktree and one explicit candidate; full unchanged v0.5 upstream comparisons once each; actual-reference A/B on that candidate; task-led walkthrough with exact generated transcripts; compact report and raw archive.

**Deviations:** Michael approved `/tmp/aip-i5.3` instead of the profiles' frozen host checkout path; container paths, configured roots, source modes and all original dossier bytes remained unchanged. Quarkus's fresh clone reused verified Git objects only. The demo qualification wrapper supplies the candidate build argument and an isolated project name, then invokes the unchanged demo; it is an execution record, not a shipped launcher. The first documentation placement tripped the golden-path checksum guard, so the companion moved outside `examples/`, preserving the I6-owned pins. The corrected candidate reran the local gate and actual-reference A/B; discarded/preflight runs are not promoted to final qualification. Scratch public-read checks were corrected for native Neo4j timestamp representation and typed claim/graph fields without changing any expected fact or production code. Whole-graph dumps serve within-run zero-write checks; their formatting is not controlled-reference canonical-byte qualification. The optional demo graph dump omits external mapping context and is explicitly labelled; the production snapshot pin is verified through real answers.

**Specification questions:** none requiring a semantic decision. The sole frozen-path exception was explicitly approved.

**Deferred/limits:** I5.4 owns completion, pilot disposition and I6 handoff; #323 remains open. I6 must rerun against its final candidate. Accepted I4 measured-cost/retained-state limitations remain; production capacity, customer outcomes and release readiness are not established.
