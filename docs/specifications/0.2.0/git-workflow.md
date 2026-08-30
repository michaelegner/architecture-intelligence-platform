# AIP v0.2.0 — Git Branching, Commit and PR Strategy

**Status:** Draft  
**Applies to:** `v0.2.0` implementation iterations I1–I5

## 1. Principle

Development SHALL use short-lived task branches and focused pull requests against `main`.

```text
main <- task branch <- focused PR
```

An iteration is a planning/release unit, not a long-lived integration branch.

Do **not** use:

```text
develop
v0.2
v0.2-i1
release/v0.2-i1
```

as intermediate integration branches.

## 2. Branch Strategy

Create one branch per logical change or implementation task.

Recommended naming:

```text
feat/v0.2-i1-evaluation-skeleton
feat/v0.2-i1-runtime-fixtures
feat/v0.2-i1-canonical-comparison
feat/v0.2-i1-scenarios

fix/v0.2-i1-otlp-resolution
docs/v0.2-evaluation
```

Each new branch SHALL start from the latest `main`:

```bash
git switch main
git pull
git switch -c feat/v0.2-i1-evaluation-skeleton
```

## 3. Pull Request Strategy

Every normal feature or fix SHALL be merged through a PR to `main`.

PRs SHOULD contain one logical change.

For I1, the recommended PR split is:

```text
PR 1 — Evaluation skeleton
PR 2 — Isolation and runtime fixtures
PR 3 — Canonical projection and comparison
PR 4 — Three I1 scenarios and reporting
```

Large changes MAY be opened early as Draft PRs.

PR descriptions SHOULD state:

- which iteration/task they implement,
- what is included,
- what is intentionally deferred,
- relevant issue references.

Example:

```text
Part of v0.2.0 / I1 Evaluation Kernel.

Implements:
- RelationFact projection
- scenario-owned scope
- exact expectation comparison

Deferred to I2:
- forbidden facts
- exhaustive unexpected facts
- inverse-direction assertions
```

## 4. Commit Strategy

Feature branches MAY contain several small, meaningful commits.

Preferred examples:

```text
feat(evaluation): add scenario model and loader
feat(evaluation): add canonical fact projection
test(evaluation): cover status mismatches
docs(evaluation): document scenario format
```

Avoid non-descriptive commits such as:

```text
work
fix
more fixes
final
```

Use **squash merge** for PRs unless preserving individual commits has a clear benefit.

The resulting `main` history should therefore normally contain one clean commit per PR.

## 5. Push Strategy

Push task branches early:

```bash
git push -u origin feat/v0.2-i1-evaluation-skeleton
```

Continue pushing during implementation so CI and review can start before the PR is complete.

Direct feature development on `main` is discouraged.

## 6. CI and Merge Conditions

Before merge, the PR SHOULD satisfy the repository contribution requirements:

```text
tests green
lint green
format check green
no secrets or production/customer data
documentation updated where required
```

A merged commit on `main` SHOULD always represent a complete and tested logical change.

## 7. Issues and Iterations

Use the iteration as a planning unit:

```text
v0.2.0
├── I1 — Evaluation Kernel
├── I2 — Topology and Directionality
├── I3 — Evidence and Runtime Semantics
├── I4 — Coverage and Hardening
└── I5 — Release Qualification
```

Implementation issues may correspond to individual PRs.

Example for I1:

```text
I1.1 Evaluation Skeleton
I1.2 Isolation and Input Fixtures
I1.3 Canonical Projection and Comparison
I1.4 Scenarios and Reporting
```

PRs SHOULD reference or close the corresponding implementation issue.

## 8. Tagging and Pre-Releases

Do not tag after every PR.

Tag only when an iteration is complete and `main` satisfies that iteration's acceptance criteria:

```text
I1 complete -> v0.2.0-alpha.1
I2 complete -> v0.2.0-alpha.2
I3 complete -> v0.2.0-alpha.3
I4 complete -> v0.2.0-rc.1
I5 complete -> v0.2.0
```

## 9. Summary

The governing rules are:

```text
Branch lifetime = one logical change
PR = one focused reviewable change
main = continuously integrated development state
Iteration = milestone / pre-release boundary
```

No long-lived iteration branches are required.
