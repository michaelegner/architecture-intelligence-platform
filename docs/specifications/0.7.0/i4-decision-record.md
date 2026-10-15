# AIP v0.7.0 I4 — Decision Record (I4.1)

**Status:** frozen. I4.1a (#551), I4.1b (#552) and I4.1c (#553, `d3cea3a`) have merged; the decisions below are read-only inputs of the candidate (D9). Each settles an item the [I4 specification](i4-deterministic-real-system-and-product-value-qualification.md) revision 0.2 leaves to I4.1. None reopens a parent, I0–I3 or public-contract semantic.
**Governing:** I4 specification §§3–6, 8–10, 12–13; parent [`specification.md`](specification.md) §§22–26; [I0 source-selection decision](i0-source-selection-decision.md); [I0 acquisition/replay plan](i0-acquisition-replay-plan.md) §§4–5; the [coverage register](i4-coverage-register.md).
**Precedent:** the v0.6.0 I4 decision record and ledger design ([`../0.6.0/i4-decision-record.md`](../0.6.0/i4-decision-record.md), [`../0.6.0/i4-ledger-and-comparator-design.md`](../0.6.0/i4-ledger-and-comparator-design.md)).

## D1 — Candidate identity and CI (I4 spec §3)

| Item | Frozen decision |
|---|---|
| Candidate | One full 40-hex `I4_CANDIDATE_SHA`, a commit on `main` after I4.1a, I4.1b and I4.1c have merged. The checkout `HEAD` equals it and the worktree is clean (`git status --porcelain --untracked-files=all` empty). Being on `main`, the qualification tier ran on that commit. |
| Threaded identity | The sha is passed explicitly (`--candidate-sha`) and exported as `I4_CANDIDATE_SHA` and `AIP_BUILD_REVISION` to every worker. A worker, benchmark or replay refuses a mismatch with `HEAD` or with the other variable. |
| Required CI checks | Every one of these, `completed/success` on the **candidate** SHA, read through the check-runs API for that SHA (not `gh pr checks`): `quality`, `changes`, `integration-core (heavy)`, `integration-core (rest)`, `integration-qualification (heavy)`, `integration-qualification (oracle)`, `integration-qualification (other)`, `demo-e2e`, `lint + test`, `dependency security scan (pip-audit, spec §29)`, `static analysis (semgrep)`, `analyze (python)`, `analyze (actions)`. `CodeQL` is a workflow title, not an emitted check; both analysis jobs stay mandatory. A `skipped` required check blocks. |
| Qualification code | The qualification tooling, replay assets, register and vectors are part of the candidate identity (I4 spec §3). A change to any of them after a candidate is selected selects a new candidate and reruns every affected gate. |

## D2 — F1: page before enrich is deferred past the candidate (owner decision, 2026-10-15)

The I3 completion record's finding F1 (the projection builds and sorts the public form of the whole selection before it takes a page) stays **open and recorded**. I4 qualifies and measures the implementation I3 shipped. F1 does not land before I4.2. If it is ever implemented it is a new candidate, and every affected gate (the oracle, the parity checks, the cost rerun) reruns on it. The decision is the owner's and was taken at I4.1 planning; this record does not reopen it.

## D3 — Ledger vocabulary and what blocks (I4 spec §10)

The result vocabulary is the I4-only one of the specification (`I4_CORRECT`, `I4_EXPECTED_NEGATIVE`, `I4_SEMANTIC_DEFECT`, `I4_REPLAY_DEFECT`, `I4_SURFACE_MISMATCH`, `I4_MODEL_GAP`, `I4_PRODUCT_VALUE_FAIL`, `I4_NOT_RUN`) and never becomes public vocabulary.
- A row is `I4_EXPECTED_NEGATIVE` only when the answer equals the independently frozen expectation, limitation included. "Unresolved" without that match is `I4_SEMANTIC_DEFECT`.
- A mandatory `I4_NOT_RUN`, an unexplained mismatch, a skipped mandatory case or a changed expectation after execution blocks I4.
- The register's second table (positive and abstaining cases per class) is part of the ledger's denominators: a class with no executed positive case blocks.

## D4 — The APISIX replay package: real versus derived (I4 spec §5)

Pins: APISIX 3.19.0 `apache/apisix@sha256:9a7e45dc943fbf10ec916d1232bae4cda9302ae28a4696cfb83c2da01d261141`, etcd v3.5.16 `quay.io/coreos/etcd@sha256:d967d98a12dc220a1a290794711dba7eba04b8ce465e12b02383d1bfbb33e159`, upstream `traefik/whoami@sha256:43a68d10b9dfcfc3ffbfe4dd42100dc9aeaf29b3a5636c856337a5940f1b4f1c`, fake credentials only. The package lives under `i4-replay/` (I4.1c). Expected readings are fixed here, before any capture, from the replay plan §5 table and the frozen I2 and I3 vocabulary.

| Case | Origin | Configuration → measurement | Expected reading |
|---|---|---|---|
| `P1` | real capture | consumer C allow-listed on Route R; upstream series for (R, C) | configured access established; `OBSERVED_USAGE`, upstream count equal to the traffic the capture README records |
| `P2` | real capture if the capture procedure can assert closed coverage, else derived (the README records why) | C allow-listed on R; no series; coverage attested | configured access established; `MEASURED_ZERO` under `SUFFICIENT_FOR_ZERO`. Metric absence alone is never zero |
| `N1` | real capture | C allow-listed on R; the Prometheus plugin disabled for R | configured access established; `USAGE_UNESTABLISHED`, `UNKNOWN_COVERAGE`, `GWM_ROUTE_PROMETHEUS_DISABLED` |
| `N2` | real capture | C not allow-listed on R; a rejected `403` from the gateway | no configured access fact; rejected-attempt count only; no usage |
| `N3` | real capture | any; a series with `consumer=""` | no consumer row; the Route carries `GWM_UNATTRIBUTED_UPSTREAM` |
| `N4` | real capture | C allow-listed on R; a series for C on another Route R2 | usage on R2 only; none attributed to R |
| `OBS` | real capture | C' not allow-listed on R; an upstream series for (R, C') | `NO_MATCHING_CONFIGURED_ACCESS_FACT` with `OBSERVED_USAGE`; not a policy finding |
| `R1`→`R2` | two real captures | R2: a consumer removed from an allow-list, a Route removed, a Route added | the second import's snapshot reflects only R2; a cursor and a ref minted under R1 are `SNAPSHOT_NOT_AVAILABLE`; a repeat of R2 is a no-op |
| `W-INVALID` | **derived**, mutation fixed here | the real `P1` manifest with `end_settled` set to `false` | window reasons `[GWM_WINDOW_NOT_SETTLED]`; rows keep their identities and carry no counts; `WINDOW_NOT_VALID` |
| `W-NONE` | request-level | a request for a window that was never imported | `MEASUREMENT_WINDOW_NOT_AVAILABLE`, `data` null |

