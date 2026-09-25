# v0.5.0 release golden-path profile

This directory is the frozen release golden-path profile required by I6
[§7](../../docs/specifications/0.5.0/i6-release-candidate-publication-and-post-release-verification.md)
(Draft 0.3). Slice 1a freezes it: the owner's merge of the PR that adds this directory is the freeze.
The profile was authored from the component tests and fixtures cited below, and never from AIP
output. No harness has run against it. `run.sh` and the per-phase checks arrive in Slice 1b (I6 §7.4).
If the harness then disagrees with `expected.json`, that is a finding under I6 §14. The fix is never
an edit to `expected.json`.

## Layout

| Path | What it is |
|---|---|
| `profile/<phase>/phase.yaml` | The phase's AIP config path, its mounts (repository path to container path), its steps and its observation context |
| `profile/<phase>/config.yaml` | The phase's AIP configuration. The `demo` phase uses the unmodified repository `config.demo.yaml` instead. |
| `profile/<phase>/declarations/`, `otlp.json`, `mapping.yaml` | Transcribed inputs (I6 §7.2; see below) |
| `expected.json` | The frozen expected output, keyed by phase. Every check cites its source by path and line. |
| `SHA256SUMS` | Digests of `profile/`, `expected.json` and every referenced component file |

No discoverer candidate filename (`openapi.yaml`, `asyncapi.yaml`, `architecture.yaml`, …) sits
directly in this directory. It lies inside the bundled `examples` source root, whose direct
subdirectories are enumerated as service directories. The transcribed declarations sit four levels
down, where that discoverer never looks.

## Phases

Each phase starts from a clean graph (a fresh Compose project and a fresh Neo4j volume). It runs
`POST /api/import`, then its OTLP step, if it has one, through the pinned collector, then its reads.

| Phase | Reproduces | Environment and window | Covers |
|---|---|---|---|
| `demo` | the runtime demo, as `docker-compose.demo.yml` and `examples/runtime-demo/mcp-demo.sh` run it | `demo`, 2026-08-26 | OpenAPI, AsyncAPI Queue, deterministic OTel, positive declared identity, COMPLETE inventory, the full REST and negotiated-MCP workflow including reconnect |
| `pubsub` | `tests/integration/test_i4_pubsub_qualification.py` `_qualify_fixture` for `google-pubsub` | `production`, 2026-09-23 | AsyncAPI Topic, explicit Subscriptions, Pub/Sub observation |
| `k8s-agree` | `tests/integration/test_i3_cross_source_qualification.py:219-255` | `prod`, 2026-09-18 | Kubernetes offline discovery; `RESOLVED_EXPLICIT` supported by Paths A, B and C |
| `k8s-conflict` | `tests/integration/test_i3_cross_source_qualification.py:258-278` | `prod`, 2026-09-18 | the conflicting-identity case (Path A vs Path B) |
| `k8s-unresolved` | `tests/integration/test_i5_qualification_tooling.py:268-287` | `prod`, 2026-09-18 | the unresolved-identity case, through the public projection |

The `pubsub` and `k8s-*` configs disable HTTP correlation and set no aliases. That matches the
component tests, which pass no correlation buffer and no aliases to `adapt`. The `demo` phase
keeps `config.demo.yaml` unchanged.

## Unmodified component inputs

| Input | Used by |
|---|---|
| `examples/` and `config.demo.yaml` | `demo` |
| `examples/runtime-demo/seed_frozen_evidence.py`, `check_fixture_state.py`, `fixture-state.json`, `read_revision_fence.py` | `demo`; `read_revision_fence.py` is used by every phase |
| `tests/fixtures/pubsub/google-pubsub/declarations/` and `expected.yaml` | `pubsub` |
| `tests/fixtures/kubernetes/i2-independent-capture/` | all `k8s-*` phases |
| `tests/fixtures/deployment/i3-cross-source/service-workload-mapping-agree.yaml` | `k8s-agree` |
| `tests/fixtures/deployment/i3-cross-source/service-workload-mapping-conflict.yaml` | `k8s-conflict` |

`SHA256SUMS` pins each of these files. A change to a component invalidates the frozen profile.

## Transcribed inputs (I6 §7.2)

Each transcription is mechanical. `tests/unit/test_release_golden_path_profile.py` proves it
equivalent through production code.

| Transcription | Source | Equivalence proof |
|---|---|---|
| `profile/k8s-*/declarations/runtime-demo/openapi.yaml`, `profile/k8s-conflict/declarations/runtime-demo-alt/openapi.yaml` | the in-memory declarations of `_declare_service` in `tests/integration/test_i3_cross_source_qualification.py:108-119` (`Service(id, name, version="1")`) | real filesystem discovery and the OpenAPI adapter emit exactly that Service, with no operation, schema, message or relation, and the source is `ACCEPTED` with a `COMPLETE` inventory |
| `profile/k8s-agree/otlp.json` | `_runtime_demo_span(service_name="runtime-demo")` in `tests/integration/test_i3_cross_source_qualification.py:122-137` | OTLP JSON → protobuf → `decode_export_request` gives the identical `RuntimeSpan` |
| `profile/pubsub/otlp.json` | `_spans()` over `google-pubsub/spans.yaml` in `tests/integration/test_i4_pubsub_qualification.py:107-126` | the same, for all four spans, in order |
| `profile/k8s-unresolved/mapping.yaml` | `_TWO_ABSENT_TARGET_MAPPINGS` in `tests/integration/test_i5_qualification_tooling.py:248-265` | byte-identical to the test constant |

The OTLP payloads follow the OTLP/HTTP JSON encoding: trace and span ids are hex strings, not
base64. The pinned collector accepts that encoding and forwards protobuf to AIP's `/v1/traces`.

## What is checked, and what is not

- **Expected facts.** Every expected fact comes from the cited component expectation. Identity
  values are not frozen: claim, evidence, resolution and snapshot ids. The one exception is the demo
  oracle's `expected_snapshot_id` (I6 §7.1).
- **The `pubsub` graph-fact checks.** These use the component's own read-only Cypher queries, the
  same way the `demo` oracle reads Neo4j read-only.
- **`unresolved_spans: 1` from `google-pubsub/expected.yaml`.** No public interface or graph query
  exposes this adapter-internal count, so `expected.json` lists it under `not_observable`. It stays
  covered by the component test.
- **`k8s-unresolved`.** The component freezes only the two `UNRESOLVED` resolutions. The real
  capture's Path A resolution for the same Service is not frozen, so the phase does not expect it.

## Entry audit (I6 §5), recorded at this profile's freeze

| Check | Result |
|---|---|
| `main` contains the I5 completion merge `1ebca5e96a24156179f0a57b5abbdfe9b51c1ee7` | yes (`main` is at `a4f69d8`, the Draft 0.3 merge) |
| Post-I5 mutation since `aa04a150965924bd23ecf0125bcf7095a3cf72d9` | `git diff --name-only aa04a15 a4f69d8` lists only `docs/` |
| I1-I5 completion records | all present in `docs/specifications/0.5.0/` |
| I4 disposition | `GO` |
| I5 state | `FINAL_CANDIDATE_QUALIFIED`, with no unresolved material supported mismatch (F1-F8 each dispositioned) |
