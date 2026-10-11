# AIP v0.6.3 — Runtime and Import Robustness

**Status:** Accepted maintenance specification  
**Target:** `v0.6.3`  
**Baseline:** Published and post-release-verified `v0.6.2`  
**Scope authority:** [ROADMAP.md — v0.6.3](../../../ROADMAP.md)

## 1. Promise

v0.6.3 is a **maintenance release**. It adds no new Architecture Knowledge semantics, source family, schema, architecture-question class or MCP tool.

It fixes two bounded robustness defects in already-supported paths:

1. `POST /v1/traces` blocks the FastAPI event loop while synchronous ingestion runs, so unrelated REST, MCP and UI requests can wait for the whole batch.
2. An OpenAPI or AsyncAPI document containing an integer outside RFC 8785's safe integer domain can raise `rfc8785.IntegerDomainError` during canonical hashing and abort the whole multi-source import run instead of rejecting only the offending source ([#305](https://github.com/michaelegner/architecture-intelligence-platform/issues/305)).

The release promise is:

> **Existing v0.6 Architecture Knowledge remains semantically unchanged, while telemetry ingestion no longer blocks unrelated requests for the duration of a batch and one source with an unsupported canonicalization value cannot abort otherwise valid sources in the same import run.**

## 2. Constraints

- Patch-release semantics only: no new architecture question, canonical entity/relation, public schema or MCP tool.
- Existing v0.5/v0.6 Current-State, locality, messaging, evidence, snapshot and qualification semantics remain unchanged.
- No generic performance project, queueing subsystem or ingestion redesign.
- No RFC 8785 replacement, lossy number coercion, tagged-integer encoding or canonical-hash migration in this release.
- No claim that out-of-range integers become supported OpenAPI/AsyncAPI semantics. The bounded fix is **containment plus explicit diagnosis**.
- No unrelated adapter cleanup.
- Implement against this lightweight specification; no increment-specific specification files are required.

## 3. I1 — Telemetry ingestion responsiveness

### 3.1 Problem

`app/api/telemetry.py` exposes `POST /v1/traces` as an async route and directly calls synchronous `ingest_trace_spans`. The ingestion path performs Neo4j reads and writes on the event loop.

The committed `benchmarks/traces_stall.py` baseline demonstrates that other requests wait approximately for the ingestion duration under the measured workload.

### 3.2 Required outcome

Move the blocking ingestion work off the FastAPI event loop while preserving **serialized ingestion**.

An acceptable implementation may use an explicit single-flight lock, a single-worker executor, or an equivalent mechanism. The implementation choice is not frozen here; the invariant is:

```text
event loop remains responsive
+
at most one ingestion unit executes through the serialized critical section
+
existing evidence semantics remain unchanged
```

A plain synchronous FastAPI route that permits concurrent ingestion is insufficient because current correlation/ingestion behavior relies on serialization.

### 3.3 Acceptance

The change SHALL include tests proving:

- an unrelated request can complete while deliberately slow trace ingestion is still running, using resolvable client/server span pairs exercised through the real ingestion path as in `benchmarks/traces_stall.py`, not an injected sleep as a substitute for ingestion cost;
- two ingestion requests do not execute the protected ingestion work concurrently;
- removing/bypassing the serialization guard causes the serialization test to fail;
- existing telemetry semantic tests remain unchanged or are updated only where concurrency mechanics require it;
- the correlation-buffer documentation reflects the actual concurrency contract;
- the full unit and integration suites pass.

The existing stall benchmark SHALL be rerun before release. It is **measurement evidence**, not an SLO and not a release threshold.

## 4. I2 — Per-source containment for RFC 8785 integer-domain failures

### 4.1 Problem

