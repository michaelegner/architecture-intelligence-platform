# v0.6.0 I4.2 — Execution record

**Status: implementation prepared; deterministic qualification BLOCKED pending an immutable harness candidate.**
Governing: [I4 accepted revision 0.2](i4-deterministic-semantic-qualification.md), §8 I4.2.
This is a local implementation/validation record, not an I4-qualified SHA or I4 completion.

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

## Local validation

Checkout base (captured with `git rev-parse HEAD` when writing this record): `c283031673ac2d4f1beec85d966b765a25ddf379`.
This commit does **not** contain the uncommitted I4.2 harness and is **not** its qualification candidate.

| Check | Result |
|---|---|
| Ruff format and check | Clean |
| Pyright | 0 errors, 0 warnings |
| Import boundaries | 8 kept, 0 broken |
| Full unit suite | 3,403 passed |
| Full integration suite, with development recorder | 802 passed, 1 skipped |
| Comparator checks after final completeness correction | 10 passed |
| Narrow recorder checks after pin/config/producer corrections | 5 passed |

The integration skip was the existing Quarkus Compose smoke test: `aip-qsh-demo` was already
running and was left alone. B06 independently executed its frozen replay and legacy answer pins
against the disposable integration Neo4j container. This does not turn the skipped Compose test
into a pass.

Local artifact pointers (uncommitted implementation evidence):
- `/tmp/aip-i4.2-local-gate/ledger.json`: 600 semantic artifacts; all 52 required X/P/Q/B case IDs
  present, zero recorded oracle failures and zero within-run surface differences, including three
  real-HTTP independent-client query/evidence/reconnect artifacts.
- `/tmp/aip-i4.2-final-recording-verification/ledger.json`: final producer version/SHA checks,
  ingestion flags and distinct retained C1/C2 generated inputs. Its five tests passed.

Both ledgers explicitly have `qualification_eligible: false`. The full suites preceded the last
recorder metadata/producer corrections; focused checks verified those corrections without
repeating unrelated regression work. No qualifying A/B comparison has been executed.

## Blockers and remaining work

1. The owner must request the harness commit before a candidate SHA containing it exists
   (`AGENTS.md`: do not commit unless the owner asks).
2. Run the coordinator on that clean, immutable SHA, with fresh A/B processes and containers;
   record actual raw-byte differences or zero differences. Retrieve and disposition its exact-SHA CI.
3. Publish the resulting report/artifacts and reconcile the actual qualification outcome.

Known debt #323 remains open as recorded by I2 F1/I3; I4 does not claim to correct it. Growth
measurements and owner capacity disposition remain I4.3. The actual controlled capture remains
I5, and I6 must rerun qualification on its exact final candidate.