**Case ids and the first-attempt note (I4.1c).** The replay cases are `P1`, `P2`, `N1`, `N2`, `N3`, `N4`, `N4b`, `OBS`, `REVa`, `REVb`, `REVc`, `W-INVALID` and `W-NONE` (frozen in `i4-replay/expected-replay.json`), plus the structural `EV`, `REVd` and `REVe` (an evidence request, and a cursor and a reference minted under R1 and refused after R2). `N4b` is the other half of `N4`: the usage belongs to the Route it happened on. `R1`→`R2` is `REVa`–`REVe`. The first capture attempt was discarded because readiness probes created series outside the plan; the readings were not changed (`i4-replay/README.md`).

`B07` is not a replay case: it is the synthetic exact-handoff-state bridge vector of the register (S22-07).

## D5 — B07 is frozen here (I4 spec §4.1 row 7, §13)

`B07a`, `B07b` and `B07c` in [`i4-vectors/expected-i4.json`](i4-vectors/expected-i4.json) are authored by hand before any I4 execution, from the K06/K08 shape: a Route with no explicit mapping whose exact path and method are exposed by two Operations of two contracts. No test of the I4.1a freeze projected them. The I4.1b runner smoke (`tests/integration/test_v070_i4_runner.py`, development mode, never eligible to qualify) executes them as part of exercising the tooling; they matched the hand-authored expectation unchanged, and the expectation was not edited by it. The first *qualifying* projection is the I4.2 runner on the candidate. A disagreement is a defect or a reviewed specification question; the expectation is never edited to fit a run.

