# 14. Support negotiated MCP client interoperability without weakening the direct 2026-07-28 contract

Status: Accepted — implemented in `v0.4.2` I1. Superseded by 0016 for the active `v0.5+`
architecture (the AIP-specific direct MCP envelope this ADR's dual-mode decision retained alongside
negotiated MCP is retired in `v0.5.0` I3 Slice 5a); this ADR's body remains unchanged as the
historical rationale and implementation record for the `v0.4.2` dual-mode release.

## Context

`v0.4.0` introduced AIP's `/mcp` endpoint as a strict direct per-request envelope on the
`2026-07-28` protocol revision: every request carries `mcp-method`/`mcp-name` headers and a
`params._meta` object naming its protocol version and client capabilities, validated by
`app.mcp.guard.ModernProtocolGuard` in front of the pinned MCP SDK's mounted app. That guard was
built to *reject* the SDK's own legacy `initialize`/session handshake outright — a request missing
the direct envelope, or naming a pre-`2026-07-28` handshake version, was treated as a release
blocker (spec `docs/specifications/0.4.0/i2-mcp-vertical-slice-and-evidence-drill-down.md` §4/§20),
because the SDK otherwise silently served it through its legacy path instead of enforcing AIP's
stricter, deterministic contract.

That decision was correct for `v0.4.0`'s goal — a deterministic, evaluable MCP surface with no
ambiguity about protocol era — but it has a real cost: mainstream local coding-agent clients (Codex
CLI, Claude Code, Cursor, VS Code) speak the *standard* negotiated MCP handshake, not AIP's direct
envelope. None of them could connect to AIP's `/mcp` endpoint at all. `v0.4.2`'s release intent
(`docs/specifications/0.4.2/specification.md`) is to make AIP's existing read-only architecture
surface directly consumable by those clients, without weakening anything the direct contract
guarantees. The governing invariant, repeated throughout the `v0.4.2` spec and its I1 increment
(`docs/specifications/0.4.2/i1-dual-mode-mcp-transport.md`):

> Transport negotiation may differ; architecture meaning must not.

## Decision

1. **`/mcp` remains the sole public MCP path**, now serving two connection modes rather than one:
   the existing strict **direct** mode, unchanged, and a new **negotiated** mode that defers to the
   pinned MCP SDK's own `initialize`/negotiation/session machinery.

2. **`stateless_http=True` (and `json_response=True`) stay the default.** I1 does not introduce
   server-side session persistence merely because the SDK supports it. Confirmed live: the SDK's
   stateless per-request handler (`StreamableHTTPSessionManager._handle_stateless_request`)
   constructs each request's transport with `mcp_session_id=None` and issues no session identifier
   at all — and, confirmed live against the actual mounted app, a standalone negotiated `tools/list`
   with only a recognized `MCP-Protocol-Version` header succeeds statelessly with no prior
   `initialize` required on the same connection. Client interoperability is required; stateful
   sessions are not. A discovery that a qualified client genuinely cannot work statelessly would
   require this ADR and the parent specification to be revised explicitly before introducing that
   redesign — no such discovery has occurred in I1.

3. **The exact AIP direct-envelope discriminator.** A request is direct-mode when it carries **at
   least one** AIP-specific marker: the `mcp-method`/`mcp-name` HTTP headers, or
   `params._meta`'s `io.modelcontextprotocol/protocolVersion`/`clientCapabilities` keys in the body.
   Every currently-valid direct request already carries these, so this classification preserves
   `v0.4.0`/`v0.4.1` behavior byte-for-byte for all of them.

4. **`MCP-Protocol-Version` alone, and an MCP session identifier alone, are deliberately NOT
   direct-mode markers.** Both are legitimate on ordinary negotiated SDK traffic — a negotiated
   client sends the protocol-version header on every request by design, and session identifiers are
   SDK transport state, not an AIP-specific signal.

