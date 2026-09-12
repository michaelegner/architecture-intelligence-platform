# I1 Completion Record — v0.4.2 Dual-Mode MCP Transport

**This record is retrospective.** I1 (`docs/specifications/0.4.2/i1-dual-mode-mcp-transport.md`,
merged to `main` as `2b6f865` via PR #135) did not originally require a candidate-bound completion
record — only a narrative "Implementation record" section in
[ADR 0014](../../adr/0014-negotiated-mcp-client-interoperability.md). I3's entry gate (spec
`i3-client-qualification-and-release-preparation.md` §3.1) requires one, so this record is written
now, after I1 and I2 are both complete, satisfying that gate.

## Run identity

- **I1 (Dual-Mode MCP Transport):** merged to `main` as `2b6f865` (PR #135, predates I2 entirely).
- **Retrospective candidate binding:** `279c0ae824b3a7ef9c57f99e3e29790f4ac90e1a` — current `main` HEAD
  as of this record's authorship (I2 fully merged: PRs #136/#137/#139). This is **not** a frozen
  `RELEASE_CANDIDATE_SHA` — that happens later in I3, per spec §4.3. If a candidate-affecting change
  lands on `main` before that freeze, re-bind this record to the new HEAD (spec §4.4); I1's own suite
  is unmodified and still passes at every commit since `2b6f865`, so re-binding is a citation update,
  not a re-verification.
- I1's own suite is exercised unmodified at this SHA — none of I1's test files changed since `2b6f865`.

## Regression suite (full local run at the retrospective binding)

| Suite | Result |
|---|---|
| `uv run ruff check .` | clean |
| `uv run ruff format --check .` | clean |
| `uv run pytest tests/unit` | 998 passed |
| `uv run pytest tests/integration` | 281 passed |

281 integration tests = the 277 I2.3 baseline (`docs/specifications/0.4.2/i2-completion-record.md`)
+ 4 new in this same I3.1 slice: 1 consolidated zero-write completion-gate test (below) + 2
`read_revision_fence.py` helper tests + 1 `mcp-demo.sh` invalid-`BUILD_REVISION` rejection test —
none of which are I1 regressions; they're new I3.1 coverage landing in the same commit range.

## I1 §3.1 required items

| Item | Evidence |
|---|---|
| Direct mode (unchanged v0.4.0 envelope) | `tests/unit/test_mcp_discovery.py::test_mcp_protocol_and_discovery` — all pre-existing `_check_*` helpers exercising the direct envelope |
| Negotiated mode | `tests/unit/test_mcp_discovery.py`'s `_check_markerless_initialize_reaches_negotiated_sdk_path`, `_check_negotiated_tools_call_shares_the_direct_tool_implementation` |
| Malformed-body precedence | `tests/unit/test_mcp_discovery.py`'s `_check_malformed_json_without_direct_header_reaches_sdk_parse_handler` (owned by the SDK's parser when no direct header is present) and `_check_malformed_json_with_direct_header_is_owned_by_direct_path` (stays on the direct path when `mcp-method` is present) |
| Unsupported HTTP methods (405 contract) | `tests/unit/test_mcp_discovery.py`'s `_check_get_is_rejected_with_405_before_sdk_invocation`, `_check_delete_is_rejected_with_405_before_sdk_invocation`, `_check_head_is_rejected_with_405_and_empty_body`, `_check_other_non_post_methods_are_rejected_with_405` (PUT/PATCH/OPTIONS) |
| Origin/Host enforcement | `tests/unit/test_mcp_discovery.py::_check_disallowed_origin_is_rejected`; `tests/integration/test_mcp_negotiated_transport.py::test_negotiated_origin_and_host_security_matches_direct_mode` (proves the negotiated path introduces no bypass) |
| Cross-mode semantic equivalence | `tests/integration/test_mcp_negotiated_transport.py::test_direct_and_negotiated_structured_content_are_semantically_equivalent`, `::test_cross_mode_snapshot_interoperability_both_directions` (both directions), `::test_mandatory_negotiated_flow_against_real_data` (full initialize → tools/list → drift → evidence → disconnect → reconnect flow against real graph data) |
| Conditional-session result | **`NOT_APPLICABLE`** — `tests/unit/test_mcp_discovery.py::_check_negotiated_mode_issues_no_session_id` confirms no session IDs are issued in either mode; the candidate issues no session IDs and no I2 client tuple requires stateful sessions (I3 spec §3.3's `NOT_APPLICABLE` condition) |
| Automated zero-write result | `tests/integration/test_mcp_i1_zero_write_completion_gate.py::test_zero_graph_writes_across_every_i1_routing_path` — see below |
| I1 blockers | `0` |

### Closing a real gap: the automated zero-write result

Before this record, zero-write evidence existed but was split across three per-tool,
**direct-mode-only** files — `test_mcp_service_dependencies_equivalence.py`,
`test_mcp_architecture_drift_equivalence.py`, `test_mcp_evidence_equivalence.py` — each proving one
tool leaves `(:AipInternalState).revision` unchanged for a successful and a refused call. None of
them, nor any other file, proved "zero graph writes across *all* I1 routing paths" (direct **and**
negotiated, all three tools, including malformed/rejected requests) in one place, which is exactly
what I3 spec §3.1/§3.3/§8.3 require as I1 completion evidence.

New file `tests/integration/test_mcp_i1_zero_write_completion_gate.py` closes this: one test brackets
a single `read_revision` before/after a sequence covering direct-mode success (all three tools) and
rejection (malformed body, unsupported HTTP method `GET`), then negotiated-mode success (all three
tools, via a real `initialize` handshake) and rejection (malformed body, unsupported protocol
version) — asserting the fence never advanced across the entire run. It complements, rather than
duplicates, the three existing files' broader semantic-equivalence assertions.

## Scope preservation

- `ArchitectureAnswer<T>` schema family: unchanged, `schema_version` still `"0.4"`.
- Exactly three read-only MCP tools: unchanged.
- Public MCP path `/mcp`: unchanged, `POST`-only in this stateless release.
- Canonical Model / graph schema: unchanged — I1 is a transport-layer increment only.

## I1 exit statement

> GO — At `279c0ae824b3a7ef9c57f99e3e29790f4ac90e1a` (retrospective binding), AIP's direct
> (`2026-07-28`) and negotiated MCP transport modes remain semantically equivalent: identical
> `ArchitectureAnswer` results for equivalent requests, identical snapshot/evidence continuity in
> both cross-mode directions, identical Origin/Host protection, and identical non-POST rejection
> behavior. Neither mode issues a session identifier (`NOT_APPLICABLE` for conditional-session
> qualification). Zero graph writes occur across every I1 routing path — direct and negotiated,
> success and rejection, for all three tools — proven in one consolidated test rather than only
> per-tool. I1 blockers = 0.
