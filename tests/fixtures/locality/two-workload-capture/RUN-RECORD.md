# I5.1 actual controlled reference — run record

**Label:** `ACTUAL_CONTROLLED_REFERENCE` (new acquisition, not rehearsal, production observation or pilot).
**Status:** ACQUIRED; source checks PASS; acquisition-owner sign-off **PENDING**.
**Owner:** Michael Egner; executor: Codex, under the approved I5.1 plan.
**Governing:** merged I5 revision 0.1 §3/§8 and the I1 capture acquisition runbook §§2–5.
**Acquisition harness revision, verified from git when writing this record:** `072fa446f847173590b524dd9fa306da74151511`.
**Actual-capture AIP ingestion/query, expected-answer authoring and qualification:** **NOT_RUN**.

## Acquired evidence

Command: `bash harness/locality-capture/rehearse.sh --actual /tmp/aip-i5.1-acquisition-02`.
The preserved `run-log.txt.gz` records the actual tool/image pins and API command output.
It is compressed losslessly to retain raw CLI whitespace: `gzip -dc run-log.txt.gz` restores
the exact original bytes, including the recorded stop.
One throwaway kind cluster, namespace `aip-locality`, two separate Deployment Workloads,
real SDK-instrumented HTTP CLIENT calls, no Collector identity enrichment or fabricated spans.

| Identity/time | Observed value |
|---|---|
| Cluster (`kube-system` Namespace UID, command in log) | `2fe6677a-390d-458c-9e4c-85ae44b62f91` |
| P1 Pod / Deployment UID | `d31ca716-e7fa-420c-821c-b79cd907d3c5` / `a8df1913-530a-40cf-9fb4-f143f019ef08` |
| P2 Pod / Deployment UID | `febe35bd-15a9-411a-ba33-cbd82da14169` / `e7d1033a-3b23-4913-bf59-c67de08d0f07` |
| Traffic window, including shutdown/export | `2026-10-05T06:01:59Z` → `2026-10-05T06:10:53Z` |
| C1 overlap | `2026-10-05T06:07:30Z`; `c1-2026-10-05T06-07-30Z` |
| C2 post-promotion | `2026-10-05T06:10:02Z`; `c2-2026-10-05T06-10-02Z` |
| Successful emitted CLIENT HTTP requests | pricing: 359; legacy-pricing: 508 |
| Pre-C1 recorded CLIENT traffic | P1: 331.488 s; P2: 331.471 s |
| Recording | 52 OTLP-JSON lines; SHA-256 `76fe0043a9c0da853169b55e1767c38eceeb2e2294bc038a10861f752d0c5eac` |

Application image digest: `sha256:c4d4a23deb7af4d8b8992aa5d8e13b50110784abc5fb177dc3ff0cb9311e35fb`.
Node: `kindest/node:v1.31.2@sha256:18fbefc20a7113353c7b75b5c869d7145a6abd6269154825872dc59c1329912e`.
Recording Collector: `otel/opentelemetry-collector-contrib:0.161.0@sha256:fd328de2552466ad78385e1b1289c3f2402b1c45f265b252aab1955b42845ac1`.
Tools: kind v0.33.0; kubectl v1.36.1; API server v1.31.2; Docker 29.8.1.
The frozen `harness/app/` includes pinned base image, SDK dependencies and instrumentation;
`manifests/` retains exactly the applied configurations. The real runtime image IDs are also in
raw C1/C2 Pod status. Collector startup/end logs and its unmodified file export prove receipt.
File-export batch boundaries are recorded requests, not a claim of one line per incoming SDK export.

## Stop-condition evidence

| Check | Result and direct source |
|---|---|
| P1/P2 Running with distinct Deployment owner chains in C1 | PASS; raw `c1/resources.yaml`, UID chains in `acquisition-checks.json` |
| P1 stable through overlap; P2 stable through C2 | PASS; API/log checks plus identical P2 owner chain in C1/C2 |
| CLIENT Pod/cluster/environment attributes, Pod/namespace/Deployment consistency | PASS; `analysis.json`, zero CLIENT identity violations |
| CLIENT `k8s.cluster.uid` byte-equal to captured cluster UID | PASS; standalone analysis and both capture envelopes |
| Real successful GET `/prices` traffic, correct configured peers | PASS; all 867 CLIENT spans HTTP 200; `recording-inspection.json` |
| P1 absent after removal; P2 remains Running at C2 | PASS; raw C2 resources, same P2 owner UIDs |
| Traffic and captures within admitted UTC day | PASS; every recorded span and both captures on 2026-10-05; raw timestamp inspection |
| Raw bytes unchanged; valid envelope/resource digests | PASS; validator checks and `SHA256SUMS`; recording digest matches original export log |
| Acquisition-owner sign-off | PENDING — Michael Egner |

