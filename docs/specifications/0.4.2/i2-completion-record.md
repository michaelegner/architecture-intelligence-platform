# I2 Completion Record — Client-Ready Demo and Documentation

Auditable completion record for `v0.4.2` I2, required by
[`i2-client-ready-demo-and-documentation.md`](i2-client-ready-demo-and-documentation.md) §63. This
record captures verification performed against the candidate commit below, plus this record's own
sub-PR (I2.3), which closed the gaps that verification found.

## Run identity

- **Candidate commit verified against:** `d5c6320` (branch `v0.4.2-i2.3-clean`, tip before this
  record's own commit) — includes I2.1, I2.2, and I2.3's own test/doc fixes.
- **I1 dependency (Dual-Mode MCP Transport):** merged to `main` as `2b6f865` (PR #135).
- **I2.1 (Client-Ready Demo — `--serve` mode and fixture-state oracle):** merged to `main` as
  `0447d88` (PR #136).
- **I2.2 (Candidate Client Setup Guides and Onboarding Docs):** merged to `main` as `c409ba6`
  (PR #137) — review round fixed one real factual error (Codex CLI's `--url` flag, wrongly
  described as an invented/undocumented third-party flag) and one real scope-semantics gap (the
  project-scoped Codex alternative is not reachable from an arbitrary directory the way the global
  CLI-added server is), both confirmed against official docs and the installed `codex-cli 0.154.0`
  binary before fixing.
- **I2.3 (this record) — completion record and final documentation-coherence/DoD verification:**
  found and closed two real gaps beyond documentation wording (below), rather than only recording a
  passing checklist.

## I2.3 findings and fixes

I2.3's own job (per PR #137's stated scope) was the completion record plus final
documentation-coherence/DoD verification across the whole I2 spec — not a rubber stamp. Two real
gaps against the spec's "SHALL" requirements were found and fixed before this record was written:

1. **Missing committed, automated shell/e2e coverage for `mcp-demo.sh` itself (spec §42-45/§44.1).**
   `tests/unit/test_check_fixture_state.py` and
   `tests/integration/test_check_fixture_state_classification.py` already covered
   `check_fixture_state.py`'s classification logic in isolation, but nothing automated the shell
   script's own orchestration — argument parsing, the EMPTY/COMPLETE branch actually taken, or the
   promise that `--serve` never issues a scripted MCP call — against the real
   `docker-compose.demo.yml` stack. Manual verification (this session, and PR #136's own
   description) is evidence of one run, not committed, repeatable coverage. Fixed by adding
   `tests/integration/test_mcp_demo_script.py` (6 tests, detailed below).
2. **`docs/mcp.md` never stated the local/trusted-network security boundary (spec §40/§60).** The
   root README and `examples/mcp-clients/README.md` both already had it; `docs/mcp.md` — which §60's
   own DoD checklist separately requires to state it — did not. Fixed with a short "Local security
   boundary" section.

## Demo

| Item | Result |
|---|---|
| Fixture manifest path | `examples/runtime-demo/fixture-state.json` (sha256 `887b8117...b3c0c`) |
| Fixture checker path | `examples/runtime-demo/check_fixture_state.py` |
| Fixture checker command | `"${COMPOSE[@]}" exec -T architecture-intelligence python examples/runtime-demo/check_fixture_state.py --json` |
| Host Python required | false — verified by never invoking the checker outside `docker compose exec` in either `mcp-demo.sh` or the new test module |
| Expected `snapshot_id` | `aip:snapshot:v1:685a34157b6842b00d7130b8490df63060c3d80871c2ed6f56cd9206e62342d8` |
| `EMPTY` strict-zero classifier | PASS — `test_empty_requires_zero_whole_database_counts` (unit), `test_empty_on_a_clean_database` (integration), live-verified against a `down -v` stack |
| `COMPLETE` exact-manifest classifier | PASS — `test_complete_matches_an_identical_state` (unit), `test_complete_matches_a_freshly_captured_state` (integration), live-verified |
| Polluted-state rejection | PASS — `test_partial_from_an_unrelated_node[_with_no_revision_singleton]`, `test_node_count_mismatch_from_a_stray_node`, `test_unexpected_graph_data_from_an_extra_service` |
| Double-seeded-state rejection | PASS — `test_partial_from_duplicated_telemetry`, plus the `observation_count`/`first_seen`/`last_seen`/`sample_trace_ids` mismatch cases in `test_evidence_field_mismatches_use_specific_codes` |
| `--serve` from `EMPTY` | PASS — live run + `TestServeLifecycle.test_full_lifecycle` |
| `COMPLETE` fixture reuse / no reseed | PASS — same test; second run's stdout contains neither "Importing the declared architecture" nor "Seeding frozen runtime evidence" |
| `PARTIAL_OR_INCOMPATIBLE` rejection | PASS — `test_partial_from_a_missing_observed_relation`, `test_declared_relation_mismatch_when_a_declared_relation_disappears`, `test_observed_relation_mismatch_when_an_observed_relation_disappears`, `test_evidence_mismatch_for_a_missing_evidence_record`, `test_drift_claim_mismatch_when_the_claim_set_differs` |
| No-arg regression (existing hero demo) | PASS — live run: full `tools/list` → `get_architecture_drift` → `get_evidence` walkthrough completes, same `snapshot_id` as the `--serve` runs |
| `--down` | PASS — live run + `TestServeLifecycle.test_full_lifecycle`'s teardown step |
| Teardown-failure path | PASS — `TestTeardownFailure` (compose file temporarily unavailable → exit non-zero, non-empty actionable stderr) + live-verified manually |
| Repeated-`--serve` | PASS — `TestServeLifecycle.test_full_lifecycle` |
| Second-run telemetry submissions | 0 — observed-relation count identical (6 → 6) between runs; second run's stdout never reaches the seeding step |
| Second-run fixture mutations | 0 — second run's own container logs contain zero `POST /api/import` calls |
| Snapshot equality result | `snapshot_after_run_1 == snapshot_after_run_2 == aip:snapshot:v1:685a3415...` |
| No-scripted-MCP assertion | PASS — proven from the AIP container's own uvicorn access log (a "deterministic server request audit" per spec §43): zero `POST /mcp` lines after either `--serve` run |

Discovered incidentally (not a blocker, but worth recording): `docker compose up -d --build`
recreates the `architecture-intelligence` container on every `--serve` invocation even with no
source changes, because a rebuilt image still gets a new image id. This is harmless to fixture
correctness — Neo4j is the only stateful service in this flow and is never recreated by `--serve` —
but it does mean the container's own log history resets each run, which is why the e2e test asserts
against each run's own logs in isolation rather than comparing before/after counts across a possible
restart.

## Prepared state

| Item | Result |
|---|---|
| `LegacyPricingService` `OBSERVED_ONLY` via `GET /pricing/{sku}` | PASS |
| `unused-q` `NOT_OBSERVED_IN_WINDOW` | PASS |
| Observation window | PASS — `2026-08-26T00:00:00.000000Z` / `2026-08-27T00:00:00.000000Z` everywhere the machine-facing window is printed (script output, `docs/mcp.md`, `seed_frozen_evidence.py`); the human-facing stable prompt (README, client README, all four guides) uses the equivalent shorter `2026-08-26T00:00:00Z` / `2026-08-27T00:00:00Z` form — the same instant, confirmed by issuing the shorter form directly against a live `get_architecture_drift` call and getting an identical result. Not a documentation defect: spec §29 itself specifies the stable prompt in the shorter form. |

## Documentation

| Item | Result |
|---|---|
| Root README | PASS — "Connect AIP to Your Coding Agent" section present with `--serve`, endpoint, Codex/Claude Code examples, collapsed Cursor/VS Code, stable prompt, both findings, local/trusted-network + hosted-agent caveats, link to `examples/mcp-clients/` |
| `docs/mcp.md` | PASS (after I2.3's "Local security boundary" addition) — direct/negotiated modes, stateless HTTP method contract, exactly three tools, local security boundary all explicit |
| Client README (`examples/mcp-clients/README.md`) | PASS — prerequisite, start command, endpoint, links to all four guides, stable prompt, both deterministic findings, local/trusted-network + hosted-agent caveats, syntax-vs-qualification distinction, teardown command |

## Documentation coherence (spec §48)

Cross-checked MCP endpoint, service id, environment, observation window, tool count/names, teardown
command, and local/trusted-network caveat across `mcp-demo.sh`, root README, client README, all four
client guides, and `docs/mcp.md`. Result: **PASS**, no mismatches — `http://localhost:8000/mcp`,
`service:order-service`, `demo`, the frozen window (in the two equivalent forms noted above), exactly
`get_architecture_drift`/`get_evidence`/`get_service_dependencies`, and
`examples/runtime-demo/mcp-demo.sh --down` are identical everywhere they appear.

## Client syntax verification

| Client | Official source | Verification date | Version observed | Result |
|---|---|---|---|---|
| Codex CLI | <https://learn.chatgpt.com/docs/extend/mcp?surface=cli> | 2026-09-12 | `codex-cli 0.154.0` (installed locally; `codex mcp add/list/remove` run end to end) | PASS |
| Claude Code | <https://code.claude.com/docs/en/mcp> | 2026-09-12 | Claude Code `2.1.269` (installed locally; `claude mcp add/list/get/remove` run end to end) | PASS |
| Cursor | <https://cursor.com/docs/mcp> | 2026-09-12 | Not locally installable in this environment — re-verified by re-fetching the official page during I2.3; `url`-only remote-server schema (no `type` field) and the `.cursor/mcp.json` (project) / `~/.cursor/mcp.json` (global) locations confirmed against current page content | PASS |
| VS Code | <https://code.visualstudio.com/docs/agent-customization/mcp-servers>, <https://code.visualstudio.com/docs/agents/reference/mcp-configuration> | 2026-09-12 | Not locally installable in this environment — re-verified by re-fetching both official pages during I2.3; `servers` top-level key (not `mcpServers`), required `"type": "http"`, workspace `.vscode/mcp.json`, and the "MCP: Open User Configuration" command all confirmed against current page content | PASS |

Codex CLI and Claude Code were additionally verified functionally (not just textually) by running
the documented `add`/`list`/`remove` (Codex) and `add`/`list`/`get`/`remove` (Claude Code) commands
against the installed CLI binaries in this environment. Cursor and VS Code have no locally
installable CLI to exercise the same way in this environment; their verification is syntax-only,
consistent with spec §23's "checked against the official stable documentation" standard (not I3's
actual-client interoperability qualification).

Actual-client interoperability qualification: **PENDING I3.**

## Link validation

PASS. All relative links in the touched/added Markdown files (`README.md`, `docs/mcp.md`,
`examples/mcp-clients/{README,codex,claude-code,cursor,vscode}.md`) resolve to real repository paths.
The only non-resolving pattern found (`../../discussions` in the README) is a pre-existing,
intentionally GitHub-relative link outside I2's scope, already noted in PR #137's own test plan.

## Security / hygiene

| Item | Result |
|---|---|
| No secrets in client examples | PASS — scanned for API keys/tokens/passwords/secrets/bearer values; only documented placeholders and "no auth required" statements found |
| No active client config accidentally committed | PASS — no `.cursor/mcp.json`, `.vscode/mcp.json`, or `/.mcp.json` in the repository |
| No OS metadata artifacts committed | PASS — `git ls-files` contains zero `*:Zone.Identifier`/`.DS_Store`/`Thumbs.db` entries (some exist as untracked local WSL cruft elsewhere in the working tree, none under `examples/mcp-clients/` or `examples/runtime-demo/`, and none tracked by git anywhere) |

## Regression

| Suite | Result |
|---|---|
| `uv run ruff check .` | clean |
| `uv run ruff format --check .` | clean |
| `uv run pytest tests/unit` | 998 passed |
| `uv run pytest tests/integration` | 275 passed (269 pre-I2.3 baseline + 6 new in `test_mcp_demo_script.py`) |
| Hero demo (no-arg mode), live | PASS — same `snapshot_id` as every `--serve` run |
| Architecture Answer evaluation (`test_evaluation_architecture_answers.py`) | 7 passed |

## I2 exit statement

> GO — At `d5c6320` (plus this record's own commit), a new user can run
> `examples/runtime-demo/mcp-demo.sh --serve`, get a deterministic, idempotent, MCP-call-free
> prepared architecture state, and configure one of four candidate coding-agent clients from
> documentation whose syntax is verified against each client's current official documentation (two
> of the four — Codex CLI and Claude Code — additionally verified by running the documented commands
> against the installed CLI binaries). Both deterministic drift findings
> (`LegacyPricingService`/`OBSERVED_ONLY`, `unused-q`/`NOT_OBSERVED_IN_WINDOW`) are reproducible and
> traceable to evidence at a stable snapshot. Repeated `--serve` performs zero duplicate telemetry
> submissions and zero fixture mutations. The existing no-argument hero demo is unchanged. I2 release
> blockers (spec §62) = 0. This is a client-onboarding capability, not yet a supported-client claim —
> that requires I3's actual-client interoperability qualification.
