# Decision: Canonical Redesign Gate

Spec §13, informed by the eight Mandatory Cross-System Questions (spec §9) and every finding in
`../finding-ledger.md`.

## Context

I4's terminal question is whether any unresolved I2/I3 finding requires a fundamental Canonical
Model redesign before `v0.4`, per spec §13:

```text
NO  — current supported claims remain semantically correct;
      limitations are explicit and bounded.

YES — a false supported claim or fundamental invariant failure
      cannot be fixed safely within the current model.
```

`YES` would block `v0.3.0-rc.1` until a redesign is specified, implemented, regression-tested, and
both systems revalidated. This decision is made only after every other I4.1 decision record is
final, since it is a rollup of them.

## Independent evidence

Frozen qualifying results (spec §5), both zero `INCORRECT_SUPPORTED` and zero `MISSING_SUPPORTED`:

```text
Quarkus:  CORRECT 38, UNSUPPORTED 2, INSUFFICIENT_EVIDENCE 1, INCORRECT_SUPPORTED 0, MISSING_SUPPORTED 0
Airflow:  CORRECT 9, UNSUPPORTED 3, UNRESOLVED_IDENTITY 2, INSUFFICIENT_EVIDENCE 1, INCORRECT_SUPPORTED 0, MISSING_SUPPORTED 0
```

## Mandatory Cross-System Questions (spec §9) — answered with explicit evidence

