# v0.6.0 I4.2 execution

Governing method: [I4 revision 0.2](i4-deterministic-semantic-qualification.md), §§3–5 and §8.
Expectations remain those frozen in I4.1. This runbook introduces no semantic contract.

## Run

After the owner requests a commit containing the harness, use its full SHA from `git rev-parse
HEAD`. Run from a clean checkout of that commit:

```sh
uv run python -m evaluation.i4 --candidate-sha <40-hex-SHA> --out /tmp/i4-qualification
```

The output directory must be new. The coordinator passes the same explicit identity to two
separate pytest processes, each with its own session-scoped, digest-pinned Neo4j testcontainer.
Both workers verify HEAD, producer revision and the #410 ancestry. They execute every coverage
register anchor plus the oracle, bridge, adapter, independent-client, schema and legacy-evaluator
gates. Full repository regression runs separately, once, in the normal local gate.

Each worker writes `ledger.json` and complete canonical semantic JSON under `bytes/`. The
coordinator compares actual bytes, checks required case/surface inventories, and writes
`report.json` and the exact-SHA `ci-check-runs.json`. Failed/skipped required tests, absent evidence,
oracle failures, byte differences or incomplete CI produce `BLOCKED`, never a qualification pass.
The report is an I4.2 result, not all-I4 completion or release readiness.

For an **uncommitted development check only**, the pytest plugin accepts `--i4-development` along
with `--i4-candidate-sha`, `--i4-run` and `--i4-out`. Its ledger has
`qualification_eligible: false`; the comparator refuses to qualify it. This mode is unavailable
through the qualification coordinator.

## Frozen assertion mapping

`tests/integration/test_v060_i4_bridges.py` implements B01a/B01b and B02–B06. The I3 matcher remains
the oracle-only matcher for X/P cases. No matcher or ID substitution touches A/B bytes.

| Frozen I4 assertion | Executable observation |
|---|---|
| `positive` | Exact locality Workload UID and Operation assessment; `APPLICABLE`, reachable positive qualification, exact observation evidence IDs and selected capture revisions |
| `unresolved` | Candidate with the original v2 ID remains present, `UNRESOLVED`/`INAPPLICABLE`, no applicable pair or positive assessment uses it |
| `localities_exactly` | Exact set of `data.localities[].workload.uid` |
| `compare_only_in` | Exact Operation in the selected side's `only_in_first`/`only_in_second`, absent from the other side and `in_both` |
| `evidence_refs_resolve` | Evidence entries resolve; exact SCOPED_V2 IDs, forbidden IDs excluded; the requested Pod capture ref is independently read from its InfrastructureContribution |
| `refusal` | Null data and the frozen limitation code |
| `snapshot_differs_from_step` | Complete answer snapshot IDs differ between C1 and the C2 stale-snapshot request |
| `forbidden` | Case-specific checks of assessments, candidate/pair dispositions, provider-group refs, comparison memberships and closed answer fields; no generic substring-only substitute for an assertion |
| `snapshot_unchanged_except` | B02's legacy placement remains resolved, with the same canonical snapshot as the empty local answer |
| `equals` | B04 target scope is `UNKNOWN`; B06 has zero persisted v2 records and zero returned localities |
| `bytes_equal_to_step` | B05 baseline and post-offer answer bytes, including snapshot and lineage, are identical |
| `matches_frozen_pins` | The existing Quarkus `check_ready.check_answer` checks the legacy answer without changing its expectations |

B01 imports C1 and C2 over one stable configured source/root through real Kubernetes discovery
and authoritative import, and persists each Pod's own v2 through the existing production write
path. B02's unscoped CLIENT/SERVER pair and separate Pod identity observation go through
`POST /v1/traces` with scoped evidence enabled. B05 offers Markdown to filesystem discovery and
narrative content under a discoverable candidate filename to the importer, requiring no graph
change. B06 imports the frozen runtime dossier and operator overlay, replays the frozen OTLP
payload, and checks the existing legacy pins. B01–B05 are synthetic; the rehearsal is REHEARSAL,
not the I5 actual capture. I3's P08 predecessor-copy and X25 capture-clone disclosures still apply.

## Boundaries

The retained approved plan belongs in the initial PR description. Record local-gate results and
qualification results separately. Known debt #323 remains open; growth measurements and capacity
disposition belong to I4.3. I6 must rerun the mandatory qualification on its exact final candidate.
