# v0.6.0 I4 — Completion record

**Status: execution and measurements complete; owner capacity and external-review dispositions pending.**
Governing: [I4 accepted revision 0.2](i4-deterministic-semantic-qualification.md), §§4, 6–8;
accepted parent §§20–21, 25. I4 is not yet declared qualified for handoff or release-ready.
Exact candidate, captured from git while writing this record: `460c6c20eb704caac479111da31292204fa2a1aa`.

## Qualification and coverage

The [coverage register](i4-coverage-register.md) and independently frozen I1/I2/I3/I4 expectations
are unchanged. All 52 required X/P/Q/B cases ran in two separate processes/fresh Neo4j containers:
417 passed each, no skips; 600 complete semantic artifacts per run; zero oracle failures,
zero raw canonical A/B differences and zero service/REST/negotiated-MCP differences.
Q01–Q08 exercised actual adapters; the independent HTTP client verified query/evidence/reconnect.
No semantic normalization was applied. The earlier I4.2 SHA is historical evidence, not substituted
for these complete new runs.

| Run | Process | Fresh Neo4j container | Resets | Artifacts |
|---|---|---|---|---|
| A | 42269 | `0d78745e403bf9c915451b5162a1c007b2710deed017dd9067d7239f7e1db19a` | 76 | 600 |
| B | 44740 | `92cbf139aaa7d5a954abff92c1e6033877b3febc18df86df5a767cb8fd120dee` | 76 | 600 |

The local gate passed Ruff, Pyright (zero errors), 8 import contracts, 3,482 unit tests and
803 integration tests. One existing demo smoke skipped because the owner’s Compose project was
running; no mandatory qualification case skipped. Exact-candidate CI includes all 11 required
check names, with 19 successful test/demo/security/quality check runs. The failed optional
Copilot job is retained: weekly quota exhausted, HTTP 429; check `111504163660`. It is not presented
as successful. The untouched coordinator report remains BLOCKED solely for that external job;
owner disposition is still required before the consolidated record declares qualification.

## Observed growth and retained state

Both benchmarks explicitly accepted and verified the same candidate SHA/producer/package identity.
They ran sequentially after local test workers stopped, each in its own pinned Neo4j container.
Host: WSL2, 14 logical CPUs, approximately 16 GB, Python 3.13.14, Neo4j 5.26.31, Docker 29.8.1.
Read timings are medians of five repeated reads. Imports and POSTs are individually measured,
not five independent reimports. Existing demo/background host activity was not claimed absent.
Normal Neo4j driver notifications remained enabled; timings include the configured driver behavior.
These are observations from one host/run, not an SLO or evidence of production pilot capacity.

| Caller Pods, one Workload | Total nodes off → on | v2 records on | Median POST ms off → on | Fingerprint ms off → on |
|---|---|---|---|---|
| 0 | 8 → 8 | 0 | None → None | 99.774 → 77.77 |
| 100 | 512 → 614 | 100 | 1208.926 → 1786.262 | 52.69 → 69.973 |
| 1000 | 5012 → 6014 | 1000 | 989.973 → 1474.914 | 97.97 → 263.248 |

At N=1,000, v2 adds 1,002 nodes: one record per distinct Pod UID plus two operational nodes.
The POST on/off ratio is 1.49× and fingerprint on/off ratio is 2.69×. Scoped fingerprint cost is
1.025× the historical I2 value. Retained evidence still grows with churn; no compaction or deletion
was introduced. Source state replacement removes current capture membership while old v2 stays.

| Frozen case/state | v2 records | Total nodes/relationships | Capture import ms | POST ms | Query ms | Unresolved candidates |
|---|---|---|---|---|---|---|
| B01a/C1 | 2 | 37/3 | 452.1 | 568.4 | 117.0 | 0/2 |
| B01a/C2 | 3 | 39/4 | 350.1 | 265.9 | 115.4 | 1/3 |
| B01b/C1 | 2 | 37/3 | 303.6 | 207.9 | 115.6 | 0/2 |
| B01b/C2 | 3 | 39/4 | 404.2 | 297.8 | 116.8 | 1/3 |

Both UID variants change capture selection from 2/2 to 2/3 and unresolved from 0/2 to 1/3.
Main cursor walks have 0/1 refused pages and zero retries. Frozen bridge assertions also verify
P3’s own support, forbidden P1→P3 transfer and stale-snapshot refusal. These observed denominators
are per-query candidates/pages, not global absence or population rates. Actual production import
cost is separated from fixture authoring/capture-total overhead in the raw JSON.

