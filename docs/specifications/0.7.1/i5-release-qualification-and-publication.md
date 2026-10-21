# AIP v0.7.1 I5 — Release

**Status:** Proposed  
**Basis:** [I4 result](i4-result-record.md) (`CONTINUE`), [I4 → I5 handoff](i4-i5-handoff.md), [release specification](specification.md) §7–§9.

## Goal

Ship the already-qualified Kafka consumer-attribution capability as v0.7.1. Update the six-tool release examples and documentation, run normal release checks, publish and verify. **Reuse I4 evidence; do not repeat qualification for documentation or dev-only dependency changes.**

## Scope

1. **Re-freeze release materials:** `examples/release-golden-path/` (`TOOLS`, `expected.json`, README), `README.md` tool table/count, MCP client guides (`cursor.md`, `vscode.md`), `examples/runtime-demo/hero-demo.md`, `CHANGELOG.md` and release notes. Verify the negotiated MCP list has **six tools**, including `get_destination_consumers`; the five existing contracts stay unchanged.
2. **Clarify the evidence request:** I4 found that `evidence_refs` must be sorted and duplicate-free, but the advertised schema only says unique. Document the ordering rule in the tool description/examples. Avoid an API change in this release unless the documentation-only approach proves inadequate.
3. **State the product boundary accurately:** Kafka attachment at capture time T plus independent Service mapping; only `RESOLVED` attributes a Service. Capture coverage is limited (`CAPTURE_SCOPE_LIMITED`); absence is not proof of non-consumption. RabbitMQ is not shipped as an adapter. Mention the Kafka snapshot-id change and the existing absolute-checkout-path dependence. Carry the material I4 limitations without turning the release notes into a qualification report.
4. **Release checks:** Pick and record the release commit SHA. Run normal CI, tests, dependency/security scan and the six-tool golden-path check; check relevant release documentation against the running candidate. Publish/tag that verified SHA, then check published artifacts and the hosted MCP tool list.
5. **Record the outcome:** A short release record with SHA/tag, green checks, six-tool verification, publication links/status and any remaining limitations.

## Reuse of I4 and #611

I4's deterministic A/B replay, real Kafka check, REST/MCP parity and product-value investigation are **already qualified** on `df3a9e4`; the [result record](i4-result-record.md) is the evidence.

Merged [#611](https://github.com/michaelegner/architecture-intelligence-platform/pull/611) updated only the **dev-only** `certifi` entry in `uv.lock` to `2026.10.19` (`PYSEC-2026-4320`). This does not invalidate I4 or require another Kafka capture/A-B replay. Include the change in the release candidate and let normal tests and the dependency scan verify the updated environment.

**Re-run affected qualification only if production behavior, relevant schemas, or qualification inputs change.** A docs-only re-freeze or dev-only lockfile update is not by itself a reason to rerun the entire I4 campaign.

## Done

- Release-facing six-tool docs/golden artifacts match the chosen commit.
- Normal release CI/tests/security checks pass; any actual behavior change has targeted requalification.
- The `evidence_refs` rule and key product limitations are clear.
- v0.7.1 is tagged, published and verified against the recorded commit.

**Not in scope:** new adapters, RabbitMQ implementation, broker-topology expansion, changed I1–I3 semantics, or repeating the I4 experiment for its own sake.
