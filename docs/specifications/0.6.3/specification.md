# AIP v0.6.3 — Runtime and Import Robustness

**Status:** Draft 0.1 — lightweight maintenance specification  
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

- an unrelated request can complete while deliberately slow trace ingestion is still running;
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

Contain this failure **per source**.

When canonicalization of one source document fails because an integer is outside the supported RFC 8785 domain:

1. that source SHALL be rejected with an explicit deterministic diagnostic;
2. it SHALL contribute zero canonical artifacts;
3. unrelated valid sources in the same import run SHALL continue according to the existing per-source import semantics;
4. the failure SHALL not be converted into a lossy or alternate canonical hash;
5. the source's previous accepted state SHALL follow the existing failed-source/authoritative-removal rules — failure itself must not silently erase accepted state unless those rules already require it.

The implementation SHALL cover OpenAPI and AsyncAPI if both can reach the same failure mode. Any other caller of document-content canonicalization found during implementation SHALL either receive the same bounded containment or be explicitly recorded as not source-import-facing and therefore outside this slice.

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

- an OpenAPI source with an out-of-range integer is rejected with the explicit diagnostic;
- a valid source in the same import run still imports successfully;
- the rejected source emits zero new canonical artifacts;
- no lossy canonical hash is created for the invalid value;
- AsyncAPI receives equivalent protection if the same path is reachable;
- a normal in-range document produces the same canonical identity/hash as before;
- existing atomicity remains intact **within one source document** — containment across sources must not create partial artifacts from the rejected document.

## 5. I3 — Qualification and release

Before candidate freeze:

- I1 and I2 acceptance tests pass;
- full unit and integration suites pass;
- existing v0.6 golden-path/demo semantics remain unchanged;
- CodeQL, dependency and repository security checks satisfy the current release policy;
- `benchmarks/traces_stall.py` is rerun and the before/after observation is recorded without introducing an SLO;
- #305's bounded containment behavior is demonstrated end-to-end through the import path;
- version consistency, CHANGELOG, release notes, `server.json` and release metadata are updated through the normal release workflow.

No separate product-value pilot is required for this maintenance release.

## 6. Exit criteria

v0.6.3 is complete when:

> **Telemetry ingestion preserves serialized semantics without blocking unrelated requests for the whole ingestion batch, and an unsupported RFC 8785 integer in one OpenAPI/AsyncAPI source is contained to that source with an explicit diagnostic rather than aborting unrelated imports.**

The release must preserve the v0.6 architecture-question space and public Architecture Intelligence semantics unchanged.

## 7. Decision register

| ID | Decision | Status |
|---|---|---|
| D1 | v0.6.3 is a maintenance release with no new architecture-question class. | Accepted |
| D2 | The POST /v1/traces stall is fixed in v0.6.3, not v0.7. | Accepted |
| D3 | Ingestion remains serialized while blocking work moves off the event loop. | Accepted |
| D4 | Issue #305 is included only as per-source containment plus explicit diagnosis. | Accepted |
| D5 | Strict current RFC 8785 hashing semantics are preserved; no lossy coercion or alternate encoding. | Accepted |
| D6 | Broader support for out-of-range integers and any canonical-hash migration are deferred. | Accepted |
