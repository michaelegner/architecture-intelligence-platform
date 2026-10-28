# v0.8 I4 evidence

**Governs:** [I4 specification](../i4-agent-run-report-and-release.md) Draft 0.3, §3, §4.3 and §9.

## Frozen in I4a, before any agent run (E1)

| File | Content | Digest |
|---|---|---|
| [`plan-key.json`](plan-key.json) | The plan answer key K1–K8 (§3.1): the binding items with their expected rows and requirement, and the mechanism items with their sub-checks. It scores Proof A and the Proof B coverage rule | `plan-key.sha256` |
| [`task-card.md`](task-card.md) | The agent's whole brief (§4.3): the goal, the environment, the constraints, the two sessions and the plan format with its JSON Schemas | `task-card.sha256` |

The agent sees the task card only. It never sees the key or this directory (§4.2).
`tests/unit/test_v080_i4a_keys.py` checks both digests and the task card's leak guard.

The Proof C reference stays [`../i3-evidence/expected-after.json`](../i3-evidence/expected-after.json),
pinned by its SHA-256 in `harness/v08/i4/plan_format.py` (§3).

## Added in I4b

The run package of §9: the agent record, both transcripts, the audit, B-R, A-R and A-K with G/G′,
the recorded AIP answers, the configuration checks, the ground truth, the functional test, the
scoring and citation results, the report, `observed-metadata.json`, `run-record.md` and `SHA256SUMS`.
The operator steps are in [`harness/v08/i4/README.md`](../../../../harness/v08/i4/README.md).
