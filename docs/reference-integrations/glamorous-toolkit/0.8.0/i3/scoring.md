# GT 0.8.0 I3 scoring

**Status: owner-approved (2026-11-10).** Claude scored the four sessions against the [researcher key](../i1-freeze/researcher-key.md). Each arm ran once, so every result is exploratory. The records are in [`sessions/`](sessions/), and the harness is in [`harness/`](harness/README.md).

## Sessions

All four audits are clean. Every session ran `claude-opus-5-5` on Claude Code 2.1.322.

| Session | Duration | Turns | Cost | Tool calls | AIP use |
|---|---|---|---|---|---|
| [G-1](sessions/G-1/) | 370 s | 139 | $1.57 | 69 view reads, 63 navigations | none (no AIP in the image) |
| [GA-1](sessions/GA-1/) | 257 s | 119 | $1.34 | 61 view reads, 52 navigations | **none**: opened the AIP client's views, never ran the query |
| [A-1](sessions/A-1/) | 155 s | 40 | $0.82 | 25 reads, 6 globs, 6 greps | none (no AIP) |
| [AA-1](sessions/AA-1/) | 126 s | 39 | $0.84 | 27 reads, 3 globs, 3 greps | `get_binding_picture` (query mode) and `get_service_dependencies` (NOT_ANSWERED); frozen snapshot |

**GA-1.** The agent listed the AIP client's views. It read the Queries view, which has one row, `binding picture`, and the client's Messages view. It never selected the row, so no request reached hosted AIP. The exported client log holds only the MCP handshake. The session is clean and stays as recorded: the plan does not allow a re-run to get a better result.

Legend: ✓ found and stated correctly; ◐ partly; – not found; n/a not available in the arm.

## 1. Established facts

| Ref | G-1 | GA-1 | A-1 | AA-1 | Note |
|---|---|---|---|---|---|
| F1 CAT-OFFER-01: existing consumers only, no latency | ✓ | ✓ | ✓ | ✓ | |
| F2 PQ-ACCEPT-01: Product Query's own projection only | ✓ | ✓ | ✓ | ✓ | |
| F3 PQ-READ-01: provisioned clients, no freshness | ✓ | ✓ | ✓ | ✓ | |
| F4 IMG-OFFER-01: no additional consumers | ✓ | ✓ | ✓ | ✓ | |
| F5 DEMO-CONTRACT-001: accepted requests, no fixed time | ✓ | ✓ | ✓ | ✓ | All four state that acceptance and pending are not withdrawal |
| F6 no contract names the connector | ✓ | ✓ | ✓ | ✓ | |
| S1 disable is `ProductUpdatedEvent` with `Enabled` | ✓ | ✓ | ✓ | ✓ | |
| S2 delete carries only the product ID | ✓ | ✓ | ✓ | ✓ | All four add that it has no version |
| S3 outbox in the same transaction, best-effort send | ✓ | ✓ | ✓ | ✓ | G, A and AA also read the relay in `ecommerce-commons` (see insights); GA says the relay timing is not established |
| S4 Product Query handles updated, deleted, image promoted | ◐ | ✓ | ◐ | ✓ | G and A cite Product Query's delete and upsert behavior, not the handler registration |
| S5 Product Query copies `Enabled`; read filtering open | ◐ | ✓ | ✓ | ✓ | G: hedged, "did not see a filter". GA: hedged correctly. A and AA resolve the key's open point (see insights) |
| A1 Product Query × product topic `PROMISED_AND_OBSERVED`, 4 refs | n/a | – | n/a | ◐ | AA: query mode only, with the limitations quoted; no evidence mode |
| A2 9 rows, 2 promised and observed, 7 unresolved | n/a | – | n/a | ◐ | AA: "PARTIAL", "several" unresolved; no counts |

## 2. Invalid inferences

No session made any of X1–X9.

- **X1:** all four refuse an unconditional 15-minute promise and compose it from separately owned budgets.
- **X6:** AA quotes AIP's own limitation that an attachment does not establish which events a group handles.
- **X8:** A and AA call the contracts fictional. G and GA do not say so, but they also make no claim that the contracts are real commitments.

## 3. Open design decisions

| Decision | G-1 | GA-1 | A-1 | AA-1 |
|---|---|---|---|---|
| Stages (a)–(d) and their owners | four stages, no bound on any; two have no applicable offer | four stages, with broker → connector as a separate platform stage | Catalog, connector and marketplace stages as commitments C1, C3, C4 | budgets T₁ (Catalog), T₂ (connector), T₃ (marketplace) |
| Where the connector gets changes | events under a new Catalog offer; Product Query reads only for reconciliation | events; Product Query polling would add an unbounded stage | events; rejects Product Query for detection; reconciles against Catalog | events; Product Query reads for reconciliation, with provisioning |
| What the connector commits to | own stage, polls outcome to *completed*, escalates; declines the 15 minutes | same, plus reconciliation | same, plus tombstones and measured end-to-end time | same, plus tombstones |
| What remains unowned | marketplace bound; tenant scoping; liability | tenant context; revoked credentials; meaning of "withdrawn" | tenant field; Product Query access; failure outcomes | tenant context; clock start; outage windows; notice of format changes |
| Decision class | conditional proceed; defer if the 15 minutes is hard | conditional proceed; defer for the hard guarantee | conditional proceed; withhold the 15 minutes until C1 and C4 exist | conditional proceed; defer without the Catalog and marketplace commitments |