5. **AIP does not run a second general MCP protocol-era classifier.** The pinned SDK's
   `mcp.shared.inbound.classify_inbound_request` remains the sole authority for direct-mode
   validation (unchanged from `v0.4.0`). For the new negotiated branch, `app.mcp.guard` imports
   `MODERN_PROTOCOL_VERSIONS` from the SDK's own `mcp_types.version` module — the same constant
   `classify_inbound_request` itself uses — rather than hard-coding `"2026-07-28"` or maintaining a
   competing list of recognized handshake-era versions. Beyond recognizing that one direct-era value
   (to reject it on a markerless follow-up), AIP delegates entirely: confirmed live that the SDK's
   own dispatch already produces a correct JSON-RPC error and never reaches tool dispatch for a
   `MCP-Protocol-Version` value it doesn't recognize as either the direct or a handshake era, with no
   help from AIP's ingress layer.

6. **No-downgrade rule.** Once a request is classified as direct (by header or body marker), that
   classification is sticky even if the body turns out to be malformed — the direct path owns the
   failure response rather than silently falling through to the SDK's negotiated parse handler. A
   markerless non-`initialize` request never reaches SDK tool dispatch unless it carries a header
   naming a real handshake era; a markerless follow-up naming the direct `2026-07-28` era is rejected
   outright rather than delegated.

7. **`/mcp` HTTP method contract.** For this stateless release, `POST` is the only supported method.
   Every other method — `GET`, `DELETE`, `HEAD`, and everything else — is rejected with `405`
   (`Allow: POST`) **before the SDK is invoked at all**: the SDK's own `streamable_http_app` would
   otherwise natively open an SSE stream for `GET` or attempt session termination for `DELETE`, both
   of which this stateless release advertises as unsupported. `HEAD` returns an empty body per HEAD
   semantics; every other rejected method returns a fixed, ≤512-byte sanitized JSON body.

8. **Transport state is not architecture state.** Any SDK transport/session state — including a
   session identifier, if one were ever issued — must never affect qualification, claim identity,
   evidence identity, snapshot identity, observation context, tool semantics, ordering, or graph
   contents. The architecture snapshot remains the sole consistency boundary.

9. **Same three tools, same architecture semantics, both directions.** Direct and negotiated modes
   dispatch to the exact same registered tool implementations (`app/mcp/tools.py`, unmodified by
   this increment) — there is no negotiated-only architecture service, no duplicated qualification
   or evidence-resolution logic. Confirmed live that a negotiated `tools/call` produces the identical
   sanitized-error shape a direct-mode call gets from the same unconfigured-wiring scenario.

10. **Cross-mode snapshot interoperability.** A claim obtained via one mode's `get_architecture_drift`
    resolves successfully through `get_evidence` called via the *other* mode, at the same
    `snapshot_id`, in both directions. Connection mode never creates a separate consistency domain.

11. **Security posture unchanged.** Existing Origin and Host allow-listing protects both connection
    modes and every supported HTTP method identically; the negotiated path introduces no new bypass.
    The deployment posture remains local/trusted-network only — this release adds no authentication
    or TLS.

12. **Qualified client/platform tuples are a later increment's concern.** I1 proves the generic
    negotiated transport contract with a deterministic protocol harness. It establishes no
    client-family support claim — Codex CLI, Claude Code, Cursor, and VS Code qualification against
    actual client software is I3's job (`docs/specifications/0.4.2/specification.md` §31–§37).

### Alternatives considered

- **Run a full SDK-negotiated session lifecycle unconditionally** (mint and track session IDs even
  though the SDK's stateless mode doesn't require them) — rejected: adds real operational state
  (session storage, expiry, invalidation) for a property no evidence says any targeted client needs,
  contradicting the "client interoperability is required; stateful sessions are not" rule this ADR
  restates from the spec.
- **Build an independent protocol-era/version classifier inside AIP** rather than delegating to the
  pinned SDK's own constants and dispatch — rejected: duplicates logic the SDK already owns
  correctly (confirmed live for the unrecognized-version case), and creates exactly the
  two-sources-of-truth risk `app.mcp.guard`'s existing docstring already warns against for the
  direct-mode ladder.
