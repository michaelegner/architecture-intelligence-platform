# Findings — Quarkus Super Heroes

Findings from the qualifying comparison (I2.3, `results.md`), classified per the I1 finding
vocabulary. No `INCORRECT_SUPPORTED`, `MISSING_SUPPORTED`, or `UNRESOLVED_IDENTITY` findings
resulted from this run; one `INSUFFICIENT_EVIDENCE` finding did (a diagnostic re-run's own raw
telemetry inspection, not the frozen comparator result — see `qsh-kafka-operation-type-gap` below).

## Summary of material findings

```text
CORRECT                38   (35 PROVIDES + 3 CALLS) — see results.md for the full per-fact transcript
UNSUPPORTED             2   (qsh-grpc-locations, qsh-kafka-fights-topic)
INSUFFICIENT_EVIDENCE   1   (qsh-kafka-operation-type-gap)
MISSING_SUPPORTED       0
INCORRECT_SUPPORTED     0
UNRESOLVED_IDENTITY     0
```

`CORRECT` findings are not individually re-listed here beyond the summary above — enumerating all
38 would only restate `results.md`'s transcript with no additional disposition content, since a
`CORRECT` finding by definition needs no disposition. `results.md` is the source of truth for their
exact identities, and now (after the capture-tool correction below) for their evidence flags too:
all 35 `PROVIDES` facts are `CORRECT` against `evidence: {declared: true}`, not merely against bare
identity.

## Methodology note — a capture-tool defect was found and fixed mid-PR, not the ground truth

