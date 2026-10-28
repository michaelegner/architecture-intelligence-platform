# AIP v0.8 I4: Agent Run, Report and Release

**Status:** Draft 0.2 (2026-10-28; review on #650: Proof B coverage rule for K1–K4)  
**Governs:** [v0.8 specification](specification.md) §4.4, §6, §7 I4 and §8, as amended by D16–D19 (§14).  
**Baseline:** `main` at `459d863` (I3 complete: [completion record](i3-completion-record.md), [handoff](i3-i4-handoff.md)).  
**Hands off to:** the v0.8.0 release closure.

## 1. Purpose

I4 runs wave 1 (parent §4) a second time. This time a coding agent plans the wave and carries it
out. I4 does four things:

1. **Proofs A–C** (parent §4.4) on the live environment:
   - A: the agent's plan is scored against a plan answer key that is frozen before the run;
   - B: every AIP claim that the plan cites resolves and supports the binding behind the plan item;
   - C: the after-wave captures reproduce `expected-after.json`.
2. **The report:** one generated HTML report in four parts (parent §6), built around the five
   situation-awareness questions (§8).
3. **The frozen replay package:** the frozen inputs reproduce the report and the citations.
4. **The release:** the lightweight v0.8.0 demonstration release.

The demonstration line, which the report states:

> AIP establishes the bindings. The agent derives the migration requirements, then chooses and
> carries out the plan. Independent evidence establishes what the migration achieved.

**Non-goals:**
- the hosted redeploy with the experimental tool on (D19);
- any change to AIP semantics, the six existing tools or the binding-picture contract;
- a claim that AIP makes the migration correct, safe or lossless.

## 2. Pins

| Item | Pin |
|---|---|
| Environment | unchanged from I3: the [package README pins](i3-evidence/README.md#pins), including the Logto digest that is new for I4 |
| Sokol111 revisions | unchanged: the v0.7.2 [freeze](../0.7.2/i2-evidence/sokol111/freeze.md) |
| AIP | built from the I4a merge commit, with `experimental.binding-picture` on |
| Capture utility | unchanged: `harness/kafka-capture/capture.py` with `confluent-kafka==2.16.0` |
| Agent | Claude Code. The operator records the exact model ID, the Claude Code version and the settings file before the planning session. The record is committed with the run |

## 3. Two keys (D16)

I4 uses two frozen references. They measure different things, and they are never mixed.

| Key | Measures | File | Frozen |
|---|---|---|---|
| **Plan answer key** | Proof A: does the agent's plan contain the expected wave plan? | `i4-evidence/plan-key.json` + `plan-key.sha256` | in I4a, before any run; never edited |
| **Capture reference** | Proof C: do the after-wave captures give the expected binding picture? | [`i3-evidence/expected-after.json`](i3-evidence/expected-after.json) | in I3a; unchanged |

The I3 handoff calls `expected-after.json` "the scoring key". In I4 it scores Proof C only.

### 3.1 Plan answer key

The key is written from parent §4.1 and §4.2. It has two kinds of item:

- **Binding items** (K1–K4) preserve the delivery of one topic across the boundary. AIP establishes
  the binding behind the item. Source, configuration and technical reasoning support the chosen
  mechanism.
- **Mechanism items** (K5–K8) are about how the wave is carried out. AIP gives only the reason for
  the item: which bindings must stay available. AIP never establishes that the mechanism is correct.

| # | Kind | Item | Architecture evidence (expected AIP rows, before the wave, Redpanda) | Implementation justification (never AIP) |
|---|---|---|---|---|
| K1 | binding | mirror `tenant.tenant.events` Redpanda → Kafka | Catalog × tenant, Image × tenant (`INBOUND`, undeclared) | the tenant producer stays on Redpanda (Tenant's `topics.go`); the consumer wiring in each moving service |
| K2 | binding | mirror `catalog.product.events` Kafka → Redpanda | Product Query × product (`OUTBOUND`, promised and observed) | Catalog and Image produce it (`topics.go`) and move |
| K3 | binding | mirror `catalog.category.events` Kafka → Redpanda | Category Query × category (`OUTBOUND`, undeclared) | Catalog produces it and moves |
| K4 | binding | mirror `catalog.attribute.events` Kafka → Redpanda | Product Query × attribute, Category Query × attribute (`OUTBOUND`, undeclared) | Catalog produces it and moves |
| K5 | mechanism | no topic is mirrored in both directions: the allow-lists of the two flows are disjoint | the rows of K1–K4, as the reason | the allow-lists in the agent's MirrorMaker 2 configuration |
| K6 | mechanism | hand off the committed offsets of the Catalog and Image groups on `tenant.tenant.events` to Kafka, and verify them before the moved services start | Catalog × tenant, Image × tenant, as the reason | MM2 checkpoints and group-offset sync; the final Redpanda offset, the checkpoint and the installed Kafka offset |
| K7 | mechanism | change only the Kafka bootstrap address of Catalog and Image | the rows whose consumer is Catalog or Image (`INBOUND` or `INSIDE`), as the reason | the Helm values in `ecommerce-infrastructure` |
| K8 | mechanism | the cut-over checks, in the order of parent §4.2: replication caught up before a stop; Image caught up before Image stops; the remaining Redpanda consumers drained; the offset hand-off verified; flow B started only after the producers stop; the restart checks | the rows of K1–K4, as the reason | broker-tool output; the functional test |

The key states the parent §4.2 steps 1–9 as K8's sub-checks, so that each sub-check has its own
verdict. K1, K3 and K4 rest on undeclared rows only. A plan made from the documents alone would miss
them (parent §1).

## 4. Agent visibility and independence (D17, handoff §1.1 check 1)

The answer key, the I3 runbook and the run record must not predetermine the agent's plan. This
section says what the agent may see, and how the record shows that the plan is the agent's own.

### 4.1 What the agent sees

- **Workspace:** a new directory outside the AIP checkout. It contains:
  - the Sokol111 clones at the freeze commits, with the disclosed local adaptations;
  - `.mcp.json`, which connects to the local AIP with the experimental tool on;
  - the task card (§4.3).
- **Configuration:** a new, empty `CLAUDE_CONFIG_DIR`. The agent has no user memory, no global
  `CLAUDE.md`, no plugins and no skills from the operator's setup.
- **Tools:** the file and shell tools, the AIP MCP server, and these CLIs on `PATH`: `docker`,
  `kubectl`, `helm`, `rpk` (in the Redpanda container) and the Kafka scripts (in the Kafka image).

### 4.2 What the agent does not see

- **The AIP repository:** every specification, `harness/v08/`, `i3-evidence/`, `i4-evidence/`, the
  git history and the pull request bodies.
- **The web:** WebFetch and WebSearch are denied. The AIP repository on GitHub is public, so web
  access would expose the answer.
- **The I3 environment files:** the operator starts Kafka from a Kafka-only Compose file that I4a
  provides and that is kept outside the AIP checkout. The I3 Compose file names both flows and their
  allow-lists. Also, `docker inspect` and `docker compose ls` show a project's file paths, so a path
  in the AIP checkout would point the agent to it.
- **The AIP launch:** `.mcp.json` connects to AIP over HTTP. A stdio launch command would point
  into the AIP checkout.
- **Enforcement:** the agent's settings deny Read and Edit on the AIP checkout path and deny the web
  tools. A setting cannot block a shell command, such as `curl`, `wget` or `git clone`. The
  transcript audit (§4.4) covers these.

### 4.3 Task card

The task card is committed in I4a with its digest and is never edited. It contains:

- **Goal:** move Catalog Management (Catalog and Image) from Redpanda to Apache Kafka. MirrorMaker 2
  bridges the two brokers. Nothing that consumes today may break.
- **Environment facts:** the broker addresses; the Kafka image, already running and empty; the
  pinned images; the AIP identifiers to query (`catalog-management`, environment `local`).
- **Constraints:**
  - no topic is mirrored in both directions;
  - stop when a check fails, and report it;
  - make no lossless or exactly-once claim;
  - remove only what you created;
  - use only the pinned images;
  - ask the operator to run the functional test.
- **Plan format:**
  - a structured item list, `plan.json`: per item an id, the action, the topics, the direction
    (source broker → target broker), the services, the files it changes,
    `architecture_citations[]` and `implementation_justification[]`;
  - a prose rationale, `plan.md`.

The task card does not contain a topic list, a mirror direction, a step list or the kinds of check.

### 4.4 Record of independence

- **Planning is a separate session.** Its settings allow file writes only to `plan.json` and
  `plan.md` in the workspace. A setting cannot make every shell command read-only, so the audit
  checks the planning transcript for any command that changes the environment. The session ends
  when the agent writes the two plan files.
- **The plan is frozen before execution.** The operator records the plan digests and the UTC time
  before the agent runs its first mutating command.
- **Execution is a second session.** It starts from the frozen plan. A change to the plan during
  execution is an **amendment**: a new item or a changed item, with its reason and UTC time. It is
  never a silent edit. The scorer scores the frozen plan; the report shows the amendments.
- **Transcripts.** Both sessions are exported to a directory outside the workspace, so that the next
  session cannot read them.
- **Audit.** Before scoring, the operator checks both transcripts for:
  - any read of a withheld path, through any tool, including every shell command (`cat`, `grep`,
    `find`, `ls`, `git`, `gh` and so on);
  - any network fetch outside the environment: the web tools, `curl`, `wget`, `git clone`,
    `gh`, package managers and so on;
  - in the planning transcript, any command that changes the environment.

  A hit is recorded. The owner decides if the run stays valid.

## 5. Roles (D18)

**The operator frames the run, and the agent migrates.**

| Operator | Agent |
|---|---|
| Reset and bring-up ([handoff §2](i3-i4-handoff.md#2-reset-procedure-back-to-the-before-wave-state)) and the before-state checks. The operator does these checks, not the agent; this replaces handoff §2 step 6 | — |
| Verifies how `rpk group list` and `rpk group describe` show an `Empty` group, and bases every absence check on what they show ([handoff §4](i3-i4-handoff.md#4-known-behaviour-from-the-reference-run)) | — |
| Starts the Kafka container from the pinned image, empty, in a new Compose project | — |
| Captures **B-R** (Redpanda, before) with G/G′, imports it, checks the nine I2 §8.1 rows, then starts AIP for the agent | — |
| — | Plans from the AIP binding picture and the Sokol111 sources (S2) |
| — | Writes the MirrorMaker 2 configuration and the Helm values |
| — | Carries out the wave with its own commands and checks (S3) |
| Runs the functional test when the agent asks | Asks for it, and reads the result |
| After the agent reports the end: captures A-R and A-K with G/G′, imports the after-wave declarations, records the broker-tool ground truth, scores the plan and checks the citations (S4) | — |

- The operator may use the I3 harness (`capture.sh`, `functional_test.py`, the token helper) for its
  own tasks. The agent never sees it.
- **Interventions.** The operator intervenes only for an environment fault, never in the agent's
  plan or decisions. Each intervention goes into the intervention log, with its UTC time, cause and
  action.
- The I3 P4 per-probe timeout stays deferred: I4 does not run the I3 preflight.

## 6. Proof B: citations

- **A citation** names the before-wave snapshot id and one binding-picture row (`broker_id`,
  `topic_name`, `consumer_service_id`), or one or more `binding-evidence:` refs from that answer.
- **The snapshot is fixed.** The operator freezes the B-R import inputs. Snapshot ids are content
  fingerprints, so the same inputs give the same snapshot id in the replay.
- **The requests are fixed.** A `binding-evidence:` ref is bound to the snapshot and to the digest of
  the exact query. The operator takes every `get_binding_picture` request of the agent from the
  transcript and freezes it in the package.
- **A citation resolves** when the cited row is in the answer to the agent's request at that
  snapshot, or when the ref resolves through evidence mode for that request. AIP answers only for the
  current snapshot (`SNAPSHOT_NOT_AVAILABLE` otherwise), so citations are resolved while B-R is
  current: on the live AIP in S4, before the after-wave import, and in replay phase 1 (§9).
- **The support rule** checks the binding, not the action:
  - binding item: the cited row's topic equals the item's topic, and its crossing is `INBOUND` or
    `OUTBOUND`;
  - mechanism item: the AIP citations are optional, and the rule above does not apply. An item must
    have at least one implementation justification. If it has none, it is scored **unjustified**,
    even when it cites AIP rows.

  A pass means "the binding behind this item is evidenced". It never means "this action is correct".
- **The coverage rule** (K1–K4 only): `plan-key.json` names each expected row of §3.1 by
  `consumer_service_id`, `topic_name` and `broker_id`. The plan item that Proof A matches to a
  binding key item must cite **every** expected row of that key item. A plan with no AIP citations,
  or with only part of the rows (for example K1 with Catalog but not Image, or K4 with Product Query
  but not Category Query), does not pass. The verdict per binding key item is:
  - `COVERED`: every expected row is cited, and every cited row resolves and supports;
  - `INCOMPLETE`: at least one expected row is not cited; the verdict names the missing rows;
  - `NOT_CITED`: the matched plan item cites no AIP row, or no plan item matches the key item.

  Only `COVERED` passes. A cited row that does not resolve or support makes the item
  `DOES_NOT_SUPPORT`, whatever its coverage.
- **The mechanism is verified independently** in S4: replication progress per source partition,
  consumer lag, the offset hand-off positions and the functional test. AIP establishes none of these
  (parent §4.4).

## 7. Scoring

**Proof A.** A deterministic scorer reads the frozen `plan.json` and `plan-key.json`.

| Key items | Verdict | How |
|---|---|---|
| K1–K4 | `MATCHED`, `DIFFERENT` or `MISSING` | by topic and direction |
| K5 | `MATCHED` or `DIFFERENT` | computed from the plan's allow-lists |
| K7 | `MATCHED`, `DIFFERENT` or `MISSING` | by the services and the changed setting |
| K6, K8 (each sub-check) | `MATCHED`, `DIFFERENT` or `MISSING` | the owner judges against the key's wording; the scorer lists the candidate plan items |

- Plan items that no key item matches are listed as `EXTRA`.
- The owner records a reason for each `DIFFERENT`, `MISSING` and owner-judged verdict (parent:
  "matches or the difference is recorded").
- The citation check (§6) gives each item `RESOLVED`/`UNRESOLVED` and `SUPPORTS`/`DOES_NOT_SUPPORT`.
  It also gives each binding key item (K1–K4) `COVERED`, `INCOMPLETE` or `NOT_CITED`, and each
  mechanism item `JUSTIFIED`/`UNJUSTIFIED`.

**Proof C.** A-R and A-K, with the after-wave declarations from the I3 package, give exactly the
`expected-after.json` rows and limitations. The broker-tool ground truth and the functional test are
recorded separately from AIP's claims (parent §4.4).

## 8. Report (handoff §1.1 check 2)

One static HTML report. It is not a visualisation product.

- **Inputs:** the AIP answers recorded through the REST interface: the before-wave answers while B-R
  is current, and the after-wave answers while A-R and A-K are current. AIP answers only for the
  current snapshot, so the generator works from these recorded answers, never from a live query.
  The other inputs are the frozen agent record, the scoring and citation results, the broker-tool
  ground truth and the functional test result.
- **Deterministic:** the same inputs give the same bytes. The report contains no generation time
  and no other wall-clock or random input; every time it shows comes from a recorded input.

### 8.1 Structure

The four parts of parent §6 answer the five situation-awareness questions:

| Part | Questions answered |
|---|---|
| 1. Before | (1) What boundary changes? Catalog Management moves from Redpanda to Kafka. (2) Which relationships cross it? |
| 2. Insight | (3) Which are declared, observed or unresolved? Each with the parent §3.4 chain |
| 3. Agent | (4) Why do they matter for this migration? The requirement chains (§8.2) |
| 4. After | (5) What does the after-wave evidence establish, on both brokers? What stays unresolved? The external checks, apart from AIP's claims |

### 8.2 Requirement chains

For each `INBOUND` or `OUTBOUND` row after the wave, the report shows one chain with four links. It
also names the before-wave row it continues.

| Observed binding (AIP) | Migration requirement | Agent decision | Independent verification |
|---|---|---|---|
| the row, its status and its evidence refs | what the move must preserve | the plan item, its implementation justification and its Proof A verdict | replication progress, consumer lag, the functional test step |

Example: Category Query consumes `catalog.category.events` → preserve category-event delivery to
Redpanda → the agent configures Kafka → Redpanda replication for the category topic → replication
progress, lag 0 for Category Query, functional test step 2.

A chain with no matching plan item, or with a failed verification, is shown as such.

### 8.3 Narrative

- Open with the modernization problem and the flow, not with the agent or the MCP tools.
- Show the undeclared tenant and attribute bindings before any plan.
- Make the before/after binding picture the central view.
- Present the proof boundaries (parent §4.4) as the strength: what an instrument measures is not what
  people conclude from it.
- End with an invitation to evaluate AIP on the reader's own architecture.

### 8.4 Wording rules

- Say "understanding" or "visibility", never "control". AIP is read-only.
- Say "bindings" (consumer attachments at capture time), not "dependencies".
- Say "before and after" the wave, never "during".
- Write "the agent accounts for X" only when Proofs A–C show it.
- Do not call AIP a "superagent".
- Use no industry statistics as showcase metrics.
- Never present a consumer attachment as a verified end-to-end event flow.
- Make no claim about resilience, recovery, security, code review or skills.

### 8.5 Disclosures

The report and the release notes show:
- the parent §2 disclosures;
- the I3 and I4 adaptations: the second broker and the bridge, the MinIO images, the Logto pin, the
  host DNS workaround, `logto-seed` run twice;
- the agent setup: the model, the task card, what the agent did not see, and the interventions.

## 9. Package and replay

**Package** `i4-evidence/`:
- `plan-key.json`, `task-card.md` and their digests (from I4a);
- the agent record: model and settings, `plan.json`, `plan.md` and their digests with the freeze
  time, the amendments, both transcripts, the audit result, the intervention log;
- B-R, A-R and A-K with G/G′ in `raw/`;
- the broker-tool ground truth, the functional test result, the scoring and citation results;
- the agent's `get_binding_picture` requests, and the recorded before-wave and after-wave AIP
  answers (§8);
- the report;
- `observed-metadata.json`, `run-record.md` and `SHA256SUMS`.

**Freeze order** (as I3): sanitize → secret scan → `SHA256SUMS` → verify → commit.

**Replay test** (qualification tier), in three phases:
1. Import the before-wave inputs (I1 declarations, B-R, the Redpanda mapping, the catalog). The
   answer gives the nine I2 §8.1 rows. Issue the agent's frozen requests again, through the surface
   the agent used: the answers equal the recorded ones, and every citation resolves at the B-R
   snapshot.
2. Import the after-wave inputs (the after-wave declarations, A-R, A-K, both mappings). The answer
   equals `expected-after.json`, and equals the recorded after-wave answer.
3. Generate the report from the answers of phases 1 and 2. It is byte-identical to the frozen
   report.

## 10. Stages

Each stage fits one daily usage window and ends with a checkpoint record: what ran, which checks
passed, and where the next stage starts.

| Stage | Who | Content |
|---|---|---|
| S1 | operator | reset and bring-up, the before-state checks, the `rpk` absence check, Kafka up and empty, B-R with G/G′, the AIP start |
| S2 | agent | the planning session; the plan freeze |
| S3 | agent | the execution session, with the functional test on request |
| S4 | operator | first, while B-R is still current: the audit, the citation check and the recorded before-wave answers. Then A-R and A-K with G/G′, their import, the recorded after-wave answers, the ground truth and the scoring |
| S5 | operator | the report, the package freeze, the replay test |

**Stop rule** (parent §7): if a step cannot be done as specified, record the attempt and ask. Never
fake a result. A failed agent check stops S3. The owner decides whether the run continues, is
repeated from a reset, or is recorded as failed.

## 11. Release (I4c)

A lightweight demonstration release, through the `release-publication` skill:
- the version bump, the CHANGELOG and the release notes, with the disclosures (§8.5) and the
  narrative (§8.3);
- the ROADMAP v0.8 status;
- exact-candidate readiness, the owner's publication decision, the tag, the GHCR digest and the
  closure PR.

The hosted redeploy is not part of I4 (D19).

## 12. Acceptance

| # | Check |
|---|---|
| E1 | `plan-key.json` and `task-card.md` hash to the digests committed in I4a, and git shows them unchanged |
| E2 | The plan was frozen before the first mutating command; both transcripts are kept; the audit is recorded and the owner accepted any hit |
| E3 | Proof A: every key item has a verdict; every `DIFFERENT`, `MISSING` and owner-judged verdict has a recorded reason |
| E4 | Proof B: every citation resolves; the support rule is applied to every item; each of K1–K4 is `COVERED` (every expected row of the plan key cited), and any other verdict is recorded as a Proof B failure; no mechanism item counts as supported without an implementation justification |
| E5 | Proof C: A-R and A-K reproduce `expected-after.json`; B-R reproduces the nine I2 §8.1 rows |
| E6 | The functional test passes, and it and the broker-tool ground truth are recorded apart from AIP's claims |
| E7 | The report has the four parts, the five questions, a requirement chain for each `INBOUND`/`OUTBOUND` row after the wave, and the disclosures; it keeps the §8.4 wording rules |
| E8 | The replay test passes all three phases, and the report is byte-identical |
| E9 | v0.8.0 is published and verified through the release-publication skill |

## 13. Delivery

| PR | Content | Acceptance |
|---|---|---|
| I4a | `plan-key.json` and `task-card.md` with their digests; the agent workspace and settings template; the Kafka-only Compose file (§4.2); the scorer, the citation checker and the report generator, with unit tests. No live run | the unit tests; the digests committed |
| I4b | the live run S1–S5, the frozen `i4-evidence/` package, the replay test, the completion record | E1–E8 |
| I4c | the v0.8.0 release | E9 |

## 14. Decisions

| # | Decision | Source |
|---|---|---|
| D16 | Two keys: the plan answer key (frozen in I4a) scores Proof A; `expected-after.json` scores Proof C. A plan item has two kinds of support: architecture evidence (AIP) for the binding behind it, and an implementation justification (never AIP) for the mechanism | owner plan review, 2026-10-28 |
| D17 | The agent works in a workspace outside the AIP checkout, with a new Claude Code configuration, no web access and a task card that gives the goal and the safety constraints only. The plan is frozen before execution, and both transcripts are audited | owner, 2026-10-28 |
| D18 | The operator frames the run (bring-up, Kafka up and empty, captures, functional test, scoring); the agent plans and carries out the wave | owner, 2026-10-28 |
| D19 | The hosted redeploy with the experimental tool on is not part of I4 | owner, 2026-10-28 |