- **Treat `MCP-Protocol-Version` presence alone as sufficient for direct-mode routing** — rejected:
  negotiated clients legitimately send this header on every request, so using it as a direct-mode
  signal would misroute ordinary negotiated traffic into the strict direct ladder and reject it.

## Consequences

- `app/mcp/guard.py`'s `ModernProtocolGuard` gains a routing decision in front of its existing,
  unmodified direct-mode ladder, plus non-POST method rejection ahead of both paths. Every existing
  direct-mode test remains valid unchanged, because every one of them already constructs requests
  carrying a direct-envelope marker.
- `app/mcp/tools.py`, `app/mcp/wiring.py`, and `app/mcp/server.py` require no changes — tool
  registration and dispatch were already fully mode-agnostic.
- A future increment that discovers a qualified client genuinely requires stateful sessions must
  revise this ADR (and the parent `v0.4.2` specification) explicitly before implementing that
  change — it is not a decision this ADR pre-authorizes.
- `docs/mcp.md` must stop categorically stating AIP has no initialization handshake, and instead
  describe both modes as exposing identical Architecture Intelligence semantics.
- Historical `v0.4.0`/`v0.4.1` specifications are not rewritten to imply negotiated initialization
  was ever supported before this release — this ADR records the additive decision, they remain an
  accurate record of what shipped when.

## Implementation record (v0.4.2 I1)

