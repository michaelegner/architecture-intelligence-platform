# v0.7.0 I4.3 — Product-value pilot record

The owner's recorded coding-agent session (the rerun), run with the [pilot runbook](i4-pilot-runbook.md) steps. Method: [decision record](i4-decision-record.md) D7. **This is one recorded session, not user research.** The disposition is the owner's and rests on this session alone. The record was drafted from the session transcript and the operator's timestamped notes, at the owner's request; the transcript is kept outside the repository and not committed.

**Superseded first session.** A first session the same day (disposition `CONTINUE`) did not follow the method: the agent had shell and file access and used it (it read the working copy and ran pasted operator commands), and after the refresh it was asked the R1 window instead of the R2 window. It is replaced by this rerun and is not evidence.

## 1. Session

| Field | Value |
|---|---|
| Date and operator | 2026-10-15, Michael Egner (rerun start 15:43:33Z) |
| Agent or client, and version | Claude Code 2.1.300, started with its built-in tools disabled (`claude --tools ""`) |
| Model and version | Opus 5.5 (the banner and `/model` show "Opus 5.5") |
| AIP checkout and server start | Clean `main`, which was `cd7f154e727fe844028b0e59ae90755860f0a596` at the time (the notes did not log `HEAD`; `origin/main` is still that commit); server on port 8000 started from the operator's own terminal, start time not recorded |
| Replay world | R1 then R2 of `i4-replay/` (pinned APISIX 3.19.0 captures); R1 window `2026-10-15T08:15:03Z` to `08:15:38Z`, R2 window `2026-10-15T08:16:15Z` to `08:16:54Z` |
| Context card given to the agent (verbatim) | The task sentence of the runbook, then `Operation id: operation:service:order-service:POST:/orders`, `gateway_instance_id: gw-i4-replay`, `environment: replay`, and the `window_start` and `window_end` of the revision being asked (R1 for Phases 1 and 2, R2 for Phase 3) |
| Tools the agent could use | The `aip-pilot` MCP server only. The transcript shows only `aip-pilot` calls and no shell, file or Neo4j access |
| Transcript or recording location | `/home/michael/aip-pilot-session/rerun-transcript.md` and `rerun-notes.txt` (kept outside the repository; not committed) |

## 2. Per phase

Times are UTC from the operator's notes.

| Measure | Phase 1 (R1, no mapping) | Phase 2 (operator mapping) | Phase 3 (R2 refresh) |
|---|---|---|---|
| Setup effort (minutes; Phase 1 only) | About 9.4: from the rerun start (15:43:33) to the first question (15:52:57), including the R1 import, connecting the agent and checking its tools | n/a | n/a |
| Source synchronization effort | R1 import 15:47:05 to 15:47:15 (about 10 s), one command | Import with the mapping 15:58:06 to 15:58:08 (about 2 s), one command, plus the operator's check-data script | R2 refresh 16:02:12 to 16:02:39 (about 27 s): copy the R2 files, one import; the mapping file stayed in place |
| Consumer-attribution effort | None: no consumer rows were returned | Consumers came back by username with the rows; no operator lookup; not measured | None: usernames came back with the rows |
| Identity-mapping effort | None: no mapping existed | 15:55:38 to 15:57:40 (about 2 min 2 s): list the 5 Routes, choose one, write and check `apisix-mapping.json` with one `route_operation` entry (`orders-route` to the Operation) and an empty `target_service`. The owner chose `orders-route`; no Route URI or method matched `POST /orders`, and the Route id contains "orders" | The mapping stayed valid after the refresh (`orders-route` exists in R2); no re-authoring was needed |
| Manual input required | The context card (Operation id, gateway instance, environment, window): none of these is discoverable through a public tool | The same card, plus the mapping content (Route id found by listing the capture file, and the Operation id) | The same card with the R2 window read from the new manifest |
| Answer outcome and limitations | `NOT_ANSWERED`, `NO_ROUTE_SELECTED`, snapshot `939d689a…5392`; window valid | Answered; one Route linked (`orders-route`, explicit mapping and its contract version); snapshot `be301e9e…6617`; window valid | Answered; the same Route linked; snapshot `dc83fca9…01f8`; revision `apisix:3.19.0+etcd:31`; window valid |
| Rows: configured only / observed / measured zero / unestablished | 0 rows | 0 / 1 (alice: 3 upstream, 0 rejected) / 3 (bob, dave, erin) / 1 (carol: no configured access, 0 upstream, 2 rejected) | 0 / 0 / 2 (alice, erin: 0 / 0) / 0 |
| Unresolved and ambiguous associations | 5 of 5 Routes unresolved to any Operation; none ambiguous or conflicting | 4 of 5 Routes unresolved (1 resolved to the Operation); Route to Service for `orders-route` unresolved (no `target_service`, as intended) | The same: 4 other Routes unlinked; Route to Service unresolved |
| Useful answer coverage | Question 3 (what remains unresolved) covered; questions 1 and 2 unknown, with the reason | All three covered, for `orders-route` only; the agent states the other 4 Routes could also expose the Operation | All three covered for the R2 window and revision |
| Agent behavior | Concluded "unknown", explicitly not "no consumers, safe to change"; advised fixing the Route-to-Operation mapping, or querying a Route directly; noted the start reading's digest is that of empty input while the window is valid | Presented the table, separated observed, measured zero and not-established, and listed what remains unresolved; advised treating alice, bob, dave and erin as consumers that "may be affected" and finding out why carol is rejected | Compared with the earlier window: bob, dave and carol no longer appear, "I won't guess why from that alone"; alice's earlier requests do not carry over because usage is per window; stated that no observed usage is not "safe to change" |

