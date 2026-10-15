# v0.7.0 I4.3 — Product-value pilot record

The owner's first recorded coding-agent session, which deviated from the frozen method (see sections 3 and 4) and is to be replaced by a rerun, run with the [pilot runbook](i4-pilot-runbook.md). Method: [decision record](i4-decision-record.md) D7. **This is one recorded session, not user research.** The disposition is the owner's and rests on this session alone. The record is the owner's, with sections 2 to 5 drafted from the session transcript at the owner's request (the transcript is kept outside the repository and not committed).

## 1. Session

| Field | Value |
|---|---|
| Date and operator | 2026-10-15T14:00:45Z, Michael Egner |
| Agent or client, and version | Claude Code 2.1.300 |
| Model and version | Opus 5.5 (as shown in the Claude Code banner of the transcript: "Opus 5.5 · Claude Pro") |
| AIP checkout (`git rev-parse HEAD`) and server start | cd7f154e727fe844028b0e59ae90755860f0a596, server started 2026-10-15T14:13:59Z,  NEO4J_PASSWORD=pilot-local-only CONFIG_PATH="$PILOT/config.yaml" uv run uvicorn app.main:app --port 8000 |
| Replay world | R1 then R2 of `i4-replay/` (pinned APISIX 3.19.0 captures) |
| Context card given to the agent (verbatim) | An agent is about to change an API Operation and asks which configured consumers are related to that exposure, which have independently observed usage in the selected completed window, and what remains unresolved. Operation id: operation:service:order-service:POST:/orders, gateway_instance_id: gw-i4-replay, environment: replay, window_start: 2026-10-15T08:15:03Z, window_end: 2026-10-15T08:15:38Z
 |
| Tools the agent could use | aip-pilot, no Neo4j, no replay files |
| Transcript or recording location | /home/michael/aip-pilot-session/pilot-transcript.md (kept outside the repository; not committed) |

## 2. Per phase

Times are UTC (the transcript shows local time, UTC+2). Source of each value: the session transcript (`pilot-transcript.md`), `notes.txt`, `phase2.json`, and the operator's terminal log.

