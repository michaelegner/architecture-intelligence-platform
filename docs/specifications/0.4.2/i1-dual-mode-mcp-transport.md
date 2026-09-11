# AIP v0.4.2 I1 — Dual-Mode MCP Transport

**Status:** Draft  
**Release:** `v0.4.2`  
**Increment:** I1  
**Parent specification:** `docs/specifications/0.4.2/specification.md`  
**Proposed repository path:** `docs/specifications/0.4.2/i1-dual-mode-mcp-transport.md`

---

## 1. Purpose

I1 adds mainstream MCP negotiation compatibility to AIP's existing `/mcp` endpoint without weakening the strict direct `2026-07-28` contract introduced in `v0.4.0`.

The increment SHALL preserve AIP's current architecture semantics and read-only safety while making the transport boundary capable of serving:

1. the existing AIP direct per-request envelope; and
2. standard SDK-negotiated MCP requests.

The governing invariant is:

> **Transport negotiation may differ; architecture meaning must not.**

I1 is complete when a negotiated MCP client and the existing direct caller can use the same `/mcp` path with identical Architecture Intelligence semantics, no validation downgrade, and no unnecessary stateful-session redesign.

---

## 2. Baseline

The implementation baseline is the published `v0.4.1`.

The current MCP implementation:

- uses the pinned MCP SDK;
- mounts one `/mcp` endpoint;
- uses `json_response=True`;
- uses `stateless_http=True`;
- wraps the SDK app in AIP's direct-protocol ingress guard;
- deliberately rejects the SDK's negotiated initialization path today;
- exposes exactly three read-only tools:
  - `get_service_dependencies`;
  - `get_architecture_drift`;
  - `get_evidence`;
- performs zero graph writes through the MCP surface;
- binds Architecture Intelligence answers to graph snapshots;
- preserves the existing direct validation/error-priority contract.

I1 SHALL extend transport interoperability only.

---

## 3. Scope

I1 SHALL deliver:

```text
ADR 0014
exact direct-envelope marker definition
decision-complete routing behavior
pinned-SDK negotiated initialization
stateless-by-default interoperability
direct-path regression preservation
explicit POST / GET / DELETE behavior
conditional session handling only when required
direct-vs-negotiated semantic equivalence
cross-mode snapshot/evidence interoperability
Origin/Host protection on all supported paths
release-version consistency updated to 0.4.2
```

---

## 4. Non-Goals

I1 SHALL NOT deliver:

- Codex-specific onboarding;
- Claude Code onboarding;
- Cursor onboarding;
- VS Code onboarding;
- actual-client support qualification;
- client compatibility matrices;
- `mcp-demo.sh --serve`;
- README onboarding;
- public authentication;
- TLS;
- remote/public MCP hosting;
- new MCP tools;
- changed tool schemas;
- changed `ArchitectureAnswer` schemas;
- changed qualification semantics;
- new architecture discovery;
- new Canonical Model entities;
- graph writes from MCP;
- agent orchestration;
- LLM-dependent correctness.

Those belong to later `v0.4.2` increments or later releases.

---

## 5. Public Contract Invariants

I1 MUST preserve:

```text
public MCP path = /mcp
tool count = 3

tools:
- get_service_dependencies
- get_architecture_drift
- get_evidence

schema_version = "0.4"
graph writes through MCP = 0
LLM API key required by AIP = false
```

The following architecture semantics MUST remain unchanged:

- `CONFIRMED`;
- `OBSERVED_ONLY`;
- `NOT_OBSERVED_IN_WINDOW`;
- observation-context meaning;
- evidence applicability;
- snapshot identity meaning;
- evidence-reference meaning;
- limitation semantics;
- direct-dependency semantics;
- drift semantics.

---

# Part I — Transport Model

## 6. One Public Path, Two Connection Modes

`/mcp` SHALL remain the sole public MCP path.

It SHALL support two transport modes.

### 6.1 Direct mode

The existing strict AIP `2026-07-28` per-request envelope.

Direct mode retains its existing:

- request metadata;
- validation ladder;
- error precedence;
- unknown-tool handling;
- closed argument handling;
- security checks.

### 6.2 Negotiated mode

Standard MCP initialization and follow-up traffic handled by the pinned MCP SDK.

