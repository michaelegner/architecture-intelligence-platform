# I4 — Cross-System Model Hardening

This directory holds the I4 evidence and decision trail (see
[`docs/specifications/0.3.0/i4-cross-system-model-hardening.md`](../../specifications/0.3.0/i4-cross-system-model-hardening.md)).
I4.1 and I4.2 derive decisions from the two independent qualifying results already frozen by I2
(Quarkus Super Heroes) and I3 (Apache Airflow) and introduce no new validation profile, using the
same six-classification vocabulary frozen by I1 (see [`../README.md`](../README.md)). I4 as a whole
still required fresh evidence: per spec §19/§27, I4.4 executed both existing profiles again,
twice each, against the same final candidate (`9f95d48`) before qualification — frozen I2/I3
results, and a source diff or content-equivalence argument, could not substitute for that
real-system execution (see [`revalidation.md`](revalidation.md)).

```text
docs/real-world-validation/quarkus-super-heroes/   I2's independent dossier and qualifying result
docs/real-world-validation/apache-airflow/         I3's independent dossier and qualifying result
docs/real-world-validation/cross-system/           this directory — I4's joint decision trail
```

## Delivery split (spec §27)

```text
I4.1  Finding Consolidation and Decision Freeze         <- complete (PR #49)
I4.2  General Model and Runtime Hardening               <- complete, NO_CHANGE (see hardening.md)
I4.3  Distilled Regression and Synthetic Revalidation   <- complete (see regression-map.md)
I4.4  Final-Candidate Real-System Revalidation          <- complete (see revalidation.md)
I4.5  RC Qualification                                  <- complete (see report.md); GO recorded,
                                                            v0.3.0-rc.1 tagged at the candidate
```

I4 as a whole is now complete: [`report.md`](report.md) is the single deterministic cross-system
report drawing I4.1-I4.4 together, plus the Definition of Done
([`definition-of-done.md`](definition-of-done.md)), the release-blocker assessment, and a **GO**
record. The `v0.3.0-rc.1` tag was cut and pushed at the literal candidate SHA
`9f95d48046ab1942bb1a77c9a3a887a542120b98` and published as a GitHub prerelease:
https://github.com/michaelegner/architecture-intelligence-platform/releases/tag/v0.3.0-rc.1.

I4.1's gate (spec §27): *no production semantic change begins before its decision record is
approved.* I4.1 made no production code change and approved zero `FIX` dispositions, so I4.2 (per
spec §27's own explicit allowance) records an evidence-backed `NO_CHANGE` rather than manufacture
hardening work — it also makes no production code change.

## I4.1 contents

```text
finding-ledger.md                                the normalized ledger (spec §6)
decisions/messaging-operation-compatibility.md   spec §10.1
decisions/queue-topic-boundary.md                spec §10.2
decisions/runtime-role-identity.md               spec §11
decisions/canonical-redesign-gate.md             spec §13
```

## I4.2 contents

```text
hardening.md                                     evidence-backed NO_CHANGE record (spec §27/§28)
```

## I4.3 contents

```text
regression-map.md                                finding-to-test map, distilled tests, bound
                                                  candidate results, determinism verification
                                                  (spec §17/§27)
```

## I4.4 contents

```text
revalidation.md                                  clean Quarkus + Airflow runs (2x each) against the
                                                  literal 9f95d48 candidate, full identity blocks,
                                                  artifact/report hashes, final dispositions
                                                  (spec §19/§20/§27)
artifacts/                                       captured actual-facts YAML and comparator reports
                                                  for both systems, both runs, plus each profile's
                                                  fully resolved (and hashed) Compose configuration
```

## I4.5 contents

```text
report.md                                        the single deterministic cross-system report
                                                  (spec §21/§27): candidate identity, result
                                                  counts, finding ledger, regression map, known
                                                  limitations, redesign-gate answer, release-
                                                  blocker assessment, GO/NO-GO, I5 handoff
definition-of-done.md                            every spec §28 checkbox verified against the
                                                  actual evidence, not assumed
```

## Decision vocabulary (spec §7)

| Disposition | Meaning |
| --- | --- |
| `FIX` | A general defect or safely correctable semantic gap is demonstrated and corrected. |
| `DOCUMENT_UNSUPPORTED` | The mechanism is deliberately outside current AIP semantics. |
| `DEFER` | A plausible future capability or model change lacks sufficient evidence or safe scope. |
| `NO_CHANGE` | Current behavior is already correct for the claimed scope. |

I4.1's outcome: every finding remains `NO_CHANGE`, `DEFER`, or `DOCUMENT_UNSUPPORTED`; no `FIX` is
approved. The approved production-change list for I4.2 was therefore empty — I4.2 records that
evidence-backed `NO_CHANGE` in `hardening.md` (spec §27's own explicit allowance for this outcome),
with no production code change.