| Measure | Phase 1 (R1, no mapping) | Phase 2 (operator mapping) | Phase 3 (R2 refresh) |
|---|---|---|---|
| Setup effort (minutes; Phase 1 only) | 21 (operator's figure). Interval per the operator terminal log: session start 14:00:45 to the R1 import at 14:21:25, about 20 min 40 s; it includes clearing port 8000, the Neo4j start (ready 14:12:57) and the server start (14:13:59) | n/a | n/a |
| Source synchronization effort (minutes, commands, steps) | R1 import 14:21:25 to 14:21:57 (about 32 s), one command (`curl -s -X POST localhost:8000/api/import`); health check `{"status":"ok"}` before it | Import with the mapping: 14:52:00 to 14:52:06 (about 6 s), one command, followed by `save_phase2.py`. Two further imports found nothing new (same snapshot): 14:55:04 to 14:55:06 (about 2 s, operator terminal) and 14:56:54 to 14:56:56 (about 2 s, run through the agent session). `save_phase2.py` was run three times (twice in the operator terminal, once through the agent session); each time the snapshot was `…8f61c66d…2f5c` | R2 refresh 15:00:27 to 15:00:58 (about 31 s): copy of the R2 `gateway` and `metrics` files, then one import; the mapping file stayed in place |
| Consumer-attribution effort (minutes; what had to be looked up) | No consumer rows were returned, so no attribution step arose; not measured | The consumers (erin, alice) came back by username with the rows; no operator lookup appears in the transcript or notes; not measured | n/a (no rows returned) |
| Identity-mapping effort (minutes; which ids, from where) | None: no mapping existed | The operator listed the 5 Routes (id, URI, methods) from `$PILOT/gateway/apisix-capture.json`; no Route had a method or a URI equal to `/orders`. Chose `billing-route`. Wrote `apisix-mapping.json` (226 bytes, modified 14:49) with one `route_operation` entry (`billing-route` to `operation:service:order-service:POST:/orders`) and `target_service` empty. The authoring ended at 14:50:09 (the time printed right after the file was validated); its start was not recorded, so duration: not measured. Basis for choosing `billing-route`: none; no Route URI or method matched POST /orders, and the choice was arbitrary (owner's statement) | The mapping pointed at `billing-route`, which R2 removes; it was not re-authored in the session, so after R2 no current Route was mapped to the Operation. Re-authoring effort: not measured |
| Manual input required (what the operator supplied beyond the runbook) | The context card: Operation id, `gateway_instance_id`, `environment`, `window_start`, `window_end` (none of these is discoverable through a public tool) | The same context card, plus the mapping file content (a Route id found by listing the capture file and the Operation id) | The context card re-sent with the **R1** window, not the R2 window (see section 3) |
| Answer outcome and limitations returned | `NOT_ANSWERED`, limitation `NO_ROUTE_SELECTED`, `selected_routes` empty. The window was reported valid (an evidence ref resolved: both boundary readings stable 20 s, no restart, APISIX 3.19.0, revision `apisix:3.19.0+etcd:25`). Snapshot `aip:snapshot:v1:939d689a…5392` | The agent reports that the platform answered (the outcome label is not quoted in the transcript). One Route selected, `billing-route`. All evidence refs of the rows resolved. Window valid. Snapshot `aip:snapshot:v1:8f61c66d…2f5c`. Asked a second time at 14:55 with the same result and snapshot | `NOT_ANSWERED`, limitation `MEASUREMENT_WINDOW_NOT_AVAILABLE`, snapshot `aip:snapshot:v1:4abe15df…5bb4`. The question carried the R1 window (`08:15:03Z` to `08:15:38Z`); the R2 window is `08:16:15Z` to `08:16:54Z` |
| Rows: configured only / observed / measured zero / unestablished | 0 rows (no Route selected) | 0 configured only; 1 observed (erin: 4 upstream requests, 0 rejected); 1 measured zero (alice: 0 / 0, `SUFFICIENT_FOR_ZERO`); 0 unestablished | 0 rows (refused, `data` null) |
| Unresolved and ambiguous associations (Routes unresolved of total, ambiguous) | 5 of 5 Routes unresolved to any Operation; none ambiguous or conflicting (as the agent stated) | 4 of 5 Routes still unresolved (1 resolved to the Operation); ambiguous: not stated in the transcript. Route to Service for `billing-route`: unresolved (no `target_service` entry, as intended) | Not measured from the answer (it was a refusal). The agent reported, from files it read on disk, that the mapped Route no longer exists and no current Route is linked |
| Useful answer coverage (which parts of the question the answer covered) | Question 3 (what remains unresolved): covered. Questions 1 and 2 (configured consumers, observed usage): not answerable (unknown, with the reason) | All three covered, for `billing-route` only. The agent states the list is complete for that Route and not for the Operation as a whole | None for the R2 state (asked with the R1 window). The R2 window was never asked |
| Agent behavior (what it concluded, what it asked next) | Concluded "unknown", explicitly not "no consumers" and not "safe to change". Offered two ways forward: an explicit Operation mapping at the source, or querying the Route directly. Flagged that the start reading's digest is the SHA-256 of empty input while the window is valid, as an unconfirmed guess. | Reported the exposure and both consumers. Remarked that the Route name is odd for an order-creation Route while noting the platform does not infer from names. Said "Treat Erin as an active consumer who will be affected". Said Alice's zero "says nothing about longer periods". Again flagged the empty start reading. Offered to read the gateway files on disk | Concluded the earlier answer is out of date and the mapping is stale. Used two shell commands to inspect files on disk (see section 4). Suggested re-mapping and querying the new window |

## 3. Keeping the evidence current

Over the two synchronization cycles (the initial import of R1, then the refresh to R2):

- **Time and cost of each cycle:** the R1 import took about 32 s (14:21:25 to 14:21:57). The Phase 2 import with the mapping took about 6 s (14:52:00 to 14:52:06). The R2 refresh took about 31 s (15:00:27 to 15:00:58). Each import was one command. Cost in money: none (local, no LLM in AIP). The agent's token cost: not measured.
- **What had to be re-done by hand:** nothing was redone, but the operator mapping did not survive the refresh in a usable form. It names `billing-route`, which R2 removes, so after the refresh no Route is mapped to the Operation. Making the Operation answerable again would need a new mapping entry for a current Route; that was not done in this session.
- **Stale cursor and reference:** the operator resubmitted, unchanged, the Phase 2 evidence request (same context and snapshot id) and the Phase 2 cursor after the refresh. Both returned `NOT_ANSWERED`, data `None`, `['SNAPSHOT_NOT_AVAILABLE']` (operator's terminal output). This check was run by the operator's script, not by the agent, so the agent's reaction to it is not part of this record.
- **Whether the agent noticed the changed state:** it noticed that the answer changed to `MEASUREMENT_WINDOW_NOT_AVAILABLE` and that the snapshot changed. From files it read on disk it also reported that the window now is `08:16:15Z` to `08:16:54Z`, that `billing-route` is gone, and that the current Routes are `legacy-route`, `open-route`, `orders-route`, `reports-route` and `shared-route`. It did not describe the removal of consumers from an allow-list. These details came partly from file access, which the runbook did not allow (section 4).
- **Deviation from the runbook:** after the refresh the agent was asked the R1 window again, not the R2 window as the runbook requires, so the refreshed state was never queried through the AIP tool. The owner did not state whether this was intended.

## 4. Semantic correctness (what the evidence establishes)

Judged separately from usefulness. The statements below are taken from the agent's answers. A column "Supported by the answer?" is filled only where the transcript shows the answer's own content; the owner makes the final judgement.

**Deviation that affects this section.** The runbook says the agent uses the AIP tools only (no Neo4j, no replay files). The transcript shows that when the operator's own shell commands were pasted into the agent's prompt, the agent ran them: it read `~/aip-pilot-session/PILOT_DIR.txt`, listed and read files in the working copy (`gateway/`, `metrics/`, the manifest, `apisix-mapping.json`), ran an import (14:56) and ran `save_phase2.py`, and in Phase 3 ran two shell commands to inspect the changed files. The answers at 14:37 (Phase 1), 14:53 and 14:55 (Phase 2) were produced from `aip-pilot` tool calls only, but before the 14:53 answer the agent had already read `PILOT_DIR.txt` and listed the working copy (about 14:46), so it knew the directory contents. The Phase 3 explanation of what changed on disk, and the agent's offers to read the gateway files, were not AIP-only.

| Agent statement | Supported by the answer? | Notes |
|---|---|---|
| Phase 1: nothing could be answered because no Route is linked to the Operation (`NO_ROUTE_SELECTED`); this "doesn't mean nobody is configured" | Yes | Keeps "unknown" apart from "none" |
| Phase 1: 5 Routes can't be linked to any Operation, none ambiguous or conflicting | Yes | Matches the association summary the answer carries |
| Phase 1: the window is valid; readings stable 20 s, no restart, revision `apisix:3.19.0+etcd:25` | Yes | Backed by the resolved window evidence ref |
| Phase 1 and 2: the start reading's digest is the SHA-256 of empty input, window still valid; "my guess is that no metrics existed yet"; "I haven't confirmed" | Factually true of the replay data; the guess is marked as a guess | The start metrics file in the replay package is empty. The agent had no way, through the AIP answer, to learn why the window is still valid, and said so |
| Phase 2: `billing-route` is linked to the Operation by an explicit mapping entry; the contract version matched | Yes | |
| Phase 2: erin observed (4 upstream, 0 rejected); alice measured zero (0 / 0, `SUFFICIENT_FOR_ZERO`) | Yes | Keeps observed, measured zero and configured access apart |
| Phase 2: "the name 'billing-route' is just a label … an odd name for an order-creation route" | Appropriate | Does not use the name to decide |
| Phase 2: "Alice has access but sent nothing during this 35-second window, which says nothing about longer periods" | Yes | Respects the window bound |
| Phase 2: "Treat Erin as an active consumer who will be affected" | No (drafter's reading; the owner has not judged it) | The answer establishes observed requests by erin on `billing-route` in a 35-second window, and that the Route is linked to the Operation by the operator's mapping. "Will be affected" is an impact inference beyond that |
| Phase 2: "Don't call the consumer list complete until the 4 unlinked Routes are linked or ruled out" | Yes | |
| Phase 3: the platform could not answer for the selected window (`MEASUREMENT_WINDOW_NOT_AVAILABLE`); the earlier answer is out of date | Yes | |
| Phase 3: `billing-route` no longer exists; the routes now are …; `legacy-route` has no measurement coverage; the mapping is unchanged since 14:49 | Outside the AIP answer | Read from files on disk, not from the tool |
| Phase 3: "`orders-route` looks like it may have replaced `billing-route` … a guess based on matching config and a name" | A guess, marked as one | Beyond the evidence; the agent itself says the platform rightly does not make that link and the agent shouldn't either |

Statements about dependency, ownership, authorization, approval or intent: the drafter found none in the answers other than the "will be affected" and "may have replaced" remarks above. The answer's own limitation wording was respected where the transcript shows it (unknown is not none; a measured zero is bound to its window). `USAGE_UNESTABLISHED` did not occur. No specification §13 stop was raised during or after the session.

## 5. Product usefulness (whether obtaining and maintaining the evidence is worthwhile)

Judged separately from correctness. This section holds the session's observations; the judgement is the owner's.

**Observations from the session**
- Without a mapping the agent got no answer to the question and was told so clearly (Phase 1), with two ways forward.
- After one operator-authored mapping entry the agent received a bounded answer with consumers, their access and their observed usage or measured zero, and with what remained unresolved (Phase 2). The answer is for one Route, not for the Operation as a whole, because the other 4 Routes stayed unlinked.
- The identity mapping required the operator to find the Route ids (listing the capture file), decide which Route exposes the Operation, and write the file. Duration: not measured. The Route chosen and the reason: operator's.
- The R1 and R2 imports were one command each and took about 32 s and 31 s; the import with the mapping took about 6 s; imports with no changes took about 2 s.
- The refresh to R2 invalidated the Phase 2 answer and the mapping: the mapped Route was removed, so the Operation became unanswerable until a new mapping is written. The recurring cost per revision therefore includes re-checking and possibly re-authoring the mapping; whether it would recur in practice depends on how often Routes change. That is not measured here.
- The agent could not tell from the answer why the window is valid with an empty start reading, and said that its "measured zero" for alice depends on it.
- Nothing in the transcript shows what the agent would have decided without the answer.

**Owner's judgement:** the owner's disposition is `CONTINUE` (section 6). The three usefulness questions (decision improvement, proportionality of the effort, one-time versus recurring) were not answered separately: not judged. The observations above are the facts available.

## 6. Disposition (owner)

Exactly one of `CONTINUE`, `NARROW`, `DEFER`, `STOP`, with the owner's reasoning and the reviewer and date. State the single-session basis. A semantically correct result may still be `NARROW`, `DEFER` or `STOP` if synchronization or mapping cost is disproportionate.

| Field | Value |
|---|---|
| Disposition | CONTINUE |
| Reasoning | Results as expected (owner's wording). Basis: one recorded session in which the frozen behavior held in Phases 1 and 2 and for the stale-reference check; the deviations in sections 3 and 4 (agent shell access, Phase 3 asked with the R1 window) and the unmeasured mapping effort apply. The disposition rests on this single session. |
| Owner and date | Michael Egner, 2026-10-15 |