Negotiated mode SHALL reuse the same registered tool implementations and SHALL NOT contain independent Architecture Intelligence logic.

---

## 7. Stateless by Default

I1 SHALL preserve:

```python
stateless_http=True
```

unless implementation evidence proves that negotiated interoperability cannot work without stateful sessions.

The increment MUST NOT introduce session persistence merely because the SDK supports sessions.

The rule is:

> **Client interoperability is required; stateful sessions are not.**

If the SDK can perform negotiated initialization and tool calls without issuing a session identifier, that stateless behavior is the preferred and required I1 design.

A discovery that stateful sessions are actually required SHALL stop implementation of that change until ADR 0014 and the parent `v0.4.2` specification are explicitly updated.

---

## 8. HTTP Method Contract

The sole public path is `/mcp`.

### 8.1 POST

```text
POST /mcp
```

MUST support:

- direct AIP per-request traffic;
- SDK-negotiated initialization;
- SDK-negotiated follow-up requests that satisfy §11;
- SDK-negotiated tool discovery;
- SDK-negotiated tool calls.

### 8.2 All non-POST methods

For the stateless I1 baseline, `POST` is the only supported HTTP method on `/mcp`.

The AIP ingress layer MUST reject **every non-POST method before the pinned SDK is invoked**.

For `GET`, `DELETE`, `PUT`, `PATCH`, `OPTIONS`, and any other non-POST method except `HEAD`, the required response is:

```text
HTTP 405 Method Not Allowed
Allow: POST
Content-Type: application/json
```

with a fixed sanitized JSON body equivalent to:

```json
{
  "error": {
    "code": "METHOD_NOT_ALLOWED",
    "message": "Only POST /mcp is supported in stateless mode."
  }
}
```

The body MUST be at most 512 bytes and MUST NOT reflect request content or expose stack traces, credentials, sessions, account data, or internal infrastructure data.

The rejection MUST allocate no SSE stream, session lifecycle resource, or other SDK transport resource.

For:

```text
HEAD /mcp
```

the required response is:

```text
HTTP 405 Method Not Allowed
Allow: POST
```

with an empty response body, preserving normal HEAD semantics. The SDK MUST NOT be invoked.

`OPTIONS` has no special exemption in I1. It returns the same 405 contract. If browser/CORS preflight support is intentionally added later, ADR 0014 and the parent specification MUST be revised explicitly before that behavior is introduced.

If later real-client qualification proves GET/SSE, DELETE/session lifecycle, OPTIONS/preflight, or any other non-POST behavior is required, ADR 0014 and the parent specification MUST be revised explicitly before that behavior is introduced.

---

# Part II — Direct vs Negotiated Routing

## 9. Design Principle

AIP SHALL NOT create a second general MCP protocol-version or protocol-era classifier.

The pinned SDK remains authoritative for normal MCP negotiation.

AIP's ingress boundary SHALL answer only:

> **Is this request unmistakably using AIP's existing direct-envelope contract?**

If yes, the existing direct validation behavior owns the request.

If no, the pinned SDK owns normal negotiated MCP processing.

---

## 10. Exact Direct-Envelope Markers

A request is considered direct-mode traffic when **at least one** of these AIP-specific markers is present:

```text
HTTP header:
- mcp-method
- mcp-name

body:
- params._meta.io.modelcontextprotocol/protocolVersion
- params._meta.io.modelcontextprotocol/clientCapabilities
```

These are the direct-envelope discriminators for I1.

The following MUST NOT by themselves select direct mode:

```text
MCP-Protocol-Version
MCP session identifier
JSON-RPC method name alone
```

Reason:

- negotiated SDK clients may legitimately send `MCP-Protocol-Version`;
- session identifiers belong to SDK transport state;
- ordinary JSON-RPC method names are shared across modes.

---

## 11. Normative Routing and Negotiated Follow-Up Rule

Only `initialize` MAY be markerless.

For any non-`initialize` request with no AIP direct-envelope marker:

1. `MCP-Protocol-Version` MUST be present; and
2. the pinned SDK MUST recognize its value as a supported **handshake-era negotiated protocol version**.

AIP MUST use the pinned SDK's own classifier/constants for this recognition rather than maintain an independent protocol-era list.

