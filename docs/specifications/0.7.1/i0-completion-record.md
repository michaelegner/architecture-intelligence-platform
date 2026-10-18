# AIP v0.7.1 I0 — Completion Record

**Status:** COMPLETE on merge of the I0.2 PR (closure SHA to be added in a follow-up).
**Outcome:** `READY_FOR_I1`, recorded by the owner on merging the I0.2 PR.

I0 is documentation and throwaway spike evidence only. It implements no adapter, schema, endpoint or tool.

## Run identity

| Slice | Deliverables | PR | Merge commit |
|---|---|---|---|
| I0 spec | [`i0-consumer-attribution-semantic-freeze.md`](i0-consumer-attribution-semantic-freeze.md) | #576 | `45a34fbec2101fe95a6b10ad13205c93f4b135ae` |
| I0.1 | [`i0-spike/`](i0-spike/README.md) | #577 | `1a18246c9f01674e5b41f3a49b5154d0c6e4181f` |
| I0.2 | decision record, handoff, this record | this PR | read from `gh pr view --json mergeCommit` after merge |

## Exit criteria (I0 §11)

| Criterion | Status | Evidence |
|---|---|---|
| Broker identity and Service identity stay distinct | Met | Decision D1, D3 |
| Attachment and mapping semantics frozen | Met | D2, D3 |
| Temporal compatibility defined | Met | D4 |
| Deterministic identity and lifecycle frozen | Met | D1, D6 |
| Kafka evidence accepted or refresh required | Met | Decision §2: reuse for semantics, fresh I1 fixture |
| RabbitMQ contrast outcome recorded | Met | Decision §3: SOURCE_SPECIFIC |
| I1 does not need to invent semantic meaning | Met | [Handoff](i0-i1-i2-handoff.md) |

## I0 §8 cases

| Case | Where decided |
|---|---|
| Attachment + mapping -> attributable; attachment + no mapping -> unresolved | D5 |
| Mapping + insufficient broker evidence -> not a negative | D2 |
| Ambiguous / conflicting mapping | D5 |
| Incompatible environment or time | D4 |
| Several group members, one Service | D2 (members are evidence detail) |
| One group on several Topics | D2 (one edge per destination) |
| Undeclared destination; unresolvable Service | D2, D3 (never minted) |
| Offsets without live assignment | D2 |
| Unsupported broker object; no message-processing evidence | D2; I0 §3 |

## Carried forward
No sixth tool is pre-authorized (I3 decides). The release-facing wording and issue-state re-check stay in I5.
