# I4.5 — Deterministic Cross-System Report

Spec §21/§27's I4.5 deliverable: one deterministic report drawing together I4.1-I4.4's evidence,
plus the Definition of Done, blocker assessment, and GO/NO-GO this iteration adds. I4.5 introduces
no new semantics — every number and disposition below is unchanged from I4.1-I4.4.

## 1. Exact candidate identity (spec §3/§20)

```text
AIP candidate SHA:         9f95d48046ab1942bb1a77c9a3a887a542120b98
Dependency lock (uv.lock) SHA-256:
                            7945b63c47391d7bd81a9c7025dc2004907c33db6147cb169795357a27381a6a
```

Full per-system upstream/profile/image/provider identity blocks are recorded once, in
[`revalidation.md`](revalidation.md)'s "Candidate identity", "Quarkus Super Heroes", and "Apache
Airflow" sections, and are not duplicated here — this report cites them by reference rather than
risking a second, potentially drifting copy.

```text
Quarkus upstream commit:    8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
Quarkus profile revision:   see revalidation.md — runtime/, expected.yaml, ground-truth.md,
                            profile.md unchanged since 9f95d48; runbook.md pinned to a81a01f
                            (window-closing fix; component manifest with git blob hashes in
                            revalidation.md)
Airflow upstream commit:    3adbbe1c58e4532df1964cb7794805e763816ee8
Airflow profile revision:   docs/real-world-validation/apache-airflow/runtime/ @ 9f95d48 (unchanged)
```

## 2. Deterministic result counts (spec §21)

No weighted or composite score. Two counts are reported for Quarkus, per the same convention
`quarkus-super-heroes/results.md` and `revalidation.md` already use — the comparator scores only
what `expected.yaml` declares, and `expected.yaml` declares no `insufficient_evidence:` entries, so
the comparator-only number is not the complete dossier result.

### Quarkus Super Heroes — comparator-only result

| Classification | Count |
|---|---|
| Expected supported facts | 38 |
| Correct | 38 |
| Missing supported | 0 |
| Incorrect supported | 0 |
| Unsupported constructs | 2 |
| Unresolved identities | 0 |
| Insufficient-evidence items | 0 |
| Critical semantic errors | 0 |

### Quarkus Super Heroes — overall dossier result (comparator + `qsh-kafka-operation-type-gap`)

| Classification | Count |
|---|---|
| Expected supported facts | 38 |
| Correct | 38 |
| Missing supported | 0 |
| Incorrect supported | 0 |
| Unsupported constructs | 2 |
| Unresolved identities | 0 |
| Insufficient-evidence items | 1 |
| Critical semantic errors | 0 |

### Apache Airflow — result (comparator already includes all frozen classifications)

| Classification | Count |
|---|---|
| Expected supported facts | 9 |
| Correct | 9 |
| Missing supported | 0 |
| Incorrect supported | 0 |
| Unsupported constructs | 3 |
| Unresolved identities | 2 |
| Insufficient-evidence items | 1 |
| Critical semantic errors | 0 |

Both revalidated twice each against the literal candidate above, byte-identical both times
(`revalidation.md`).

## 3. Input finding ledger and final dispositions (spec §6/§21)

Deterministic ordering: by system, then classification, then severity, then finding id — matching
`finding-ledger.md`'s own presentation order, reproduced here as the flat list spec §21 requires.

| # | System | Finding | Classification | Severity | Disposition |
|---|---|---|---|---|---|
| 1 | Quarkus | `qsh-grpc-locations` | UNSUPPORTED | INFO | `NO_CHANGE` |
| 2 | Quarkus | `qsh-kafka-fights-topic` | UNSUPPORTED | INFO | `DOCUMENT_UNSUPPORTED` |
| 3 | Quarkus | `qsh-kafka-operation-type-gap` | INSUFFICIENT_EVIDENCE | MINOR | `DEFER` |
| 4 | Airflow | `airflow-scheduler-postgres-dependency` | UNSUPPORTED | INFO | `NO_CHANGE` |
| 5 | Airflow | `airflow-apiserver-postgres-dependency` | UNSUPPORTED | INFO | `NO_CHANGE` |
| 6 | Airflow | `airflow-celery-result-backend-postgres-dependency` | UNSUPPORTED | INFO | `NO_CHANGE` |
| 7 | Airflow | `airflow-execution-api-boundary` | UNRESOLVED_IDENTITY | MINOR | `NO_CHANGE` |
| 8 | Airflow | `airflow-runtime-role-identity` | UNRESOLVED_IDENTITY | MINOR | `DEFER` |
| 9 | Airflow | `airflow-celery-messaging-runtime-status` | INSUFFICIENT_EVIDENCE | MINOR | `DEFER` |
| 10 | Airflow | `i4-celery-instrumentation-semconv-mismatch` (new, discovered in I4.1) | INSUFFICIENT_EVIDENCE | MINOR | `DEFER` |