A markerless non-`initialize` request with no protocol header MUST be rejected before SDK tool dispatch.

A request carrying direct-era `2026-07-28` as `MCP-Protocol-Version` but no direct-envelope markers MUST also be rejected rather than accepted as negotiated follow-up traffic.

This prevents bare stateless `tools/list` / `tools/call` requests from bypassing the existing direct validation contract.

The negotiated follow-up header requirement is evaluated **only after the body has been parsed into a valid JSON-RPC request and a method has been extracted**. If the body is malformed/non-object and no direct-specific header establishes direct ownership, the pinned SDK parse handler owns the failure. The expected oracle is the SDK's JSON-RPC parse error, not AIP's missing-header 400.

### 11.1 Routing table

| Request shape | Required behavior |
|---|---|
| `POST` + any direct-envelope marker | Route to existing strict direct validation. |
| Direct marker + missing/malformed direct `_meta` | Direct error; no fallback. |
| Direct marker + header/body method mismatch | Direct error; no fallback. |
| Direct marker + unknown tool | Direct error; no fallback. |
| Direct marker + unexpected direct tool arguments | Direct error according to existing contract. |
| Direct marker + session identifier | Direct mode wins; session state MUST NOT relax validation. |
| Markerless `initialize` without protocol header | Delegate to pinned SDK initialization. |
| Markerless `initialize` with protocol header | Delegate to pinned SDK initialization/version handling. |
| Non-`initialize`, no direct marker, recognized handshake-era `MCP-Protocol-Version` | Delegate to pinned SDK negotiated handling. |
| Non-`initialize`, no direct marker, missing `MCP-Protocol-Version` | Reject before SDK tool dispatch. |
| Non-`initialize`, no direct marker, direct-era `2026-07-28` header | Reject; MUST NOT become negotiated traffic. |
| Non-`initialize`, unsupported/invalid protocol version | Use pinned SDK recognition/error semantics; MUST NOT reach tool dispatch. |
| Session identifier only, no direct marker, no recognized handshake-era version | Reject. |
| Malformed/non-object JSON + direct-specific header (`mcp-method` or `mcp-name`) | Direct ownership remains sticky; no negotiated fallback. |
| Malformed/non-object JSON without a direct-specific header | Delegate immediately to the pinned SDK parse handler. Do not apply the negotiated-header check because no valid method has been extracted yet. |
| `GET /mcp` | AIP ingress returns HTTP 405 + `Allow: POST`; SDK not invoked. |
| `DELETE /mcp` | AIP ingress returns HTTP 405 + `Allow: POST`; SDK not invoked. |
| `HEAD /mcp` | AIP ingress returns HTTP 405 + `Allow: POST`, empty body; SDK not invoked. |
| `PUT`, `PATCH`, `OPTIONS`, or any other non-POST method | Same bounded HTTP 405 contract; SDK not invoked. |

---

## 12. No-Downgrade Rule

The most important routing safety property is:

> **Once direct intent is established, a malformed direct request MUST never become a valid negotiated request.**

Direct intent is sticky for the lifetime of that request.

Examples that MUST remain failures:

```text
mcp-method present + missing _meta
mcp-name present + malformed tool body
direct _meta present + method/header mismatch
direct envelope + unsupported protocol version
direct envelope + unknown tool
```

No such request may be retried internally through the SDK's negotiated path.

In addition, a markerless non-`initialize` request MUST NOT reach negotiated tool dispatch unless it carries a pinned-SDK-recognized handshake-era `MCP-Protocol-Version`.

---

## 13. SDK Delegation

Where possible, I1 SHOULD delegate the following to the pinned MCP SDK:

- negotiated initialization;
- protocol-version negotiation;
- generic JSON-RPC parsing;
- negotiated tool discovery;
- negotiated tool dispatch;
- standard transport errors;
- any optional session behavior actually produced by the SDK.

AIP SHOULD NOT duplicate SDK logic merely to determine which negotiated MCP revision or lifecycle applies.

AIP-specific custom logic SHOULD remain limited to:

1. detecting unmistakable direct-envelope intent;
2. preserving existing direct validation semantics;
3. protecting no-downgrade behavior;
4. preserving AIP-specific error corrections already required by the direct contract.

---