## 3. Keeping the evidence current

- **Time and cost of each cycle:** R1 about 10 s; the mapping (one-time, about 2 min 2 s of operator work) plus about 2 s to import it; the R2 refresh about 27 s. Money: none (local). The agent's token cost: not measured.
- **What had to be re-done by hand:** nothing. The mapping stayed valid because `orders-route` exists in R2. A mapping to a Route that R2 removes (for example `billing-route`) would not have stayed valid.
- **Stale cursor and reference:** the operator resubmitted, unchanged, the Phase 2 evidence request (same context and snapshot id) and the Phase 2 cursor after the refresh; both returned `NOT_ANSWERED`, `None`, `['SNAPSHOT_NOT_AVAILABLE']`. This check ran from the operator's terminal, not through the agent.
- **Whether the agent noticed the changed state:** yes, from the AIP answer alone: new snapshot and revision (`etcd:31`), a different allow-list (alice and erin only), and different usage. It did not mention the removed Route or the added Route, which do not concern this Operation.

## 4. Semantic correctness (what the evidence establishes)

No deviation this time: the transcript shows only `aip-pilot` calls.

| Agent statement | Supported by the answer? |
|---|---|
| Phase 1: unknown, not "no consumers"; 5 Routes unresolved, none ambiguous or conflicting; the window is valid | Yes |
| Phase 1: the start capture's digest is that of empty input while the window is valid | True of the replay data; stated as an observation, not a conclusion |
| Phase 2: `orders-route` linked by explicit mapping and contract version; the table of alice (3 observed), bob, dave, erin (measured zero), carol (no configured access, 2 rejected) | Yes |
| Phase 2: bob, dave and erin "had no traffic in this 35-second window. That doesn't mean they never use the operation" | Yes, respects the window bound |
| Phase 2: carol's attempts "isn't usage" | Yes |
| Phase 2: "treat alice, bob, dave and erin as consumers that may be affected" and "carol may be a client that expects to have access" | Hedged inferences beyond what the answer establishes (impact; carol's intent) |
| Phase 3: only alice and erin configured; both measured zero; the earlier window's usage does not carry over | Yes |
| Phase 3: "I won't guess why from that alone" | Yes, declines to infer |

Statements about dependency, ownership, authorization, approval or intent: only the two hedged remarks above. The answer's limitation wording was respected (unknown is not none; a measured zero is bound to its window). The agent did not make the cross-Route guess of the first session. No specification §13 stop was raised.

## 5. Product usefulness (whether obtaining and maintaining the evidence is worthwhile)

**Observations from the session**
- Without a mapping the agent got no answer and was told clearly why, with two ways forward.
- After one operator-authored mapping entry (about 2 min of work and a 2 s import) the agent received a bounded, evidence-separated answer with consumers, access, usage and what remained unresolved.
- Each later synchronization was one command taking under 30 s, and the answer after the refresh was correct for the new revision without re-mapping.
- The answer covers one linked Route; four other Routes stayed unlinked, so the consumer list is not complete for the Operation.
- No public tool discovers the gateway instance, environment, window or canonical ids; the operator supplied them.
- The mapping choice is a judgement the operator made without tool support.

**Owner's judgement:** the disposition is `CONTINUE` (section 6). The three usefulness questions (decision improvement, proportionality, one-time versus recurring) were not answered separately: not judged.

## 6. Disposition (owner)

| Field | Value |
|---|---|
| Disposition | CONTINUE |
| Reasoning | Rerun captured expected answers (owner's wording). Basis: one recorded session in which the agent used only the AIP tools, the Phase 1, 2 and 3 answers and the stale-reference check behaved as specified, and the evidence was kept apart from inference. The disposition rests on this single session |
| Owner and date | Michael Egner, 2026-10-15 |