Full evidence, cross-system relevance, and reasoning for each row: [`finding-ledger.md`](finding-ledger.md).
Every material finding has exactly one final disposition (spec §7); none is `FIX`.

## 4. Accepted production changes

**None.** I4.1 approved zero `FIX` dispositions ([`finding-ledger.md`](finding-ledger.md)'s closing
line); I4.2 recorded an evidence-backed `NO_CHANGE` on that basis
([`hardening.md`](hardening.md)); no finding discovered afterward (I4.3, I4.4, or this report)
reopened that outcome.

## 5. Regression-test mapping

Full finding-to-test map, the four distilled characterization tests added, and their exact
assertions: [`regression-map.md`](regression-map.md). Since no `FIX` was accepted, spec §17's
per-fix regression requirement is vacuously satisfied — the map instead ties every ledger finding to
what the existing suite already proves about its current, unchanged behavior, and the two tests that
make previously-implicit `DEFER` prerequisites literally test-traceable
(`test_topic_shaped_destination_is_still_minted_as_observed_only_queue`,
`test_generic_service_name_is_still_minted_as_qualified_observed_only`).

## 6. Before/after semantics

**Unchanged.** No production code was modified at any point in I4 (I4.1 through I4.4, and this
report, all record zero production changes). AIP's supported-scope semantics entering I4 and exiting
I4.5 are identical.

## 7. Known limitations

Reproduced from [`revalidation.md`](revalidation.md#known-limitations-carried-forward-unchanged):

| Limitation | Status | Disposition |
|---|---|---|
| gRPC/protobuf calls (Quarkus) | unsupported | `DOCUMENT_UNSUPPORTED` |
| Kafka topic/subscription semantics (Quarkus) | unsupported | `DOCUMENT_UNSUPPORTED` |
| `messaging.operation`/legacy attribute gap (Quarkus, `qsh-kafka-operation-type-gap`) | insufficient evidence | `DEFER` |
| PostgreSQL/database dependencies (Airflow, x3) | unsupported | `NO_CHANGE` |
| Airflow Execution API caller identity | unresolved | `NO_CHANGE` |
| Airflow runtime-role identity | unresolved | `DEFER` |
| Airflow Celery messaging identity/semconv (x2 findings) | insufficient evidence | `DEFER` |

None is a material `INCORRECT_SUPPORTED` claim (spec §24).

## 8. Canonical-redesign gate answer (spec §13)

**NO** — current supported claims remain semantically correct; every limitation above is explicit
and bounded. Full reasoning against all eight mandatory cross-system questions:
[`decisions/canonical-redesign-gate.md`](decisions/canonical-redesign-gate.md). This does not block
`v0.3.0-rc.1`.

## 9. Release blocker assessment (spec §23)

Every named blocker, checked explicitly against the evidence above — none present:

| Blocker | Present? | Evidence |
|---|---|---|
| Material `INCORRECT_SUPPORTED` finding | No | §2 above: 0 in both systems, both runs |
| Wrong relation direction | No | No finding reports one; comparator asserts direction per relation |
| Invented canonical identity | No | `decisions/canonical-redesign-gate.md` Q2/Q5; no per-role `Service` or guessed identity minted |
| False identity merge or split producing a supported claim | No | Same — `UNRESOLVED_IDENTITY` used instead, both systems |
| Wrong runtime status | No | §2 above; `revalidation.md`'s byte-identical comparator output both runs, both systems |
| Lost or fabricated evidence | No | `decisions/canonical-redesign-gate.md` Q6; `finding-ledger.md` re-verification |
| Unsupported mechanism coerced into a supported relation | No | `hardening.md` hardening-checklist item; `decisions/queue-topic-boundary.md` |
| Ground truth derived from AIP output | No | `expected.yaml` frozen before every capture (I2/I3 dossiers); untouched by I4 |
| System-specific production workaround | No | Zero production changes across all of I4 |
| Unrecorded semantic change | No | Zero production changes; every doc change traces to a spec section cited above |
| Accepted fix without deterministic regression coverage | No | Zero fixes accepted (§4) |
| Quarkus or Airflow revalidation failure | No | `revalidation.md`: both systems, both runs, byte-identical, matching frozen baseline |
| v0.2 evaluation failure without approved migration | No | §10 below: 10/10 PASS at the literal candidate |
| Nondeterministic qualifying comparison | No | `revalidation.md`: byte-identical captures/reports across both runs, both systems |
| Unbound candidate/profile/upstream identity | No | §1 above + `revalidation.md`'s full identity blocks, including the profile-revision component manifest |
| Fundamental redesign required before v0.4 | No | §8 above: `NO` |
| Red CI, CodeQL, or dependency audit | No | §10 below: all green at the literal candidate SHA |

```text
Critical semantic errors = 0
Release blockers        = 0
```

## 10. Quality gates at the literal candidate (spec §22)

Bound to `9f95d48046ab1942bb1a77c9a3a887a542120b98` exactly (a detached-HEAD `git worktree`, not a
content-equivalence argument from a later commit — I4.3's own review history is exactly why this
distinction matters here):

```bash
uv sync --locked                             -> resolved, no lock drift
uv run ruff check .                          -> All checks passed
uv run ruff format --check .                 -> 159 files already formatted
uv run pytest tests/unit -q                  -> 508 passed
uv run pytest tests/integration -q           -> 160 passed
uv run python -m evaluation run              -> 10/10 PASS, 0 missing/unexpected/forbidden/wrong-status/evidence-errors
uv run --with pip-audit pip-audit            -> No known vulnerabilities found
```

508 + 160 = 668, matching I4.3's own `regression-map.md` count exactly (664 baseline + 4 distilled
tests it added, all still present).

