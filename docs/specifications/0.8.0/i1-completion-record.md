# AIP v0.8 I1: Completion Record

**Status:** COMPLETE on merge of the I1b PR. The closure SHA is added in a follow-up only if the owner asks.
**Outcome:** `READY_FOR_I2` if the owner records it on merging the I1b PR.

This record covers the [I1 spec](i1-declared-side-and-inventory.md), Draft 0.1, under the [v0.8 specification](specification.md), Draft 0.2. It reconciles the result against the approved plan, which is kept verbatim in the #638 PR description.

## Run identity

| Slice | Deliverables | PR | Merge commit | Merged (UTC) |
|---|---|---|---|---|
| I1 spec | [`i1-declared-side-and-inventory.md`](i1-declared-side-and-inventory.md), parent Draft 0.2 (D7, D8) | #637 | `ad95dad74c0feb7f1ed87fc841dbc4e5677d059f` | 2026-10-26T12:08:42Z |
| I1a | AsyncAPI topic-only channels, both declaration sets, mappings, C1 copy, [`i1-vectors/`](i1-vectors/), A4–A8 | #638 | `010ec00349e3624b3260a818515bebf141a3c191` | 2026-10-26T13:17:52Z |
| I1b | upstream bytes, generator, catalog, lookup, loader, shared bounded YAML, this record, [`i1-i2-handoff.md`](i1-i2-handoff.md), A1–A3 | this PR | read from `gh pr view --json mergeCommit` after merge | |

The I1 spec and I1a merge commits above were read from `gh pr view --json mergeCommit,mergedAt`.

## Completed as planned

- **AsyncAPI change (§3):** a qualified Topic channel is supported without operations. `mapping_rule_version` stays `v2`.
- **Declarations (§4):**
  - Redpanda: the 5 Services and the pre-wave producers;
  - Kafka: the 4 Topics without operations.
- **Topic ids (§6):** `i1-vectors/ids.json`, checked against the spec table and `topic_owned_id`.
- **Mappings (§7)** with a review file.
- **Package (§8)** with `SHA256SUMS`.
- **Generator (§5.4):**
  - digest-pinned upstream documents and fixed tables;
  - a hard failure, with file and line, on an unknown label;
  - deterministic output. The catalog digest is `ff24602762eb2bac4d56955900b82f00f23f01dc5479a12140719753e9ae250e`.
- **Loader (§5.5):** the closed subset, the bounds and the four reason codes. It outputs a typed declaration set and persists nothing.
- **Registration:** `SourceKind.EVENT_CATALOG`, `EventCatalogSourceConfig` and `SourcesConfig.event_catalogs`. None of them is wired into `run_all_configured_sources`.
- **Refactoring (plan task I1b.3):** the hardened YAML loader moved from `app/sources/kubernetes_envelope.py` to `app/common/bounded_yaml.py`. The depth is now a parameter. The Kubernetes envelope maps the two shared errors onto its own §4.3 buckets, so its behaviour is unchanged (269 envelope, Kubernetes and workload-mapping unit tests pass).

## Deviations and justification

| # | What | Why |
|---|---|---|
| 1 | The vectors are in `docs/specifications/0.8.0/i1-vectors/`, not in `i1-evidence/` | I1 spec §6 and the precedent of earlier releases put them next to the spec (#638 review) |
| 2 | The shared YAML loader takes the depth as a parameter, but the exception types are not parameters. It raises two neutral errors (`BoundedYamlLimitExceeded`, `BoundedYamlMalformed`), and each caller maps them | One mapping site per caller is simpler than passing exception classes in |
| 3 | `catalog.SHA256SUMS` lists paths relative to `catalog/` | §5.4 says "one line per file under `catalog/`". Check it with `cd catalog && sha256sum -c ../catalog.SHA256SUMS` |

## Specification questions discovered

These are loader rules inside the closed subset that I1 spec §5 does not state. Each one only rejects input that the generator never writes:

| Rule | Reason code |
|---|---|
| Two entries of one kind with the same `id` | `EVENTCATALOG_INVALID` |
| A symlink under `catalog/` | `EVENTCATALOG_UNSUPPORTED` |
| A `catalog_relative_path` that is missing, not a directory or outside `root`, or a `lookup_relative_path` outside `root` | `EVENTCATALOG_INVALID` |
| A lookup entry for an event that is not in the catalog | `EVENTCATALOG_REFERENCE_UNRESOLVED` |
| A duplicate lookup entry | `EVENTCATALOG_INVALID` |
| A lookup document nested deeper than 32 | `EVENTCATALOG_UNSUPPORTED` |
| `summary` is required on an event entry | `EVENTCATALOG_INVALID` |

If the owner wants any of these rules different, it is a spec amendment, not a code change.

## Deferred work

- Promise record, assessment, projection, tool and field descriptions (I2).
- Wiring the EventCatalog into the import pipeline (I2).
- The after-wave declaration set (I3).

## Test and qualification evidence

| Tier | I1a (#638) | I1b (this PR) |
|---|---|---|
| `tests/unit` | 4926 passed | see the PR body |
| `tests/integration -m "not qualification"` | 883 passed, 1 skipped | see the PR body |
| `tests/integration -m qualification` | 121 passed | see the PR body (I1b changes `app/sources/`, a qualification input) |

| Acceptance | Evidence |
|---|---|
| A1 | `tests/unit/test_v080_i1_eventcatalog.py`: byte-equal regeneration; digest change and unknown label stop before any write |
| A2 | the same module: the loaded catalog equals the hand-written parent §3.1 and I1 §5.2 tables |
| A3 | the same module: one parametrized case per rejection, with a canary that never appears in the problem |
| A4 | `tests/unit/test_asyncapi_adapter_pubsub.py` (guard proven by a revert) |
| A5, A8 | existing suites unchanged (#638) |
| A6 | `tests/integration/test_v080_i1_declarations.py` |
| A7 | `tests/integration/test_v080_i1_c1_replay.py` (qualification tier) |

## Remaining limitations

- The catalog is generated for the showcase. Its owners are illustrative, and its entries count as confirmed promises only by a disclosed assumption (parent §2).
- The Kafka declaration set has not been imported together with a Kafka capture yet; that happens in I3.
- The Kafka server `url` in the declarations is a placeholder.
