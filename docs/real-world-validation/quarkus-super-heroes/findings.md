# Findings — Quarkus Super Heroes

Findings from the qualifying comparison (I2.3, `results.md`), classified per the I1 finding
vocabulary. No `INCORRECT_SUPPORTED`, `MISSING_SUPPORTED`, `UNRESOLVED_IDENTITY`, or
`INSUFFICIENT_EVIDENCE` findings resulted from this run.

## Summary of material findings

```text
CORRECT                38   (35 PROVIDES + 3 CALLS) — see results.md for the full per-fact transcript
UNSUPPORTED             2   (qsh-grpc-locations, qsh-kafka-fights-topic)
MISSING_SUPPORTED       0
INCORRECT_SUPPORTED     0
UNRESOLVED_IDENTITY     0
INSUFFICIENT_EVIDENCE   0
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

Confirmed as ground-truth anticipated: the qualifying traffic included a real `POST /api/fights`
call, which persists a fight and publishes to Kafka topic `fights` (confirmed via `rest-fights`'
own producer logs — a benign, expected `UNKNOWN_TOPIC_OR_PARTITION` warning on the topic's
first-ever use, followed by normal operation). `expected.yaml`'s scope deliberately includes
`service:event-statistics` and `SENDS`/`RECEIVES_FROM` specifically so a false Queue mapping would
have been observable as an unexpected in-scope `INCORRECT_SUPPORTED` finding (PR #39 review F2) —
none appeared. AIP correctly emitted zero `SENDS`/`RECEIVES_FROM` facts for this topic. This is
exactly the outcome I2 spec §13-15 requires: the Kafka boundary was genuinely exercised by real
message traffic, and AIP did not stretch Queue semantics to cover it. No decision record needed.

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
profile reproducible:                               yes - two independent clean-state runs in this
                                                     PR produced identical classifications/counts
                                                     (results.md "Repeatability evidence")
ground truth frozen before AIP result:              yes (I2.1/I2.2, merged before this run)
>= 4 REST provider contracts in scope:               yes (4: rest-fights/rest-heroes/rest-villains/rest-narration)
>= 3 REST caller dependencies investigated:          yes (3: heroes/villains/narration)
>= 1 runtime-confirmed REST flow:                    yes (3: all three CALLS relations CONFIRMED)
gRPC boundary evaluated:                             yes (UNSUPPORTED, confirmed not misrepresented)
Kafka topic boundary evaluated:                      yes (UNSUPPORTED, confirmed not misrepresented)
all findings classified:                             yes
all CRITICAL findings dispositioned:                 yes (none exist)
critical false supported facts:                      0
```

## Decision records

None required. Every material finding in this run received `NO_CHANGE` — the pre-existing I2.1/I2.2
ground-truth classifications were confirmed exactly as frozen, with no AIP behavior contradicting
them. No `docs/real-world-validation/quarkus-super-heroes/decisions/` directory is created for this
run; the `_template/decision-record.md` template remains available for I2.4 or I3 should a future
run surface something requiring one.
