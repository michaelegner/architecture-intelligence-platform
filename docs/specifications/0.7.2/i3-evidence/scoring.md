# I3 scoring (written before either arm ran)

Both arms are scored against independent evidence, not against either agent's account ([spec](../specification.md) §5.3). The simulator's 0–100 evaluator score and attribution are secondary.

## Ground truth

Sources:
- [`expected.json`](../i2-evidence/sokol111/expected.json), which was authored from source and configuration before any capture;
- [`mapping-review.md`](../i2-evidence/sokol111/mapping-review.md);
- the stock `rpk` output in [`raw/`](../i2-evidence/sokol111/raw/) (G1 and G1');
- the frozen sources ([`freeze.md`](../i2-evidence/sokol111/freeze.md)).

| Fact | Kind | Basis |
|---|---|---|
| `ProductUpdatedEvent` is published on `catalog.product.events` | configured | `ecommerce-catalog-service-api` `pkg/events/topics.go` |
| Producer: `ecommerce-catalog-service`, through its outbox | configured | `product_event_factory.go`, and `ecommerce-commons` outbox |
| Consumer: `ecommerce-product-query-service`, with group `ecommerce-product-query-service` | configured **and** observed | `values/ecommerce-product-query-service.yaml` `default-group-id`; `Stable` and attached to the Topic at T `2026-10-21T17:53:57Z` (C1, G1) |
| Consumer: `ecommerce-image-service`, with group `ecommerce-image-service` | configured **and** observed | `values/ecommerce-image-service.yaml`; `Stable` and attached at the same T |
| `ecommerce-category-query-service` and `ecommerce-catalog-service` do not consume the Topic | configured, and observed at T | their groups are attached to other topics only |
| The observation covers only the four deployed groups of the local environment at T | scope limit | `CAPTURE_SCOPE_LIMITED`; there is no production observation and no observation after T |
| Fields read: Product Query reads all fields; Image reads only `ProductId` and `ImageId` | configured | their `product_handler.go` |

## Rubric, per arm

| # | Question | Score |
|---|---|---|
| R1 | Consumers found or missed: both true consumers named, and no false consumer? | found / missed / false |
| R2 | Unsupported claims: any relationship, environment or "complete list" asserted without evidence? | list |
| R3 | Current State vs. history: are configured, observed-at-T and inferred kept apart? Is T stated? Is a past capture presented as live or production behaviour? | yes / no, with a quote |
| R4 | Unresolved vs. asserted: what does the arm leave open, for example production, consumers outside the capture, or deployed versions? | list |
| R5 | Provenance actually used: files, Unblocked citations, raw `rpk` files, AIP calls and evidence drill-down (`mode: evidence`) | list |
| R6 | Concrete change: a different consumer set, rollout gate, check or code change compared with the other arm, or **no additional value** | text |
| R7 | Navigation (arm B only): did the task's ordinary words lead the agent to an AIP query context, meaning the Topic id, `kafka:sokol111-local` and `local`? Which calls failed or refused? | text |
| R8 | Contamination: does the arm pass every after-run check in the [README](README.md)? Those are: no token leak; no `gh`, `curl` or `wget`; no read outside its own worktree, and no other arm's branch; no AIP repository content or `context_get_urls` URL; no AIP in arm A. Also list arm B's AIP errors and 429s | pass / fail, with a list |

Secondary: effort to set up, map and refresh; tokens, time and cost from `result.json`; and the simulator score.
