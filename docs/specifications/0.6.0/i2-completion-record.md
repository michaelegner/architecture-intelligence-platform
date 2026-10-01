# AIP v0.6.0 I2 — Completion Record

**Status:** **COMPLETE.** Closed by PR #376, merge `46f700ee4a67399a67e406c8e445db572fd0a31a` (2026-09-30T20:22:25Z). The closure SHA was written into this record by a follow-up PR, because a PR cannot record its own merge commit (the two-step closure pattern, as for I1 in #318).
**Release / increment:** `v0.6.0` — Locality-Aware Current State / I2.
**Governing specification:** [I2 specification](i2-scoped-evidence-and-qualified-local-assessment.md) revision 0.4, merged in #312 (`6cebe35b1c520f754c6306a5ff9629c89ace6dc5`) and accepted by the owner (status line changed in #320). This record covers the whole of I2: slices I2.1–I2.6, 17 merged slice PRs plus this record.
**Not claimed:** I2 is not qualified, not released and not public. There is no REST/MCP surface or public schema (I3). There is no final-candidate repeatability or surface qualification (I4). The real controlled I5 capture is **`NOT_RUN`**. The I2.6a harness run is a labelled **rehearsal**, not I5 evidence.

## Run identity

Merge commits were read with `gh pr view --json mergeCommit,mergedAt`, not typed. "Planning started" is the value of the PR-body marker (`aip-agent-metadata:v1`).

| Slice | PR | Merge commit | Merged (UTC) | Planning started |
|---|---|---|---|---|
| I2 spec (rev. 0.4) | #312 | `6cebe35b1c520f754c6306a5ff9629c89ace6dc5` | 2026-09-29T06:51:48Z | — |
| I1 closure SHA | #318 | `059ac6369df74d5e1b645d346ef67fd80a23d4fe` | 2026-09-29T07:41:33Z | 2026-09-29T06:52:59Z |
| I2.1a decision record D1–D11 | #320 | `2c7e7dd2019f6fe2b67ee96faa0e3fb485407f5d` | 2026-09-29T08:15:52Z | 2026-09-29T06:52:59Z |
| I2.1b NL reachability gate | #321 | `7daacd275720063d5b2f86647b354ffcba367b05` | 2026-09-29T08:39:19Z | 2026-09-29T06:52:59Z |
| I2.1c CLIENT carrier, guards I-1..I-5 | #328 | `1f41d656095cd0ee0a6af101f67811890273cef1` | 2026-09-29T09:43:42Z | 2026-09-29T06:52:59Z |
| I2.2a v2 record, ID, merge, config, reader | #331 | `f1ef382b34264b914a9a96e250242de88423347d` | 2026-09-29T11:12:36Z | 2026-09-29T10:13:40Z |
| I2.2b per-POST persistence | #335 | `37d3b60a1450cf8ab0dd3542236c1084d0295620` | 2026-09-29T11:51:10Z | 2026-09-29T10:13:40Z |
| I2.2c cutover ledger, membership, report | #337 | `aafa9b7c5d99e9f66ec4cb8b827e6ff13a4cae33` | 2026-09-29T13:10:33Z | 2026-09-29T10:13:40Z |
| I2.2d capture scope, fence rule | #339 | `ea930929639589cfc71393f36131a9ecbb9305b0` | 2026-09-29T13:49:21Z | 2026-09-29T10:13:40Z |
| I2.3a pure applicability evaluator, D13 | #361 | `ea33bb1fc79cb44fb444c920b56eff18219ec4fe` | 2026-09-30T08:11:49Z | 2026-09-30T07:24:10Z |
| I2.3b fenced applicability reads | #363 | `48905cc1139128704651ec058311c314aabfc204` | 2026-09-30T08:58:14Z | 2026-09-30T07:24:10Z |
| I2.4a assessment identity vectors, D14 | #364 | `5832aa02cd7fd21ce9c2eb68919a7bd98fb0c84e` | 2026-09-30T09:30:37Z | 2026-09-30T09:00:05Z |
| I2.4b qualified local assessment | #365 | `a208e18580a0bf4b422e31dd7da40c458f73b435` | 2026-09-30T10:10:37Z | 2026-09-30T09:00:05Z |
| I2.5a after-snapshot vector, D15 | #366 | `c62ae8bc164e945c8390c1967d253e3c977ceecc` | 2026-09-30T11:11:54Z | 2026-09-30T10:11:13Z |
| I2.5b conditional snapshot keys | #369 | `de8d55070f7e69adf1dcac6fd364f48c59d3384c` | 2026-09-30T12:06:57Z | 2026-09-30T10:11:13Z |
| I2.5c flag flip deferred, D16 | #371 | `1c72e574434ab6d5817d91f564e63121cf4350de` | 2026-09-30T13:24:16Z | 2026-09-30T10:11:13Z |
| I2.6a capture harness and rehearsal | #373 | `a64c6227ce7391aeed4f389fd25dcdef1c1528c4` | 2026-09-30T19:08:20Z | 2026-09-30T13:25:14Z |
| I2.6b 65-variant conformance matrix | #374 | `fec7df7bc406e595f557eefa32af2268609a780c` | 2026-09-30T19:30:38Z | 2026-09-30T13:25:14Z |
| I2.6c Pod-churn cost measurement | #375 | `95bebe2787c41b501edf9035057eaf27f80d65cc` | 2026-09-30T19:56:09Z | 2026-09-30T13:25:14Z |
| I2.6d I3 handoff and this record | #376 | `46f700ee4a67399a67e406c8e445db572fd0a31a` | 2026-09-30T20:22:25Z | 2026-09-30T13:25:14Z |

