# Owner review: proposed verdicts (not approved)

> **Superseded by the owner decisions of 2026-10-30.** This README describes the proposals as first
> submitted. The final verdicts are in `../owner-verdicts/`, each with its basis: K6.2 and K8.6 in
> F-_r2, F-_r3 and F+_r2 are DIFFERENT (owner); Q5 is MATCHED in F+_r1 and DIFFERENT in F+_r2 (owner
> test); U2 in F-_r2 plan item 5 is UNSUPPORTED; U2 in F+_r3 q5[5] is NOT_A_CLAIM. The comparison in
> `compare-if-proposals-accepted.json` is from before those decisions; the official one is
> `../compare-final.json`.

One file per session, `<session>.proposed.json`. Each one has every owner item that the scorer left
pending, each with a proposed verdict and its reason:

- `K6_K8`: the 11 sub-checks, with the plan items. I applied the same strictness as the v0.8 owner
  verdicts (`0.8.0/i4-evidence/owner-verdicts.json`): the order of spec §4.2, an exact lag 0, and the
  checkpoint equality before the restart.
- `Q4`, `Q5`: the Q5 entry also gives the coverage of the four key statements (a–d).
- `claims`: the U1/U2/U5/U6 keyword candidates and the U3 claims the scorer could not resolve.

Items marked **BORDERLINE** need your decision:

- K6.2/K8.6 in F-_r2, F-_r3 and F+_r2. The plan checks the final Redpanda offsets against the installed
  Kafka offsets before the restart, through the end offsets, but names no checkpoint record. I propose
  MATCHED.
- Q5 d in F+_r1 and F+_r2. The statement names a missing promise in the event catalog, not a missing
  document. I propose DIFFERENT.
- U2 in T+_r3 plan.md. The handler statement has no source reference in plan.md, but answers q4 has
  one. I propose SUPPORTED.

U3 direction claims (45, 40 of them in `-` sessions). `matrix.json` has no frozen `direction`
locations, and its producer locations are only the `topics.go` constants. Most claims cite producer
call sites (`TopicFor(...)`, the event-to-topic map) together with a binding from R1, broker output or
a frozen location. I propose those as SUPPORTED. I propose UNSUPPORTED where the evidence does not
establish the direction: values-file lines only, a producer with no binding, or a binding with no
producer.

`compare-if-proposals-accepted.json` is the comparison that results if every proposal is accepted. It
was computed in a scratch copy. It is not the official score.

- F+ vs F-: K6 WORSE. This rests on the BORDERLINE K6.2 proposals: with all of them DIFFERENT, K6 is
  EQUAL. Q3 coverage BETTER (row 5, see `../sensitivity-row5.json`). All other items EQUAL.
- T+ vs T-: requests BETTER. All other items EQUAL or not distinguishable.
- Unsupported claims are NOT_DISTINGUISHABLE in both settings (F- 5/5/0 against F+ 1/1/1; T- 4/5/4
  against T+ 4/1/4).

An observation that does not change a criterion: Q5 statement a ("an attachment does not establish
event handling") appears in all six `+` sessions and in none of the six `-` sessions.
