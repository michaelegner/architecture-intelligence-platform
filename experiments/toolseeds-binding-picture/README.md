# ToolSeeds bindingPicture experiment — Sokol111 (AIP v0.8)

**External, read-only research prototype. No AIP product code is changed.**

## Question

When Catalog Management is moved from Redpanda to Kafka, which qualified consumer/topic bindings cross its boundary and what remains unknown? This is a contextual UI for existing provider answers, **not** a reimplementation of AIP's qualification logic.

## Inputs (already committed to this repository)

- `docs/specifications/0.8.0/i4-evidence/answers-before.json`: the recorded AIP query from the controlled v0.8 Sokol111 experiment (capture 2026-10-28T11:55:58Z).
- `docs/specifications/0.8.0/i2-vectors/c1-expected.json`: independently authored C1 expectation (2026-10-26).

## Reproduce locally

Requires Node.js 18+; no dependencies, network or secrets:

```sh
node experiments/toolseeds-binding-picture/build.mjs
node --test experiments/toolseeds-binding-picture/test.mjs
node experiments/toolseeds-binding-picture/build.mjs --without-provider
```

Open `experiments/toolseeds-binding-picture/results/binding-picture.html` locally. Filter by crossing direction/status and select a row to inspect exact AIP fields and opaque evidence references.

## Result

- **PASS:** nine provider bindings match the independent reference: two `PROMISED_AND_OBSERVED`, seven `UNRESOLVED` with `PROMISE_COVERAGE_MISSING`.
- **PASS:** original nine rows, source snapshot, 21 opaque evidence references, capture time, and four limitations retained without changing provider semantics.
- **PASS:** three negative mutations rejected (status, refs, limitation). Removing provider input returns **zero** provider-derived binding rows. HTML render repeated identically.
- **NOT RUN:** interactive browser verification, source handler tracing, live MCP calls, and evidence-mode ref resolution.

**Important:** The recorded AIP answer is `PARTIAL` (bounded consumer-group capture). A captured attachment does not prove handling, delivery, or completeness. Missing event-catalog promise coverage does not establish that no promise exists elsewhere. The frozen query contains evidence-ref identifiers but no same-snapshot evidence-mode response; they are retained, **not independently resolved**.

## Scope of evaluation

This tests fidelity and contextual presentation on Sokol111 only. It does **not** prove the generic ToolSeed works without AIP, that the UI improves comprehension or decisions, or that AIP adds value relative to an agent using source/broker tools directly. Those require later comparative tasks. No release claim follows from this experiment.