# Part III — Negotiated Stateless Behavior

## 14. Mandatory Negotiated Flow

I1 SHALL prove a generic negotiated MCP flow against the release candidate:

```text
initialize
   ↓
tools/list
   ↓
get_architecture_drift
   ↓
get_evidence using returned snapshot/evidence refs
   ↓
client disconnect
   ↓
fresh initialize / reconnect
```

The negotiated caller used in I1 MAY be an independent SDK test client or deterministic protocol test harness.

Actual Codex / Claude Code / Cursor / VS Code qualification belongs to I3.

---

## 15. Conditional Session Behavior

Session behavior is conditional.

### 15.1 No session ID issued

If the release candidate remains stateless and does not issue an MCP session identifier:

```text
session creation tests      = NOT_APPLICABLE
session reuse tests         = NOT_APPLICABLE
invalid-session tests       = NOT_APPLICABLE
session termination tests   = NOT_APPLICABLE
GET/SSE session tests       = NOT_APPLICABLE
DELETE session tests        = NOT_APPLICABLE
```

This is a valid I1 completion state.

### 15.2 Session ID is issued

If the pinned SDK issues a session identifier under the chosen configuration, I1 MUST additionally test:

- creation;
- propagation;
- reuse;
- invalid identifier behavior;
- termination behavior;
- GET/SSE if required by that lifecycle;
- DELETE if required by that lifecycle.

### 15.3 Stateful redesign discovered

If supporting negotiated clients requires changing AIP away from `stateless_http=True`, I1 SHALL NOT silently perform that redesign.

Instead:

1. document the evidence;
2. update ADR 0014;
3. update the parent `v0.4.2` specification;
4. explicitly approve the architectural change;
5. only then implement stateful behavior.

---

# Part IV — Architecture Semantics

## 16. Shared Tool Implementation

Direct and negotiated modes MUST use the same registered tool implementations.

There MUST NOT be:

- a negotiated-only architecture service;
- duplicated qualification logic;
- duplicated evidence resolution;
- duplicated snapshot handling;
- separate schemas by mode.

Transport mode MUST terminate before Architecture Intelligence semantics begin.

---

## 17. Semantic Equivalence

For equivalent inputs against the same graph state:

```text
direct structuredContent
      ≡
negotiated structuredContent
```

The equivalence check MUST cover:

- `schema_version`;
- producer identity except transport-irrelevant request metadata;
- tool identity;
- outcome;
- snapshot identity;
- observation context;
- claims;
- qualifications;
- evidence references;
- limitations;
- returned data;
- deterministic ordering where part of the contract.

Transport-only envelope differences are allowed.

Architecture meaning differences are not.

---

## 18. Cross-Mode Snapshot Interoperability

I1 SHALL prove both directions.

### 18.1 Negotiated drift → direct evidence

```text
negotiated get_architecture_drift
    -> snapshot S
    -> evidence_refs R

direct get_evidence(S, R)
    -> success
```

### 18.2 Direct drift → negotiated evidence

```text
direct get_architecture_drift
    -> snapshot S
    -> evidence_refs R

negotiated get_evidence(S, R)
    -> success
```

This proves that transport mode does not create separate snapshot or evidence domains.

---

## 19. Transport State Is Not Architecture State

Any SDK transport state MUST NOT affect:

- qualification;
- claim identity;
- evidence identity;
- snapshot identity;
- observation context;
- tool semantics;
- limitation semantics;
- ordering;
- graph contents.

No MCP session identifier may be required to reconstruct Architecture Intelligence consistency.

The architecture snapshot remains the consistency boundary.

---

# Part V — Security and Safety

## 20. Origin and Host Protection

Existing Origin and Host protection SHALL apply to:

- direct POST requests;
- negotiated POST requests;
- any GET/DELETE behavior exposed by the mounted SDK app.

No negotiated path may bypass transport security already applied to `/mcp`.

---

## 21. Zero-Write Invariant

All I1 transport paths MUST preserve:

```text
graph writes caused by MCP tools = 0
```

This includes:

- direct mode;
- negotiated mode;
- malformed requests;
- failed initialization;
- GET/DELETE handling;
- optional session lifecycle behavior.

---

## 22. Error Sanitization