## D6 — Tyk dossier structure (I4 spec §6)

The I4.3 dossier is `docs/specifications/0.7.0/i4-tyk-dossier.md`, built only from the real Tyk 5.13.0 spike assets under [`i0-spike/tyk/`](i0-spike/tyk/) and the I0 spike findings. Its sections are frozen:
1. Native configured-access relationship (key `access_rights`) and how it differs from APISIX `consumer-restriction`.
2. Identity distinctions: key, alias, application, policy; which are stable and which are secret.
3. **F6**: two distinct keys with the same alias merge into one request series (series 3 → 4), so the alias alone cannot license one resolved canonical consumer. Parent §22 item 6 is qualified here and nowhere else (register S22-06, `DOSSIER_ONLY`).
4. Request attribution (the custom `api_metrics` instrument) and its label set.
5. Environment, window and coverage semantics, and what must be operator-asserted.
6. Concepts that do not map cleanly to APISIX consumer restriction.
7. The frozen AIP vocabulary term by term: represented, represented with a source-specific distinction kept explicit and unnormalized, or a gap.
8. The outcome: `REPRESENTABLE`, `REPRESENTABLE_WITH_SOURCE_SPECIFIC_DISTINCTION` or `MODEL_GAP`, with the parent §24 reading. Unlike native concepts are never renamed into one generic "subscription".

## D7 — Pilot method (I4 spec §9)

- One recorded coding-agent session, run by the owner, against the pinned APISIX replay world of D4, using only the public Architecture Intelligence surface. The record names the agent or client and the model and version; the agent consumes AIP and is never semantic authority. The disposition therefore rests on a single session, which the record states.
- The task: an agent is about to change an API Operation and asks which configured consumers are related to that exposure, which have independently observed usage in the selected completed window, and what remains unresolved.
- Measures, all recorded: useful answer coverage; setup effort; source synchronization effort; consumer attribution effort; identity mapping effort; unresolved and ambiguous rate; manual input required; time and cost to keep evidence current, measured over at least two synchronization cycles (the initial pinned capture and import, then one controlled APISIX revision and measurement refresh, `R1` → `R2`); and whether the answer materially improves the coding-agent decision.
- Semantic correctness and product usefulness are judged separately. The session ends in exactly one owner-reviewed disposition: `CONTINUE`, `NARROW`, `DEFER` or `STOP`.
- The pilot executes only after the candidate qualification has passed (I4.3).

## D8 — Qualification tooling is generalized by profile (I4 spec §3)

`evaluation/i4` is v0.6-specific. I4.1b introduces a per-release profile mechanism: the `v0.6` profile holds today's constants and worker-test list verbatim and stays the default, so the v0.6 I4 record remains reproducible; the `v0.7` profile adds the API-usage register, required cases and runner. The cost artifact on the candidate runs through the I4 identity machinery (D1); `benchmarks/api_usage_cost.py` alone is not an I4 artifact. The design is reviewed in I4.1b.

## D9 — Freeze rule

After I4.1c merges, the register, the decision record, `i4-vectors/`, `i4-replay/` and `evaluation/i4` are read-only inputs of the candidate. Anything that must change afterwards is a reviewed change followed by a new candidate and a rerun of the affected gates, never an edit of a result ledger or of an expectation after an AIP run.

## Needs a reviewed amendment if it changes

D1 (the required checks and the exact-SHA rules), D2, D3, D4's expected readings and its real or derived classification, D5, D6's sections, D7, D9, and the I4 specification's §13 stop conditions.
