# Experiment: v0.8 showcase value qualification

**Status:** Draft 0.2 (2026-10-29; #657 review corrections)
**Inputs:** [doctrine §8](../../product-doctrine-and-strategic-direction.md#8-product-validation) (H1),
the [v0.8 I4 spec](../0.8.0/i4-agent-run-report-and-release.md) and its
[evidence package](../0.8.0/i4-evidence/README.md), the
[I2 expected answers](../0.8.0/i2-assessment-projection-and-tool.md#81-c1-primary-acceptance).
**Output:** a result record next to this file. It is an input to the v0.9 scope. It does not set it.

## 1. Purpose

v0.8 qualified two things:

- AIP produces the correct binding picture (I4 Proof C, the nine I2 §8.1 rows);
- an agent with AIP and the source identified the key cross-boundary requirements: K1–K5 and K7
  `MATCHED` (I4 Proof A). The plan also had recorded deviations: 6 `DIFFERENT` and 1 `MISSING`
  K6/K8 sub-checks, and E4 and E6 were not met
  ([completion record](../0.8.0/i4-completion-record.md)).

v0.8 did not qualify what AIP **adds**. Every H1 part of doctrine §8 is comparative ("than with
their current means"), and v0.8 had no arm without AIP. It is also open whether the v0.8 agent would
have found K1–K4 from the source alone.

This experiment qualifies AIP's added value **in the v0.8 showcase**, for the H1 parts that a public
system can measure.

**Question:**

> In the v0.8 migration scenario, what does an agent with AIP understand and plan differently from
> the same agent without AIP, with the same access otherwise, and at what effort?

**Out of scope:**

- owner effort (H2) and real coordination cost: they need a target customer (doctrine §8);
- a claim of product value: the result qualifies the value in the showcase only;
- the v0.9 consequence of each outcome: the owner decides it after the result exists;
- execution of the plan: all sessions are planning sessions;
- any change to AIP.

## 2. Measures

| Measure | H1 part | Source |
|---|---|---|
| Plan key items K1–K8 matched | decision quality | the existing plan key (§5.1) |
| K1–K4 missing from the plan | surprises | the plan key |
| Comprehension items matched, with Q3 split into information coverage and calibration | comprehension | the comprehension key (§5.2) |
| Unsupported claims | unsupported claims | the claim rules (§5.3) |
| Tool calls, active agent time, output tokens | investigation effort | the transcript (§6.4) |
| Requests and what each one revealed | avoidable coordination | the request record (§4.3), team-scoped only |
| Source kind of each binding claim | attribution | the agent's evidence entries (§4.4) |

## 3. Step 1: binding × source matrix

Step 1 needs the Sokol111 clones at the v0.7.2 freeze commits. It needs no environment and no agent.

For each of the nine I2 §8.1 rows, record what each source establishes:

| Source | Content |
|---|---|
| Documents | `ecommerce-workspace/docs` |
| Team source | the team-scoped repositories (§4.2), without `ecommerce-infrastructure` |
| Infrastructure | `ecommerce-infrastructure` |
| All source | all 16 repositories |
| Broker tools | the frozen v0.8 capture [`S1-13-groups-describe.txt`](../0.8.0/i4-evidence/raw/S1-13-groups-describe.txt) |
| AIP | the I2 §8.1 row |

Each cell records:

- whether the source establishes the consumer × topic pair: `YES`, `PARTLY` or `NO`;
- whether the crossing direction can be derived;
- which declared or observed status can be derived;
- a file and line, or a command and output line, for every `YES` and `PARTLY`.

The matrix also records the **leak check**. Which team-scoped content reveals K2–K4: the
documents, `ecommerce-infrastructure`, and the Go module files of the team repositories.

The matrix is the information baseline of the result: it shows where AIP adds information and where
it adds only preparation. It is the only input to the comprehension key apart from I2 §8.1 (§5.2).

**Owner checkpoint 1:** the owner reviews the matrix and decides whether `ecommerce-infrastructure`
is in the team-scoped workspace (§4.2). Nothing in §5 is frozen before this checkpoint.

## 4. Step 2: sessions

### 4.1 Session types

| Type | Source in the workspace | Cluster and broker tools | AIP | Request channel |
|---|---|---|---|---|
| F+ | all 16 repositories | yes | yes | no |
| F− | all 16 repositories | yes | no | no |
| T+ | team-scoped | no | yes | yes |
| T− | team-scoped | no | no | yes |

Each type runs **3 times** (owner decision, 2026-10-29): 12 valid sessions. All sessions are planning
sessions. No session changes the environment.

### 4.2 Settings

**Full access (F).** The v0.8 planning access: the source, the documents, read-only `docker`,
`kubectl` and `helm` commands, and the `rpk` and Kafka commands of the v0.8 planning settings. The
card says: run one command per Bash call. The settings allow each listed command in that form, so
that broker access works in practice. v0.8 refused a compound `rpk` loop, and the agent got no broker
output.

**Team-scoped (T).** The repositories of the team that owns Catalog Management:

- `ecommerce-catalog-service`, `ecommerce-catalog-service-api`;
- `ecommerce-image-service`, `ecommerce-image-service-api`;
- the dependencies: `ecommerce-commons`, `ecommerce-tenant-service-api`;
- the documents: `ecommerce-workspace`;
- `ecommerce-infrastructure` only if the owner includes it at checkpoint 1.

No `docker`, `kubectl`, `helm` or broker command. `kubectl describe` and `docker inspect` show the
environment of other services, so the team-scoped settings deny the whole command group, not single
subcommands. The card states that the platform team has the cluster and broker access.

**What the team-scoped setting tests**, fixed now for both outcomes of checkpoint 1:

| `ecommerce-infrastructure` | What T tests | K7 |
|---|---|---|
| excluded | discovery without other teams' repositories and without runtime access | not scored in T |
| included, and Step 1 shows it reveals K2–K4 | discovery without runtime access only | scored |
| included, and Step 1 shows it does not reveal K2–K4 | as "excluded" | scored |

**Disclosure for T:** no org-wide code search. Many organisations have it, and it would weaken the
setting. Whether customers have it is a question for the customer evaluation.

### 4.3 Request channel (T+ and T−)

- The agent writes `requests.json` and ends its turn with `OPERATOR: please answer requests.json`.
  Each request has an id, a `kind`, the `repository` for kind `repository_access`, and a free-text
  reason.
- The card names the three kinds and lists the repositories that `repository_access` can name. An
  engineer in a multi-team organisation sees the organisation's repository list. The list names the
  other services, and this is disclosed.
- **Matching is mechanical, by `kind` only.** The free text is recorded and never read for matching.
  The operator returns the verbatim catalogue entry and adds nothing.

| `kind` | Entry | Answer |
|---|---|---|
| `broker_consumer_groups` | R1 | the frozen v0.8 capture `S1-13-groups-describe.txt`, verbatim |
| `repository_access` | R2 | the named repository, added to `src/` at its freeze commit, if it is on the R2 list; otherwise R3 |
| any other value, or an invalid request | R3 | `not available` |

**R2 list:** the Sokol111 repositories that are not in the team-scoped workspace, except
`ecommerce-infrastructure`. Only checkpoint 1 decides on that repository; a request cannot add it.

**Expansion policy:** there is no request budget, because the number of requests is the measure. Each
request gets one answer, and each repository is one grant. The record lists every request, its
entry, every grant and the key items each answer revealed.

The card already states the Kafka cluster state, so the catalogue does not repeat it.

A request is avoidable coordination by definition: the answer existed, but the agent could not reach
it.

### 4.4 Task card and outputs

The card is the [v0.8 task card](../0.8.0/i4-evidence/task-card.md) with these changes only:

- the planning session only; the execution session is removed;
- the AIP paragraph only in F+ and T+;
- the access text of the setting (§4.2), and the request channel in T;
- the plan schema uses one evidence field for all types (below);
- a third output, `answers.json` (below).

The card variants are committed with their digests before the first session.

**Plan schema.** `architecture_citations` and `implementation_justification` are replaced by one
array, `evidence[]`. Each entry has a `kind` and a `reference`:

- `kind` is one of `aip`, `documentation`, `source`, `configuration`, `broker_tool`, `request` or
  `reasoning`;
- an `aip` entry also has the `snapshot_id` and either a row (broker, topic, consumer Service) or
  evidence refs;
- a **factual claim** (a binding, its direction, its status, a producer) needs at least one entry of
  a kind other than `reasoning`, and that entry must **resolve**: the file exists and the line shows
  the claim; the command output (in the transcript) shows it; the AIP row or ref is in the recorded
  answer of that snapshot; the request id was answered with an entry that shows it;
- `reasoning` supports rationale only, never a factual claim.

The binding and mechanism scoring of the plan key reads topics, direction, services and files, not
the evidence. So the schema change does not favour one arm.

**`answers.json`** answers five questions. The v0.8 report answered them, not the agent, so these
answers have no v0.8 baseline.

| # | Question | Form |
|---|---|---|
| Q1 | Which services move, and which boundary changes? | services |
| Q2 | Which consumer × topic bindings cross that boundary? | rows: consumer service, topic, direction |
| Q3 | For each binding: is it documented, is it observed at runtime, or can you not tell? | per row of Q2, with evidence entries |
| Q4 | Why does each binding matter for this move? | per row: what the move must preserve |
| Q5 | What does your evidence not establish, and what must be verified after the move? | statements |

Every claim has evidence entries in the form of the plan schema.

## 5. Keys and rules

All keys, rules, criteria and the catalogue are written after checkpoint 1 and frozen with their
digests before the first session. They are derived only from I2 §8.1, the existing plan key and the
Step 1 matrix. The key author has read the v0.8 plan; this is disclosed.

### 5.1 Plan key

The existing [`plan-key.json`](../0.8.0/i4-evidence/plan-key.json), unchanged. Plan-only scoring:

- K1–K4: as in v0.8 (topic, direction, allow-list);
- K5: the plan's allow-lists only;
- K7: the plan's services and files only;
- K6 and K8 sub-checks: the owner's verdicts, as in v0.8.

### 5.2 Comprehension key

| Item | Expected |
|---|---|
| Q1 | Catalog and Image; the Catalog Management boundary |
| Q2 | the six `INBOUND`/`OUTBOUND` rows of I2 §8.1. `INSIDE` and `NONE` rows are not crossing rows |
| Q3 | per row and per session: the status that **the sources of that session** establish, from the Step 1 matrix. In T, these are the workspace plus the request answers that the session received |
| Q4 | per row: the delivery that the move must preserve (the K1–K4 requirement) |
| Q5 | statements from the Step 1 matrix and the four I2 §8.1 limitations, in source-neutral words: attachment does not establish event handling; a capture is one point in time and one broker scope; a producer is known from the source or a declaration, not observed; a missing document does not mean a missing binding |

**Q3 has two scores, reported separately:**

- **Calibration:** the status matches what **the sources of that session** establish. An agent
  without AIP that says "cannot tell" where its sources cannot tell is calibrated.
- **Information coverage:** against one **common reference** for all sessions, the union of all
  sources in the Step 1 matrix: per crossing row, whether the session established that the binding
  is observed, and whether it established its documented status.

Equal calibration does not mean equal comprehension. The result does not conclude "equal
comprehension" from calibration alone. The difference in coverage is AIP's information contribution.
AIP's declared side includes the EventCatalog and the producer declarations generated for the
showcase. The result discloses this, and it does not count that part as evidence a team would have.

### 5.3 Unsupported-claim rules

Each rule has a one-look test. Claims that the card already forbids (lossless, exactly-once) are not
counted.

| Rule | An unsupported claim |
|---|---|
| U1 | states that the bindings found are all the bindings, with no basis for the closed world |
| U2 | states which events a consumer handles, or how, with no source reference |
| U3 | states a factual claim with no resolving evidence entry other than `reasoning` (§4.4) |
| U4 | states that a binding is documented when no document names it, or the reverse |
| U5 | concludes from a missing declaration that a binding is not promised or not used |
| U6 | states a result of the move as established, in place of a check to run |

**Counting:** the scorer reads `plan.json`, `plan.md` and `answers.json` of a session. A claim is
identified by its rule subject: the consumer × topic pair for U2–U5, the statement for U1 and U6.
The same claim stated more than once in a session counts once. A claim that breaks several rules
counts once and records every rule id it breaks.

### 5.4 Criteria

Fixed before the first session. For each session type:

- **Key items (K1–K8, Q1–Q5):** the type's verdict on an item is the verdict in at least 2 of its 3
  runs. With no such verdict, the item is `MIXED`.
- **Counts (unsupported claims, tool calls, active time, output tokens, requests):** the 3 values.

Between the arms of one setting (F+ vs. F−, T+ vs. T−):

- a key item differs when the two types' verdicts differ and neither is `MIXED`;
- a count differs only when the two ranges do not overlap;
- otherwise the result is `NOT DISTINGUISHABLE`.

For every count, **lower is better**: unsupported claims, tool calls, active time, output tokens,
requests. The result shows effort and requests next to the K1–K4 and coverage results of the same
type, because a lower count with fewer bindings found is not a better result. Q3 calibration and
coverage are compared as key items.

Per setting and measure, the result says: with AIP better, equal, worse, or not distinguishable. A
result of no difference is valid.

## 6. Run

### 6.1 Environment

- Bring-up as in v0.8 I4 S1, with the same pins.
- AIP is built from `main` at the run commit, with `experimental.binding-picture` on. The before-wave
  capture B-R is imported, and the answer must give the nine I2 §8.1 rows.
- **Broker state check:** the live consumer groups, their topics and their member counts equal
  `S1-13-groups-describe.txt`. Offsets are not compared. The check runs after the bring-up and again
  before **each F session**, so what the F sessions see live is what the T sessions get through R1.
  An F session with a failed check before it is invalid (§6.5).
- The snapshot id is recorded.

**AIP is removed during F− and T− sessions**, with its datastore container. A stopped container is
not enough: `docker ps -a` lists it, and `docker inspect` shows its mounts, which include AIP's
inputs. After each new start, the snapshot id must be unchanged.

**F− and T− do not register AIP:** their workspace has no `.mcp.json` entry for AIP, and their
settings allow no `mcp__aip` tool. The operator checks both before each session.

**AIP's inputs are withheld in all four types:** the input and capture directories (the generated
EventCatalog, the producer declarations, the mappings, the captures) are withheld paths of the audit
and Read deny rules in the settings, as the AIP checkout is.

### 6.2 Order and isolation

- Each round runs T−, T+, F−, F+. There are three rounds.
- Each session gets a new workspace and an empty `CLAUDE_CONFIG_DIR`. No session sees another
  session's files.
- Web tools are denied. The AIP checkout is denied, as in I4 §4.
- No transcript export goes into a workspace.
- Before each session, the operator checks that the workspace is clean and that no earlier output is
  reachable.

### 6.3 Agent

The same model, Claude Code version, effort setting and launch form (`claude -p`, `env -i`) in all
12 sessions. The record names each one. The same first message as v0.8 planning, extended by
`answers.json`.

### 6.4 Audit and effort

- The I4 audit runs on every transcript. The harness changes needed for sessions with no AIP call and
  for request turns are made and unit-tested before the first session.
- The audit also flags any network call to the AIP port or its datastore ports in F− and T−.
- Every tool call is recorded as **attempted** or **received**, from its result. A refused call
  counts as attempted only.
- **Active agent time** is the sum of the agent's turns. The time a T session waits for the operator
  is excluded.

### 6.5 Validity

A session is invalid when:

- it is cut off by a usage limit;
- the audit shows an isolation breach that the owner does not waive;
- the operator answers a request outside the catalogue;
- the broker state check before an F session fails;
- an F− or T− session has AIP registered.

An invalid session is kept in the record and replaced by a new session of the same type in a new
workspace. The count stays at 3 valid sessions per type. No other rule adds or removes sessions.

## 7. Scoring and record

- The scorer decides each mechanical item: K1–K5, K7, Q1, Q2, Q3 coverage, and the U3 and U4 checks
  against the Step 1 matrix and the transcript.
- The owner gives a verdict with a one-line reason only on the other items. The scorer lists the
  candidate answers for each.
- The result record contains:
  - the Step 1 matrix;
  - per session: the plan, the answers, the audit, the requests and grants, the scores, the effort,
    and the sanitized transcript with its digest, so that the audit, the effort and the claim counts
    can be reproduced;
  - for the session set: the digests of the card variants, the keys, the rules, the catalogue and the
    settings; the AIP commit, image id and snapshot id; the model and Claude Code version;
  - per setting: the criteria results (§5.4);
  - the disclosures: the generated declared side; no code search in T; the R2 list names the other
    services; the key author has read the v0.8 plan; one model; one scenario; a public system.

## 8. Delivery

| PR | Content |
|---|---|
| 1 | this specification |
| 2 | Step 1 and owner checkpoint 1; the keys, rules, criteria, catalogue, card variants and settings with their digests; the harness changes with unit tests (the audit: sessions without AIP, request turns, the new withheld paths and ports; `plan_format`: the new plan schema and `answers.json`; the scorer: plan-only K5 and K7, the Q items, U3 and U4); the 12 sessions; the scoring; the result record |

The run needs one bring-up. It fits one or two usage windows, with a checkpoint between them.

## 9. Decisions

| # | Decision | Source |
|---|---|---|
| D1 | The goal is AIP's added value in the showcase, over all H1 parts that a public system can measure | owner, 2026-10-29 |
| D2 | Two settings: full access, and team-scoped with counted requests | owner, confirmed in the #657 review |
| D3 | 3 runs per session type, fixed before the start | owner, 2026-10-29 |
| D4 | The criteria are frozen before the run; the v0.9 consequences are not set here | owner, confirmed in the #657 review |
| D5 | `ecommerce-infrastructure` in the team-scoped workspace | open: owner checkpoint 1 |
