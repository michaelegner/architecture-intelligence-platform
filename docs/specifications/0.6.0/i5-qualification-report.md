# I5.2 qualification report

Governing specification: [I5 revision 0.1](i5-real-system-qualification-and-product-demonstration.md), §§4–5 and §8 I5.2; accepted parent specification and I1 E1–E7. **Controlled-reference qualification: CORRECT.** No production code or public/default behavior changed.

## Identity and retained evidence

- Independently adopted oracle commit: `e48cae8f9842bd197061ba1b2c38ccd78f67b608`. Michael adopted the source-derived expectations before this commit and before actual-capture evaluation.
- Qualified candidate: `3c10560620164d6ba589c68546ee4ce3fdb79255`. Both production images and all answers thread this exact SHA.
- Original 42 acquisition files remain checksum-identical. Oracle SHA-256: `9bca35f18b20b596b4696c69922742fbf6aff856a2e45bc92824051ceda4a7fd`.
- [Raw archive](i5-qualification-artifacts/actual-capture.tar.gz) contains A/B requests, service/REST/MCP canonical bytes, raw HTTP responses, snapshot state, import reports, configuration and image digests, process/container identities, command logs, wire accounting and validation logs/JUnit. [Archive checksum](i5-qualification-artifacts/SHA256SUMS): `257fa8a1240838e8a250ce669b59e270459131379a99b4b5ad59d91d6aeb9ff6`.
- Workers 7217 and 8126 used distinct fresh Neo4j/AIP/Collector projects; both recorded zero initial graph nodes. Pinned images, actual image IDs and configuration hashes are in each ledger. Each replayed all 52 original requests once, in order, with 52 Collector HTTP 200 and 52 AIP HTTP 200 responses. C2 replaced bytes at the same configured source/root without a second replay.

The later merge from main adds unrelated documentation only; record/archive commits do not establish a new qualified executable SHA. I6 must rerun I4/I5 against its final candidate.

## Results and finding ledger

| Requirement | Evidence and disposition |
| --- | --- |
| C1 supported positives | Both Workloads enumerated completely. W1→pricing `APPLICABLE`/`CONFIRMED`; W2→legacy-pricing `APPLICABLE`/`OBSERVED_ONLY`. Exact source-derived ownership, evidence IDs and capture references checked. CORRECT. |
| C2 replacement | Retained P1 becomes `UNRESOLVED`/`LOCALITY_CAPTURE_MISSING_POD`; P2 remains eligible. No reassignment; changed snapshot; C1-bound query, evidence and cursor refused. CORRECT. |
| Honest bounds | Target locality `UNKNOWN`, local coverage unavailable, no invented absence claims. Unauthorized, wrong-caller and wrong-Operation references refused; wrong environment has no supported positive. CORRECT. |
| Coexistence | Source-derived counts 359 and 508 retained in v1/v2, unchanged through replacement. No duplicated replay or fabricated attribution. CORRECT. |
| Public adapters and determinism | 17 cases per run, service/REST/negotiated MCP agreement; all 70 required canonical artifacts byte-identical A/B. Only transport wrappers removed; no field masking or identifier normalization. CORRECT. |
| Pagination | Actual two-candidate inventory complete, no continuation. Stale cursor is a protocol-generated negative control; cap/continuation/refusal coverage comes from existing frozen synthetic regressions. These are not actual capture positives. |
| Startup retry | One retained attempt failed before import/ingestion because Docker Desktop refused a host port. Fresh-port retry of the same candidate passed A/B. Environment failure; no oracle change. |

No oracle disagreements, reference leaks, adapter drift or nondeterminism remain. Earlier plumbing attempts and the first partially completed run lost their temporary artifacts during an environment reset; they are not claimed as auditable qualification. The successful rerun and retained startup failure are archived.

## Validation and compatibility bounds

Required local gate ran in order: `uv run ruff format .`, `uv run ruff check .`, `uv run pyright`, `uv run lint-imports`, `uv run pytest tests/unit`, `uv run pytest tests/integration`. Explicit Ruff checks also cover `evaluation/i5` and the source-only helper. Results: **3,485 unit tests passed; 803 integration tests passed, 1 skipped**. The existing Quarkus demo smoke skipped because `aip-qsh-demo` already existed; its live Compose smoke is not claimed here. Ruff and Pyright passed; eight import contracts passed. Archived logs/JUnit retain the exact results and skip reason.

Existing frozen Quarkus/Airflow source-dossier checks, two-pass architecture-answer scenarios, no-v2 snapshot compatibility and pagination regressions are reused from the required suites on the qualified implementation. The bundled evaluator's upstream scenarios are v0.3-derived compatibility evidence, not a fresh full v0.5 upstream acquisition/dossier. New per-system upstream dossiers and the user walkthrough remain I5.3 work. Required PR CI results are retained in the PR once available.

## Reconciliation against retained plan

**Completed as planned:** owner-adopted oracle frozen first; original inputs verified; two fresh-process staged runs; independent HTTP client, three-adapter parity, exact canonical comparison, source-derived lineage/count checks and raw evidence retention. Two small guard tests reject unadopted expectations and modified input bytes.

**Deviations and justification:** qualification plumbing needed mounted-input, import-report and production-image HTTP-client fixes; the client uses stdlib HTTP already available in the unchanged image. An environment reset required a full auditable rerun and persistent scratch storage. No semantic expectations were changed. Existing compatibility suites are reused rather than reacquiring upstream systems; full upstream dossiers belong to I5.3.

**Specification questions discovered:** none requiring a new semantic decision. Frozen I3 contracts determine comparison statuses and refusal behavior.

**Deferred work and limitations:** I5.3 upstream dossiers/walkthrough; I5.4 pilot and closure; #323; I6 final-candidate rerun. This establishes bounded qualification, not production capacity or release readiness. Accepted I4 measured-cost/retained-state limitations remain in force.
