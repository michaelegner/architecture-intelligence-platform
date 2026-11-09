# GT 0.8.0 tooling (I2)

**Increment 2** of the [GT 0.8.0 specification](../specification.md) provides neutral GT 1.1.657 tooling for a promise-first investigation, and an empty, executable investigation page. It contains no worked investigation.

**The I2 done-when is not yet met.** It requires that a person unfamiliar with Sokol111 tells the stages apart and records a revised conclusion. The GT participants in I3 assess it. The owner's smoke gate in the [runbook](RUNBOOK.md) checks only that the tooling works.

**GT baseline:** `GlamorousToolkit-Windows-x86_64-v1.1.657.zip`, sha256 `19ae8ba3edd80a786a56d44d35f52b7d4796312da676d1104fcef7b4fecfd4da`, which equals the release's `.sha256` asset. It pins gt4llm `v0.7.341`, gtoolkit-phlow `v0.9.207` and lepiter `v0.7.430`.

## Smoke gate (owner, 2026-11-09)

Run in GT 1.1.657 on Windows, from the runbook:

| Check | Result |
|---|---|
| Connectivity to the hosted endpoint, packages load, contracts view | pass |
| Investigation page created, its snippets run, and it is kept after save and restart | pass |
| No AIP classes in an image without the AIP package | waived by the owner |
| Re-smoke after the review fixes: first impression before the snippets, `DEMO-CONTRACT-001` / `external contract`, `session` drill-down, log with query and evidence calls on the frozen snapshot | pass |
| Binding picture with 9 rows, evidence drill-down, snapshot mismatch error, log export | pass |
| Lepiter storage | `Documents\lepiter\default`, outside the image; isolation steps added to the runbook |

## Materials per condition

| Material | GT | GT + AIP |
|---|---|---|
| Participant corpus built by [`materialize_corpus.py`](materialize_corpus.py) `--gt` | yes | yes |
| [`AIP-GT-Promises.st`](AIP-GT-Promises.st): contracts, task, investigation page | yes | yes |
| [`AIP-GT-Promises-AIP.st`](AIP-GT-Promises-AIP.st): hosted binding picture and evidence | no | yes |

[`contracts.json`](contracts.json) is a GT-only structured rendering of the four YAML contracts. `materialize_corpus.py --check` confirms that it equals the frozen YAML. The frozen files stay authoritative, and GT shows each one in a Raw view. The corpus follows [`i1-freeze/participant/MANIFEST.md`](../i1-freeze/participant/MANIFEST.md); `i1-freeze/` is unchanged.

## Neutrality

- The Contracts view is a flat list of the five contracts, ordered by file path. Every field has equal weight. There is no graph, route or comparison view.
- Evidence links open the pinned file in the local corpus. A link outside the corpus shows "not in corpus". GT does not open a browser.
- The investigation page holds the task text and the five "Your answer" items of `task.md`, and nothing else. The first item (first impression) comes before the snippets that open contracts or AIP.
- The AIP views show every binding-picture row with all of its fields and refs per role. Evidence drill-down works on any row. It fetches all refs in batches of at most 20.

## Limits

- GT checks the snapshot ID of every AIP answer. The canonical answer digest is checked outside GT, as in the [I1 freeze record](../i1-freeze/README.md).
- `GtAipHostedClient` asks only the frozen `get_binding_picture` scope (Catalog Management, local broker). The agent + AIP condition can use all seven read-only tools and any scope. The researcher chose this fixed GT view, and GT participants cannot change it.
- `GtAipHostedClient session` is the one client per image. Its `exportLogTo:` records every MCP message sent through it, as parsed objects. The log is not byte evidence. Calls through another client instance are not in it.
- In I3, humans operate GT and agents operate the other two conditions. Comparisons across operator types are therefore exploratory. GT vs GT + AIP and agent vs agent + AIP are the attribution pairs.