- **Routing logic**: `app/mcp/guard.py`'s `ModernProtocolGuard.__call__` — non-POST methods
  rejected before body inspection; direct-envelope-marker detection from headers (before JSON parse,
  so a malformed body with a direct header still resolves to a direct-path failure) and, for
  parseable bodies, from `params._meta`; markerless `initialize` and markerless non-`initialize`
  requests carrying a non-direct-era `MCP-Protocol-Version` header delegate to `self._app(...)`
  (the SDK's mounted app) unchanged; everything else guard-rejected with a bounded JSON-RPC error.
- **Regression + routing-truth-table tests**: `tests/unit/test_mcp_discovery.py` — every existing
  direct-mode case unchanged, plus new coverage for markerless `initialize`, a markerless
  `MCP-Protocol-Version`-only follow-up reaching the SDK statelessly, missing-header and
  direct-era-without-marker rejections, session-ID-alone non-discrimination, malformed-JSON
  ownership in both directions, an unrecognized-version case delegated to and handled by the SDK,
  negotiated `tools/call` sharing the direct dispatch path, and the full non-POST method matrix
  (`GET`/`DELETE`/`HEAD`/`PUT`/`PATCH`/`OPTIONS`).
- **Version-consistency**: `pyproject.toml`/`uv.lock` bumped to `0.4.2`;
  `tests/unit/test_release_version_consistency.py` re-pinned; the 23 frozen
  `evaluation/architecture_answers/scenarios/*/expected_answer.json` fixtures' `producer.version`
  updated in lockstep (the same drift class PR #120 found, now guarded by the version-consistency
  test failing loudly instead of silently agreeing on a stale value).
- Cross-mode snapshot/evidence interoperability and semantic-equivalence tests against real graph
  data, and the qualified client/platform matrix, are tracked separately per the delivery split in
  `docs/specifications/0.4.2/specification.md` §44 (I1 proves the generic transport contract; I3
  proves actual-client qualification).

## Amendment (v0.4.2 I3.3 actual-client qualification — direct-marker method allowlist)

I3.3's real Claude Code qualification run found that this ADR's original routing decision was based
on an incorrect premise: it treated `mcp-method`/`mcp-name` (imported from the pinned SDK's own
`mcp.shared.inbound`, never AIP-invented) as **AIP-specific** direct-envelope markers that only AIP's
own historical hero-demo script would ever send. In fact a real, current, fully compliant MCP client
— Claude Code (`claude-code/2.1.270`) — sends these same header names as part of its own legitimate
SDK-native transport handshake (`mcp-method: server/discover`, then `mcp-method: subscriptions/listen`,
both under protocol era `2026-07-28`), for a purpose unrelated to AIP's `tools/list`/`tools/call`-only
direct envelope.

Because `ModernProtocolGuard` forwarded any direct-marked request whose method it didn't specifically
validate (only `tools/call` got extra checks) straight to `self._app` on the assumption that a direct
marker implied "safe to dispatch as-is", Claude Code's `subscriptions/listen` request reached an SDK
code path that hangs indefinitely under AIP's stateless single-worker deployment. **A single,
unauthenticated request from an ordinary, spec-compliant client pegged the process at ~100% CPU and
made it unresponsive to every other client, including its own health check** — confirmed via a
minimal `curl` repro requiring zero Claude Code involvement, and confirmed that `asyncio.wait_for`
cannot preempt it (the offending code does not yield control back to the event loop). This is a
release-blocking defect independent of client qualification, not merely "Claude Code fails to
qualify" — full finding, reproduction, and root-cause isolation recorded in
`docs/release-validation/v0.4.2-client-traces/claude-code.md`. It invalidated the `v0.4.2-rc.1`
candidate frozen by I3.2 (`docs/release-validation/v0.4.2-rc.1-candidate-preparation.md`, now marked
`INVALIDATED`), per spec §4.4 ("MCP transport implementation" is a named candidate-affecting-change
example).

**Fix** (`app/mcp/guard.py`): direct-marked dispatch is now a closed allowlist,
`_DIRECT_MODE_METHODS = frozenset({"tools/list", "tools/call"})` — the exact set direct mode has ever
actually implemented — checked immediately after `classify_inbound_request` accepts the request and
before any forwarding. Any other method name, including any future real SDK-native method this guard
has not been taught about, is rejected with a fast, deterministic `METHOD_NOT_FOUND` **before**
`self._app` is ever called. This is a general boundary-correction, not a `subscriptions/listen`-specific
denylist entry: `server/discover` (the other real method observed, which happened to return a
plausible response rather than hang) is rejected the same way, on the same principle — anything not on
the closed allowlist is untrusted by default, regardless of whether it currently happens to be benign.

Regression coverage added to `tests/unit/test_mcp_discovery.py`: the exact `subscriptions/listen`
repro terminates fast (bounded by `asyncio.wait_for`, and independently confirmed to genuinely hang
the whole test run without the fix — not just a slow response); `server/discover` is rejected the
same way; a header/body mismatch still takes priority over the new allowlist check (existing rung
ordering preserved); an ordinary direct `tools/list` and a fresh negotiated `initialize` both still
succeed immediately after a rejected unimplemented-method request (no residual event-loop damage,
direct/negotiated classification stays distinct). Full unit (998) and integration (287) suites pass
unmodified otherwise.

This amendment does not change the routing *contract's* dual-mode shape (direct vs. negotiated
classification is unchanged); it closes a gap in what the direct path is willing to do once a request
is classified as direct. `docs/specifications/0.4.2/i1-dual-mode-mcp-transport.md` is corrected in
lockstep to state the same allowlist as a normative requirement and to stop describing
`mcp-method`/`mcp-name` as AIP-proprietary.

## Amendment (v0.4.2 I3.4 actual-client qualification — negotiated missing-header fallback)

