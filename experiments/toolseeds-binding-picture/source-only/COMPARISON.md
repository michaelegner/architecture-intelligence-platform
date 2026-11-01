# Sokol111 bindingPicture: full-source vs. frozen AIP (first comparison)

**Outcome:** Source-only configured-pair discovery matches the recorded AIP answer's nine candidate consumer × topic pairs and selected-boundary crossing classes. AIP's frozen runtime-capture attachments and demonstration EventCatalog promise assessments are different claims that the source-only investigation does not establish.

**Qualified CI:** [successful run 41345041929](https://github.com/michaelegner/architecture-intelligence-platform/actions/runs/41345041929) · [HTML/JSON artifacts](https://github.com/michaelegner/architecture-intelligence-platform/actions/runs/41345041929/artifacts/13098697509).

## Inputs and scope

- **No AIP in extraction:** `source-only/core.mjs` → `investigate(inputs)` reads only 14 reviewed, redacted source-file excerpts captured at exact Sokol111 2026-10-21 revision SHAs. It derives configured consumer/topic pairs from the four pinned local Helm values and producer topic paths from the pinned Go API mappings and event factories. Documentation is treated as documentary context, **not owner promises**.
- **Explicit boundary:** migration task places Catalog and Image inside Catalog Management. It does not infer a bounded context from repository naming.
- **Comparison only:** `compare(source, recordedAipResponse)` joins the independently generated configured-pair result with the frozen 2026-10-28 `get_binding_picture` answer. The source-only tool does not access runtime broker captures or AIP data.
- **AIP reference:** `docs/specifications/0.8.0/i4-evidence/answers-before.json`, capture 2026-10-28T11:55:58Z, AIP response `PARTIAL`.

## Findings

| Consumer service | Topic | Selected-boundary crossing | Source-only | AIP assessment |
|---|---|---|---|---|
| Product Query | `catalog.product.events` | OUTBOUND | Configured | PROMISED_AND_OBSERVED |
| Image | `catalog.product.events` | INSIDE | Configured | PROMISED_AND_OBSERVED |
| Catalog | `tenant.tenant.events` | INBOUND | Configured | UNRESOLVED / PROMISE_COVERAGE_MISSING |
| Image | `tenant.tenant.events` | INBOUND | Configured | UNRESOLVED / PROMISE_COVERAGE_MISSING |
| Category Query | `catalog.category.events` | OUTBOUND | Configured | UNRESOLVED / PROMISE_COVERAGE_MISSING |
| Product Query | `catalog.attribute.events` | OUTBOUND | Configured | UNRESOLVED / PROMISE_COVERAGE_MISSING |
| Category Query | `catalog.attribute.events` | OUTBOUND | Configured | UNRESOLVED / PROMISE_COVERAGE_MISSING |
| Product Query | `tenant.tenant.events` | NONE | Configured | UNRESOLVED / PROMISE_COVERAGE_MISSING |
| Category Query | `tenant.tenant.events` | NONE | Configured | UNRESOLVED / PROMISE_COVERAGE_MISSING |

**9/9 pairs and 9/9 crossing classes matched; zero source-only runtime attachment claims.** Source documents directly describe two of the configured consumption paths in the examined product-update diagram. This must not be equated with two owner-confirmed architectural promises.

The provider's original limitation codes remain: `CAPTURE_SCOPE_LIMITED`, `EVENT_HANDLING_NOT_ESTABLISHED`, `PRODUCER_SIDE_DECLARED_ONLY`, `PROMISES_ASSUMED_CONFIRMED`. AIP's seven missing-coverage rows do not imply absence of an agreement outside the demonstration EventCatalog.

## Implications for the ToolSeed and AIP v0.9

1. **The source-only arm works:** the seed's investigation question is feasible without AIP on this project, including revision- and line-linked evidence. The concrete implementation is Sokol111-adapted; that does not validate broad prompt portability.
2. **No uniquely discovered binding:** in this full-source+infrastructure condition, AIP does not add an otherwise missing consumer/topic pair. The incremental information is qualified observation-at-T and EventCatalog-assessment semantics.
3. **Not yet a controlled value comparison:** this exercise did not give the source-only arm broker tools, and did not evaluate agent task outcomes, comprehension, time or maintenance effort. Earlier AIP v0.8 full-access A/B tests are the relevant harder baseline and should not be contradicted by this narrower experiment.
4. **Identity caution:** service identity derived from source-repository names is explicit within this fixture, not a general reconciliation algorithm. The first test exposed a `Sokol111/` repo-qualified-vs-service identifier mismatch, which was corrected before the successful run.

## How to reproduce

```sh
node experiments/toolseeds-binding-picture/source-only/build.mjs
node --test experiments/toolseeds-binding-picture/source-only/test.mjs
```

The CI run publishes `source-only.html`, `comparison.html` and their JSON equivalents. Browser interaction was not independently exercised, and this was not a blind external coding-agent run.

**Decision:** useful feasibility and information-comparison result; no v0.9 product-value claim, additional AIP implementation, or upstream ToolSeeds readiness is established by this experiment.
