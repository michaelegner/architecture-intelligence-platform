# v0.7.0 I4.3 — Product-value pilot record (template)

Copy this file to `i4-pilot-record.md` and fill it in from the single session run with the [pilot runbook](i4-pilot-runbook.md). Method: [decision record](i4-decision-record.md) D7. Record facts as they happened; leave a field `not measured` rather than estimate it. **This is one recorded session, not user research.** The disposition is the owner's, and it rests on this session alone.

## 1. Session

| Field | Value |
|---|---|
| Date and operator | |
| Agent or client, and version | |
| Model and version | |
| AIP checkout (`git rev-parse HEAD`) and server start | |
| Replay world | R1 then R2 of `i4-replay/` (pinned APISIX 3.19.0 captures) |
| Context card given to the agent (verbatim) | |
| Tools the agent could use | AIP MCP tools only, no Neo4j, no replay files |
| Transcript or recording location | |

## 2. Per phase

| Measure | Phase 1 (R1, no mapping) | Phase 2 (operator mapping) | Phase 3 (R2 refresh) |
|---|---|---|---|
| Setup effort (minutes; Phase 1 only) | | | n/a |
| Source synchronization effort (minutes, commands, steps) | | | |
| Consumer-attribution effort (minutes; what had to be looked up) | | | |
| Identity-mapping effort (minutes; which ids, from where) | | | |
| Manual input required (what the operator supplied beyond the runbook) | | | |
| Answer outcome and limitations returned | | | |
| Rows: configured only / observed / measured zero / unestablished | | | |
| Unresolved and ambiguous associations (Routes unresolved of total, ambiguous) | | | |
| Useful answer coverage (which parts of the question the answer covered) | | | |
| Agent behavior (what it concluded, what it asked next) | | | |

## 3. Keeping the evidence current

Over the two synchronization cycles (the initial import of R1, then the controlled refresh to R2):
time and cost of each cycle; what had to be re-done by hand (for example the mapping file); whether stale cursors and references were refused and how the agent reacted; whether the agent noticed the changed state (a consumer removed from an allow-list, a Route removed, a Route added).

## 4. Semantic correctness (what the evidence establishes)

Judged separately from usefulness. For each statement the agent made: whether it is supported by the answer's rows, limitations and evidence, and whether the agent kept apart configured access, observed usage, measured zero, unestablished usage and the unresolved associations. List every statement that went beyond the evidence (dependency, ownership, authorization, approval, intent, "safe to change"), and whether the answer's own wording (limitations, `USAGE_UNESTABLISHED` is not zero) was respected. If the agent could not separate evidence from unsupported inference, stop and report (specification §13).

## 5. Product usefulness (whether obtaining and maintaining the evidence is worthwhile)

Judged separately from correctness. Did the answer materially improve the coding-agent decision about changing the Operation (what would the agent have done without it)? Is the effort of attribution, identity mapping and synchronization, measured above, proportionate to that benefit? Which part of the effort was one-time and which recurs each cycle?

## 6. Disposition (owner)

Exactly one of `CONTINUE`, `NARROW`, `DEFER`, `STOP`, with the owner's reasoning and the reviewer and date. State the single-session basis. A semantically correct result may still be `NARROW`, `DEFER` or `STOP` if synchronization or mapping cost is disproportionate.

| Field | Value |
|---|---|
| Disposition | |
| Reasoning | |
| Owner and date | |