I3.4's real VS Code (1.137.0) + GitHub Copilot Chat qualification run found a second incorrect premise
in this ADR's original routing decision, this time on the *negotiated* side rather than the direct
side: `ModernProtocolGuard` treated a *missing* `MCP-Protocol-Version` header on any markerless
non-`initialize` request as an outright rejection ("A negotiated follow-up request requires an
MCP-Protocol-Version header"), on the assumption that the header's presence was mandatory for the
request to be trustworthy at all.

Two independent facts contradict that assumption, and they establish two *separate* normative points,
not one. The MCP specification's own text says both: *"the client MUST include the
MCP-Protocol-Version... header on all subsequent requests"* **and**, separately, for backward
compatibility, *"if the server does not receive an MCP-Protocol-Version header, and has no other way
to identify the version... the server SHOULD assume protocol version 2025-03-26."* A client omitting
the header is not itself spec-conformant — but the spec still directs a *server* that receives such a
request to tolerate it gracefully, not reject it. AIP's guard conflated these: it enforced the
client-side `MUST` as a hard rejection, with no allowance at all for the server-side `SHOULD`. Second,
the exact MCP SDK AIP has pinned (`mcp==2.2.0`) already implements that server-side graceful default
itself: `mcp.server.streamable_http` falls back to a `DEFAULT_NEGOTIATED_VERSION` constant when the
header is absent, and its own `_validate_request_headers` comment states outright that "the legacy
version-gate is gone." AIP's guard, sitting in front of that SDK, was **stricter than both the spec's
own server-side allowance and the SDK it wraps** — even though the traffic triggering it was not
itself perfectly spec-conformant client behavior.

VS Code's real MCP client exposed this directly: it negotiated a current protocol version
(`protocolVersion: "2025-11-25"`) correctly via `initialize` — AIP responded successfully — and then
sent `notifications/initialized` with no `MCP-Protocol-Version` header at all (an omission the spec's
client-side `MUST` does not authorize, but one its server-side backward-compatibility clause exists
specifically to accommodate). AIP's guard rejected it with `400`/`-32600` before `tools/list` ever ran,
killing the connection outright. **Under the pre-fix candidate, VS Code could not connect to AIP at
all, in any invocation** — not an intermittent or edge-case failure, and a real, release-blocking
interoperability defect regardless of which side's spec obligation was technically at issue. Full
finding recorded in `docs/release-validation/v0.4.2-client-traces/vscode.md`.

**Fix** (`app/mcp/guard.py`): the negotiated-mode branch no longer treats a missing
`MCP-Protocol-Version` header as a rejection reason. A markerless non-`initialize` request with no
version header at all is now forwarded to the pinned SDK, which applies its own
`DEFAULT_NEGOTIATED_VERSION` fallback. The one case that remains rejected is unchanged and still
correct: a markerless follow-up whose header is *present* and explicitly names the direct/
single-exchange `2026-07-28` era — that is a genuine contradiction (claiming the direct era while
behaving like negotiated traffic), categorically different from a header that is simply absent, and
delegating it as negotiated traffic would be a real no-downgrade violation. An explicitly present but
otherwise-unrecognized version value is still handled entirely by the SDK's own recognition/error
semantics, unchanged.

Regression coverage added to `tests/unit/test_mcp_discovery.py`: one dedicated scenario test,
`_check_vscode_full_sequence_without_protocol_header_is_accepted`, performs `initialize` →
`notifications/initialized` → `tools/list`, all three requests itself (not relying on adjacent-test
call order) and all headerless — asserting the negotiated `2025-11-25` `initialize` result, the
notification's exact `202 Accepted`/empty-body response (not merely "not a 400"), and a successful
three-tool `tools/list` immediately after. Only the `initialize` → headerless-`notifications/initialized`
portion of this sequence was directly observed in VS Code's own client trace log (that is the exact
real-world reproduction); its queued `prompts/list`/`tools/list` never completed once the connection
died, so their headers were never observed. Covering headerless `tools/list`/`tools/call` in the same
scenario and elsewhere in this file is deliberate, broader contract coverage for the general fallback
rule §11 now states — not a claim that VS Code's own `tools/list` was confirmed headerless too. The
general markerless
`tools/list`/`tools/call`-without-header checks were updated from asserting rejection to asserting the
SDK fallback now answers them normally; a session identifier alone (still no version header) is
likewise now delegated to the SDK, not rejected; the direct-era-header-present-without-marker
rejection case is unchanged and still covered. No hang or event-loop risk exists in this code path (unlike
the I3.3 amendment's `subscriptions/listen` finding), so no subprocess-isolated regression test was
needed here — an in-process ASGI check is sufficient and sound.

This amendment does not change the routing contract's dual-mode shape or the direct-marker allowlist
from the I3.3 amendment above; it corrects the negotiated side's missing-header handling to match both
the MCP specification's own backward-compatibility clause and the pinned SDK's own already-implemented
behavior. `docs/specifications/0.4.2/i1-dual-mode-mcp-transport.md` §11/§11.1/§12/§28 and its
Definition of Done/Release Blockers sections are corrected in lockstep.