| Locality point | First-page admitted pairs | Query median ms | Versus historical I3 | Full-walk pages |
|---|---|---|---|---|
| churn, N=0, S=1 | 0 | 112.9 | 0.64× | 1 |
| churn, N=100, S=1 | 100 | 142.8 | 1.01× | 1 |
| churn, N=1000, S=1 | 500 | 736.9 | 1.17× | 2 |
| workload-cap, N=60, S=1 | 50 | 137.8 | 1.15× | 2 |
| membership-cap, N=1, S=1 | 200 | 476.0 | 1.30× | 2 |
| fan-out, N=500, S=1 | 500 | 476.5 | 0.92× | 1 |
| fan-out, N=500, S=5 | 400 | 412.2 | 1.20× | 2 |
| fan-out, N=500, S=50 | 40 | 188.3 | 1.09× | 13 |
| covering-fan-out, N=400, S=5 | 2000 | 2921.3 | 1.20× | 1 |
| covering-fan-out, N=40, S=50 | 2000 | 2337.0 | 1.23× | 1 |

All locality cursor walks saw every fixture candidate once, with zero main-query refusals and
zero stable-read retries. The covering points perform 2,000 actual admitted pairs at S=5 and S=50,
not merely a large source inventory. Their costs are 20–23% above the historical I3 values;
results are disclosed rather than called a pass against an invented latency threshold.
Per-page bounds remain 2,000 pairs, at most 500 candidates before source-count reduction,
50 Workloads, 200 memberships and 20 evidence refs. These bounds do not bound whole-graph
fingerprint latency; retained-state growth remains an operational concern.

## Capacity/operational disposition

**PENDING — Michael Egner.** The owner must review Pod-churn growth, retained state, capture
overhead, the measured ratios and limits of one host before the measurements are called acceptable
(I4 §6). No automatic budget approval, numerical SLO or enacted ADR 0012 policy is implied.

## Evidence, reconciliation and limits

[Full evidence bundle](../../release-validation/v0.6.0-i4/evidence-460c6c2.tar.gz) retains complete A/B
ledgers/raw bytes/input pins, commands, benchmark JSON and exact-SHA check runs.
Archive SHA-256: `a9f4117eb9d61a07d60b19baa5aedf2cf7b2407d018be6010f563ea54db67e06`.
[Summary](../../release-validation/v0.6.0-i4/i4-summary.json),
[churn JSON](../../release-validation/v0.6.0-i4/churn.json),
[locality JSON](../../release-validation/v0.6.0-i4/locality.json) and
[CI evidence](../../release-validation/v0.6.0-i4/ci-check-runs.json) are also separately tracked.
After extraction, `compare_runs(Path("aip-i4.3-qualification-460c6c2"))` from `evaluation.i4.__main__` independently
repeats the raw semantic comparison; original `/tmp` pointers map to the archive’s relative contents.

The approved plan is retained verbatim in PR #420. Completed as planned: pinned benchmarks,
existing scale profiles and covering fan-out, real frozen C1/C2 replacement measurements,
source/configuration/producer verification, full new A/B qualification and durable evidence.
The shared `measure_reads` extraction avoids duplicating existing phase measurement. No semantic
question or production/default/schema/expectation change occurred. Remaining work is owner
capacity/external-review disposition and finalizing the [I5 handoff](i4-i5-handoff.md).

Synthetic benchmark inputs are labelled as such. X25’s S>2,000 correctness is separately qualified
with the previously disclosed capture cloning; its refusal latency was not measured. Actual I5
capture overhead and product pilot capacity are NOT_RUN/unmeasured. No missing measurement is
presented as zero cost. Legacy compatibility, read-only/ref isolation and frozen-schema evidence
are in the new qualification/regression runs. Known #323 and other I2/I3 carried findings remain
unchanged; the repository owner retains their release disposition, and no new assignee is asserted.

This record’s later evidence-only commit is not itself claimed as the tested candidate. I5/I6
changes to code, schema, fixtures, defaults or packaging require I6’s exact-final-candidate rerun.
The actual controlled two-Workload capture remains I5 work; publication/release readiness remains I6.
