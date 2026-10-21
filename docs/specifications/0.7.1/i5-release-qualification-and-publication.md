# AIP v0.7.1 I5 — Release qualification and publication

**Status:** Proposed  
**Depends on:** completed [I4 result](i4-result-record.md), [I4 → I5 handoff](i4-i5-handoff.md), [v0.7.1 release specification](specification.md) §7–§9.  
**I4 owner decision:** `CONTINUE`.

## 1. Goal

Publish v0.7.1 from one **exact release commit**, with reproducible six-tool MCP golden output, accurate client documentation and release notes, and verified published artifacts. I5 packages the already-qualified Kafka consumer-attribution capability; it does not revisit I0–I4 semantics.

## 2. Candidate selection (including #611)

- The I4 qualified candidate is `df3a9e4f4ca7ee89aa5afdde836b2905027dd30f`. I4's clean A/B replay and independent ground-truth qualification remain valid **for that SHA**, not automatically for a later one.
- **Post-candidate dependency change:** merged PR [#611](https://github.com/michaelegner/architecture-intelligence-platform/pull/611), merge `686a6a5`, updated **only `certifi` in `uv.lock`** to `2026.10.19` for `PYSEC-2026-4320`. Its recorded dependency tree has no non-dev `certifi` dependency; the change does not affect the runtime image. However, it **does change the locked test environment**, so an I4 pass cannot be represented as an exact-candidate qualification of a release SHA containing #611.
- Select and record a **new exact candidate SHA** from the release-facing commit (including #611 and I5 edits). Compare it with the I4 candidate: record the exact production, schema, source-input, lockfile and golden-path differences. Re-run required gates, security scan, six-tool parity/golden checks and the deterministic A/B replay on the selected SHA; retain the I4 real-broker provenance without claiming it was captured on that later SHA.
- If any relevant behavioral/schema/input difference exists, qualify its affected cases against independent expectations before freezing; if replay or parity changes unexpectedly, resolve and select a new SHA. Do not silently normalize golden output or transplant snapshot IDs across checkout paths.
- Record `uv.lock` / `certifi` version, vulnerability-scan result, test environment and candidate SHA in the final release record. Re-check `PYSEC-2026-4320` status as part of the release security review.

## 3. Release-facing re-freeze

Update and exercise these concrete surfaces from [the handoff](i4-i5-handoff.md):

- `examples/release-golden-path/TOOLS`, `expected.json`, README re-freeze section;
- `README.md`: six-tool count and the `get_destination_consumers` entry;
- `examples/mcp-clients/cursor.md` and `examples/mcp-clients/vscode.md`;
- `examples/runtime-demo/hero-demo.md`;
- `CHANGELOG.md` and v0.7.1 release notes.

The negotiated MCP `tools/list` must advertise exactly six tools. Keep the five existing tool contracts unchanged. Verify the new tool's query/evidence examples on REST and negotiated MCP with consistent outcome, limitations and evidence links. Golden outputs are captured against the chosen SHA in a clean, fixed checkout location.

## 4. Contract and documentation decision

The I4 agent session exposed an `evidence_refs` ordering requirement: the evidence request rejects unsorted refs, while the published request schema advertises only uniqueness. **Before the release freeze**, choose one of:
- document sorted, duplicate-free refs in the schema/tool description and client examples; or
- relax the implementation to accept any unique order, with deterministic internal canonicalization.

Prefer a **documentation-only fix** unless a product reason requires changing behavior. If behavior changes, it requires a new candidate and affected contract/parity qualification. Record the decision. Do not broaden I5 into other API redesigns.

## 5. Release communication and boundaries

Release notes must explicitly state:
- Kafka attachment at **T**, combined with independently qualified Service mapping; only `RESOLVED` names a Service;
- `CAPTURE_SCOPE_LIMITED` and the need to maintain capture allow-lists; missing attachments are **not** negative consumption claims;
- new snapshot IDs when Kafka consumer state is present (`kafka_topic_brokers_v1`), and the pre-existing absolute-checkout-path dependence of snapshot identities, refs and output digests;
- RabbitMQ is a semantic contrast only, **not** a shipped adapter.

Carry documented limitations from [I4](i4-result-record.md): one local Kafka system and one agent session; synthetic-only ambiguity/conflict cases; derived incomplete capture; the namespaced/explicit-id Topic limitations; unresolved `ops-tail` and incomplete Service mapping. Re-check every referenced issue, CVE and limitation against its **current** state before publishing; note changes instead of repeating stale claims.

## 6. Exact-candidate checks and publication

1. Freeze candidate SHA, clean checkout path, lockfile digest and commands. Run format/lint/type checks, unit, integration and qualification tiers, vulnerability/dependency scan, and relevant CI checks.
2. Re-run deterministic A/B with frozen Kafka inputs and independent expectations on that candidate and **one absolute checkout path**, verify public service/REST/negotiated-MCP parity, evidence safety, no-source compatibility and the six-tool golden path. A/B runs must use clean independent state. Record exact hashes, pass/fail and any differences from I4.
3. Verify release documentation and client instructions against the running candidate (no placeholders or obsolete five-tool statements); ensure no test credentials/secrets in release artifacts.
4. Tag and publish **the same verified SHA** with the established v0.7.0 release procedure. Confirm build/package metadata, release/tag association, hosted MCP tool enumeration and public installation/golden-path instructions. Do not claim publication until verified.
5. Record a compact I5 release result: SHA and tag, gate/CI and replay results, lockfile/security status (including #611), tool count/golden digest, artifacts, publication checks, and carried limitations.

## 7. Done criteria

I5 is complete only when a single release SHA containing the #611 lockfile update and I5 re-freeze has passing gates, deterministic A/B and public-surface parity; the six-tool docs/golden assets match it; the ordering decision and limitations are visible; and the tagged, published artifacts have been checked against that SHA.

**Out of scope:** new RabbitMQ carrier; new Kafka semantics or I1–I3 attribution rules; generalized event impact analysis; new adapters, topology, policy, Intent or Assessment; rewriting I4 evidence or the owner decision.
