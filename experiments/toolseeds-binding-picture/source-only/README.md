# Source-only Sokol111 experiment

This is an independent **source/configuration-only** application of the `bindingPicture` ToolSeed task. It consumes no AIP data in `investigate()`. The separate `compare()` step reads the recorded AIP result **after** the source investigation and compares both outputs.

Inputs are small, reviewed, redacted excerpts from **14 Sokol111 files** in the 2026-10-21 frozen multi-repo revision set, including 4 local Helm configuration files, 3 event/topic mappings, 5 event-factory sources, and 2 architecture documents. The pinned original URL and line number are retained for each excerpt. No full credential-bearing Helm values were copied.

## Commands

From repository root (Node 18+):

```sh
node experiments/toolseeds-binding-picture/source-only/build.mjs
node --test experiments/toolseeds-binding-picture/source-only/test.mjs
```

Outputs:

- `results/source-only.json` + `source-only.html`: configured pairs and source pointers, no AIP input.
- `results/comparison.json` + `comparison.html`: side-by-side information comparison against the unchanged AIP pre-migration recorded answer.

## Interpretation

The source-only run can reconstruct all **9 configured** consumer/topic pairs and derive the same candidate crossing directions using the explicitly selected Catalog Management migration boundary and producer event-factory/topic-map paths. This is *not* an observed broker attachment.

The AIP frozen capture establishes all 9 consumer group attachments at its capture time and qualifies 2 EventCatalog promises, leaving 7 `PROMISE_COVERAGE_MISSING` assessments. It does **not** establish event handling, delivery or global completeness.

The source-only run has 2 direct documented consumption paths in the selected project diagram; those are documentation claims, not owner-confirmed promises. No source-only promise assessments are manufactured.

## Limitations

- **Full-source scenario only.** This includes the infrastructure repository, unlike the previously evaluated team-scoped restriction. It is not a customer-workflow trial.
- Source extractor is intentionally **Sokol111-adapted**, based on Go topic maps and Helm value excerpts; portability of the prompt to other codebases is NOT proven.
- The source-only research code and inputs were assembled for this experiment; this is not evidence that a separate coding-agent execution independently generated the tool from scratch.
- Captures and provider evidence refs were **not freshly collected** here, and referenced AIP evidence was **not dereferenced** in this comparison.
- No timing, participant comprehension, counterfactual planning, or decision quality was evaluated. This is **an information availability comparison**, not proof of AIP product value.
