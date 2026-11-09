# GT 0.8.0 experiment: I1 freeze record

**Increment 1** of the [GT 0.8.0 specification](../specification.md) (Draft 0.16): freeze the independent offers and evidence. The digests are in [`SHA256SUMS`](SHA256SUMS). Run `sha256sum -c SHA256SUMS` in this directory.

| Path | Audience |
|---|---|
| [`participant/task.md`](participant/task.md) | participant: the task and a brief orientation |
| [`participant/MANIFEST.md`](participant/MANIFEST.md) | operator: the participant corpus per condition |
| [`researcher-key.md`](researcher-key.md) | researcher only |
| [`aip/`](aip/) | researcher only: frozen AIP requests and responses |

## Promise Contracts

The four service contracts and the marketplace contract in [`../demo-promises/`](../demo-promises/README.md) are frozen. Before the freeze they had an **editorial trim and source pinning; their contractual meaning is unchanged**:

- AIP/C1 remarks and connector- or marketplace-specific hints are removed. Each provider keeps its own limitations.
- The marketplace contract no longer explains how its stages combine with other parties' commitments.
- Two neutral rewordings: `IMG-OFFER-01` "Does not authorize additional consumers" replaces the marketplace-specific limitation; the marketplace `Evolution` line now reads "Only the modeled marketplace role may revise this fictional offer."
- Every `blob/master` link is pinned to the commit in the v0.7.2 freeze. Every cited file resolves at its commit.

| Contract | Fixture version |
|---|---|
| `CAT-OFFER-01`, `IMG-OFFER-01` | 1 → 2 |
| `PQ-ACCEPT-01`, `PQ-READ-01` | 2 → 3 |
| `DEMO-CONTRACT-001` | v2 → v3 |

## Identities

Each identity was captured from git or from the live read-only answer on 2026-11-09. Each one is recorded separately.

| Identity | Value |
|---|---|
| Input package | [v0.8 I1 evidence package](../../../../specifications/0.8.0/i1-evidence/README.md) at tag `v0.8.0` (commit `63534a650b8d1f947aa0d930f678dd0a0cb718e4`). sha256 of its `SHA256SUMS`: `0cc5259a7501b20d6b9ca2d5dc6f8194d7fcbe2c5129a74876f25af017fbf450`. It is unchanged on `main` |
| EventCatalog | catalog digest `ff24602762eb2bac4d56955900b82f00f23f01dc5479a12140719753e9ae250e`; lookup digest `63adbc14429b0cea899076e44ae0f4fc8e3b7ab259a87bfd918526866973adf1` (from the answer's `catalog_source`) |
| Snapshot | `aip:snapshot:v1:7f171aea2d3c5070e6be3dd9c6b53a234ad75934be5724681b95cd3e1705c413` |
| C1 capture | broker `kafka:sokol111-local`, T `2026-10-21T17:53:57Z` |
| Query scope | `{"mode": "query", "bounded_context_id": "catalog-management", "environment": "local", "broker_ids": ["kafka:sokol111-local"]}`; no `limit`, as in the [hosted walkthrough](../../../../../examples/sokol111-demo/TRY_IT_HOSTED.md) |
| Serving build | `producer.version` `0.8.0`, `producer.build_revision` `63534a650b8d1f947aa0d930f678dd0a0cb718e4` (from the answer). The image digest `sha256:8f3cad874e3b0d1c63918dca9fed35862fb1e3ba1831a491bdfc255af12e5fcd` comes from the [release record](../../../../release-validation/v0.8.0-release-record.md); it was not observed live |
| Sokol111 source | the 16 repositories at the commits of the [v0.7.2 freeze](../../../../specifications/0.7.2/i2-evidence/sokol111/freeze.md), including `ecommerce-infrastructure` (owner decision, 2026-11-09): the consumer-group mapping was authored from it, so excluding it would give AIP exclusive access to evidence. The [v0.8 value experiment](../../../../specifications/evaluation/v08-showcase-value-qualification-experiment.md) excluded it (D5), so the two source corpora differ. Do not claim identical conditions when comparing with that experiment |

## AIP responses

`aip/*.request.json` holds the exact JSON-RPC request bytes. `aip/*.response.json` holds the HTTP response body bytes. The endpoint is `https://mcp.daip.io/mcp`.

The **canonical answer digest** covers the MCP tool result's `result.structuredContent`. That is the object that `_tool_call` in [`verify_public_edge.py`](../../../../../examples/sokol111-demo/hosted/verify_public_edge.py) checks. The digest is computed as follows:

```python
hashlib.sha256((json.dumps(result["structuredContent"], sort_keys=True) + "\n").encode()).hexdigest()
```

The serialization uses Python's default separators and `ensure_ascii`, with one trailing newline. This convention reproduces the hosted record's `9c97b871…945c81`. The compact `(",", ":")` variant does not, and neither does the request with `limit: 200`.

| Capture | Captured | Outcome | Response-body sha256 | Canonical answer sha256 |
|---|---|---|---|---|
| `query` | 2026-11-09T16:34:02Z | `PARTIAL`, 9 rows | `ee5fefc88294b6350a14933ac5f1d5794bb0b225d36c9ce8e9bd403ef7130aec` | `9c97b871e1369c0c06cd14b4850110b8a1e62c59693f154bf2ede2bc08945c81` = [hosted record](../../../../release-validation/v0.8.0-hosted-record.md) |
| `evidence-pq-product` | 2026-11-09T16:34:28Z | `ANSWERED`, 4 `RESOLVED` | `f9fab1da740d9b0f17303be2ae9aa7f985cdd8ef20033290c882a0c7dbf232b5` | `9f6a107330f7fa39b02bcc940849b0d8500741e0675663b455fd5a0a16f6e035` |

The evidence capture covers the four refs of the Product Query × `catalog.product.events` row. It records **which evidence was available**. It does not answer the research question.

## Key author

Claude drafted [`researcher-key.md`](researcher-key.md) for the owner and has read the specification. Owner approval: **approved** (2026-11-09).

## For I3

- Before each condition, re-run the `query` request. Compare the snapshot ID and the canonical answer sha256 with this record. On a mismatch, stop and record it. Do not adopt a new baseline silently.
- Set up each condition only from [`participant/MANIFEST.md`](participant/MANIFEST.md). The key is public in this repository, so a participant session must have no access to the repository or the web.
- Record each participant's prior familiarity with Sokol111, this specification and earlier conditions. If independence cannot be shown, report the comparison as exploratory.