Maintenance PR during I2.6, not part of I2 scope: #372 (`5d7f287c90e7a8dff917fffbc0ab6c2248d8a677`), which bumps pyjwt 2.15.0 and urllib3 2.8.0 for CVEs flagged by `pip-audit`.

## Decisions frozen during I2

All are in the [decision record](i2-decision-record.md). Each fills a gap the accepted specification left open, and none weakens an I1 or parent constraint.

| Decision | Subject | Slice |
|---|---|---|
| D1–D4 | v2 storage and isolation (standalone `ScopedObservedCallV2`, no `:Evidence`/relationships/`owner_source_ids`, default-off flag); the fail-closed NL reachability gate; the unfiltered candidate reader (500-record pages); source selection and one-candidate roll-up with S01–S06 | I2.1a |
| D5 | Capture scope persisted on `SourceState`, the second conditional key, and the fence rule. It carries amendments to I2 §6, §11 and v2 contract §8. | I2.1a |
| D6–D8 | One-POST unit and atomicity; the transition report; the cutover ledger and durable legacy membership. `LOCALITY_LEGACY_V1_UNSCOPED` is never emitted in v0.6. | I2.1a |
| D9–D11 | Assertion/instance identity; source identity and revision; items deferred to later slices | I2.1a |
| D12.1–D12.9 | I2.2 clarifications, including the `lock_revision` correction (D12.8) and the in-memory capture scope (D12.9) | I2.2 |
| D13.1–D13.7 | I2.3: CAP-AMB/CAP-CONF realization, within-phase collection, the explicit selector, `REQUEST_ENVIRONMENT_MISMATCH`, summary reasons, per-source evaluation, bounds | I2.3a |
| D14.1–D14.8 | I2.4: Workload encoding, instance inputs and rule IDs, grouping, qualification input, answer level, Current State only, snapshot binding, bounds | I2.4a |
| D15.1–D15.5 | I2.5: after-vector fixture, one condition for both keys, the v2 entry and scope projections, read cost | I2.5a |
| D16 | The default flip is deferred to the next reviewed release-golden-path re-freeze (it amends D1) | I2.5c |

## I2 Definition of Done (I2 §16)

