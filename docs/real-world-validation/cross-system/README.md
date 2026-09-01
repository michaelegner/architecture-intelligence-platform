# I4 — Cross-System Model Hardening

This directory holds the I4 evidence and decision trail (see
[`docs/specifications/0.3.0/i4-cross-system-model-hardening.md`](../../specifications/0.3.0/i4-cross-system-model-hardening.md)).
I4 does not run a new validation profile against either upstream system; it converts the two
independent qualifying results already frozen by I2 (Quarkus Super Heroes) and I3 (Apache Airflow)
into one evidence-based model-hardening decision, using the same six-classification vocabulary
frozen by I1 (see [`../README.md`](../README.md)).

```text
docs/real-world-validation/quarkus-super-heroes/   I2's independent dossier and qualifying result
docs/real-world-validation/apache-airflow/         I3's independent dossier and qualifying result
docs/real-world-validation/cross-system/           this directory — I4's joint decision trail
```

## Delivery split (spec §27)

```text
I4.1  Finding Consolidation and Decision Freeze   <- this directory's first contents
I4.2  General Model and Runtime Hardening
I4.3  Distilled Regression and Synthetic Revalidation
I4.4  Final-Candidate Real-System Revalidation
I4.5  RC Qualification
```

I4.1's gate (spec §27): *no production semantic change begins before its decision record is
approved.* I4.1 makes no production code change.

## I4.1 contents

```text
finding-ledger.md                                the normalized ledger (spec §6)
decisions/messaging-operation-compatibility.md   spec §10.1
decisions/queue-topic-boundary.md                spec §10.2
decisions/runtime-role-identity.md               spec §11
decisions/canonical-redesign-gate.md             spec §13
```

## Decision vocabulary (spec §7)

| Disposition | Meaning |
| --- | --- |
| `FIX` | A general defect or safely correctable semantic gap is demonstrated and corrected. |
| `DOCUMENT_UNSUPPORTED` | The mechanism is deliberately outside current AIP semantics. |
| `DEFER` | A plausible future capability or model change lacks sufficient evidence or safe scope. |
| `NO_CHANGE` | Current behavior is already correct for the claimed scope. |

I4.1's outcome: every finding remains `NO_CHANGE`, `DEFER`, or `DOCUMENT_UNSUPPORTED`; no `FIX` is
approved. The approved production-change list for I4.2 is therefore empty — I4.2 is expected to
record an evidence-backed `NO_CHANGE` rather than manufacture hardening work (spec §27's own
explicit allowance for this outcome).
