# v0.6.0 I5 completion and I6 handoff

Governing: merged [I5 revision 0.1](i5-real-system-qualification-and-product-demonstration.md) §§7–9 and accepted [parent specification](specification.md) §§24–27, 30. This record reconciles I5.1–I5.3; it adds no production behavior, public contract, schema, default or golden-path change.

**Technical disposition: awaiting explicit acquisition-owner acceptance. Product pilot: NOT_RUN.** Qualification results below are established; final acquisition acceptance is recorded separately from passing checks. This is neither release readiness nor a publication decision.

## Evidence, chronology and identities

The original [actual acquisition record](../../../tests/fixtures/locality/two-workload-capture/RUN-RECORD.md) is labelled `ACTUAL_CONTROLLED_REFERENCE`, run `aip-locality-i5-20261005t060050z-4392`. Its historical `PENDING` and `NOT_RUN` statements describe acquisition-time status; frozen originals are not rewritten. The [adopted source-derived oracle](../../../tests/fixtures/locality/two-workload-capture/expected.md), [I5.2 report](i5-qualification-report.md) and [I5.3 report](i5-upstream-and-walkthrough-report.md) supply subsequent outcomes.

| Stage | Immutable identity and evidence |
| --- | --- |
| Acquisition | [PR #422](https://github.com/michaelegner/architecture-intelligence-platform/pull/422), merged `469f7f2573969f5c1d5156e1f7187542dd31195e` at 2026-10-05T06:37:21Z. Original 42 checksum-pinned files retain authentic SDK CLIENT traffic, API-issued Pod/cluster/Deployment identities, C1 overlap and C2 replacement. |
| Independent expectation | Michael adopted the source-derived oracle before its freeze and first AIP evaluation. Original freeze `e48cae8f9842bd197061ba1b2c38ccd78f67b608`; oracle SHA-256 `9bca35f18b20b596b4696c69922742fbf6aff856a2e45bc92824051ceda4a7fd`. |
| I5.2 evaluation | Tested executable `3c10560620164d6ba589c68546ee4ce3fdb79255`; [PR #431](https://github.com/michaelegner/architecture-intelligence-platform/pull/431) merged `c5bc7cb58d4d6efef80b744347c51f36d14b6356` at 2026-10-05T12:04:19Z. This squash carrier contains the byte-identical prior oracle; it is not a new adoption. |
| I5.3 cross-system evaluation | Tested executable `8df3d118a967a650cbc5b3c6fa40db0e2adaa3eb`; [PR #432](https://github.com/michaelegner/architecture-intelligence-platform/pull/432) merged `5493cc63366cdc1a782944b592debed3261c0ced` at 2026-10-05T13:47:50Z. Full upstream runs, controlled-reference A/B and isolated demo use that tested executable. Later record/merge commits are not newly qualified executables. |

The [artifact checksums](i5-qualification-artifacts/SHA256SUMS) pin both raw archives and the [363-file I5.3 manifest](i5-qualification-artifacts/i5.3-artifact-manifest.json). They retain exact commands, source/image/configuration/schema identities, telemetry and capture digests, imports, process/container identities, request/response bytes and validation logs. I5.2 archive SHA-256: `257fa8a1240838e8a250ce669b59e270459131379a99b4b5ad59d91d6aeb9ff6`; I5.3: `47819d9c95efb3decea08882a2338af52a464a42bb86b03631c4f4493cefea32`. Original inputs and expectations remain immutable.

## Acceptance and case dispositions

| I5 §9 gate | Evidence and disposition |
| --- | --- |
| 1 — actual acquisition | Original source checks pass: distinct Deployment owner chains, stable P1/P2 through overlap, byte-equal CLIENT/capture cluster identity, successful real HTTP traffic, admitted UTC day and intact recording. Capture is non-atomic and completeness self-declared. Acquisition-owner disposition remains separately required. |
| 2 — prior independent oracle | Adopted prior freeze establishes C1 W1/pricing `APPLICABLE`/`CONFIRMED`, W2/legacy-pricing `APPLICABLE`/`OBSERVED_ONLY`, distinct Operation/evidence/source lineage and forbidden claims. CORRECT. |
| 3 — clean A/B and public parity | Both I5.2 and I5.3 retain two independent fresh processes/states, 17 cases per run and 70 raw canonical artifacts matching without field masking. Each replays 52 original requests once, in order, with 52 Collector and 52 AIP HTTP 200 responses. Service, REST and negotiated MCP agree; scoped evidence authorization and same-snapshot checks pass. CORRECT. |
| C2 / bounds / coexistence | P1 retained event becomes `UNRESOLVED` / `LOCALITY_CAPTURE_MISSING_POD`; P2 remains eligible. Snapshot changes; stale C1 request/evidence/cursor refused. Counts 359/508 preserved without double counting. Target locality UNKNOWN; local coverage unavailable; no invented absence, global dependency set or reassignment. CORRECT. |
| 4 — upstream truth | Quarkus: 45 supported facts correct, 0 missing/incorrect, 4 forbidden absent; 3 unsupported constructs preserved. Airflow: 9 supported facts correct, 0 missing/incorrect, 2 forbidden absent; 3 unsupported constructs, 2 unresolved identities and 1 insufficient-evidence case preserved. No critical semantic errors. Original source modes/dossiers unchanged; neither supplies positive caller-locality evidence. |
| 5 — developer demonstration | [Task-led walkthrough](../../real-world-validation/v0.6.0/locality-walkthrough.md) links retained transcripts: Quarkus limits, separate actual C1 discovery without supplied Workload IDs, comparison/evidence, C2 limitation and honest abstention. Replay needs no live cluster, Kafka, upstream build or LLM once dependencies/images are cached. Original no-v2 demo snapshot and pinned answers pass. |
| 6 — audit and pilot | Reports/archives retain identities, outcomes, commands, failures, limits and validation. Pilot NOT_RUN with named owner and stable-contract carry-forward below. |
| 7 — I6 handoff | Final-candidate obligations and remaining #323 below. No release claim. |

No missing supported positive, reference leak, wrong lineage, source-mode drift, adapter disagreement or nondeterminism remains in retained successful runs. Actual two-candidate enumeration is complete; synthetic cap/continuation tests remain synthetic. Protocol-generated stale-cursor controls are not additional acquired traffic. I2 rehearsal/I4 synthetic bridges are never substituted for actual capture.

I5.2 retained an environment startup failure before ingestion and a successful fresh-port retry; unretained earlier attempts are not auditable qualification. I5.3 retained initial golden-pin validation failure, corrected by placing companion documentation outside frozen examples. Its approved host-path exception and isolated demo execution are disclosed in the report. No independent expectation or production semantics changed.

## Costs and owner dispositions

The acquisition took approximately ten minutes on one local host, with traffic from 06:01:59Z to 06:10:53Z and more than 331 seconds per caller before C1. These are observed durations, not a capture-overhead benchmark. Individual capture overhead, representative operator effort, production capacity and customer value remain unmeasured.

The [I4 owner disposition](i4-i5-handoff.md) remains: “Accept these measured costs and retained-state limitations for the bounded I5 handoff; production capacity remains unestablished.” It does not establish a numerical SLO, production sizing, a product pilot or adoption of proposed ADR 0012 retention/compaction. Replaced-Pod attribution remains unresolved; saved captures do not create historical snapshot access.

## Product pilot and stable-contract admission carry-forward

**Status: NOT_RUN. Pilot owner and follow-up owner: Michael Egner.** The owner selected this disposition for I5.4. Technical capture and demonstration are not product validation. No success thresholds were invented or applied retrospectively.

**Follow-up action:** before observing pilot results, freeze representative service-change tasks, independently checkable answers, comparable with/without-AIP source access and owner-chosen numeric or categorical success/stop criteria. Include time/effort, useful supported coverage, justified abstention, false local/global/absence assumptions, setup/capture overhead and preservation of evidence scope. Obtain rollout-overlap capture before authoritative replacement; score unavailable attribution honestly. Then execute and record CONTINUE, NARROW, DEFER or STOP against those criteria.

**v1.0-rc stable-contract admission-ledger carry-forward:** product-value evidence for locality-aware service-change context remains unsatisfied, owned by Michael Egner. Carry this entry into that ledger and resolve it with an accepted pilot disposition before claiming stable-contract readiness for the affected capability. Demonstrated customer benefit, reduced engineering effort and stable-contract readiness are not established by I5.

## I6 handoff

- Pin one exact final candidate, versions, schemas/rules/mappings, input/configuration/image digests and all qualification outputs. Prior I4/I5 candidates and this closure commit do not substitute for that candidate.
- Rerun I4 independent qualification and growth/retained-state obligations, I5 actual-reference clean A/B using the unchanged adopted oracle, both full pinned upstream evaluations, service/REST/negotiated MCP and same-snapshot evidence checks, and the task-led no-v2 demo/golden snapshot pins. Reuse commands and wire/configuration records in the linked reports/archives; thread the final SHA explicitly.
- Review scoped-evidence default and four-tool golden-path deployment; complete version/migration/documentation, dependency/container/security/SBOM gates. Known [#323](https://github.com/michaelegner/architecture-intelligence-platform/issues/323) remains carried, not cleared by qualification.
- Before freeze, reconcile ROADMAP v0.6 scope and explicitly defer/unassign region, tenant, service-version and messaging locality. Respect the current ROADMAP sequencing; do not allocate these dimensions to another release without authorization.
- Record exact-candidate GO/NO_GO. Publication remains the owner's decision; tags, images, published-digest verification and terminal release disposition belong to I6.

## Reconciliation and closure validation

Completed as planned: one completion record joins existing evidence, per-case dispositions, costs, pilot NOT_RUN and I6 obligations without rewriting frozen artifacts. No new tests, qualification runs, runtime changes or issue were introduced.

Material deviations: none. Specification questions: no new semantic decision; explicit acquisition-owner acceptance is pending. Deferred: representative pilot, production capacity, #323 and I6 final-candidate/release work.

Qualification-local gates remain those retained in I5.2/I5.3: Ruff/Pyright and 8 import contracts passed; 3,485 unit passed; 803 integration passed, 1 skipped because the owner's fixed-name demo project existed. I5.3 separately passed its isolated explicit-candidate demo, preserving the owner project.

I5.2 [CI](https://github.com/michaelegner/architecture-intelligence-platform/actions/runs/37306491676) and [CodeQL](https://github.com/michaelegner/architecture-intelligence-platform/actions/runs/37306491690) succeeded on their evidence PR head. I5.3 [CI](https://github.com/michaelegner/architecture-intelligence-platform/actions/runs/37314261370) and [CodeQL](https://github.com/michaelegner/architecture-intelligence-platform/actions/runs/37314261296) succeeded on its evidence PR head. CI does not requalify squash merges by implication.

Closure validation ran once in the required order: `uv run ruff format .`, `uv run ruff check .`, `uv run pyright`, `uv run lint-imports`, `uv run pytest tests/unit`, `uv run pytest tests/integration`. Ruff passed with no formatting changes; Pyright reported zero errors; all 8 import contracts passed; **3,485 unit tests passed; 803 integration tests passed, 1 skipped** (the preserved owner demo project). Acquisition and archive checksums, all 363 I5.3 manifest entries, oracle freeze/carrier byte equality and local links passed. Final diff contains only this completion record; no production refactoring applies. I5.4 PR CI identity/status is retained in the PR description. This completion record is excluded from the documentation-only exemption. Remaining limitations are those stated above; no release-readiness claim follows.