**1. Does canonical `Service` remain adequate for the supported v0.3 scope?**
Yes. Every `CORRECT` `PROVIDES`/`CALLS` fact in both dossiers resolves against the
`{id, name, version?}` `Service` model without ambiguity. The one case where it is not fully
adequate (Airflow's role/instance distinction) is explicitly captured as `UNRESOLVED_IDENTITY`, not
silently absorbed - see `runtime-role-identity.md`.

**2. Is a runtime role/instance distinction needed to prevent a false supported claim, or is
`UNRESOLVED_IDENTITY` the safe result?**
`UNRESOLVED_IDENTITY` is the safe result. See `runtime-role-identity.md`: no false claim exists
today, and no cross-system evidence yet justifies the model change.

**3. Can legacy and current OpenTelemetry messaging-operation attributes be normalized without
widening unsupported mechanisms into Queue semantics?**
Not yet demonstrated safely. See `messaging-operation-compatibility.md`,
`queue-topic-boundary.md`, and question 5 below: normalizing either Quarkus's or Airflow's legacy
shape without an accompanying Queue/topic guard (question 4) and Service-identity guard
(question 5) would risk exactly the false claim this question asks about. Deferred, not abandoned;
each guard's absence is the named prerequisite, not the difference between the two systems' shapes.

**4. Is `Queue` safe for competing-consumer queues while excluding topic/subscription semantics?**
Only incidentally, not structurally. The frozen qualifying result is safe - zero facts exist for
Kafka's `fights` topic - but that is a side effect of the narrow operation-attribute allowlist
filtering the span before it ever reaches `resolve_queue()`, not a property of the resolver itself.
Re-reading `resolve_queue()` directly (`queue-topic-boundary.md`) shows it has no topic-vs-queue
refusal path at all: any unmatched destination name is unconditionally minted as an `OBSERVED_ONLY`
Queue. A structural guard does not yet exist, and is the named prerequisite for ever safely
widening question 3's attribute recognition.

**5. Are resolved logical sender and consumer identities prerequisites for `SENDS` and
`RECEIVES_FROM`?**
Not yet enforced by production code, which is itself the finding. Airflow's zero
`SENDS`/`RECEIVES_FROM` facts are evidence that its messaging span is filtered out by the
operation-attribute check *before* `resolve_runtime_span()`/`resolve_service()` is ever reached
(`correlate_queue_observations()`'s check order, re-verified for this decision) - not evidence that
a resolved-identity prerequisite is already safely enforced downstream. Re-reading
`resolve_service()` shows its Tier 4 mints an `OBSERVED_ONLY` Service for any unmatched
`service_name` unconditionally, with no refusal for a generic/ambiguous name such as Airflow's
`unknown_service` (`messaging-operation-compatibility.md`). So the answer to this question is:
**it should be**, but is not yet a demonstrated, enforced property of the current implementation -
it is named as an explicit, additional prerequisite (alongside the Queue/topic guard) for any
future widening of messaging-operation-attribute recognition, not something today's zero-fact
result already proves.

**6. Does runtime evidence/status handling lose, fabricate, or overstate evidence?**
No. Zero `INCORRECT_SUPPORTED` findings exist in either dossier across all qualifying runs (I2.1-
I2.3, I3.1-I3.4). Every `UNSUPPORTED`/`UNRESOLVED_IDENTITY`/`INSUFFICIENT_EVIDENCE` finding is
explicit and traceable to a named evidentiary gap, not silently dropped or converted into a
supported claim.

**7. Do database dependencies require an immediate canonical relation family for correctness?**
No. Airflow's three PostgreSQL-dependency findings are `UNSUPPORTED` with `INFO` severity and no
correctness impact - see `../finding-ledger.md`. Spec §12 explicitly disallows adding a Database
family absent a release-blocking false claim, and none exists.

**8. Does any finding require a fundamental Canonical Model redesign before v0.4?**
No - see Decision below.

## Alternatives considered

1. **NO** - current supported claims remain correct; every limitation is explicit and bounded.
   Chosen.
2. **YES** - would require identifying a false supported claim or fundamental invariant failure.
   None exists: `INCORRECT_SUPPORTED` is 0 in both dossiers across every qualifying run to date,
   and every open finding above is a bounded, explicit, correctly-withheld claim rather than an
   incorrect one.

## Decision

`NO`. Current supported claims in both dossiers remain semantically correct. Every open limitation
(messaging-operation-attribute scope, runtime-role identity, database dependencies, Execution API
boundary) is explicit, bounded, and does not represent a fundamental invariant failure.

## General semantic rule

The Canonical Model's existing invariants - Queue/Message separation, DECLARED-only provenance,
explicit `UNRESOLVED_IDENTITY`/`UNSUPPORTED` over guessing - remain sufficient for the v0.3 scope
validated by I2 and I3. No redesign is undertaken.

## Consequences

- `v0.3.0-rc.1` is not blocked by this gate.
- The approved production-change list for I4.2 is empty (see `../finding-ledger.md`,
  `../README.md`); I4.2 SHALL record an evidence-backed `NO_CHANGE` per spec §27's explicit
  allowance for this outcome.
- Every `DEFER` above (`qsh-kafka-operation-type-gap`, `airflow-celery-messaging-runtime-status`,
  `i4-celery-instrumentation-semconv-mismatch`, `airflow-runtime-role-identity`) remains open for a
  future iteration, each with its prerequisite(s) explicitly named in its own decision record -
  including the newly identified Service-identity guard (question 5) alongside the Queue/topic
  guard (question 4), both now required before any messaging-operation-attribute widening.

## Production changes

None.

## Regression coverage

None required (no implementation change).

## Quarkus impact

None. All Quarkus findings and dispositions stand exactly as I2 left them.

## Airflow impact

No classification or graph-state change. `airflow-celery-messaging-runtime-status`'s I4 disposition
is corrected from an I3.2-era `NO_CHANGE`-leaning framing to `DEFER` (see
`messaging-operation-compatibility.md`); every other Airflow finding stands exactly as I3 left it.

## Deferred work

None beyond what each individual decision record (`messaging-operation-compatibility.md`,
`queue-topic-boundary.md`, `runtime-role-identity.md`) already names as its own prerequisite -
notably, any future messaging-operation-attribute widening now requires **both** a Queue/topic
safety guard and a Service-identity safety guard, not just the former.