An earlier draft of this comparison used a version of `real_world_validation/capture.py` that did
not query declared/observed evidence for `PROVIDES` facts, and (incorrectly) removed the frozen
`declared: true` expectation from `expected.yaml` to match that gap. Review (PR #41 F1) confirmed
AIP's own canonical/provenance model already attaches real `DECLARED` evidence to every `PROVIDES`
relation (`app/ingestion/openapi_adapter.py`) and even has a genuine observed-`PROVIDES` concept for
runtime-discovered operations (`docs/graph-model.md`) — the ground truth was correct all along. The
fix was to correct `capture.py` (now covers AIP's complete canonical relation vocabulary generically,
`app.graph_schema.registry.RELATIONS`, not only the types that also have runtime status) and
re-execute the full live profile from clean state, never to hand-patch the captured result. See
`ground-truth.md`'s "Change log" and `results.md`'s intro for the full account. This is recorded
here because it is itself the kind of methodological event I1 exists to catch: the temptation to
weaken an oracle to match a tool's current limitation, caught and reversed before merge.

## `qsh-grpc-locations`

```text
classification:  UNSUPPORTED
severity:         INFO
disposition:      NO_CHANGE
```

Confirmed as ground-truth anticipated: `rest-fights` called `grpc-locations` during the qualifying
traffic (`GET /api/fights/randomlocation`), and AIP emitted **no** HTTP `CALLS` relation for it —
the gRPC dependency was neither silently dropped into a false supported claim nor otherwise
misrepresented. This is exactly the outcome I2 spec §12/§39 requires. No decision record needed;
the pre-existing `UNSUPPORTED` classification in `expected.yaml` stands unchanged.

## `qsh-kafka-fights-topic`

```text
classification:  UNSUPPORTED
severity:         INFO
disposition:      NO_CHANGE
```

The dossier's `UNSUPPORTED` classification for the Kafka `fights` topic mechanism itself is
unchanged and correct: nothing in this run makes Kafka topics a supported AIP mechanism, and
`expected.yaml` never asserted otherwise. The qualifying traffic did include a real `POST
/api/fights` call that persists a fight and publishes to Kafka topic `fights` (confirmed via
`rest-fights`' own producer logs — a benign, expected `UNKNOWN_TOPIC_OR_PARTITION` warning on the
topic's first-ever use, followed by normal operation), and AIP emitted zero `SENDS`/`RECEIVES_FROM`
facts in scope. **What that "zero" result does and does not prove is qualified by the separate
finding below** — read them together, not this one in isolation.

## `qsh-kafka-operation-type-gap` (PR #41 re-review)

```text
classification:  INSUFFICIENT_EVIDENCE
severity:         MINOR
disposition:      DEFER
```

A dedicated diagnostic re-run (raw OTLP inspection, `evidence/messaging.md`) found that
`rest-fights`' real Kafka producer span uses the attribute `messaging.operation: publish` (the
legacy OTel messaging convention), not `messaging.operation.type` — the only attribute name
`app/telemetry/adapter.py::correlate_queue_observations()` checks
(`app/telemetry/semconv/messaging.py`'s `MESSAGING_OPERATION_TYPE`). A span with no recognized
`operation.type` is silently skipped by that function's own design (not even recorded as
unresolved), and no consumer-side (`event-statistics`) messaging span was observed in this window
at all. **This means the "0 SENDS/RECEIVES_FROM" result above does not demonstrate that AIP safely
refuses to map a *recognized* Kafka messaging span onto Queue semantics** — no span with AIP's
expected attribute shape was ever produced by this profile to test that path in the first place.
The producer/consumer *architecture* relationship (`rest-fights` → topic `fights` → `event-statistics`)
remains independently established from source/config evidence (`evidence/messaging.md`) regardless;
only the runtime-safety claim is affected.

See [`decisions/qsh-kafka-operation-type-gap.md`](decisions/qsh-kafka-operation-type-gap.md) for
the full decision record: deferred to I3/I4, because (a) one system's evidence is not enough to
generalize an attribute-recognition widening, and (b) widening it here would immediately activate
the exact Topic-vs-Queue safety question this finding shows was never actually tested — that
deserves its own explicit decision informed by real evidence, not a side effect of a narrow
attribute fix.

## Non-material observation — narration fallback text (not a finding)

See `results.md`'s "Notable runtime observation." `rest-fights`' `POST /api/fights/narrate`
response used its own local fallback text rather than a live `rest-narration`-generated narration,
most likely due to `rest-narration`'s own startup-time thread contention (`BlockedThreadChecker`
warnings) engaging `rest-fights`' client-side `@Fallback`. This is **not** a finding under the I1
vocabulary because it does not change any comparator classification: AIP's `CALLS` fact for
`rest-fights -> rest-narration` is `CONFIRMED` regardless of which text `rest-narration` internally
returned — architecturally, the call was made and observed. Recorded here for transparency about
real-system behavior encountered during the run, per the spirit of I2 spec §36 ("Airflow/Quarkus as
a model stress test... document the mismatch"), even though it does not rise to a material finding.

## Gate check (I2 spec §46/§50)

```text
exact upstream SHA pinned:                          yes (8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce)
profile execution stability:                        yes - three independent clean-state starts in
                                                     this PR produced identical service/operation
                                                     identities, relation counts, and traffic
                                                     behavior (results.md "Repeatability evidence")
final I2 §43 qualifying-comparison repeatability:   NOT YET COMPLETE - only one comparator run
                                                     (the second) used the final, corrected capture
                                                     contract; a second same-contract comparator run
                                                     is required before this gate is satisfied
                                                     (I2.4/I5), not before I2.3 itself
ground truth frozen before AIP result:              yes (I2.1/I2.2, merged before this run)
>= 4 REST provider contracts in scope:               yes (4: rest-fights/rest-heroes/rest-villains/rest-narration)
>= 3 REST caller dependencies investigated:          yes (3: heroes/villains/narration)
>= 1 runtime-confirmed REST flow:                    yes (3: all three CALLS relations CONFIRMED)
gRPC boundary evaluated:                             yes (UNSUPPORTED, confirmed not misrepresented)
Kafka topic boundary evaluated:                      yes, mechanism confirmed UNSUPPORTED - but see
                                                     qsh-kafka-operation-type-gap: the Queue-mapping
                                                     *safety* sub-claim was not actually testable by
                                                     this profile (INSUFFICIENT_EVIDENCE, deferred)
all findings classified:                             yes
all CRITICAL findings dispositioned:                 yes (none exist)
critical false supported facts:                      0
```

## Decision records

One: [`decisions/qsh-kafka-operation-type-gap.md`](decisions/qsh-kafka-operation-type-gap.md)
(`DEFER`) — see above. Every other material finding in this run received `NO_CHANGE` — the
pre-existing I2.1/I2.2 ground-truth classifications were confirmed exactly as frozen, with no AIP
behavior contradicting them.