| # | Requirement | Evidence |
|---|---|---|
| 1 | Original CLIENT identity survives accepted same-batch and cross-batch CALLS and its ingress guards; v1 is unchanged when v2 is refused | I2.1c (#328):<br>- `test_adapter.py::test_every_pairing_path_yields_the_same_seed_for_the_same_calls` (in-batch, CLIENT-first, SERVER-first);<br>- the oracle-driven `test_ingestion_outcome_matches_the_independent_oracle` (all 19 ingestion variants);<br>- `test_v1_output_is_identical_with_and_without_kubernetes_attributes`.<br>On the real rehearsal recording, gate 4 counts every recorded CLIENT span in its own Pod's v2 record for all three arrival orders (I2.6a). |
| 2 | Exact isolated v2 ID and order-independent record; no `:Evidence`/relation/NL/MCP leak; no `owner_source_ids` removal risk; no double counting | I2.2 (#331, #335):<br>- all V/U/MP vectors, including every merge permutation;<br>- the isolation and no-leak tests, including after declaration and Kubernetes reimport and removal;<br>- the NL gate (#321).<br>L12a is pinned exactly (I2.6b). |
| 3 | One-POST atomic v1/v2, retry/replay, the transition report, cutover proof, the strict legacy-only diagnostic; no unearned exactly-once or backfill claim | I2.2b/c (#335, #337), D6–D8. A repeated successful POST counts again, as disclosed. `LOCALITY_LEGACY_V1_UNSCOPED` is not emitted (D8), and dossier L05b is not reachable. |
| 4 | Candidates without an env/day prefilter; explicit versus implicit selection; roll-up; L16; C1/C2 churn; four phases; all six §8.1 rows | I2.3 (#361, #363): every single-capture oracle row, pure and against real imports; S01–S06 on real sources. The PR #365 review added the full-Workload-identity roll-up. |
| 5 | Two Workload localities for one caller Service: `CONFIRMED` and `OBSERVED_ONLY` through the shared qualification owner; no local `NOT_OBSERVED_IN_WINDOW` | I2.4b (#365): the demonstration with the real adapters and with the oracle IDs (A01/A03). Rehearsal E1/E2 on the real `kind` capture (I2.6a). A guard plus a property test make local `NOT_OBSERVED_IN_WINDOW` impossible. |
| 6 | A typed first-class assessment with reviewed assertion and instance identity, derivation and Current-State-only scope | I2.4 (#364 vectors frozen first, #365 code); D9, D14; L30 realized structurally (D14.6) |
| 7 | No v2 gives byte-identical state, fingerprint and golden path; with v2, an independently authored full after-pin | I2.5 (#366 vector `aip:snapshot:v1:3a0b04e1…`, reproduced by a real graph in #369). The golden demo's lifecycle test is `COMPLETE` against `0bfcbded…`. The version stays 3. |
| 8 | All I1 L01–L37 variants have executable coverage; the abstract and import-rejected fixtures are made reachable; v0.5 regression gates pass | I2.6b (#374): [conformance matrix](i2-conformance-matrix.md), 65 variants, 61 covered and 2 partial (the I3 roll-up, I1 §5.1). L05b (D8) and L32b are not reachable in I2. A machine check covers every cited test. CAP-AMB/CAP-CONF are realized (D13.1); L17e/L29a use real rejected imports. |
| 9 | The two-Workload harness passes the runbook §9 rehearsal, labelled as such, with digests, provenance and a run record; the real I5 capture is not claimed | I2.6a (#373): `tests/fixtures/locality/rehearsal/RUN-RECORD.md`, all five gates pass, E1–E7 match the pre-committed `expected.md` (`33dba17`), `SHA256SUMS`, and an offline CI replay. I5 remains `NOT_RUN`. |
| 10 | This record reconciles plans, decisions, deviations, questions, deferrals, measurements, versions, commands and merged SHAs | This document |

## Check status

The CI gate ran at each slice's head; every PR body records the exact counts.

| Check | Last recorded result (I2.6c, `31d19fd`) |
|---|---|
| `uv run ruff format --check .` / `uv run ruff check .` | Clean |
| `uv run pyright` | 0 errors |
| `uv run lint-imports` | 8 contracts kept |
| `uv run deptry .` | Clean |
| `uv run --with pip-audit pip-audit` | No known vulnerabilities (after #372) |
| `uv run pytest tests/unit` | 3062 passed |
| `uv run pytest tests/integration` | 688 passed, 1 skipped (the QSH demo smoke test leaves an already-running local Compose project alone; CI runs it) |

This PR's own gate is in its description.

## Measurements (I2 §14)

**Pod churn** (I2.6c; [`i2-churn-cost.json`](i2-churn-cost.json)). This is one clean run at `97bed50` on WSL2 with 14 logical CPUs, 16 GB, Neo4j 5.26.31 and Python 3.13.14. Medians of 5 runs, with scoped evidence off → on. Observed values only; no threshold is implied.

| Caller Pods (one Workload) | v2 / v1 records | Nodes | Persist per 100-fact POST | Snapshot fingerprint | `assess_local_calls` | Transition report |
|---|---|---|---|---|---|---|
| 0 | 0 / 0 | 8 → 8 | — | 107.9 → 73.6 ms | 117.6 ms | 28.6 ms |
| 100 | 100 / 1 | 512 → 614 | 1,292.8 → 1,810.4 ms | 59.8 → 66.8 ms | 111.8 ms | 12.3 ms |
| 1,000 | 1,000 / 1 | 5,012 → 6,014 | 867.9 → 1,325.4 ms | 96.8 → 256.8 ms | 652.1 ms (page truncated at 500) | 5.9 ms |

- **v2 cost:** one v2 node per distinct caller Pod, with no relationships and a single v1 bucket, plus two operational nodes added once.
- **Fingerprint:** it grows with *N*, because the state reads every v2 record (D15.5).

**Rehearsal** (I2.6a). On the real kind run with Kubernetes v1.31.2, 52 recorded requests were all accepted end to end over the pinned wire path, in each of three clean states. 867 CLIENT spans were retained as v2 records (359 + 508).

**Source versions:**
- Python 3.13.14; Neo4j `5.26.31@sha256:5eb12ad7…`;
- the OTel Collector: core `0.161.0@sha256:b6d2b9a8…` (replay), contrib `0.161.0@sha256:fd328de2…` (recording);
- kind v0.33.0; `kindest/node:v1.31.2@sha256:18fbefc2…`;
- the harness OTel Python SDK is 1.45.0, with instrumentations 0.66b0.

## Reconciliation against the retained plans

Each slice's approved plan is kept verbatim in its PR bodies.

| Slice | Completed as planned | Deviations (disclosed in the PR, and why) |
|---|---|---|
| I2.1 | Decision record, NL gate, CLIENT carrier and guards | D5 amends accepted text (a second conditional key). Two config fields (D1/D10) and the concrete caps (D3 pages of 500, D7 samples of 20) were new. The NL gate is a separate module, not inside `validate_cypher`. Naive timestamps are read as UTC, like v1 (matrix §12.2 names no refusal code). Non-string `k8s.*` attributes are rejected by the v0.5 receiver before the carrier sees them; this is baseline behaviour. |
| I2.2 | ID, record, merge, persistence, ledger, report, capture scope | `config.demo.yaml` is unedited (D12.7). A `subject_id` index was added (D12.6). The `lock_revision` defect found and fixed in I2.2c (D12.8). The capture scope is kept in memory with `exclude=True` (D12.9). A first-unit cutover deadlock was observed in a race test and left to the driver's transient-error retry (#339). |
| I2.3 | Evaluator, fenced reads, all query rows, S01–S06 | CAP-AMB/CAP-CONF realized as D13.1. Test helpers use one stable root per source, because a changed root changes the scope definition and the v0.5 importer then retains the old resources (a finding, recorded below). |
| I2.4 | Vectors first, then the assessment and service method | Real OpenAPI Operation IDs (`operation:service:…`) differ from the oracle symbols, so A01/A03 are reproduced with the oracle IDs through the real importer. **Review fix (#365):** group and roll up by the full Workload identity including the captured UID. It surfaced that separate import runs can hold one logical Workload under two UIDs (a finding, below). |
| I2.5 | Vector, conditional keys, gate evidence | **The flag flip was not done:** with it on, the demo's pinned fixture oracle counts the two operational nodes (46 → 48), so it is deferred (D16). Three I2.2/I2.4 assertions that v2 never enters the snapshot were narrowed to "only through its two keys". |
| I2.6 | Harness and rehearsal (all gates pass), 65-variant matrix, churn measurement, this handoff | **Rehearsal attempts:** attempt 1 had no in-batch pair plus a `resources.yaml` separator defect, attempt 2 was stopped, and attempt 3 was used. By owner decision, gate 4 is split over two real recordings. The harness configuration choices are disclosed in its run record. The benchmark lives in `benchmarks/`, not `scripts/`; the image-pin literal is required by `test_image_pins.py`. |

## Specification questions and findings (not I2 defects; open)

| # | Item | Status |
|---|---|---|
| F1 | **Issue #323:** the NL query path can read Kubernetes-sourced `Evidence` that the public evidence API hides. This was disclosed in D2 and is independent of v2, which is not reachable. | Open issue |
| F2 | **Cross-run incarnations.** `K8S_RESOURCE_CONFLICT` (two captured UIDs for one logical resource) is only detected within one discovery run, so separately imported sources can commit one logical Workload under two UIDs. I2 handles it correctly: two assertions, and a roll-up `CONFLICT` (#365). | Open; no issue yet |
| F3 | **Scope-definition change.** When a Kubernetes source's root changes, the scope-definition digest changes and the importer retains the old resources (v0.5). This matters for capture runbooks: rewrite in place. | Recorded; v0.5 behaviour |
| F4 | **Deferred flag flip.** At the next reviewed golden-path re-freeze, the demo oracle must account for `ScopedEvidence*` nodes before `enabled` defaults to `true` (D16). | Deferred to I6 |
| F5 | **Operation ID convention.** Real OpenAPI Operation IDs embed the full Service ID (`operation:service:pricing:GET:/prices`), unlike the I1 oracle's shorthand. I1 is unaffected (the oracle IDs are symbols), but I3/I5 expected answers should use accepted IDs from import reports, as the runbook already requires. | Recorded |

## Deferred work (explicit, with owner)

- **I3:** public schemas, routes and tools; public bounds and continuation; the Service-level roll-up (L04a `provider_services`, L32); selected-scope comparison and enumeration; the same-snapshot scoped-evidence drill-down. See the [handoff](i2-i3-handoff.md).
- **I4:** final-candidate repeatability, permutation and surface qualification.
- **I5:** the real controlled capture. Its harness and runbook are rehearsed, and it is `NOT_RUN`.
- **I6:** the D16 default flip at the golden-path re-freeze; the ROADMAP reconciliation before the candidate freeze (parent spec).
- **ADR 0012:** scoped-evidence retention and compaction stay unenacted. v2 grows linearly with Pod churn, as measured.

## Handoff

[`i2-i3-handoff.md`](i2-i3-handoff.md) documents the internal read contract (`assess_local_calls`, `read_scoped_applicability`, the result types, pair versus candidate dispositions, bounds, the snapshot binding, the identity vectors) and what I3 must still freeze.

## I2 exit statement

I2 delivers the first internally usable, locality-qualified Current-State path. For an accepted HTTP `CALLS`, AIP keeps the original CLIENT's caller Pod and cluster identity in isolated v2 evidence without changing v1. It resolves the Pod at query time through the selected, time-compatible captured owner chain under one snapshot, and produces an independently qualified local assertion with lineage and limitations.

On a real controlled rehearsal, the two Deployment Workloads of one caller Service yield the declared Operation as `CONFIRMED` and the undeclared one as `OBSERVED_ONLY`. After promotion, the replaced Pod's evidence is retained and marked `UNRESOLVED`. This establishes **caller** locality only: not target placement, exclusivity, a universal dependency or local absence. Every item of I2 §16 is supported by the evidence above. The open findings and deferrals are listed explicitly, and none is silently deferred.
