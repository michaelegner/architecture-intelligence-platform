# Release Validation

Evidence that a release actually satisfied the H5/12G specifications (`docs/specifications/`), not
just that CI passed. The distinction that matters:

```text
docs/specifications/     what the system/release must satisfy
docs/release-validation/ evidence that a release actually satisfied it
```

CI green, CodeQL green, and a successful GHCR publish prove the build pipeline works. They don't by
themselves prove an external user can actually clone this repository, follow the README, and get a
working system — that requires running the same steps an external user would, from a clean
environment, and recording what happened. That's what these files are.

| File | Covers |
|---|---|
| [`v0.1.0-alpha.1-verification.md`](v0.1.0-alpha.1-verification.md) | Fresh-clone Quick Start, fresh-clone runtime demo, GHCR image pull/run (authenticated and unauthenticated), non-root container check, the CodeQL finding found and fixed along the way — plus an explicit release-provenance record distinguishing the original tagged release artifact from the fixes verified afterward on `main`. |
| [`v0.1.0-alpha.2-verification.md`](v0.1.0-alpha.2-verification.md) | Confirms the two gaps left open by `alpha.1` are closed: exactly one `docker.yml` run fires per release, and the non-root fix is verified against the actual pulled, tagged GHCR image rather than only a local build. |
| [`v0.1.0-go-no-go.md`](v0.1.0-go-no-go.md) | Pulls every piece of evidence above into one explicit release-readiness call for `v0.1.0` itself. |
| [`security-settings.md`](security-settings.md) | Repository security feature configuration, verified via the GitHub API rather than assumed. |
| [`public-repository-content-gate.md`](public-repository-content-gate.md) | Sign-off record for the pre-push secret/customer-data/history review performed before the repository went public. |
| [`external-smoke-test.md`](external-smoke-test.md) | Result of the clean-environment smoke test performed independently of the environment that built the repository. |
| [`v0.3.0-rc.2-candidate-preparation.md`](v0.3.0-rc.2-candidate-preparation.md) | I5.1's independent I4-entry re-audit and the `pyproject.toml`/`uv.lock` version-consistency fix (`0.2.0` → `0.3.0`) that creates the `v0.3.0-rc.2` candidate, reopening I4.4's real-system revalidation gate. |
| [`v0.3.0-release-notes.md`](v0.3.0-release-notes.md) | Draft `v0.3.0` GitHub Release notes prepared during I5.1; used, with its evidence links resolved and verified, as the basis for the notes actually published by I5.3. |
| [`v0.3.0-rc.2-real-system-revalidation.md`](v0.3.0-rc.2-real-system-revalidation.md) | I5.2's fresh, full Quarkus + Airflow revalidation (two runs each) bound to the `v0.3.0-rc.2` candidate, plus the fresh Quick Start qualification. |
| [`v0.3.0-rc.2-artifacts/`](v0.3.0-rc.2-artifacts/) | Captured actual-facts YAML and comparator reports for both systems, both runs, from the `v0.3.0-rc.2` revalidation. |
| [`v0.3.0-go-no-go.md`](v0.3.0-go-no-go.md) | I5.2's full release-readiness record for `v0.3.0-rc.2` — source, real-system, Quick Start, GHCR artifact, CI/CodeQL/Trivy qualification, release blockers, and the recorded owner decision: **GO**. |
| [`v0.3.0-post-release-verification.md`](v0.3.0-post-release-verification.md) | I5.3/I5.4's post-publication verification of the actual `v0.3.0` tag, GitHub Release, GHCR artifact (digest match, anonymous pull, non-root, health/import), and a genuine fresh clone of the tagged source. |
| [`v0.4.0-rc.1-candidate-preparation.md`](v0.4.0-rc.1-candidate-preparation.md) | I4.1's independent I4-entry re-audit (I1/I2/I3 GO re-verified against evidence, not textual claim), a stale evaluation-artifact candidate-binding fix, and the `pyproject.toml`/`uv.lock` version bump (`0.3.0` → `0.4.0`) that creates the `v0.4.0-rc.1` candidate. |
| [`v0.4.0-release-notes.md`](v0.4.0-release-notes.md) | Draft `v0.4.0` GitHub Release notes prepared during I4.1; used, with its evidence links resolved and verified, as the basis for the notes actually published by I4.3. |
| [`v0.4.0-go-no-go.md`](v0.4.0-go-no-go.md) | I4.2's full technical-precondition qualification for `v0.4.0-rc.1` — source, hero demo, local and published-image smoke, CI/CodeQL/Trivy, release blockers — plus I4.3's recorded **GO** decision and a pointer to post-release verification. |
| [`v0.4.0-post-release-verification.md`](v0.4.0-post-release-verification.md) | I4.4's independent post-publication verification of the actual `v0.4.0` tag, GitHub Release, GHCR artifact, and a genuine fresh clone of the tagged source — also corrects an I4.2 Trivy query-scoping gap (same 3 pre-existing findings already accepted for `v0.3.0`). |
| [`v0.4.1-rc.1-candidate-preparation.md`](v0.4.1-rc.1-candidate-preparation.md) | I3.2's independent I3-entry re-audit (I1/I2 GO re-verified against evidence) and clean-checkout qualification that creates the `v0.4.1-rc.1` candidate, `bc03602f95557eb0450506a9f5c3a7f7c296b2da`. |
| [`v0.4.1-read-cost-benchmark.json`](v0.4.1-read-cost-benchmark.json) / [`.md`](v0.4.1-read-cost-benchmark.md) | The committed, candidate-bound whole-graph snapshot/read-cost benchmark result (I3.1/I3.2) — machine-readable JSON plus its human-readable summary, per spec §23. |
| [`v0.4.1-release-notes.md`](v0.4.1-release-notes.md) | Draft `v0.4.1` GitHub Release notes prepared during I3.2; used, with its evidence links resolved and verified, as the basis for the notes actually published at GO. |
| [`v0.4.1-go-no-go.md`](v0.4.1-go-no-go.md) | I3.3's full technical-precondition qualification for `v0.4.1-rc.1` — source, benchmark, published-image golden path (dependency and drift flows), CI/CodeQL/Trivy, release blockers — plus the repository owner's recorded **GO** decision and final-publication identity. |
| [`v0.4.1-post-release-verification.md`](v0.4.1-post-release-verification.md) | I3.4's independent post-publication verification of the actual `v0.4.1` tag, GitHub Release, GHCR artifact, and a genuine fresh clone of the tagged source. |