Negotiated transport support MUST NOT expose internal database, stack-trace, credential, or raw telemetry details that the existing MCP contract sanitizes.

Direct-mode error priority MUST remain unchanged.

Negotiated-mode standard errors MAY differ in transport envelope where defined by the SDK, but MUST NOT change architecture semantics or leak additional sensitive internals.

---

# Part VI — Release Identity

## 23. Version Bump

I1 SHALL update the candidate's release identity to:

```text
0.4.2
```

The executable version-consistency gate MUST prove agreement across:

- `pyproject.toml`;
- root project entry in `uv.lock`;
- `app.version.package_version()`;
- MCP server advertised version;
- production `Producer.version`;
- Architecture Answer evaluator producer;
- active version-bearing evaluation fixtures/artifacts where contractually required.

`tests/unit/test_release_version_consistency.py` or its successor SHALL pin:

```python
_RELEASE_VERSION = "0.4.2"
```

The root README MUST NOT claim `v0.4.2` as the latest published release before actual release publication.

---

# Part VII — ADR 0014

## 24. Required ADR

I1 SHALL create:

> **ADR 0014 — Support Negotiated MCP Client Interoperability Without Weakening the Direct 2026-07-28 Contract**

The ADR MUST record:

- why v0.4 originally rejected negotiated initialization;
- why v0.4.2 adds interoperability now;
- preservation of `stateless_http=True` by default;
- exact direct-envelope discriminator;
- why `MCP-Protocol-Version` alone is not a direct discriminator;
- SDK delegation for normal negotiation;
- no-downgrade behavior;
- `/mcp` method contract;
- conditional session semantics;
- architecture-state vs transport-state separation;
- security posture;
- semantic-equivalence requirement;
- alternatives considered;
- consequences.

The historical v0.4 specification MUST remain unchanged.

---

# Part VIII — Implementation Guidance

## 25. Expected Code Areas

The implementation is expected to affect primarily:

```text
app/mcp/guard.py
app/mcp/app.py
app/mcp/server.py            # only if required by negotiated setup/versioning
tests/unit/
tests/integration/
tests/unit/test_release_version_consistency.py
docs/adr/
```

The exact file split is implementation-owned.

The architecture requirement is more important than preserving the current class names.

---

## 26. Guard Refactoring Guidance

The current guard was designed to reject negotiated initialization entirely.

I1 will likely require refactoring that responsibility.

The resulting ingress component SHOULD:

```text
read request enough to detect AIP direct-envelope intent
        ↓
if direct
    preserve current direct validation/corrections
else
    delegate to SDK
```

It SHOULD NOT:

- reimplement the SDK's negotiated classifier;
- infer protocol era from `MCP-Protocol-Version` alone;
- introduce architecture semantics;
- own session persistence.

A rename from a direct-only concept such as `ModernProtocolGuard` MAY be appropriate if the old name becomes misleading.

Naming is not a release requirement.

---

# Part IX — Test Plan

## 27. Direct Regression Tests

Existing direct tests SHALL remain green.

Add explicit regression tests for:

- each direct-envelope marker independently;
- marker combinations;
- missing `_meta`;
- malformed `_meta`;
- header/body mismatch;
- unsupported direct protocol;
- unknown tool;
- extra top-level arguments;
- malformed JSON after direct intent is established;
- direct marker + session identifier;
- direct no-fallback behavior.

---

## 28. Routing Truth-Table Tests

Every row in §11 SHALL have at least one executable test.

Special assertions:

```text
MCP-Protocol-Version alone            -> NOT direct
markerless initialize                 -> negotiated SDK
markerless tools/list                 -> REJECT
markerless tools/call                 -> REJECT
malformed body + direct header        -> direct-owned error
malformed body + no direct header     -> SDK parse error
handshake-era version + tools/list    -> negotiated SDK
handshake-era version + tools/call    -> negotiated SDK
2026-07-28 only + non-initialize      -> REJECT
session ID alone                      -> REJECT unless accompanied by required negotiated-era version/lifecycle
mcp-method present                    -> direct
mcp-name present                      -> direct
direct _meta present                  -> direct
```

This is a release requirement, not optional coverage.

---

## 29. Negotiated Integration Tests

Using the pinned SDK or an independent deterministic MCP client, prove:

