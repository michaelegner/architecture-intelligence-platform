# I4.2 — General Model and Runtime Hardening

Spec §27's I4.2 scope: "Implement only I4.1-approved corrections... If no production correction is
approved, I4.2 SHALL record an evidence-backed `NO_CHANGE` rather than manufacture hardening work."

## Outcome

`NO_CHANGE`. I4.1 (`finding-ledger.md`, merged as PR #49) approved **zero** `FIX` dispositions —
every finding is `NO_CHANGE`, `DEFER`, or `DOCUMENT_UNSUPPORTED`. The approved production-change
list was empty entering I4.2. This record is I4.2's own formal confirmation of that outcome, per
spec §27's explicit allowance for it, not a restatement without independent basis.

## Evidence-backed rationale

Each I4.1 decision record's actual blocking prerequisite, re-cited rather than generically restated:

- **`decisions/messaging-operation-compatibility.md`** — widening `messaging.operation`/
  `messaging.operation.type` recognition (for either Quarkus's or Airflow's legacy attribute shape)
  is blocked by two unmet safety conditions, not by a requirement that one rule cover both systems:
  no Queue-versus-topic guard exists, and no Service-identity guard exists. Both are named,
  independent prerequisites for any future `FIX`.
- **`decisions/queue-topic-boundary.md`** — `app/telemetry/queue_resolver.py::resolve_queue()` has
  no structural topic-vs-queue refusal path; any unmatched destination name is unconditionally
  minted as an `OBSERVED_ONLY` Queue. Today's zero `SENDS`/`RECEIVES_FROM` facts for Quarkus's
  Kafka `fights` topic are a side effect of the narrow operation-attribute allowlist, not a
  property of the resolver itself.
- **`decisions/runtime-role-identity.md`** — only Airflow exhibits the runtime role/instance
  ambiguity; Quarkus's service identities never needed the distinction. `Service` stays
  `{id, name, version?}`, with no `Process`/`RuntimeRole`/`Deployment`/`ServiceInstance` addition.
- **`decisions/canonical-redesign-gate.md`** — answered `NO`. Zero `INCORRECT_SUPPORTED` findings
  exist in either dossier across every qualifying run to date (I2.1-I2.3, I3.1-I3.4); every open
  limitation is explicit and bounded, not a false supported claim.

No new material finding was discovered during I4.2 itself that would reopen any of the above.

## Hardening checklist (spec §28 Definition of Done, "Hardening" section)

- [x] **Every production change maps to independent evidence.** Vacuously satisfied — zero
      production changes were made.
- [x] **Every accepted rule is general and system-independent.** Vacuously satisfied — zero rules
      were accepted.
- [x] **No unsupported mechanism is represented as supported.** Re-confirmed: `qsh-kafka-fights-
      topic` and the three Airflow PostgreSQL-dependency findings remain `UNSUPPORTED`/
      `DOCUMENT_UNSUPPORTED`; no graph fact represents any of them.
- [x] **No ambiguous identity is guessed.** Re-confirmed: `airflow-runtime-role-identity` and
      `airflow-execution-api-boundary` remain `UNRESOLVED_IDENTITY`; no per-role `Service` or
      Execution-API `CALLS` fact was invented.
- [x] **No unrelated adapter/entity family is introduced.** Re-confirmed: no gRPC adapter, Kafka
      Connect support, Topic/Subscription family, or Database family was added.
- [x] **Every accepted fix has deterministic regression coverage.** Vacuously satisfied — zero
      fixes were accepted, so none require coverage.
- [x] **Any no-change conclusion is evidence-backed.** This record, and the four I4.1 decision
      records it cites.

## Entry-gate re-verification (spec §22 Quality Gates)

Re-run against `main` at `e54e201` (I4.1's merge commit) before starting I4.2, to confirm no drift
occurred between I4.1's merge and I4.2's start:

```text
uv run ruff check .                          -> All checks passed
uv run ruff format --check .                 -> 159 files already formatted
uv run pytest tests/unit tests/integration    -> 664 passed
uv run python -m evaluation run              -> 10/10 PASS (v0.2 deterministic evaluation)
gh run list --branch main                    -> CI + CodeQL green at e54e201
```

## Handoff to I4.3

Since no production or test code changed, I4.3's "finding-to-test map" and "distilled tests"
deliverables (spec §27) reduce to confirming the *existing* regression suite still covers every
ledger finding's current, unchanged behavior — I4.3 is not blocked or altered by this record. The
entry-gate results above (unit/integration/v0.2 evaluation) may be cited directly by I4.3 rather
than re-run from scratch, since nothing in I4.2 could have invalidated them.
