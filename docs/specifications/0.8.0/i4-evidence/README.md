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

| Path | Content |
|---|---|
| [`run-record.md`](run-record.md) | Every stage, finding and decision, with its time |
| [`report.html`](report.html), [`report-inputs.json`](report-inputs.json) | The showcase report and its manifest |
| [`plan.json`](plan.json), [`plan.md`](plan.md), [`plan-freeze.txt`](plan-freeze.txt), [`amendments.json`](amendments.json) | The agent's frozen plan, its digests and freeze time, and its five amendments |
| [`agent-record.json`](agent-record.json), [`interventions.txt`](interventions.txt) | Model, settings, the owner's audit waivers, the interventions and the functional-test reply |
| `transcripts/`, `streams/`, [`audit.json`](audit.json), [`agent-requests.json`](agent-requests.json) | Both sessions (attempt 2 planning, execution), their headless streams, the audit and the agent's extracted AIP request |
| `attempt-1/` | Planning attempt 1 (no plan: the write was refused, H3), its transcript and audit |
| `captures/`, `answers-*.json`, [`proof-c.json`](proof-c.json) | B-R, A-R, A-K; the recorded AIP answers; Proof C |
| [`scoring.json`](scoring.json), [`owner-verdicts.json`](owner-verdicts.json), [`citations.json`](citations.json) | Proof A with the owner's verdicts; Proof B |
| `applied-mm2/`, [`applied-mm2.json`](applied-mm2.json), `p1b-*.json`, `helm/`, [`applied-helm.json`](applied-helm.json), [`handoff-after.json`](handoff-after.json), [`e6-gate.json`](e6-gate.json) | The configuration checks, the ground truth and the E6 gate |
| `agent-workspace/` | The agent's MirrorMaker 2 configuration, ConfigMap backups and patched copies |
| `raw/`, `images/` | Every recorded command (`raw/superseded-*` holds outputs replaced by H4–H7); the image inventories |

Local path prefixes are replaced by `<run home>` and `<AIP checkout>`. The snapshot ids in the
answers depend on the absolute input paths AIP read (`/app/sokol111-v08/...`), so a replay from
this directory gives other snapshot ids and evidence refs, and the same answers otherwise
(`tests/integration/test_v080_i4b_replay.py`).