- `initialize`;
- `tools/list`;
- exactly three tool names;
- `get_architecture_drift`;
- deterministic demo/fixture result;
- `get_evidence` with returned snapshot;
- reconnect/fresh initialization;
- no graph writes.

The test MUST exercise the mounted HTTP application rather than invoke tool functions directly.

---

## 30. HTTP Method Tests

For the stateless I1 implementation prove:

```text
POST /mcp                 supported
GET /mcp                  405, Allow: POST, bounded JSON, SDK not invoked
DELETE /mcp               405, Allow: POST, bounded JSON, SDK not invoked
PUT /mcp                  405, Allow: POST, bounded JSON, SDK not invoked
PATCH /mcp                405, Allow: POST, bounded JSON, SDK not invoked
OPTIONS /mcp              405, Allow: POST, bounded JSON, SDK not invoked
HEAD /mcp                 405, Allow: POST, empty body, SDK not invoked
representative other verb 405, Allow: POST, bounded JSON, SDK not invoked
```

The tests MUST prove no SSE stream/session allocation, no SDK dispatch, and zero graph writes for every non-POST method.

If optional session behavior becomes applicable, these expectations MUST be updated before I1 is declared complete.

---

## 31. Semantic Equivalence Tests

Use equivalent bound inputs through direct and negotiated paths and compare normalized `structuredContent`.

Required scenarios SHALL include at least:

1. `get_service_dependencies`;
2. `get_architecture_drift`;
3. `get_evidence`.

Mismatch count MUST be:

```text
0
```

---

## 32. Cross-Mode Tests

Required:

```text
negotiated drift -> direct evidence     PASS
direct drift     -> negotiated evidence PASS
```

Both flows MUST preserve the same `snapshot_id`.

---

## 33. Security Tests

Prove for both direct and negotiated POST traffic:

- allowed Origin succeeds;
- disallowed Origin fails;
- allowed Host succeeds;
- disallowed Host fails.

GET/DELETE rejection paths MUST also remain free of graph writes and sensitive error leakage.

---

## 34. Conditional Session Tests

Report exactly one of:

```text
SESSION_BEHAVIOR = NOT_APPLICABLE
```

or:

```text
SESSION_BEHAVIOR = QUALIFIED
```

`NOT_APPLICABLE` requires evidence that:

- the configured SDK does not issue a session identifier for the qualified generic negotiated path; and
- I1 does not require stateful transport.

`QUALIFIED` requires all lifecycle tests defined in the parent specification.

---

## 35. Version-Consistency Tests

The existing release consistency suite SHALL be updated to `0.4.2`.

It MUST fail when any active release identity surface still advertises `0.4.1`.

---

# Part X — Qualification Trace Safety

## 36. Trace Sanitization and Retention

I1 itself uses a generic negotiated client/harness rather than the named production clients, but any committed transport trace or diagnostic artifact produced by I1 MUST follow the same safety policy that later applies to I3 actual-client qualification.

Committed or published artifacts MUST NOT contain:

- authorization headers, bearer tokens, API keys, or credentials;
- cookies or `Set-Cookie` values;
- session secrets;
- account identifiers, email addresses, or user IDs unless replaced by explicit placeholders;
- raw system prompts;
- unrelated conversation content;
- unrelated HTTP traffic;
- private local paths or environment data not required for qualification.

Committed artifacts SHOULD contain only the minimum protocol evidence required to prove:

```text
initialization
negotiated protocol version
tools/list
tool names
drift call/result shape
evidence call/result shape
snapshot continuity
HTTP status / required MCP metadata
```

If a raw capture cannot safely be committed:

1. produce a sanitized/redacted excerpt or derived protocol summary;
2. optionally record the SHA-256 hash of the raw capture for audit correlation;
3. keep the raw capture only in an ephemeral local/CI workspace excluded from version control;
4. do not upload the raw capture as a CI or release artifact;
5. delete the raw capture after the sanitized artifact is produced and before qualification is considered complete.

---

# Part XI — Repository Hygiene

## 37. Repository Artifact Cleanup

Before the I1 specification directory is committed, remove accidental operating-system metadata.

The worktree MUST NOT contain:

```text
*:Zone.Identifier
.DS_Store
Thumbs.db
```