Issue [#305](https://github.com/michaelegner/architecture-intelligence-platform/issues/305) records that an OpenAPI schema containing an integer outside the IEEE-754 safe integer range can fail canonical hashing:

```text
OpenApiSourceAdapter.map
  -> canonical_sha256_hex
  -> canonical_json_bytes
  -> rfc8785.dumps
  -> IntegerDomainError
```

Examples include int64/uint64 bounds such as:

```text
maximum: 9223372036854775807
maximum: 18446744073709551615
```

The same failure class may affect AsyncAPI or another document-content path that calls the same canonicalizer.

Today an uncaught failure can abort the whole import run, including unrelated valid sources.

### 4.2 Required outcome

Contain this failure **at the per-source canonicalization/mapping boundary**, not only around `adapter.map(...)`.

Any RFC 8785 integer-domain failure encountered while deriving one discovered source's semantic identity/digests or while mapping that source SHALL be converted into that source's deterministic rejected outcome rather than escaping as an exception.

The implementation SHALL explicitly inspect and classify the currently known document-content canonicalization paths, including:

- the full-document `semantic_input_digest` / source-revision input path;
- OpenAPI/AsyncAPI adapter canonical hashing;
- message-contract canonical hashing;
- Kubernetes mapping canonical hashing where applicable.

Each known caller SHALL either be covered by the same bounded source-rejection path or be documented in the implementation record as not source-import-facing for this failure mode.

When one source hits the unsupported RFC 8785 integer domain:

1. that source SHALL be rejected with an explicit deterministic diagnostic;
2. it SHALL contribute zero committed canonical artifacts from that run;
3. other discovered sources SHALL still be evaluated and reported with their normal per-source outcomes;
4. the **overall discovery run SHALL preserve the existing commit gate**: a rejected source makes the run `PARTIAL`, therefore the run is not commit-eligible and **nothing from that run commits**;
5. previously accepted state SHALL remain unchanged because the `PARTIAL` run does not reconcile inventory, sources, tombstones or canonical artifacts;
6. the failure SHALL not be converted into a lossy or alternate canonical hash;
7. the rejected source SHALL not contribute a fabricated semantic digest, source revision or revision-fence value for the unsupported document.

This release therefore improves failure **containment and diagnosis**, not partial-commit semantics. It does not change the existing rule that only a `COMPLETE` discovery run may commit.

### 4.3 Explicitly deferred canonicalization decision

v0.6.3 does **not** decide whether AIP should eventually support out-of-range JSON integers losslessly.

The following remain deferred:

- coercing such integers to IEEE-754 doubles;
- encoding them as tagged strings or another non-JCS form;
- changing canonical identity/hashing rules;
- migrating existing hashes;
- broadening accepted JSON-number semantics beyond the current RFC 8785 contract.

Those choices can change identity semantics and require their own specification decision.

### 4.4 Acceptance

Regression coverage SHALL demonstrate at minimum:

- an OpenAPI source with an out-of-range integer is rejected with the explicit diagnostic rather than raising an uncaught exception;
- a valid source in the same discovery run is still evaluated and reported with its normal per-source outcome;
- the overall run is `PARTIAL` and not commit-eligible;
- **nothing from that run commits**, including artifacts from otherwise-valid sources;
- previously accepted state and inventory/revision state remain unchanged;
- the rejected source emits no committed canonical artifacts and no fabricated semantic digest/source revision for the unsupported document;
- no lossy canonical hash is created for the invalid value;
- AsyncAPI receives equivalent protection if the same path is reachable;
- the known full-document semantic-input/revision-digest path is covered, so the exception cannot escape before adapter mapping;
- message-contract and Kubernetes canonicalization callers are either covered by the same source-rejection path or explicitly demonstrated to be outside this failure mode;
- a normal in-range document produces the same canonical identity/hash as before;
- existing atomicity remains intact within each source and across the discovery run.

## 5. I3 — Qualification and release

Before candidate freeze:

- I1 and I2 acceptance tests pass;
- full unit and integration suites pass;
- existing v0.6 golden-path/demo semantics remain unchanged;
- CodeQL, dependency and repository security checks satisfy the current release policy;
- `benchmarks/traces_stall.py` is rerun and the before/after observation is recorded without introducing an SLO;
- #305's bounded rejection/diagnosis behavior is demonstrated end-to-end through the import path;
- release notes state explicitly that one out-of-range integer still makes the discovery run `PARTIAL` and prevents that run from committing; v0.6.3 changes the failure from an uncaught crash into a deterministic diagnosed outcome;
- version consistency, CHANGELOG, release notes, `server.json` and release metadata are updated through the normal release workflow.

No separate product-value pilot is required for this maintenance release.

## 6. Exit criteria

v0.6.3 is complete when:

> **Telemetry ingestion preserves serialized semantics without blocking unrelated requests for the whole ingestion batch, and an unsupported RFC 8785 integer in one source is converted into an explicit per-source rejection rather than escaping as an exception; the existing `PARTIAL` / no-commit run semantics remain unchanged.**

The release must preserve the v0.6 architecture-question space and public Architecture Intelligence semantics unchanged.

## 7. Decision register

| ID | Decision | Status |
|---|---|---|
| D1 | v0.6.3 is a maintenance release with no new architecture-question class. | Accepted |
| D2 | The POST /v1/traces stall is fixed in v0.6.3, not v0.7. | Accepted |
| D3 | Ingestion remains serialized while blocking work moves off the event loop. | Accepted |
| D4 | Issue #305 is included only as per-source rejection/diagnosis across the full source canonicalization/mapping boundary; existing `PARTIAL` / no-commit run semantics are preserved. | Accepted |
| D5 | Strict current RFC 8785 hashing semantics are preserved; no lossy coercion or alternate encoding. | Accepted |
| D6 | Broader support for out-of-range integers and any canonical-hash migration are deferred. | Accepted |


## 8. Baseline carry-forward

Once v0.6.3 ships, later releases MAY rely on two maintenance guarantees:

1. runtime ingestion that requires serialization remains serialized without keeping blocking work on the FastAPI event loop for the duration of the synchronous ingestion unit;
2. an unsupported per-source canonicalization failure is converted into a deterministic source rejection and cannot escape as an unhandled exception, while the existing discovery-run commit gate remains unchanged: `PARTIAL` and `FAILED` runs commit nothing.

A later release that introduces a materially different runtime-ingestion or source-import path SHALL qualify that path independently rather than assuming these guarantees automatically apply.
