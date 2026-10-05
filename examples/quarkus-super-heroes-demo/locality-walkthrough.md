# Before a service change: where are dependencies established?

This extends the [Quarkus walkthrough](walkthrough.md). Quarkus remains the developer entry point.
The second example is **ACTUAL_CONTROLLED_REFERENCE**, acquisition
`aip-locality-i5-20261005t060050z-4392`: two Deployments emitting calls as `service:orders`.
It is not Quarkus traffic, a synthetic fixture or a product pilot.

## 1. Inspect Quarkus before editing `rest-fights`

Run the existing demo and follow its dependency/evidence questions:

```bash
examples/quarkus-super-heroes-demo/run.sh
```

Its preserved evidence establishes three observed/declared HTTP calls, four declared calls not
observed in its frozen window, and configured deployment identity. The original replay has no
scoped-v2 Pod evidence. `DEPLOYED_AS` does not establish which Workload made a call.
Ask the new question explicitly with an ordinary HTTP client:

```bash
curl --fail-with-body -sS -X POST \
  http://localhost:8000/api/services/service:rest-fights/dependencies/by-locality \
  -H 'content-type: application/json' \
  -d '{"mode":"query","subject_service_id":"service:rest-fights","environment":"quarkus-i5","first_day":"2026-09-25","last_day":"2026-09-25"}'
```

Inspect the actual `inventory`, `coverage`, `candidates` and `localities` fields. An empty scoped
candidate set establishes no Workload-local HTTP dependency. Complete evaluated inventory is not
complete Workload traffic coverage, and missing local observations do not prove absence.
This is the **missing-local-observation** example; it must not inherit positive local claims from
configured placement, the unscoped answer or the following separate capture.

## 2. Replay the separate actual reference

From a clean checkout at the candidate being demonstrated, with Docker/Compose and installed Python
dependencies available, run the existing qualification command. It records actual ordinary HTTP REST
and initialized MCP responses as well as direct-service answers. It uses separate disposable projects
and ports, so the Quarkus example may remain running.

```bash
CANDIDATE_SHA="$(git rev-parse HEAD)"
EXPECTATION_SHA="$(git rev-parse e48cae8f9842bd197061ba1b2c38ccd78f67b608^{commit})"
LOCALITY_RUN="$(mktemp -d)/qualification"
uv run --offline python -m evaluation.i5.qualify run \
  --candidate "$CANDIDATE_SHA" --expectation-commit "$EXPECTATION_SHA" \
  --output "$LOCALITY_RUN"
```

The original acquisition, [adopted oracle](../../tests/fixtures/locality/two-workload-capture/expected.md)
and source hashes remain unchanged. Each run imports C1, replays the original 52 requests once,
evaluates C1, replaces the same capture root with C2, then evaluates C2 without replaying telemetry.
Both runs start with fresh state and must agree byte for byte. They tear down their own containers;
the following transcripts preserve each stage, rather than querying an unavailable historical state.

Offline prerequisites: cache the pinned Neo4j/replay-Collector images, AIP build bases and Python
dependencies beforehand. Replay needs no live Kubernetes cluster, upstream Quarkus build, Kafka,
LLM key or agent. Initial dependency/image acquisition can require network access.

## 3. Read C1 discovery, comparison and evidence

These are exact request/response files produced by HTTP execution, not authored example answers.
Use either A or B; the command has compared the canonical files between them.

```bash
cat "$LOCALITY_RUN/A/c1/inventory.request.json"
cat "$LOCALITY_RUN/A/c1/inventory.rest.json"
cat "$LOCALITY_RUN/A/c1/comparison.request.json"
cat "$LOCALITY_RUN/A/c1/comparison.rest.json"
cat "$LOCALITY_RUN/A/c1/evidence.request.json"
cat "$LOCALITY_RUN/A/c1/evidence.rest.json"
```

The discovery request supplies `service:orders`, environment `locality-capture` and whole UTC day
`2026-10-05`, with **no Workload IDs**. It enumerates both evidenced caller Workloads. The comparison
then selects those two exact Workloads at the same C1 snapshot. The evidence request uses admitted
v2/capture references and that snapshot. Every positive is grounded in a recorded CLIENT Pod UID
and its captured owner chain; declaration evidence distinguishes the qualifications.

| Source-derived expectation | Required actual result |
| --- | --- |
| W1/P1 calls pricing; declaration supports it | `APPLICABLE` / `CONFIRMED` |
| W2/P2 calls legacy-pricing; no supporting declaration | `APPLICABLE` / `OBSERVED_ONLY` |
| Both C1 owner chains are present | Both localities enumerated; complete inventory, no continuation |
| Target Pod identity is not established | Target runtime scope `UNKNOWN` |
| No independently justified local traffic coverage | `LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE`; no local absence claim |

Different positive Operations on each side do not establish exclusive use or absence on the other
side. This is bounded direct HTTP evidence, not the global dependency set, Kafka locality or a causal
path. Wrong-caller, unauthorized and wrong-Operation reference checks are retained alongside these
transcripts and must refuse exposure.

## 4. Read the promotion boundary under C2

```bash
cat "$LOCALITY_RUN/A/c2/inventory.rest.json"
cat "$LOCALITY_RUN/A/c2/comparison.rest.json"
cat "$LOCALITY_RUN/A/c2/evidence.rest.json"
cat "$LOCALITY_RUN/A/c2/stale-query.rest.json"
cat "$LOCALITY_RUN/A/c2/stale-evidence.rest.json"
cat "$LOCALITY_RUN/A/c2/stale-cursor.rest.json"
cat "$LOCALITY_RUN/comparison.json"
```

| Source-derived expectation | Required actual result |
| --- | --- |
| C2 has removed P1; its recorded event remains | `UNRESOLVED` / `LOCALITY_CAPTURE_MISSING_POD`; no reassignment |
| P2 and its owner chain remain | W2's observed-only call remains eligible |
| Selected capture has changed | A new snapshot; C1-bound reads are stale/refused |
| Same recording, no second replay | Counts remain 359 pricing and 508 legacy-pricing in v1/v2 |

**Record the overlap capture before promotion displaces P1.** Saved C1 transcripts show what was
supported then; they are not a historical comparison API or proof of continuous Pod presence.
C2's unresolved P1 is not a deleted event, a reassigned caller or a negative dependency.
The stale cursor is a protocol-generated negative control: this small actual inventory emits no
continuation. Synthetic pagination/cap checks remain separately labelled regression evidence.

The replay command stops on disagreement with the adopted oracle, adapter mismatch or A/B drift.
Read its results alongside the [I5 qualification evidence](../../docs/specifications/0.6.0/i5-qualification-report.md).
This demonstration establishes neither production capacity nor customer benefit; I5.4 records pilot
and completion decisions, and I6 must qualify its final release candidate.