All four decisions cite their facts and keep contract, source and capture apart.

## 4. First impression, findings and revision

| Session | First impression | Final | What changed |
|---|---|---|---|
| G-1 | conditional proceed | conditional proceed | Stricter: the audience exclusion (F1, F4), the 10-hour backoff, and no marketplace bound (F5) |
| GA-1 | conditional proceed | conditional proceed | Stricter: the audience exclusion, no marketplace bound, and the catalog omission (F9) |
| A-1 | conditional proceed | conditional proceed | Corrects its own first impression ("the sync is not freely feasible"). The 10-hour backoff and the missing `enabled` field rule out Product Query polling |
| AA-1 | conditional proceed | conditional proceed | Stricter: the marketplace addendum, the audience admission and a publication budget |

All four first impressions already named the composed, multi-party structure. The investigation sharpened the conditions but changed no decision class. So no session produced a **decision-changing** insight. The sessions differ in **discovery**, meaning which implementation facts they found; comprehension of the contracts is the same in all four.

## 5. Research-only check (A1)

- **AA-1:** its conclusions about PQ-ACCEPT-01 and PQ-READ-01 did not change because of A1. It states that `PROMISED_AND_OBSERVED` rests on the assumed-confirmed demo catalog.
- **No-AIP sessions:** G, GA and A all reached the attachment fact from the C1 capture and the mapping in the common corpus: Product Query and Image consume `catalog.product.events`, and the capture has no lag data.
- **Result:** in this run, AIP gave AA no decision-relevant fact that the corpus did not also give the other arms.

## Unexpected insights

"Verified" means checked by the scorer against the frozen corpus or the frozen AIP answer.

| Session | Insight | Evidence | Verified? |
|---|---|---|---|
| G, A, AA | The outbox retry backoff is capped by `MaxBackoff`, which defaults to 10 hours. A few failed sends push publication past 15 minutes | `ecommerce-commons/pkg/kafka/outbox/config.go` L8–L15, `repository.go` | yes |
| G, GA, A, AA | A delete has no version, so a late or redelivered older update could re-create a deleted product | Product Query `delete_product.go` and the version-guarded upsert | inference, not tested by any session |
| A, AA | Product Query list queries return only enabled products. Its `Product` message has no `enabled` field, so its reads cannot report a disable | `product_view_repository.go` L111, L154, L217; `product_query.proto` `Product` | yes |
| AA | The relay picks messages by next attempt time, then creation time, so a retried update can be published after a later delete | `repository.go` L43–L45 | sort order yes; the reordering is inferred |
| GA, A, AA | The generated EventCatalog has no `ProductDeleted` entry. Planning from the catalog alone would miss deletion | `inputs/catalog/events/` | yes |
| AA | AIP's binding picture declares only `ProductImagePromoted` and `ProductUpdated` for Product Query × `catalog.product.events`, with no `ProductDeleted` | frozen [`query.response.json`](../i1-freeze/aip/query.response.json) | yes |
| G, A | Image events share `catalog.product.events` with Catalog's events, under two separate offers | `ecommerce-image-service-api/pkg/events/topics.go` L11–L16 | yes |
| G | The upstream flow says a change "reliably reaches the storefront"; the contracts deny any guarantee | `inputs/upstream/product-update-flow.md` L3 | yes |
| AA | The requirement needs an agreed clock start (commit, not click) and agreed outage exclusions before anyone can verify it | answer §3, C6 | design point, not a fact |
| GA | Whether "no longer publicly visible" matches the merchant's meaning, including caches and search indexes | answer §4 | open question, not a fact |

## Attribution pairs

- **E1, G vs GA:** not measurable. GA never queried AIP, so any difference between G and GA is run-to-run variance, not AIP. The observation itself is a finding: AIP was reachable through GT views, but nothing told the agent that selecting the row runs a query.
- **E1, A vs AA:** AA made one binding-picture query. Its AIP finding was correct and correctly qualified, but no other arm needed AIP to reach the same conclusions. It changed no decision. Duration and cost are about the same (126 s vs 155 s; $0.84 vs $0.82).
- **E2, A vs G:** same decision class and the same contract comprehension. GT cost more: 2.4× the duration, 3.5× the turns, 1.9× the cost. Discovery differs in both directions: G found the documentation overclaim, and A found that Product Query reads cannot report a disable. In this run GT gave no decision-changing insight.

## Owner sign-off

| Decision | Value |
|---|---|
| Scoring approved | yes, 2026-11-10 |
