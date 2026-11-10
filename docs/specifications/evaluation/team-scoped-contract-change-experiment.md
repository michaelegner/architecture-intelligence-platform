# Experiment: team-scoped contract change with human plan review

**Status:** Draft 0.2 (2026-11-10; #686 review corrections)
**Inputs:** [ROADMAP v0.9](../../../ROADMAP.md) ("customer problem first"), the
[v0.8 showcase value qualification](v08-showcase-value-qualification-experiment.md) and its
[result](v08-showcase-value-qualification-result.md), the
[Step 1 matrix](v08-showcase-value-qualification-step1.md), the
[GT 0.8.0 I3 report](../../reference-integrations/glamorous-toolkit/0.8.0/i3/report.md).
**Output:** a result record next to this file. It is an input to the v0.9 decision. It does not set it.

This is a lightweight pre-v0.9 experiment. Every result is exploratory. It changes nothing in AIP.

## 1. Purpose

The two earlier experiments left two things open:

- The only measured advantage of AIP is in the team-scoped setting: the sessions with AIP sent fewer
  requests to the platform team (2, 0, 2 against 5, 5, 6). That was one task, a broker migration.
- No human used the results. The GT I2 done-when, a human who does not know Sokol111, was not
  evaluated.

This experiment tests both on one new task.

**Customer role and decision (v0.9 "customer problem first"):**

| | Role | Decision |
|---|---|---|
| Part A | An engineer in a product team. The engineer has the team's repositories only and works with a coding agent. | "Whom must I involve before I change this event contract?" |
| Part B | An architect or senior engineer who supervises agent-made plans and does not know the system. | "Do I accept this plan, and which of its claims are supported?" |

**Questions:**

> A. For a breaking change to an event contract, what does a team-scoped agent with AIP plan and
> request differently from the same agent without AIP?
>
> B. Can a human reviewer judge a plan made with AIP better or faster than a plan made without it?

**Out of scope:**

- a claim of product value, owner effort (H2) and real coordination cost: they need a target customer;
- the v0.9 consequence of each outcome: the owner decides it after the result exists;
- execution of the change: all sessions are planning sessions;
- the full-access setting, Glamorous Toolkit and Unblocked;
- any change to AIP.

## 2. Task

The system is Sokol111 at the v0.7.2 freeze commits, with the frozen broker capture and the AIP
snapshot content of the value qualification. The team owns Catalog Management, as before.

**Task:** the team wants to make a breaking change to the events on `catalog.attribute.events`. The
agent plans the change and states whom the team must involve before it ships.

Why this topic (Step 1 matrix, rows 6 and 7):

- Product Query and Category Query both consume it;
- no document names either consumer;
- the team source names the consumers only partly: it says that the query services consume catalog
  events, but not which service consumes which topic.

The exact breaking change (which event, which field) is fixed in Step 1 from the producer source in
`ecommerce-catalog-service-api`.

## 3. Step 1: task, key and freeze

Step 1 needs the Sokol111 clones and the existing matrix. It needs no environment and no agent.

1. Fix the breaking change. Record the producer location and the consumer handler locations in both
   query services.
2. Record for each consumer whether its handler reads the changed event and field: `yes`, `no` or
   `cannot tell`, with the source location. This is a separate record from the topic attachment.
   An attachment does not establish it.
3. Write the task card in two variants, T+ and T−. Start from the
   [T cards](v08-value-qualification-evidence/cards/) of the value qualification.
   - **Keep:** the environment and access text, the request channel, the `evidence[]` schema and the
     isolation rules.
   - **Replace:** the goal, the first message, the migration constraints (MirrorMaker, the functional
     test, the "lossless" and "exactly-once" text), the plan schema (no `allow_lists` field), and
     the permitted outputs. The permitted outputs are `plan.json`, `plan.md`, `involve.json` and
     `requests.json`.
   - **Remove:** `answers.json` and its five questions.
4. Write the settings from the [T settings](v08-value-qualification-evidence/settings/). Change only
   the write permissions, to the permitted outputs of the new card.
5. Write the claim rules (§5.2), the plan key (§5.1) and the review measures (§6.3).
6. Freeze the cards, the settings, the rules, the keys and the reviewer packet template with their
   digests.

Reused unchanged from the value qualification: the request catalogue (R1, the R2 list, R3), the
comparison criteria and the audit.

**Owner checkpoint 1:** the owner approves the breaking change, the cards and the keys. Nothing is
frozen before this checkpoint.

## 4. Part A: agent sessions

| Type | Source in the workspace | Cluster and broker tools | AIP | Request channel |
|---|---|---|---|---|
| T+ | team-scoped | no | yes | yes |
| T− | team-scoped | no | no | yes |

- Each type runs 3 times: 6 valid sessions. Each round runs T−, then T+.
- Environment, isolation, AIP removal in T−, agent launch form, audit, effort counts and validity
  rules are those of the value qualification (§6 there). The record names the model and the Claude
  Code version.
- The request channel and its mechanical matching are those of §4.3 there.

**Outputs of a session:**

- `plan.md` and `plan.json`, with the `evidence[]` schema of the value qualification;
- `involve.json`: each party to involve, with the reason, what to ask or tell it, and evidence entries;
- `requests.json`, when the agent sends requests.

## 5. Part A: keys and criteria

### 5.1 Plan key

| Item | Expected |
|---|---|
| P1 | The plan names Product Query as a consumer of `catalog.attribute.events` |
| P2 | The plan names Category Query as a consumer of `catalog.attribute.events` |
| P3 | `involve.json` names the owner of each of the two consumers |
| P4 | The plan does not name a party that has no binding to this topic as a party that must change |
| P5 | The plan states that a broker attachment does not establish which events or fields a consumer handles, and names how to establish it (handler source, or the consuming team) |
| P6 | The plan states that the consumer list comes from one capture at one point in time |
| P7 | The plan gives a change sequence that keeps both consumers working (for example: compatible change first, consumers next, removal last) |

The scorer decides P1–P4 mechanically. The owner gives a verdict with a one-line reason on P5–P7.

P1–P3 score the topic attachment. Both consumer owners are parties to involve, also when Step 1
records that a handler does not read the changed field: only the owner of the consumer can confirm
that.

### 5.2 Claim rules and counts

The claim rules are those of the value qualification (§5.3 there), with these changes:

- **Scope:** the scorer reads `plan.json`, `plan.md` and `involve.json`.
- **U1–U5:** unchanged.
- **U6:** an unsupported claim states a result of the contract change as established, in place of a
  check to run. Examples: "the change is backward compatible", "both consumers keep working",
  "the deployment order is safe".
- **Not counted:** claims that the new card forbids.

The counts are requests, unsupported claims (U1–U6), tool calls, active agent time and output
tokens. For every count, lower is better. The result shows the counts next to P1–P3 of the same type, because fewer
requests with a consumer missed is not a better result.

### 5.3 Criteria

The frozen comparison rule of the value qualification (§5.4 there): a 2-of-3 majority per key item,
ranges per count, and `NOT DISTINGUISHABLE` when ranges overlap. A result of no difference is valid.

## 6. Part B: human plan review

### 6.1 Reviewers

- 2 or 3 engineers or architects from outside the project. None knows Sokol111, the keys or the
  earlier results. The owner recruits them.
- Each reviewer gives about one hour.
- The record names a reviewer by a letter and a role description only.

### 6.2 Procedure

1. Before the reviews, the operator pairs the plans by round: T− and T+ of round 1, of round 2 and
   of round 3. Reviewer A gets round 1, B gets round 2, C gets round 3.
2. Each reviewer reviews both plans of the pair. A and C start with T−. B starts with T+.
3. For each plan the reviewer gets a **packet**: the task card goal, `plan.md`, `involve.json`, and
   each evidence entry resolved to its text (the file lines, the request answer, or the AIP row with
   its qualification and limits). The reviewer gets no other access.
4. The reviewer has at most 25 minutes per plan and fills one form:
   - the decision: accept, accept with conditions, or reject, with the conditions;
   - for each binding claim that the packet lists: supported, not supported, or cannot tell;
   - the minutes used and the confidence in the decision (low, medium, high);
   - one sentence on what was hard to judge.
5. After both plans, the reviewer answers one question: which packet was easier to judge, and why?

The operator gives the packets and the form unchanged and answers no content question.

### 6.3 Review measures

Part B measures how a reviewer judges the **claims that the plan presents**. A packet holds only the
evidence that the plan cites, so it cannot reveal a consumer or an owner that the plan omits.
Completeness is scored in Part A only (P1–P4). No reviewer is scored on something the packet cannot
reveal.

A **binding claim** is a claim with a consumer × topic subject (rules U2–U5). The packet lists each
one.

| Measure | Source |
|---|---|
| Binding-claim agreement: the reviewer's verdicts that agree with the scorer's verdicts for the same binding claims | the Part A claim scoring |
| Binding-claim detection: the unsupported binding claims that the reviewer marked "not supported" or "cannot tell" | the Part A claim scoring |
| Decision fit: a plan with an unsupported binding claim is not accepted without a condition that covers that claim | the Part A claim scoring and the form |
| Minutes used, confidence, the "easier to judge" answer | the form |

The result reports Part B per reviewer and per plan. It does not aggregate and it draws no
statistical conclusion from 2 or 3 reviewers.

### 6.4 Disclosures for Part B

- The review is not blind: a T+ packet contains AIP rows.
- Each reviewer sees the task twice. The start order is alternated, but with 2 or 3 reviewers the
  order effect is not removed.
- The plans of a pair differ in more than AIP: each comes from one agent run.

## 7. Record

The result record contains:

- per session: the plan, `involve.json`, the requests and grants, the audit, the scores, the effort,
  and the sanitized transcript with its digest;
- per review: the packet digest and the filled form;
- the digests of the frozen materials, the AIP commit, image id and snapshot id;
- per measure: with AIP better, equal, worse, or not distinguishable (Part A), and the per-reviewer
  table (Part B);
- the disclosures of the value qualification that still apply, and those of §6.4.

## 8. Delivery

| PR | Content |
|---|---|
| 1 | this specification |
| 2 | Step 1 and owner checkpoint 1; the frozen materials; the harness changes with unit tests (the new plan schema, `involve.json`, the P items, the adapted U6, the reviewer packet builder); the 6 sessions; the reviews; the scoring; the result record |

The 6 sessions need one bring-up and fit one usage window. The reviews depend on the reviewers'
availability and can follow days later; PR 2 stays open until they are in.

## 9. Decisions

| # | Decision | Source |
|---|---|---|
| D1 | A pre-v0.9 experiment, not a v0.9 specification; no AIP release | owner, 2026-11-10 |
| D2 | Primary scenario: a team-scoped engineer changes an event contract; the human measure is a plan review on the same task | owner, 2026-11-10 |
| D3 | Sokol111 with a new task | owner, 2026-11-10 |
| D4 | 2 or 3 external reviewers | owner, 2026-11-10 |

## 10. Open points for the owner

1. **The breaking change.** Proposed: remove or rename one field of an attribute event that at least
   one query service reads. Step 1 fixes it; checkpoint 1 approves it.
2. **Runs per type.** Proposed: 3, as in the value qualification.
3. **`ecommerce-infrastructure`.** Proposed: excluded from the workspace, as in D5 of the value
   qualification.
