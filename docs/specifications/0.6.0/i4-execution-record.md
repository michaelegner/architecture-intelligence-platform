# v0.6.0 I4.2 — Execution record

**Status: I4.2 execution PASS.** Governing: [I4 accepted revision 0.2](i4-deterministic-semantic-qualification.md), §8 I4.2.
Exact tested candidate, captured from `git rev-parse HEAD` when recording this evidence:
`4237734d22af3818f9cb8c1c70ace68f8e44de8f`. This does not declare I4 complete or release readiness.

## Implementation and reconciliation

The approved plan is retained verbatim in the prepared PR description. Completed as planned:
B01a/B01b and B02–B06 execution, Q01–Q08 actual adapter rejection, a thin two-process runner,
complete canonical semantic artifacts, raw-byte comparison, explicit candidate/producer checks,
per-state source input retention and digests, exact-SHA CI retrieval, and reuse of existing
oracle/property, adapter, independent-client and legacy evaluators. Production code, frozen
expectations, public schemas and defaults are unchanged.

No semantic specification question or scope deviation was found. Harness corrections during
local development included sorted resolved refs, mapping/context wiring, frozen assertion-key
interpretation and ledger datetime serialization. Qualification producer versions now use
`package_version()` rather than the I3 test placeholder; oracle symbols remain oracle-only.
A development-only recording option permits testing an uncommitted harness and is explicitly
ineligible for qualification. No benchmark/capacity or I5 handoff work was included.

The owner’s review found two material gaps: durable publication of actual execution evidence
and acceptance of an incomplete CI inventory. Both are addressed. The CI validator now requires
all named jobs in the current CI/CodeQL workflows, successful mandatory conclusions and exact
candidate identity. Missing/skipped/neutral jobs, wrong identity and failed duplicates are checked.
The complete mandatory A/B qualification was rerun on the revised harness candidate above;
frozen expectations, production behavior and public schemas were unchanged.

## Qualification result

| Run ID | Process ID | Fresh Neo4j container ID | Recorded resets | Semantic artifacts |
|---|---|---|---|---|
| 4237734/A | 26781 | `46ca3dbbebbb3f4ed3cca78012cdc0bc87429feda9f6a2dad2069cd3f811c438` | 76 | 600 |
| 4237734/B | 30926 | `83751d6b605de10e29c730c717994f6ca82e54ba1153e8e11734af1b2e9f8532` | 76 | 600 |

| Check | Result |
|---|---|
| Fresh run A | 417 passed, no skips |
| Fresh run B | 417 passed, no skips |
| Required X/P/Q/B inventory | All 52 required cases in both runs |
| Independent oracle checks | Zero failures |
| Raw canonical A/B comparison | Zero differences; no normalization |
| Service / REST / negotiated MCP | Zero byte differences |
| Independent HTTP client | Query, evidence and reconnect agree |
| Local unit suite | 3,474 passed |
| Local integration suite | 802 passed, 1 existing demo smoke skip |
| Format, lint, types, import boundaries | Clean; 0 type errors; 8 boundaries kept |
| Exact-candidate CI | All 19 recorded checks succeeded; all 11 required names present |

The existing Quarkus Compose smoke test skipped because the owner’s `aip-qsh-demo` project
was already running. It was left alone. B06 independently executed the frozen replay and legacy
answer pins against disposable Neo4j. Both mandatory qualification workers had no skips;
the exact-candidate CI demo end-to-end checks succeeded.

## Auditable artifacts

[Machine-readable report](../../release-validation/v0.6.0-i4.2/report.json) records PASS,
zero mismatches and the full required CI inventory.
[Exact-SHA CI check runs](../../release-validation/v0.6.0-i4.2/ci-check-runs.json) retains each
actual check ID, candidate identity, conclusion and details URL.
[Full raw evidence bundle](../../release-validation/v0.6.0-i4.2/raw-evidence-4237734.tar.gz) retains both ledgers,
complete semantic artifacts, original dispositions, digests, source/configuration pins, inputs,
reset evidence and pytest logs.
Archive SHA-256: `e214be092afe961c01648cb916118e1a859a0f6d0ca53f615bbd1c7dc515bf3d`.

Extract the bundle, then call `compare_runs(Path("aip-i4.2-qualification-4237734"))` from
`evaluation.i4.__main__` to repeat the semantic comparison independently. The report’s original
`/tmp` pointers identify execution locations; relative contents are retained beneath the archive’s
top-level directory. The initial coordinator report records incomplete CI and is retained as
`report-before-ci-refresh.json` inside the bundle. CI was refreshed through the same corrected
validator after jobs completed; no semantic artifacts changed and no semantic rerun was needed.

## Earlier execution and remaining limitations

The earlier `37eebf2` run is retained separately in
[its raw bundle](../../release-validation/v0.6.0-i4.2/raw-evidence.tar.gz),
[its report](../../release-validation/v0.6.0-i4.2/report-37eebf2.json) and
[its CI checks](../../release-validation/v0.6.0-i4.2/ci-check-runs-37eebf2.json).
Its report remains BLOCKED for the failed Copilot service review; that failure is not reclassified
as success or attributed to the revised candidate. It used the earlier incomplete CI validator,
so the current qualification claim relies on the revised candidate and its complete new runs.

This evidence-only follow-up records results for the tested candidate above. Its own later commit
is not claimed as separately A/B-qualified. Qualification code, production code, expectations,
schemas and configuration are unchanged after that tested candidate.

No semantic specification ambiguity, mismatch or unexecuted mandatory case remains in I4.2.
Known debt #323 remains open as recorded by I2 F1/I3. Growth measurements, owner capacity and
product-impact disposition, and I5 handoff remain I4.3. The controlled capture remains I5.
I6 must rerun qualification on its exact final candidate.