CI/CodeQL, confirmed via GitHub's Checks API against this exact commit SHA (not the branch tip):

```text
lint + test                              -> success
dependency security scan (pip-audit)     -> success
analyze (python)                          -> success
analyze (actions)                         -> success
```

## 11. GO/NO-GO (spec §29)

**GO** — the candidate is qualified for `v0.3.0-rc.1`. All material cross-system findings are
dispositioned (§3), all accepted general corrections are implemented (none were accepted, §4), all
accepted fixes have deterministic regression coverage (vacuous, §4), Quarkus is revalidated (§2,
`revalidation.md`), Airflow is revalidated (§2, `revalidation.md`), the v0.2 evaluation is green
(§10), and critical semantic errors = 0 and release blockers = 0 (§9).

```text
Candidate: 9f95d48046ab1942bb1a77c9a3a887a542120b98
```

**I4 is now complete.** The `v0.3.0-rc.1` tag was cut and pushed at the literal candidate SHA above
(`git rev-list -n1 v0.3.0-rc.1` resolves to `9f95d48046ab1942bb1a77c9a3a887a542120b98`, not any
later documentation-only commit, per spec §3) and published as a GitHub prerelease:
https://github.com/michaelegner/architecture-intelligence-platform/releases/tag/v0.3.0-rc.1. I4.5
closes here; I5 is next.

## 12. I5 handoff (spec §30)

I5 introduces no new model semantics. I5 receives from I4:

```text
exact candidate SHA and dependency lock         -> §1 above
Quarkus and Airflow qualifying identities       -> §1 above; revalidation.md
final ledger and decision records               -> finding-ledger.md; decisions/
regression map                                  -> regression-map.md
real-system comparison reports                  -> revalidation.md; artifacts/
known limitations                               -> §7 above
canonical-redesign gate answer                  -> §8 above (NO)
GO / NO-GO record                               -> §11 above
updated roadmap and public project status       -> ROADMAP.md, README.md, CHANGELOG.md,
                                                    docs/specifications/0.3.0/README.md
post-v0.3 release-planning baseline             -> ROADMAP.md's v0.4/v0.5/v0.9/v1.0 sequence
```

If I5 requires a production semantic change, the affected I4 decision, regression, and real-system
revalidation gates reopen, and the changed commit becomes a new candidate (spec §30).
