# v0.6.0 I4.2 — Execution record

**Status: deterministic execution passed; CI disposition BLOCKED by unavailable Copilot review.**
Governing: [I4 accepted revision 0.2](i4-deterministic-semantic-qualification.md), §8 I4.2.
Exact tested candidate, captured from `git rev-parse HEAD` when recording evidence:
`37eebf2486c0c082ccfe4a6c6f704b4d05e68a6a`. This record does not declare I4 complete or release readiness.

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

## Qualification result

| Run | Process ID | Fresh Neo4j container ID | Recorded resets |
|---|---|---|---|
| A | 16773 | `62e7ba7c7809dea0b6056379e869c12f47be355f6d4cbbd4ae3909123f130ea0` | 76 |
| B | 19161 | `d6c1b28726e16526bc47f58c34c20beb6be6ebccc5f87784aa1f32cbdad22e04` | 76 |


| Check | Result |
|---|---|
| Fresh run A | 417 passed, no skips |
| Fresh run B | 417 passed, no skips |
| Required X/P/Q/B inventory | All 52 cases executed in both runs |
| Semantic artifacts | 600 per run; all oracle checks passed |
| Raw canonical A/B comparison | Zero differences; no normalization |
| Service / REST / negotiated MCP | Zero byte differences |
| Independent HTTP client | Query, evidence and reconnect agree |
| Local unit suite | 3,404 passed |
| Local integration suite | 802 passed, 1 existing demo smoke skip |
| Format, lint, types, import boundaries | Clean; 0 type errors; 8 boundaries kept |
| Exact-candidate CI | 19 checks succeeded; Copilot review failed with a service error |

The existing Quarkus Compose smoke test skipped because the owner’s `aip-qsh-demo` project
was already running. It was left alone. B06 independently executed the frozen replay and legacy
answer pins against disposable Neo4j; both mandatory qualification workers had no skips.
CI's actual demo end-to-end checks succeeded on the tested candidate.

Run IDs, distinct process/container identities, reset evidence, original dispositions,
per-case digests, pinned inputs/configuration and raw complete semantic bytes are retained in
[raw-evidence.tar.gz](../../release-validation/v0.6.0-i4.2/raw-evidence.tar.gz).
Archive SHA-256: `e690d1b5c80f3eaf6bb81bca92843800975d3027a29ed8e4df79b6a660e26c36`.
Extract it, then run `compare_runs(Path("aip-i4.2-qualification-37eebf2"))` from
`evaluation.i4.__main__` to independently repeat the semantic comparison.
The report’s original `/tmp` pointers identify the execution locations; their relative contents
are preserved beneath the archive’s top-level directory.

[Machine-readable report](../../release-validation/v0.6.0-i4.2/report.json) and
[exact-SHA CI check runs](../../release-validation/v0.6.0-i4.2/ci-check-runs.json) are tracked separately.
The archive preserves the original pre-publication report (HTTP 422) and its subsequent CI refresh;
refreshing CI did not alter or rerun semantic artifacts.

## Blockers and remaining work

The only outstanding check is `copilot-pull-request-reviewer`, ID `111486370096`:
[service-error review](https://github.com/michaelegner/architecture-intelligence-platform/pull/418#pullrequestreview-5407287355).
It produced no findings. All test, quality, demo and security checks passed. The report retains
`BLOCKED` pending disposition of this unavailable automated review; no failed check is presented
as successful. No semantic mismatch or unexecuted mandatory scenario was found.

This evidence-only follow-up records results for the candidate above; it does not claim its own
later commit was separately qualified. The CI completeness correction changes the harness after that candidate; the revised harness
will be qualified again on a new immutable SHA. Production code, frozen expectations and
configuration are unchanged.

Known debt #323 remains open as recorded by I2 F1/I3. Growth measurements, owner capacity
and product-impact disposition, and I5 handoff remain I4.3. The controlled capture remains I5.
I6 must rerun qualification on its exact final candidate.
