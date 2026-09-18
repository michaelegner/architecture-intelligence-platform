<!--
Specification-driven agents: preserve the hidden `aip-agent-metadata:v1` planning-start marker
required by the specification-driven-implementation skill when editing this PR description.
-->

## What does this change?

<!-- Summarize the change and why it's needed. -->

<!--
The sections below apply to specification-driven increment work (see AGENTS.md and the
specification-driven-implementation skill). For a small maintenance change that doesn't touch
public contracts, identity, evidence, qualification, reconciliation, or release semantics, delete
them rather than leaving them blank.
-->

## Governing Specification & Revision

<!-- Path + exact revision/draft marker, e.g. docs/specifications/0.5.0/i1-source-ingestion-foundation.md, Draft 0.3. -->

## Approved Implementation Plan

<!-- Link to where the plan was persisted (this PR description, or the issue it was approved in) - the plan should remain visible here, not be replaced by this description. -->

## Scope & Non-Goals

<!-- Bounded scope and explicit non-goals. -->

## Requirement -> Test Traceability

<!-- Specification requirement / acceptance criterion -> the test(s) or evidence that prove it. -->

## Implementation Reconciliation

<!-- Deviations from the plan and why, specification questions discovered, deferred work, remaining limitations. -->

## Validation & Qualification Evidence

<!-- Actual command output: uv run pytest tests/unit / tests/integration, ruff check/format results, etc. -->

## Deviations & Deferred Work

<!-- Anything explicitly out of scope for this PR, pushed to a later increment. -->

## Checklist

- [ ] tests added/updated
- [ ] documentation updated
- [ ] no secrets included
- [ ] licensing compatible (new dependencies are Apache-2.0-compatible; see `THIRD_PARTY_LICENSES.md`)
- [ ] backwards compatibility considered

### If this adds or changes an adapter

- [ ] unit tests
- [ ] integration fixture (`tests/fixtures/` and/or `examples/`)
- [ ] adapter documentation (`docs/adapter-development.md` and/or the relevant `docs/*.md`)