Captures are **non-atomic** sequential kubectl calls, with verbatim namespace/namespaced outputs
joined by a YAML document separator. Completeness is **self-declared**, not external authority.
All admitted resource kinds were queried; no ownership was reconstructed by name or mapping.

C1 and C2 share the configured source in `source-registration.json`. Later replay must copy their
unchanged bytes successively into the same physical root, configured as literal relative `capture`.
C1 declares a first import; C2 already binds C1 inventory revision `urn:aip:inventory-revision:7a945af77939fd8a860b5dc6f220a0cf78b8bb67ad82c52e2a62210cb15a5055`,
computed with existing pure source formulas. Changing the configured root invalidates that binding.
No staged AIP import or semantic assertion is claimed here.

Only the frozen declarations were imported into a separate disposable Neo4j container:
`import-declarations.json` records the committed report, exact harness HEAD and container.
`accepted-operations.txt` pins accepted canonical IDs, including
`operation:service:pricing:GET:/prices` and `operation:service:legacy-pricing:GET:/prices`.
Executed inspection/import scripts are retained as text to preserve their exact original bytes.
No Kubernetes capture or telemetry was loaded into that graph; no locality answer was queried.
The import command was `PYTHONPATH=. uv run python /tmp/aip-i5.1-import-declarations.py /tmp/aip-i5.1-acquisition-02`;
its exact script is retained as `harness/import-declarations.py.txt`.

## Attempts and independently established harness errors

1. An initial invocation stopped before cluster creation: its generated kind name contained uppercase
   letters. The failed log is preserved under `attempts/01-invalid-kind-name/`; no recording/capture
   from that attempt is counted. The lowercase-name correction preceded this fresh acquisition.
2. This acquisition exported intact telemetry and C1/C2, then the shell day check falsely stopped
   because it retained YAML single quotes around `capturedAt`. The original stop remains in
   `run-log.txt.gz`. Parsed raw timestamps and standalone span inspection independently prove the same
   UTC day; this was a harness parsing error, not an acquisition timing failure. The shell check
   was corrected. Identity metadata was exported from the original log/raw API capture; the existing
   analyzer and metadata checker then passed. **No recording, envelope or resource bytes were edited.**
   `harness/inspect-recording.py.txt` retains the additional standalone proof; invoke with the artifact
   directory and C1 timestamp. Teardown of only this run's cluster followed checks (`teardown.log`).

## Validation, reconciliation and I5.2 handoff

Ruff format/check passed; Pyright zero errors; 8 import contracts kept; unit tests 3,482 passed;
integration tests 803 passed with one existing Quarkus demo smoke skip. Those regressions used
existing fixtures and never evaluated this recording. Shell syntax and checksum checks passed;
the shell-only timestamp fix received syntax verification and raw-data checks.

The retained approved plan is in the PR description. Completed as planned: isolated worktree,
explicit actual mode with preserved rehearsal defaults/artifacts, immutable harness/image pins,
real overlap and replacement, frozen successor envelope, unchanged raw export and source checks.
Deviations: the failed name attempt and independently proved quote-check recovery above;
evidence is published as a draft for concrete owner review before final acquisition acceptance.
No semantic question, production behavior change or extra test matrix was introduced.
Capture acquisition took approximately ten minutes on one local host while regressions ran;
individual capture overhead and production capacity were not measured or established.

I5.1 acceptance remains pending the named owner's stop-condition sign-off. I5.2 must independently
inspect these sources, author/freeze `expected.md` and its input hashes in a prior commit **before
any first AIP evaluation**, then qualify staged C1→C2 using the pinned wire path and registration.
The actual capture is not yet semantically qualified. I5.3 upstream revalidation/demo, pilot
status/disposition and I6 final-candidate requalification remain separate. Existing I2 rehearsal,
I4 qualification, upstream dossiers and known #323 are unchanged.