The current review specifically identified:

```text
docs/specifications/0.4.2/aip-v0.4.2-i1-dual-mode-mcp-transport-v2.md:Zone.Identifier
docs/specifications/0.4.2/aip-v0.4.2-specification-updated-after-second-review.md:Zone.Identifier
```

These files contain download-zone metadata only and MUST be deleted rather than committed.

---

# Part XII — Completion Criteria

## 38. Definition of Done

I1 is complete only when all of the following are true:

- [ ] `/mcp` remains the sole public MCP path.
- [ ] `POST /mcp` supports existing direct traffic.
- [ ] `POST /mcp` supports negotiated initialization and tool calls.
- [ ] `stateless_http=True` remains the default.
- [ ] No unnecessary server-side session persistence has been introduced.
- [ ] Exact direct-envelope markers are implemented and documented.
- [ ] Every routing truth-table row has executable coverage.
- [ ] `MCP-Protocol-Version` alone does not select direct mode.
- [ ] Only `initialize` may be markerless.
- [ ] Markerless non-`initialize` `tools/list` and `tools/call` are rejected before SDK tool dispatch.
- [ ] Recognized handshake-era protocol headers permit negotiated follow-up dispatch.
- [ ] Direct-era `2026-07-28` without direct-envelope markers is rejected as negotiated follow-up traffic.
- [ ] Malformed direct traffic never falls through to negotiated handling.
- [ ] Direct validation/error-priority regression count is zero.
- [ ] Negotiated tools/list exposes exactly three tools.
- [ ] Direct and negotiated results have zero semantic mismatches.
- [ ] Cross-mode drift/evidence flows succeed in both directions.
- [ ] Origin and Host protection applies to both modes.
- [ ] MCP graph-write count remains zero.
- [ ] Every non-POST method is rejected before SDK invocation with the defined HTTP 405 contract (`HEAD` with empty body).
- [ ] Malformed markerless JSON is handled by the pinned SDK parse handler; the negotiated-header check runs only after a valid method is extracted.
- [ ] Conditional session status is recorded as `NOT_APPLICABLE` or fully `QUALIFIED`.
- [ ] ADR 0014 is accepted.
- [ ] release version consistency reports `0.4.2` everywhere required.
- [ ] full unit/integration suite passes.
- [ ] existing Architecture Answer evaluation remains green.

---

## 39. I1 Release Blockers

Any of the following blocks I1 completion:

```text
existing valid direct request changes behavior unexpectedly
existing direct error priority changes unexpectedly
direct request can downgrade/fall through into negotiated mode
MCP-Protocol-Version alone selects direct mode
markerless non-initialize tools/list or tools/call reaches SDK tool dispatch
direct-era 2026-07-28 without direct markers is accepted as negotiated follow-up
any non-POST method does not return the defined 405 contract
any non-POST method reaches SDK stream/session allocation
malformed markerless JSON is intercepted by the negotiated-header check instead of the SDK parse handler
negotiated mode uses different architecture logic
direct and negotiated Architecture Intelligence results differ
snapshot/evidence interoperability differs by transport
stateful session redesign is introduced without explicit approval
Origin/Host security can be bypassed
MCP graph writes > 0
any active release identity still reports 0.4.1
```

---

## 40. Evidence of Completion

The I1 completion record SHOULD contain:

```text
candidate commit SHA
MCP SDK version
stateless_http setting
routing truth-table test result
direct regression result
negotiated integration result
semantic-equivalence result
cross-mode snapshot result
HTTP method result
markerless-follow-up rejection result
trace sanitization status
raw capture deletion status
session behavior: NOT_APPLICABLE / QUALIFIED
Origin/Host security result
zero-write result
version-consistency result
full test-suite result
ADR 0014 reference
```

No client-family support claim is established by I1.

Codex, Claude Code, Cursor, and VS Code support claims require I3 actual-client qualification.

---

## 41. Exit Capability

At I1 completion:

> **AIP has one `/mcp` endpoint that preserves its strict direct `2026-07-28` contract while also accepting standard negotiated MCP traffic through the pinned SDK, with stateless transport by default, zero semantic differences, zero graph writes, and no validation downgrade.**

This establishes the transport foundation for I2 onboarding and I3 real-client qualification.
