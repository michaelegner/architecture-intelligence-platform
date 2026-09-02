# I4.5 — Definition of Done (spec §28)

Every checkbox below, verified against the actual evidence at the exact candidate
`9f95d48046ab1942bb1a77c9a3a887a542120b98`, not assumed.

## Entry and evidence

- [x] I1 methodology remains frozen. No I5 or I4 change touched
      `docs/specifications/0.3.0/i1-real-world-validation-contract.md`'s finding vocabulary,
      ground-truth independence rules, supported-scope rules, or comparator semantics (spec §2).
- [x] I2 and I3 dossiers are complete. `docs/real-world-validation/quarkus-super-heroes/` and
      `docs/real-world-validation/apache-airflow/` each hold a full `upstream.md`/`profile.md`/
      `ground-truth.md`/`expected.yaml`/`results.md`/`findings.md`/`runbook.md`/`artifacts/`.
- [x] The I3 post-merge auditability correction is committed (PR #48, `a55b82d`) — binds both
      qualifying §59 runs to the same Airflow upstream SHA, AIP candidate SHA, profile revision,
      image digests, and provider/instrumentation versions.
- [x] Exact I4 base and input revisions are recorded — [`report.md`](report.md) §1.

## Cross-system decisions

- [x] Every material finding appears in the ledger and has one final disposition —
      [`finding-ledger.md`](finding-ledger.md); [`report.md`](report.md) §3 (10 findings, one
      disposition each, zero `FIX`).
- [x] Messaging attribute compatibility is decided —
      [`decisions/messaging-operation-compatibility.md`](decisions/messaging-operation-compatibility.md).
- [x] Queue-versus-topic safety and identity prerequisites are decided —
      [`decisions/queue-topic-boundary.md`](decisions/queue-topic-boundary.md).
- [x] Service/role/instance identity is decided —
      [`decisions/runtime-role-identity.md`](decisions/runtime-role-identity.md).
- [x] gRPC and database boundaries are decided — `finding-ledger.md`'s `qsh-grpc-locations` and
      three Airflow PostgreSQL-dependency rows, all `NO_CHANGE`.
- [x] The fundamental redesign gate is answered —
      [`decisions/canonical-redesign-gate.md`](decisions/canonical-redesign-gate.md): `NO`.
- [x] Known limitations are explicit — [`report.md`](report.md) §7.

## Hardening

- [x] Every production change maps to independent evidence. Vacuously satisfied — zero production
      changes (`hardening.md`).
- [x] Every accepted rule is general and system-independent. Vacuously satisfied — zero rules
      accepted.
- [x] No unsupported mechanism is represented as supported — `hardening.md`'s checklist,
      re-confirmed in `report.md` §9.
- [x] No ambiguous identity is guessed — same.
- [x] No unrelated adapter/entity family is introduced — same.
- [x] Every accepted fix has deterministic regression coverage. Vacuously satisfied — zero fixes.
- [x] Any no-change conclusion is evidence-backed — `hardening.md`, `decisions/*.md`.

## Regression and quality

- [x] Unit, integration, and I1 contract tests are green — [`report.md`](report.md) §10 (508 + 160
      = 668 unit/integration; 61 I1-contract tests, `regression-map.md`), all at the literal
      candidate SHA.
- [x] Ruff lint and format are green — `report.md` §10.
- [x] v0.2 deterministic evaluation is green — `report.md` §10 (10/10 PASS, 0 missing/unexpected/
      forbidden/wrong-status/evidence-errors).
- [x] Dependency audit, CI, and CodeQL are green — `report.md` §10 (pip-audit clean; all 4 GitHub
      check runs `success` against the literal commit SHA, not just the branch tip).

## Real-system revalidation

- [x] Quarkus and Airflow are revalidated from clean state against the final candidate —
      `revalidation.md` (2 runs each, `docker compose down -v` before every run).
- [x] Exact upstream, candidate, profile, image, and instrumentation identities are recorded —
      `revalidation.md`'s per-system identity blocks, including the Quarkus profile-revision
      component manifest (git blob hashes) added after PR #52 re-review.
- [x] Qualifying artifact and report hashes are recorded — `revalidation.md`, `artifacts/`.
- [x] Comparator output is deterministic — byte-identical across both runs, both systems.
- [x] All findings are dispositioned — `report.md` §3.
- [x] Material `INCORRECT_SUPPORTED` findings = `0` — `report.md` §2.
- [x] Critical semantic errors = `0` — `report.md` §2, §9.

## Release candidate

- [x] The deterministic cross-system report is committed — [`report.md`](report.md).
- [x] Release blockers = `0` — `report.md` §9.
- [x] GO/NO-GO names the exact candidate — `report.md` §11: **GO**,
      `9f95d48046ab1942bb1a77c9a3a887a542120b98`.
- [ ] `v0.3.0-rc.1` points to the approved candidate. **Pending** — the tag is cut as a separate,
      explicit step after this record merges (see this PR's description); it must point at the
      literal SHA above, not at any later documentation-only commit, per spec §3.
- [x] I5 receives candidate identity, dossiers, reports, limitations, and commands —
      [`report.md`](report.md) §12.

## Roadmap and public status

- [x] `ROADMAP.md` contains the v0.3 I1-I5 delivery track and actual iteration status.
- [x] `ROADMAP.md` identifies v0.4 as Architecture Intelligence Tools.
- [x] `ROADMAP.md` places Kubernetes and broader discovery in v0.5, not v0.4.
- [x] `ROADMAP.md` identifies v0.9 as Contract Freeze / Production Qualification.
- [x] `ROADMAP.md` identifies v1.0 as the first stable platform release.
- [x] Versions between v0.5 and v0.9 remain intentionally unspecified.
- [x] The validate → tools → discovery → freeze sequencing principle is explicit.
- [x] The fundamental-redesign gate blocks progression from v0.3 to v0.4 when triggered (stated in
      `ROADMAP.md`'s sequencing section; not triggered here — `decisions/canonical-redesign-gate.md`
      answered `NO`).
- [x] `README.md` Project Status matches the actual I4/I5 state.
- [x] `CHANGELOG.md` records I4 under `[Unreleased]` without prematurely declaring v0.3 shipped.
- [x] `docs/specifications/0.3.0/README.md` links this specification and reflects current status.
- [x] The four public planning surfaces (`ROADMAP.md`, `README.md`, `CHANGELOG.md`,
      `docs/specifications/0.3.0/README.md`) contain no contradictory release claims — all four
      state: I1-I4 complete, qualified as `v0.3.0-rc.1`, `v0.3.0` not yet shipped, I5 pending.

## Outstanding before I4.5 closes

Exactly one item: cutting and pushing the `v0.3.0-rc.1` tag at the literal candidate SHA, held as a
separate, explicitly confirmed action per this PR's own description (tagging a commit that is not
the branch tip is unusual enough to warrant its own sign-off, not a bundled side effect of merging
documentation).
