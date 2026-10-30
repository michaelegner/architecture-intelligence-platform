# Result: v0.8 showcase value qualification

**Governs:** [experiment specification](v08-showcase-value-qualification-experiment.md) (#657).
**Step 1:** [matrix and D5](v08-showcase-value-qualification-step1.md). **Frozen materials:**
[`v08-value-qualification-evidence/`](v08-value-qualification-evidence/) (freeze commit `c5b723d`).
**Run evidence:** [`v08-value-qualification-run/`](v08-value-qualification-run/), verified by its
`SHA256SUMS`.

## Outcome

The result is mixed. All 12 sessions are valid.

| Setting | Result under the frozen criteria (§5.4) |
|---|---|
| T+ vs T− (team-scoped) | **Requests BETTER** for T+: 2, 0 and 2 against 5, 5 and 6. All plan-key and comprehension items EQUAL. All other counts NOT_DISTINGUISHABLE |
| F+ vs F− (full access) | **Q3 coverage BETTER** for F+, but this rests on one partly documented row (row 5). The [sensitivity analysis](#row-5-sensitivity) gives EQUAL. All other items EQUAL. All counts NOT_DISTINGUISHABLE |

What this result supports:

- In the team-scoped setting, the sessions with AIP asked the platform team for less. This is an
  observed advantage under the frozen comparison rule. It is not a measurement of the coordination
  cost for a customer.
- With full access, AIP did not give better planning quality: K1–K8, Q1, Q2, Q3 calibration, Q4 and
  Q5 are EQUAL. The coverage advantage is not robust to the row 5 reading.
- K1–K5 and Q4 are MATCHED in every type. Every arm found the principal migration requirements.
- K6 and K8 are DIFFERENT in every type. No plan met the frozen checkpoint hand-off (K6.2) or the
  §4.2 order of the cut-over checks (K8).
- The unsupported-claim counts do not separate the arms: the ranges overlap (F− 5, 6, 0 against
  F+ 1, 1, 1; T− 4, 5, 4 against T+ 4, 1, 4). The criterion compares ranges, not means.

## Results per type

Item verdicts are the 2-of-3 majority. M = MATCHED, D = DIFFERENT, NS = not scored (T, D5).

| Type | K1–K5 | K6 | K7 | K8 | Q1 | Q2 | Q3 cal. | Q3 cov. | Q4 | Q5 |
|---|---|---|---|---|---|---|---|---|---|---|
| T− | M | D | NS | D | M | M | M | M | M | D |
| T+ | M | D | NS | D | M | M | M | M | M | D |
| F− | M | D | M | D | M | M | M | D | M | D |
| F+ | M | D | M | D | M | M | M | M | M | D |

| Type | Unsupported claims | Tool calls attempted / received | Active time (s) | Output tokens | Requests |
|---|---|---|---|---|---|
| T− | 4, 5, 4 | 32/29, 29/26, 43/39 | 452, 283, 330 | 17,869, 27,919, 34,825 | 5, 5, 6 |
| T+ | 4, 1, 4 | 38/34, 14/13, 29/25 | 432, 281, 370 | 37,852, 28,740, 34,582 | 2, 0, 2 |
| F− | 5, 6, 0 | 35/31, 34/29, 31/28 | 383, 380, 375 | 36,911, 35,119, 38,115 | – |
| F+ | 1, 1, 1 | 26/23, 36/33, 29/25 | 326, 460, 380 | 34,095, 41,635, 34,519 | – |

The per-session scores are in `v08-value-qualification-run/sessions/<session>/scoring.json`, and the
comparison is in `compare-final.json`.

## Row 5 sensitivity

This section is a sensitivity analysis, not the official score
([`sensitivity-row5.json`](v08-value-qualification-run/sensitivity-row5.json)).

Row 5 is Category Query × `catalog.category.events`. The matrix marks it `partly` documented: the
documents name it at diagram level only, without the topic. Under the frozen key, coverage counts row 5
only for `documented: cannot_tell`, because a `yes` needs evidence that resolves and only partial
locations exist. Calibration accepts `yes` or `cannot_tell`.

Every Q3 coverage DIFFERENT in all four types comes from row 5. When row 5 is counted as calibration
counts it, all four types are MATCHED, and F+ vs F− is EQUAL. Only F−_r3 stays DIFFERENT, because it
answered `documented: no`.

## Owner verdicts

The owner gave the three borderline decisions. The other owner-judged items were reviewed against
their cited evidence under the frozen rules, with the owner's conditional go of 2026-10-30. Each verdict
has its reason and its basis in `owner-verdicts/<session>.json`.

- **K6.2 and K8.6 in F−_r2, F−_r3 and F+_r2: DIFFERENT (owner).** The key requires the comparison with
  the checkpoint's upstream and downstream offsets. A direct comparison of the final Redpanda offsets
  with the installed Kafka offsets does not establish it.
- **Q5 statement d** ("a missing document does not mean a missing binding"):
  - **F+_r1: MATCHED.** It names five bindings that are attached but have no promise in the event
    catalog.
  - **F+_r2: DIFFERENT.** It only mentions the missing promise (owner test: an explicit non-absence
    statement is needed).
- **U2 in T+_r3 plan.md: SUPPORTED.** The source cited in answers q4 states that specific handler
  behaviour: tenant-service-api `consumer.go:15-36` and image `AGENTS.md:87-88`.
- **Direction claims (U3): 45 of them, 40 in − sessions.** `matrix.json` has no frozen `direction`
  locations, and its producer locations are only the `topics.go` constants. A claim is SUPPORTED when it
  cites a binding (frozen location, R1 or broker output) and a producer call site of that topic
  (`TopicFor(...)` in the producer's event factory, or the event-to-topic map in the producer's API
  module). 30 claims are SUPPORTED and 15 UNSUPPORTED (values-file lines only, a producer without a
  binding, or a binding without a producer). The frozen `support()` gives the same result for all 45
  when these call sites are added as producer locations.
- **Q5:** only T+_r3 and F+_r1 state all four key statements. Statement a ("an attachment does not
  establish event handling") is in all six + sessions and in none of the six − sessions. This is an
  observation. No criterion uses it.

## Validity, waivers and audit

All 12 sessions are valid ([`waivers.json`](v08-value-qualification-run/waivers.json), with the
exact command and denial of each occurrence):

- **`PLANNING_CHANGE` (waived):** refused `python3 -I -c` schema checks (round 1: 4 sessions; rounds 2
  and 3: 7) and four refused compound read commands. Each was refused before it ran and returned no
  data.
- **`SETTINGS_WRITE` (waived):** T−_r1 and T−_r2 read their own stored tool output in their config
  dir. Claude Code stores a large `grep` result there. Every path in it is inside the session's own
  workspace.
- **F−_r2 `rpk cluster config get` (waived, session valid):** the command is not on the frozen F
  allow list (the v0.8 planning list, spec §4.2). The broker access that the key needs worked in all
  six F sessions: each one received the full `rpk group describe` output.
- **Limitation:** 13 refused read-only commands in F sessions are outside the frozen list, in both F
  arms alike (mainly `kafka-topics.sh --bootstrap-server localhost:9092` and `helm list`). They are
  not audit hits.
- Every preflight before the 12 sessions was clean: AIP removed in −, the snapshot id unchanged in +,
  the broker state equal to R1 before each F session. No image was added during the runs.

## Run identities

| | Value |
|---|---|
| Model / Claude Code | `claude-opus-5-5` / 2.1.312, headless (`claude -p`, `env -i`), default effort, same launch form in all 12 sessions |
| AIP | built from `c5b723d` (the application code of `main` `c3d852d`): image `sha256:faaf121991970df37b4df1737abceb6bc5c1ac5ea0c1b25196a0eb3065f48a14` |
| Snapshot | `aip:snapshot:v1:18d59102a7c451ae8e84d3acaf3d2c6b036ff105ec14a59f255c2be0ffda906e`, unchanged across every removal and restart |
| Harness | `c5b723d` (round 1 sessions); `02f5410` (rounds 2 and 3, and the round 1 audit and scoring) |
| Frozen materials | `v08-value-qualification-evidence/SHA256SUMS` (cards, settings, matrix, keys, rules, criteria, catalogue, plan key `c1e6671a…`), unchanged |
| Order | Round 1 on 2026-10-29 20:05–20:39 UTC; rounds 2 and 3 on 2026-10-29 23:00–23:51 UTC, each round T−, T+, F−, F+ |

## Disclosures

- The declared side (EventCatalog, producer declarations) is generated, as in v0.8.
- T has no organisation-wide code search.
- The R2 list names the other services.
- The key author has read the v0.8 plan.
- One model, one scenario, a public system.
- **Claude Code injects account context into every headless session, in all four types alike:** the
  claude.ai connector tools with their server instructions, and the account's email address. A call to
  a connector tool would be an audit hit; none happened. The email address is redacted in the
  published transcripts.
- The launch form passes `KUBECONFIG` in all types. T denies every cluster and broker command.
- `docker-compose.aip.yml` and `aip-snapshot.txt` are in the run home's top level, as in v0.8. A −
  session could read them but not use AIP. No session did.
- **Harness corrections after the freeze**, each with a regression test that fails without it:
  - Q1 checks the services and the normalized boundary name;
  - the preflight accepts only the recorded bring-up adaptations;
  - the AIP audit rule names only the compose project `aip-v08-i4-aip`;
  - the executable bit is cleared on the `.py` files.

  Round 1 was audited and scored again with the corrected harness. The superseded outputs are kept in
  `sessions/*/superseded/`.
- Four preflight stops of F−_r1 and F+_r1 occurred before an agent started (in `preflight-failed/`):
  in the first attempt, the adaptation rule (corrected); in the second attempt, the operator's own
  pytest trees in `/tmp`.
- The host rebooted after the last session and its scoring. No session was affected. The image
  inventory after the runs was taken after the reboot.
- The published files are sanitized: run-home, checkout, home and operator paths become placeholders,
  and the email address becomes `<owner email>`. `transcripts.pre-sanitize.sha256` holds the digests of
  the original bytes. To rerun the audit or the scorer, map the placeholders back.
