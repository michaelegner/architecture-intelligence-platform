# AIP v0.4.2 — MCP Client Interoperability and Coding-Agent Onboarding

**Status:** Draft specification  
**Release:** `v0.4.2`  
**Parent baseline:** published `v0.4.1`  
**Project:** Architecture Intelligence Platform (AIP)  
**Primary outcome:** connect mainstream local coding-agent clients directly to AIP's existing read-only MCP surface without changing architecture semantics  
**Public schema version:** remains `0.4`

---

## 1. Release Intent

`v0.4.2` makes AIP's existing read-only Architecture Intelligence surface directly consumable by mainstream locally running coding-agent clients.

The release adds:

- negotiated MCP client interoperability alongside the existing strict per-request `2026-07-28` path;
- a deterministic `--serve` demo mode prepared for external MCP clients;
- verified, copy-paste onboarding for Codex CLI, Claude Code, Cursor, and VS Code;
- concise README onboarding from demo startup to drift and evidence inspection.

The release does **not** change AIP's architecture semantics.

The governing invariant is:

> **Transport negotiation may differ; architecture meaning must not.**

The intended user path is:

```text
start seeded AIP
      ↓
configure one coding-agent client
      ↓
run one supplied architecture prompt
      ↓
inspect qualified drift
      ↓
resolve evidence at the same snapshot
```

---

## 2. Why This Is a Patch Release

`v0.4.2` is a backward-compatible interoperability and onboarding patch over the published `v0.4` Architecture Intelligence contract.

The release MUST preserve:

```text
Canonical Model changes             = 0
architecture qualification changes  = 0
new evidence sources                = 0
new public MCP tools                = 0
answer schema changes               = 0
schema_version changes              = 0
graph writes through MCP            = 0
LLM dependency for correctness      = 0
```

The release MAY change:

```text
MCP transport compatibility         +
client interoperability             +
demo ergonomics                     +
documentation / onboarding          +
```

`v0.5` remains reserved for **Broader Architecture Discovery** and MUST NOT be used for this client-interoperability work.

---

## 3. Baseline

The release baseline is the published `v0.4.1`.

The baseline already provides:

- exactly three read-only MCP tools:
  - `get_service_dependencies`,
  - `get_architecture_drift`,
  - `get_evidence`;
- `ArchitectureAnswer<T>` contracts;
- snapshot-bound claim/evidence workflows;
- declared-versus-observed qualification;
- evidence and provenance linkage;
- zero graph writes through MCP;
- deterministic direct MCP evaluation;
- a timestamp-frozen runtime demo;
- the `2026-07-28` direct per-request protocol path;
- MCP SDK-based server implementation;
- Origin and Host allow-listing;
- semantic hardening from `v0.4.1`.

`v0.4.2` SHALL add client interoperability without weakening any of those properties.

---

## 4. Release Goal

The release goal is:

> **A locally running, explicitly qualified coding-agent client/platform combination can connect directly to AIP, discover exactly the existing three read-only tools, obtain the deterministic demo drift result, resolve its evidence at the same snapshot, disconnect, and reconnect successfully — without proxies, undocumented headers, or architecture-semantic changes.**

The client families targeted for qualification are:

```text
Codex CLI
Claude Code
Cursor
VS Code
```

A public **supported** claim SHALL be bound to the exact tested tuple recorded during qualification, including client version, extension/plugin version where applicable, operating system, execution mode, and local network topology.

Other versions, platforms, execution modes, or network arrangements are **unverified**, not implicitly supported.

Claude Desktop is explicitly deferred.

---

## 5. Non-Goals

The following are out of scope:

- Claude Desktop support;
- hosted/cloud-agent access to a user's `localhost`;
- authentication;
- TLS termination;
- public internet deployment;
- OAuth;
- agent identity or authorization;
- remote MCP hosting guidance;
- new MCP tools;
- generic graph querying;
- new Architecture Intelligence result types;
- new architecture-discovery sources;
- Kubernetes discovery;
- Pub/Sub / Topic / Subscription semantics;
- Canonical Model changes;
- Graph Schema changes;
- qualification-rule changes;
- new observation semantics;
- LLM-based correctness;
- agent orchestration;
- automatic client configuration changes;
- root-level active client config files;
- declaring untested client versions supported;
- changing historical v0.4 specifications to pretend initialization was always supported.

---

# Part I — MCP Transport Interoperability

## 6. Existing Direct Protocol Contract

AIP already exposes a strict direct per-request MCP path using protocol revision `2026-07-28`.

Existing direct calls use the current protocol/header/body markers, including:

```text
MCP-Protocol-Version: 2026-07-28
mcp-method: ...
mcp-name: ...           # tools/call only
params._meta:
  io.modelcontextprotocol/protocolVersion
  io.modelcontextprotocol/clientCapabilities
```

This path has a strict validation ladder and error precedence.

`v0.4.2` SHALL preserve that behavior.

No existing valid `v0.4.1` direct request may change architecture meaning because of this release.

No malformed direct request may become valid merely because a second connection mode exists.

---

## 7. Negotiated Client Mode and HTTP Surface

`/mcp` SHALL remain the sole public MCP path.

`v0.4.2` adds SDK-negotiated interoperability while retaining AIP's existing strict direct per-request mode.

The default transport posture remains **stateless**. `v0.4.2` MUST NOT introduce server-side session state merely to satisfy an abstract lifecycle that no qualified client requires.

### 7.1 Stateless HTTP method contract

For the stateless release candidate, `POST` is the only supported method on `/mcp`.

| Method | Required behavior |
|---|---|
| `POST /mcp` | Supported. Carries AIP direct-envelope traffic and qualified SDK-negotiated MCP traffic. |
| `GET /mcp` | AIP ingress returns HTTP `405 Method Not Allowed` with `Allow: POST`; SDK is not invoked. |
| `DELETE /mcp` | AIP ingress returns HTTP `405 Method Not Allowed` with `Allow: POST`; SDK is not invoked. |
| `PUT`, `PATCH`, `OPTIONS`, and every other non-POST method | Same HTTP `405 Method Not Allowed` contract; SDK is not invoked. |
| `HEAD /mcp` | HTTP `405 Method Not Allowed` with `Allow: POST`; response body is empty as required by HEAD semantics; SDK is not invoked. |

For every non-POST method except `HEAD`, the response SHALL include `Content-Type: application/json` and the same fixed, sanitized JSON body equivalent to:

```json
{
  "error": {
    "code": "METHOD_NOT_ALLOWED",
    "message": "Only POST /mcp is supported in stateless mode."
  }
}
```

The body MUST:

- be bounded to at most 512 bytes;
- contain no stack trace;
- contain no reflected request payload;
- contain no session, credential, account, or internal infrastructure data.

Every non-POST request MUST be rejected **before** invoking the pinned SDK transport so the SDK cannot allocate an SSE stream, session lifecycle resource, or other transport resource.

`OPTIONS` has no special exemption in `v0.4.2`; it returns the same 405 contract. If browser/CORS preflight support is intentionally added later, that is a public transport-contract change and MUST be specified and tested explicitly first.

If later qualification establishes that GET/SSE, DELETE/session termination, OPTIONS/preflight, or another method is required by a supported client tuple, this contract MUST be revised explicitly in ADR 0014, this specification, normative MCP documentation, and tests before that tuple can be published as supported.

The negotiated path exists only to improve protocol interoperability.

It MUST expose:

```text
the same three tools
the same input schemas
the same output schemas
the same ArchitectureAnswer semantics
the same snapshot semantics
the same evidence references
the same limitations
the same qualification
the same error sanitization principles
the same zero-write guarantee
```

The negotiated path MUST NOT contain independent architecture logic.

---

## 8. Normative Routing Decision

AIP SHALL NOT implement a second general MCP protocol-era classifier.

The pinned MCP SDK remains authoritative for protocol-era recognition. AIP's ingress layer SHALL only enforce the additional routing/safety rules required to preserve the existing direct contract.

### 8.1 Exact direct-envelope markers

A request is classified as **direct mode** when at least one of the following AIP-specific direct-envelope markers is present:

```text
HTTP header: mcp-method
HTTP header: mcp-name
body: params._meta.io.modelcontextprotocol/protocolVersion
body: params._meta.io.modelcontextprotocol/clientCapabilities
```

`MCP-Protocol-Version` by itself is **not** a direct-mode discriminator.

An MCP session identifier by itself is also **not** a direct-mode discriminator.

### 8.2 Negotiated follow-up requirement

Only `initialize` MAY be markerless.

For every non-`initialize` request that has no AIP direct-envelope marker:

1. `MCP-Protocol-Version` MUST be present; and
2. the pinned SDK MUST recognize that value as a supported **handshake-era negotiated protocol version**.

AIP MUST derive this recognition from the pinned SDK's classifier/constants rather than maintain a competing hard-coded protocol-era list.

If `MCP-Protocol-Version` is missing on a markerless non-`initialize` request, AIP ingress MUST reject the request **before SDK tool dispatch** with:

```text
HTTP 400
Content-Type: application/json
bounded sanitized JSON error
```

The error body SHOULD identify that a negotiated follow-up requires `MCP-Protocol-Version`, without exposing internals.

If the header identifies the direct/single-exchange `2026-07-28` era but no direct-envelope markers are present, the request MUST also be rejected rather than delegated as a negotiated follow-up.

This closes the stateless markerless-follow-up bypass: a bare `tools/list` or `tools/call` MUST NOT become valid merely because the SDK would otherwise accept it.

### 8.3 Routing truth table

The following behavior is normative:

| HTTP/request shape | Route / expected behavior |
|---|---|
| `POST`, any AIP direct-envelope marker present | Existing strict direct validation ladder. No negotiated fallback. |
| `POST`, direct marker + malformed/missing direct `_meta` | Direct-path error according to existing validation order. No fallback. |
| `POST`, direct marker + mismatched `mcp-method` / body method | Direct-path error. No fallback. |
| `POST`, direct marker + unknown tool | Direct-path error. No fallback. |
| `POST`, direct marker + session identifier | Direct path wins. Session state MUST NOT relax direct validation. |
| `POST`, `initialize`, no direct-specific marker, no protocol header | Delegate to pinned SDK initialization. |
| `POST`, `initialize`, no direct-specific marker, protocol header present | Delegate to pinned SDK initialization/version handling. |
| `POST`, non-`initialize`, no direct marker, recognized handshake-era `MCP-Protocol-Version` | Delegate to pinned SDK negotiated handling. |
| `POST`, non-`initialize`, no direct marker, missing `MCP-Protocol-Version` | Reject before SDK tool dispatch. |
| `POST`, non-`initialize`, no direct marker, direct-era `2026-07-28` header | Reject; MUST NOT become negotiated traffic. |
| `POST`, non-`initialize`, no direct marker, unsupported/invalid protocol version | Use pinned SDK recognition/error semantics; MUST NOT reach tool dispatch. |
| `POST`, session identifier only, no direct marker, no recognized handshake-era version | Reject; session identifier alone is insufficient in stateless mode. |
| `POST`, malformed/non-object JSON + any direct-specific header (`mcp-method` or `mcp-name`) | Direct ingress ownership remains sticky; no negotiated fallback. The direct path owns the failure response. |
| `POST`, malformed/non-object JSON without a direct-specific header | Delegate immediately to the pinned SDK JSON/JSON-RPC parse handler. Do **not** apply the negotiated follow-up header requirement because no valid method has been extracted yet. |
| `GET /mcp` | AIP ingress returns HTTP 405 + `Allow: POST`; SDK is not invoked. |
| `DELETE /mcp` | AIP ingress returns HTTP 405 + `Allow: POST`; SDK is not invoked. |
| `HEAD /mcp` | AIP ingress returns HTTP 405 + `Allow: POST`, with an empty body; SDK is not invoked. |
| Any other non-POST method, including `PUT`, `PATCH`, and `OPTIONS` | Same bounded 405 rejection contract; SDK is not invoked. |

### 8.4 No silent downgrade

The governing rule is:

> **A malformed direct request MUST never become a valid negotiated request by falling through to a more permissive path.**

AIP-specific direct intent is sticky for the lifetime of that request.

A markerless non-`initialize` request also MUST NOT reach SDK tool dispatch unless it carries a pinned-SDK-recognized handshake-era `MCP-Protocol-Version`.

The negotiated follow-up header check runs **only after a valid JSON-RPC request method has been extracted**. If the body is malformed/non-object and no direct-specific header establishes direct ownership, the pinned SDK parse handler owns the request and its JSON-RPC parse error is the oracle. AIP MUST NOT replace that parse error with its missing-header 400.

Where the pinned SDK can own protocol-version recognition, negotiation, parsing, or lifecycle behavior, AIP SHOULD delegate to it rather than duplicate its rules.

---

## 9. Negotiated Lifecycle Coverage

The release SHALL preserve `stateless_http=True` unless black-box qualification establishes that a targeted client cannot interoperate without stateful server sessions.

The following are mandatory for every qualified client/platform tuple:

```text
negotiated initialization
tool discovery
get_architecture_drift
get_evidence at the returned snapshot
disconnect / client stop
reconnect / fresh initialization
```

The implementation MUST record the actual lifecycle exercised by each qualified client, including whether it uses:

```text
notifications/initialized
MCP session identifiers
session identifier reuse
GET / SSE
DELETE / session termination
other SDK-negotiated transport behavior
```

Session-ID behavior is **conditional**:

- If AIP/the pinned SDK does not issue a session ID and the qualified client does not require one, no session-ID creation/reuse/termination requirement exists.
- If AIP/the pinned SDK issues a session ID, its creation, reuse, invalid-ID handling, and normal termination behavior MUST be qualified.
- If a client requires stateful behavior that the current stateless configuration cannot provide, that is an architecture-impacting discovery. ADR 0014 and this specification MUST be updated before introducing stateful session behavior.

> **Client interoperability is mandatory; stateful sessions are not.**

---

## 10. Transport-State Semantics

Negotiated transport state, including any optional session state, is transport state only.

It MUST NOT become architecture state.

Transport/session state MUST NOT affect:

- qualification;
- claim identity;
- evidence identity;
- snapshot identity;
- observation context;
- tool semantics;
- ordering;
- graph contents.

Equivalent direct and negotiated requests over the same graph state and effective observation context MUST return semantically equivalent `structuredContent`.

No session identifier is required to establish or preserve Architecture Intelligence snapshot identity.

---

## 11. Cross-Mode Snapshot Interoperability

The following SHALL be tested explicitly.

### Case A — negotiated claim, direct evidence

```text
negotiated client
    get_architecture_drift
      -> snapshot S
      -> evidence_refs R

direct 2026-07-28 client
    get_evidence(snapshot S, R)

expected:
    success
```

### Case B — direct claim, negotiated evidence

```text
direct 2026-07-28 client
    get_architecture_drift
      -> snapshot S
      -> evidence_refs R

negotiated client
    get_evidence(snapshot S, R)

expected:
    success
```

This proves that connection mode does not create separate consistency domains.

---

## 12. Security Boundary

Origin and Host allow-listing MUST protect all supported `/mcp` methods and both connection modes.

The negotiated path MUST NOT bypass any existing transport-security checks.

The default deployment remains:

> **local / trusted-network evaluation only**

The release does not introduce authentication or TLS.

Documentation MUST state that exposing the unauthenticated local MCP endpoint directly to an untrusted network is unsupported.

---

## 13. Direct-Path Error Preservation

The existing direct path's validation and error-priority behavior SHALL remain regression-protected.

This includes at least:

- missing direct protocol metadata;
- header/body disagreement;
- unsupported direct protocol version;
- unknown method/tool;
- unexpected top-level tool arguments;
- invalid tool arguments;
- disallowed Origin;
- disallowed Host;
- malformed JSON;
- graph/service failures sanitized according to existing behavior.

The negotiated mode MUST NOT weaken these protections.

---

# Part II — Demo Mode for Real Coding Agents

## 14. New `--serve` Mode

Extend:

```bash
examples/runtime-demo/mcp-demo.sh
```

with:

```bash
examples/runtime-demo/mcp-demo.sh --serve
```

The mode prepares the exact deterministic demo state but stops before scripted MCP calls.

---

## 15. `--serve` Required Behavior

`--serve` SHALL:

1. validate required local tools;
2. validate Docker Compose availability;
3. validate `curl`;
4. validate `jq`;
5. validate the repository `.env`;
6. start AIP;
7. start Neo4j;
8. start the OpenTelemetry Collector;
9. import the bundled declared architecture;
10. seed the timestamp-frozen telemetry;
11. poll until the expected observed relations have landed;
12. verify the demo state is queryable;
13. stop before any scripted `tools/list` or `tools/call`;
14. leave the stack running;
15. print:
    - MCP endpoint,
    - Service Explorer URL,
    - service id,
    - environment,
    - frozen observation window,
    - client setup guide path,
    - teardown command.

---

## 16. Existing Demo Modes

Existing behavior SHALL remain:

```text
no argument
  -> prepare deterministic demo state
  -> run complete direct MCP walkthrough
  -> leave stack running

--serve
  -> prepare deterministic demo state
  -> stop before scripted MCP calls
  -> leave stack running

--down
  -> docker compose down -v

unknown argument
  -> exit 2 with usage

conflicting arguments
  -> exit 2 with usage
```

---

## 17. Demo Determinism

Repeated `--serve` execution against an already prepared local demo MUST remain semantically deterministic.

The qualification SHALL prove:

```text
no duplicate canonical relations
no duplicate semantic architecture claims
no changed qualification
no changed expected evidence meaning
```

Additionally:

> **The architecture-answer snapshot for the prepared deterministic demo SHALL remain semantically identical across repeated `--serve` preparation.**

If repeated seeding changes graph state or evidence identity in a way that changes the snapshot while preserving only the visible relation set, that is a failed idempotency condition and MUST be resolved or explicitly redesigned before release.

---

## 18. Demo Failure Behavior

Failures MUST be actionable.

At minimum cover:

- Docker unavailable;
- Docker Compose unavailable;
- missing `.env`;
- AIP health timeout;
- declaration import failure;
- telemetry seed failure;
- observed-evidence timeout;
- unexpected empty runtime relation set;
- invalid CLI argument;
- teardown failure.

The script MUST fail non-zero and identify the failing phase.

No silent partial demo state may be reported as ready.

---

# Part III — Client Examples

## 19. Client Example Location

Create:

```text
examples/mcp-clients/
```

Recommended structure:

```text
examples/mcp-clients/
├── README.md
├── codex.md
├── claude-code.md
├── cursor.md
└── vscode.md
```

Do NOT commit active root-level client configuration files merely to demonstrate onboarding.

Client examples are opt-in documentation.

---

## 20. Verification Rule for Client Syntax

Client configuration syntax changes independently of AIP.

Therefore:

> **Every configuration command and JSON fragment MUST be verified against the official current stable client documentation immediately before implementation and again before release qualification.**

A snippet SHALL NOT be documented as supported until black-box qualification passes.

---

## 21. Codex CLI

Candidate onboarding:

```bash
codex mcp add aip --url http://localhost:8000/mcp
codex mcp list
```

Candidate configuration:

```toml
[mcp_servers.aip]
url = "http://localhost:8000/mcp"
```

The exact supported syntax MUST be reverified before implementation.

---

## 22. Claude Code

The preferred first-run demo scope SHOULD be private/local to the current project, not a committed shared project configuration.

Candidate command:

```bash
claude mcp add --transport http --scope local   aip http://localhost:8000/mcp
```

A project-shared configuration MAY be documented separately in the detailed guide if current Claude Code behavior supports it.

Candidate project configuration:

```json
{
  "mcpServers": {
    "aip": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

The exact supported syntax and scope semantics MUST be reverified before implementation.

---

## 23. Cursor

Candidate project file:

```text
.cursor/mcp.json
```

Candidate content:

```json
{
  "mcpServers": {
    "aip": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

The exact supported syntax MUST be reverified before implementation.

---

## 24. VS Code

Candidate project file:

```text
.vscode/mcp.json
```

Candidate content:

```json
{
  "servers": {
    "aip": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

The exact supported syntax MUST be reverified before implementation.

---

## 25. Qualified Client/Platform Matrix

The client guide SHALL maintain a qualification matrix whose rows represent **tested platform tuples**, not client families in the abstract.

Each row MUST record at least:

```text
client name
client version
extension/plugin version where applicable
operating system
execution mode: native / WSL / container
AIP execution location
network topology / localhost relationship
configuration method
transport
verification date
AIP candidate SHA
MCP SDK version
observed lifecycle
actual-client trace reference
result
known tuple-specific limitations
```

For VS Code, the GitHub Copilot / agent extension version SHALL be recorded whenever that extension supplies or materially affects MCP behavior.

Example summary matrix:

| Client | Client version | Extension/plugin | OS | Execution | Network | Drift→Evidence | Reconnect | Status |
|---|---|---|---|---|---|---:|---:|---|
| Codex CLI | capture during qualification | n/a | capture | native/WSL/container | capture | PASS/FAIL | PASS/FAIL | PASS/FAIL |
| Claude Code | capture during qualification | n/a | capture | native/WSL/container | capture | PASS/FAIL | PASS/FAIL | PASS/FAIL |
| Cursor | capture during qualification | capture if applicable | capture | native/WSL/container | capture | PASS/FAIL | PASS/FAIL | PASS/FAIL |
| VS Code | capture during qualification | capture required when applicable | capture | native/WSL/container | capture | PASS/FAIL | PASS/FAIL | PASS/FAIL |

The documented tuple means:

> **verified with this exact combination**

It MUST NOT be described as a minimum supported version unless older-version boundary testing independently establishes that claim.

Other combinations SHALL be described as **unverified**, not implicitly supported.

---

# Part IV — README Onboarding

## 26. Placement

Add a compact section:

# Connect AIP to Your Coding Agent

after the five-minute demo's first visible outcome and before the detailed MCP reference.

The root README MUST remain compact.

Detailed setup and troubleshooting belong under:

```text
examples/mcp-clients/
```

---

## 27. README Flow

The section SHOULD follow this sequence:

1. start deterministic client-ready demo;
2. connect one coding-agent client;
3. run the supplied prompt;
4. state the deterministic expected architecture result;
5. link to the detailed compatibility matrix and setup guide.

Example:

```bash
cp .env.example .env
examples/runtime-demo/mcp-demo.sh --serve
```

Then show:

```text
MCP endpoint:
http://localhost:8000/mcp
```

and concise Codex / Claude Code commands.

Cursor and VS Code JSON SHOULD use collapsed `<details>` blocks if needed to keep the root README concise.

---

## 28. Supplied Prompt

The README SHALL provide a stable first prompt:

```text
Use AIP to find architecture drift for service:order-service in the demo
environment between 2026-08-26T00:00:00Z and 2026-08-27T00:00:00Z.

For every finding:
1. explain its qualification;
2. resolve its evidence using the same snapshot;
3. identify what AIP actually established;
4. do not infer facts AIP does not establish.
```

The exact timestamps printed by `--serve` SHALL match the prompt.

---

## 29. Expected Demo Result

The README MUST describe both deterministic drift findings.

### Finding 1

```text
LegacyPricingService
qualification: OBSERVED_ONLY
via: GET /pricing/{sku}
evidence: OpenTelemetry observation
```

Meaning:

> A runtime dependency was observed even though no declaration supports it.

The evidence SHALL resolve through `get_evidence` at the same snapshot.

### Finding 2

```text
unused-q
qualification: NOT_OBSERVED_IN_WINDOW
evidence: AsyncAPI declaration
```

Meaning:

> The dependency is declared but was not observed in the selected window.

AIP MUST NOT describe this as:

```text
unused
dead
obsolete
safe to remove
```

unless separate evidence exists.

This second finding demonstrates:

> **non-observation is not absence.**

---

## 30. README Caveats

The README SHALL state concisely:

- these instructions target locally executing clients;
- cloud/hosted agents generally cannot reach the user's `localhost`;
- AIP's local MCP endpoint is intended for local/trusted-network evaluation;
- unauthenticated public exposure is unsupported;
- AIP itself needs no LLM API key for correctness;
- the selected coding-agent client may require its normal account/model access.

---

# Part V — Qualification

## 31. Two Different Qualification Targets

`v0.4.2` MUST distinguish:

```text
A. deterministic transport interoperability

B. probabilistic agent workflow behavior
```

AIP release correctness MUST depend on A, not B.

---

## 32. Deterministic Interoperability — Release Gate

For each published qualified client/platform tuple, the release gate requires:

1. connect without undocumented custom headers or proxy adapters;
2. complete the actual negotiated initialization required by that client;
3. discover exactly three AIP tools;
4. execute `get_architecture_drift`;
5. receive the deterministic demo result;
6. obtain:
   - `LegacyPricingService`,
   - `OBSERVED_ONLY`,
   - `GET /pricing/{sku}`;
7. obtain `unused-q` as `NOT_OBSERVED_IN_WINDOW`;
8. execute `get_evidence` using the returned evidence references and the same snapshot;
9. preserve structured content;
10. disconnect/stop;
11. reconnect/reinitialize successfully.

### 32.1 Actual-client evidence is mandatory

A generic deterministic MCP harness MAY supplement server-level qualification, but it MUST NOT substitute for interoperability testing of the named client.

Each qualified tuple MUST produce protocol evidence from the **actual client** showing successful:

```text
initialization / negotiation
tools/list
get_architecture_drift
get_evidence at the same snapshot
disconnect/reconnect behavior
```

Acceptable evidence MAY include an HTTP/MCP protocol trace, client diagnostic log, or another reproducible capture that proves the traffic originated from the named client and reached the release candidate.

#### Trace sanitization and retention

Any qualification artifact committed to the repository or published with a release MUST be sanitized and bounded.

Committed/published artifacts MUST NOT contain:

- authorization headers or bearer tokens;
- cookies or `Set-Cookie` values;
- API keys, credentials, refresh tokens, or session secrets;
- client account identifiers, email addresses, or user IDs unless replaced with explicit placeholders;
- raw system prompts;
- unrelated conversation content;
- unrelated HTTP requests or traffic from other applications;
- secrets or private local paths not required to prove the qualification result.

A committed trace SHOULD contain only the minimum protocol evidence needed to establish:

```text
client identity/version
initialization/negotiation
tools/list
tool names
get_architecture_drift invocation/result shape
get_evidence invocation/result shape
snapshot continuity
disconnect/reconnect result
relevant HTTP status / MCP protocol metadata
```

Where a raw trace cannot safely be committed, the qualification record SHALL commit:

1. a sanitized/redacted excerpt or derived protocol summary; and
2. a SHA-256 hash of the raw capture when that hash is useful for audit correlation.

Raw captures MAY exist only in an ephemeral local/CI workspace excluded from version control. They MUST NOT be uploaded as CI artifacts or release artifacts unless sanitized first, and MUST be deleted after the sanitized qualification artifact has been produced and before the qualification run is considered complete.

If the client exposes MCP only through an LLM-driven UI, an explicit test prompt MAY be used to trigger the calls. The agent's prose quality and autonomous tool-selection quality remain non-gating; the release gate is the successful actual-client protocol interaction and deterministic AIP result.

### 32.2 Server harness remains useful

An independent deterministic harness SHOULD still qualify:

- direct-vs-negotiated semantic equivalence;
- negative/error cases;
- security checks;
- conditional session behavior;
- cross-mode snapshot interoperability.

It proves the server contract, not named-client compatibility.

---

## 33. Agent Workflow Qualification — UX Evidence

Separately, execute the supplied natural-language onboarding prompt in each client.

Record whether the agent:

- chooses AIP rather than answering from its own model knowledge;
- calls drift;
- notices both findings;
- preserves qualification meaning;
- calls evidence drill-down;
- keeps the same snapshot;
- avoids calling `unused-q` dead/unused/obsolete;
- distinguishes AIP's result from its own interpretation.

This is valuable product evidence but NOT a semantic release gate.

Reason:

> AIP correctness must not depend on a probabilistic agent selecting or explaining a tool perfectly.

---

## 34. Automated Protocol Tests

The automated suite SHALL prove:

### Direct path regression

- every existing valid direct call remains valid;
- direct validation ladder unchanged;
- direct error-priority behavior unchanged;
- malformed direct requests never fall through to negotiated mode;
- direct-specific marker truth-table cases from §8 are covered;
- `MCP-Protocol-Version` alone does not force direct mode;
- markerless `initialize` reaches the negotiated SDK path;
- markerless non-`initialize` `tools/list` is rejected;
- markerless non-`initialize` `tools/call` is rejected;
- negotiated follow-ups with a pinned-SDK-recognized handshake-era `MCP-Protocol-Version` reach the SDK;
- direct-era `2026-07-28` without direct-envelope markers is rejected as a negotiated follow-up;
- mixed direct/session requests follow §8;
- direct tool schemas unchanged;
- direct result schemas unchanged.

### Negotiated stateless path

- initialize succeeds;
- required initialized lifecycle succeeds;
- `tools/list` returns exactly three tools;
- each tool is callable;
- reconnect/fresh initialization succeeds;
- unknown methods fail safely;
- unknown tools fail safely;
- invalid arguments fail safely;
- disallowed Origins fail safely;
- disallowed Hosts fail safely;
- stateless `GET /mcp` returns HTTP 405, `Allow: POST`, bounded JSON, and allocates no SDK stream/session;
- stateless `DELETE /mcp` returns HTTP 405, `Allow: POST`, bounded JSON, and allocates no SDK stream/session;
- `PUT`, `PATCH`, `OPTIONS`, and every other non-POST method return the same 405 contract before SDK invocation;
- `HEAD /mcp` returns HTTP 405 + `Allow: POST` with an empty body and no SDK invocation;
- malformed/non-object JSON with a direct-specific header remains owned by the direct path;
- malformed/non-object JSON without a direct-specific header reaches the pinned SDK parse handler, with no negotiated-header precheck.

### Conditional session behavior

The following tests are REQUIRED **only if** AIP/the pinned SDK issues session identifiers or a published qualified client tuple requires them:

- session creation;
- session reuse;
- invalid-session handling;
- session termination;
- any required GET/SSE lifecycle;
- any required DELETE lifecycle.

No test or implementation requirement SHALL force stateful sessions when the qualified clients work with the stateless server.

### Semantic equivalence

For equivalent bound inputs:

```text
direct structuredContent
      ≡
negotiated structuredContent
```

Semantic comparison SHALL include:

- claims;
- qualification;
- evidence refs;
- snapshot identity;
- observation context;
- limitations;
- ordering where contractually deterministic.

### Write safety

For every supported transport path and method:

```text
graph writes caused by tools = 0
```

---

## 35. Cross-Mode Tests

Required integration tests:

```text
negotiated drift -> direct evidence
direct drift     -> negotiated evidence
```

Both MUST preserve the same snapshot and resolve the same evidence meaning.

---

## 36. Demo Tests

Cover:

- default mode;
- `--serve`;
- `--down`;
- invalid arguments;
- conflicting arguments;
- fresh `--serve`;
- repeated `--serve`;
- health timeout;
- evidence arrival timeout;
- declaration-import failure;
- actual printed endpoint;
- actual printed environment;
- actual printed service id;
- actual printed observation window;
- snapshot/idempotency invariant;
- existing complete hero demo remains valid;
- shell linting.

---

## 37. Client Qualification Record

For every published qualified client/platform tuple record:

```text
client name
client version
extension/plugin version where applicable
configuration method
transport
operating system
execution mode: native / WSL / container
AIP execution location
network topology / localhost relationship
verification date
AIP candidate SHA
AIP image digest if applicable
MCP SDK version
observed HTTP methods
observed initialization lifecycle
whether session IDs were issued or used
actual-client trace / diagnostic artifact reference
trace sanitization status
raw-capture retention/deletion status
deterministic drift->evidence result
reconnect result
known tuple-specific limitations
```

The record MUST distinguish:

```text
verified tuple
from
minimum supported version
from
unverified combinations
```

No minimum-version claim is allowed without explicit boundary testing.

A passing generic MCP harness result is insufficient to create a supported-client row.

---

# Part VI — Documentation and ADR

## 38. ADR Requirement

Create a new ADR recording the protocol decision.

Recommended title:

> **ADR 0014 — Support Negotiated MCP Client Interoperability Without Weakening the Direct 2026-07-28 Contract**

The ADR SHOULD capture:

- original v0.4 direct-only rationale;
- the real interoperability problem;
- preservation of `stateless_http=True` as the default;
- the rule that stateful sessions are introduced only if actual client qualification requires them;
- the exact AIP direct-envelope discriminator from §8;
- delegation of generic negotiation/protocol-era handling to the pinned SDK;
- the no-fallback rule for malformed direct traffic;
- `/mcp` as the sole public path and the allowed/conditional HTTP methods;
- transport-state-only semantics;
- same three tools;
- same architecture semantics;
- cross-mode snapshot interoperability;
- Origin/Host security posture;
- qualified client/platform tuple semantics;
- alternatives considered;
- consequences.

---

## 39. Historical Specifications

Historical v0.4 specifications MUST remain historically accurate.

Do NOT rewrite them to imply negotiated initialization was supported in the original release.

Instead:

```text
v0.4.x historical specification
    -> describes original direct-only contract

ADR 0014
    -> records the additive interoperability decision

v0.4.2 specification
    -> defines current dual-mode behavior

docs/mcp.md
    -> describes current supported behavior

CHANGELOG / release notes
    -> explain the compatibility extension
```

---

## 40. Normative MCP Documentation

Update `docs/mcp.md` so it no longer categorically states that AIP has no initialization handshake.

The current documentation SHOULD instead distinguish:

```text
Direct per-request mode
  - strict AIP 2026-07-28 direct-envelope contract
  - AIP-specific direct markers
  - deterministic validation ladder
  - no fallback after direct intent is established

Negotiated client mode
  - pinned-SDK initialization/negotiation
  - stateless by default
  - session IDs/lifecycle only when actually issued or required by a qualified client
```

The documentation MUST also define `/mcp` as the sole path and state the release's actual GET/POST/DELETE behavior.

Both modes MUST be described as exposing identical Architecture Intelligence semantics.

---

# Part VII — Release Invariants and Blockers

## 41. Public Contract and Release-Identity Invariants

`v0.4.2` MUST retain:

```text
tool count = 3

tool names:
- get_service_dependencies
- get_architecture_drift
- get_evidence

schema_version = "0.4"

graph writes through MCP = 0

LLM API key required by AIP = false
```

The release candidate MUST advertise and package itself consistently as:

```text
release version = "0.4.2"
producer.version = "0.4.2"
MCP server advertised version = "0.4.2"
```

The release gate SHALL verify version consistency across at least:

- `pyproject.toml`;
- the root project entry in `uv.lock`;
- `app.version.package_version()`;
- the MCP server's advertised version;
- the production-wired `Producer.version`;
- the Architecture Answer evaluator's producer;
- active version-bearing evaluation fixtures/artifacts where the current contract requires them;
- release documentation that is supposed to describe the candidate.

`tests/unit/test_release_version_consistency.py` (or its successor) SHALL pin `0.4.2` for the candidate and remain the executable release-version consistency owner.

The root README MUST NOT claim `v0.4.2` as the latest published release before publication is separately authorized and completed.

No fourth tool may be added as part of this release.

---

## 42. Architecture Semantics Invariants

The following MUST remain unchanged:

- `CONFIRMED`;
- `OBSERVED_ONLY`;
- `NOT_OBSERVED_IN_WINDOW`;
- observation-context meaning;
- telemetry-coverage meaning;
- evidence applicability;
- snapshot identity meaning;
- same-snapshot evidence drill-down;
- unresolved identity behavior;
- limitation vocabulary;
- direct dependency semantics;
- drift semantics.

---

## 43. Release Blockers

Any of the following blocks `v0.4.2`.

### Protocol regression

```text
existing valid direct request changes behavior
existing direct error precedence changes unintentionally
malformed direct request reaches negotiated dispatch after direct intent is established
MCP-Protocol-Version alone is incorrectly treated as AIP direct intent
markerless non-initialize tools/list or tools/call reaches SDK tool dispatch
direct-era 2026-07-28 without direct markers is accepted as negotiated follow-up
mixed direct/session request bypasses direct validation
stateful session behavior is introduced without an evidenced client requirement
any non-POST method does not return the defined 405 contract
any non-POST method reaches SDK stream/session allocation
malformed markerless JSON is rejected by AIP's negotiated-header check instead of the SDK parse handler
```

### Semantic regression

```text
direct and negotiated equivalent calls differ semantically
qualification differs by transport mode
evidence refs differ in meaning by transport mode
snapshot meaning differs by transport mode
limitation is lost or weakened
non-observation becomes absence
```

### Release identity regression

```text
package/release version != 0.4.2
MCP server advertised version != 0.4.2
Producer.version != 0.4.2
evaluator producer version != 0.4.2
active version-bearing release surfaces disagree
```

### Safety regression

```text
new MCP write path exists
graph writes caused by any supported tool > 0
Origin allowlist bypass exists
Host allowlist bypass exists
unknown tool can reach unvalidated architecture logic
```

### Client qualification failure

```text
no passing actual-client trace for a required Codex tuple
no passing actual-client trace for a required Claude Code tuple
no passing actual-client trace for a required Cursor tuple
no passing actual-client trace for a required VS Code tuple
published support claim is broader than the tested tuple
committed qualification trace contains prohibited sensitive data
raw unsanitized qualification capture is retained or uploaded contrary to policy
```

### Demo failure

```text
--serve cannot prepare deterministic state
repeated --serve changes semantic demo snapshot unexpectedly
README context differs from actual demo state
existing full direct hero demo regresses
```

---

## 43.1 Repository Hygiene

Before the `docs/specifications/0.4.2/` directory is committed, remove operating-system download metadata and other accidental filesystem artifacts.

At minimum, the worktree MUST NOT contain:

```text
*:Zone.Identifier
.DS_Store
Thumbs.db
```

The current review identified these files for removal:

```text
docs/specifications/0.4.2/aip-v0.4.2-i1-dual-mode-mcp-transport-v2.md:Zone.Identifier
docs/specifications/0.4.2/aip-v0.4.2-specification-updated-after-second-review.md:Zone.Identifier
```

Repository-hygiene artifacts are not part of the specification and MUST NOT be committed.

---

# Part VIII — Delivery Plan

## 44. Proposed Delivery Split

### I1 — Dual-Mode MCP Transport

Deliver:

```text
ADR 0014
exact direct-envelope marker definition
routing truth-table tests
pinned-SDK negotiated initialization
stateless-by-default interoperability
direct-path regression preservation
conditional session lifecycle only if qualification requires it
HTTP method behavior for POST / GET / DELETE
cross-mode semantic-equivalence tests
cross-mode snapshot/evidence tests
release-version consistency updated to 0.4.2
```

Exit capability:

> A negotiated MCP client and the existing direct `2026-07-28` caller can use the same `/mcp` path without semantic differences, validation bypass, or an unnecessary stateful-session redesign.

---

### I2 — Client-Ready Demo and Documentation

Deliver:

```text
mcp-demo.sh --serve
deterministic repeated-serve validation
examples/mcp-clients/
Codex setup
Claude Code setup
Cursor setup
VS Code setup
README onboarding section
docs/mcp.md current behavior
```

Exit capability:

> A new user can prepare the deterministic AIP demo and configure one targeted local coding client using documented copy-paste steps.

---

### I3 — Actual-Client Qualification and Release Preparation

Deliver:

```text
qualified client/platform tuple matrix
actual-client protocol traces for all four target client families
deterministic drift->evidence qualification
agent-workflow observation record
full unit/integration regression
full hero-demo regression
version-consistency gate for 0.4.2
README link validation
clean-checkout qualification
release blocker assessment
candidate identity
GO / NO-GO record
```

Exit capability:

> At least one explicitly published tuple for each target client family completes the deterministic architecture workflow against the exact release candidate without weakening the v0.4 architecture contract.

Release publication or tag creation requires separate owner authorization.

---

# Part IX — Definition of Done

## 45. Capability

- [ ] `/mcp` remains the sole public MCP path.
- [ ] `POST /mcp` supports both existing direct traffic and qualified negotiated client traffic.
- [ ] Existing direct `2026-07-28` callers still work.
- [ ] AIP-specific direct-envelope markers are defined exactly and tested.
- [ ] Direct malformed traffic cannot fall through into negotiated mode.
- [ ] `MCP-Protocol-Version` alone does not force direct mode.
- [ ] Negotiated initialization works for every published qualified client/platform tuple.
- [ ] The server remains stateless unless actual qualification proves stateful behavior is necessary.
- [ ] Session-ID lifecycle is tested only when IDs are actually issued or required.
- [ ] Stateless GET/DELETE behavior is explicitly tested and side-effect free.
- [ ] Exactly three tools are discovered.
- [ ] Every published qualified tuple can call drift.
- [ ] Every published qualified tuple can resolve evidence.
- [ ] Cross-mode evidence drill-down works both directions.
- [ ] Disconnect/reconnect succeeds.
- [ ] Actual-client protocol evidence exists for every published qualified tuple.

---

## 46. Semantics

- [ ] Direct and negotiated equivalent calls have zero semantic mismatches.
- [ ] Qualification mismatch count = 0.
- [ ] Evidence-link mismatch count = 0.
- [ ] Snapshot mismatch count = 0 for equivalent calls.
- [ ] Limitation mismatch count = 0.
- [ ] Graph writes through MCP = 0.
- [ ] Existing Architecture Answer evaluation remains green.

---

## 47. Demo

- [ ] `mcp-demo.sh --serve` works from a clean checkout.
- [ ] `--serve` prints the real endpoint and frozen context.
- [ ] repeated `--serve` is deterministic.
- [ ] default complete direct demo still passes.
- [ ] `--down` still passes.
- [ ] invalid arguments exit `2`.
- [ ] failure messages are actionable.

---

## 48. Documentation

- [ ] README contains "Connect AIP to Your Coding Agent".
- [ ] root README remains compact.
- [ ] Codex setup verified on a recorded client/platform tuple.
- [ ] Claude Code setup verified on a recorded client/platform tuple.
- [ ] Cursor setup verified on a recorded client/platform tuple.
- [ ] VS Code setup verified on a recorded client/platform tuple.
- [ ] extension/plugin versions are recorded where applicable.
- [ ] OS, native/WSL/container execution, and local network topology are recorded.
- [ ] versions are described as verified tuple components, not unproven minimums.
- [ ] combinations outside the qualified tuples are described as unverified.
- [ ] actual-client trace/diagnostic evidence is referenced for every published supported tuple.
- [ ] committed trace artifacts are sanitized and bounded.
- [ ] raw unsanitized captures are excluded from VCS and release/CI artifacts and deleted after sanitization.
- [ ] local/trusted-network caveat is explicit.
- [ ] hosted-agent localhost caveat is explicit.
- [ ] AIP's no-LLM-key requirement is distinguished from client account requirements.
- [ ] historical v0.4 spec remains unchanged.
- [ ] ADR 0014 exists.
- [ ] `docs/mcp.md` reflects current direct + negotiated, stateless-by-default behavior.
- [ ] `/mcp` HTTP method behavior is documented.
- [ ] release candidate identity is consistently `0.4.2` without prematurely claiming publication.

---

## 49. Release Quality

Before release preparation:

```text
unit tests                              PASS
integration tests                       PASS
architecture-answer evaluation          PASS
release-version consistency (0.4.2)     PASS
direct MCP regression                   PASS
routing truth-table tests               PASS
negotiated MCP integration              PASS
stateless HTTP method behavior          PASS
conditional session tests               PASS / NOT_APPLICABLE
cross-mode equivalence                  PASS
demo qualification                      PASS
four actual-client tuple qualifications PASS
actual-client trace evidence             PRESENT
README links                            PASS
shell lint                              PASS
dependency/security checks              PASS
clean worktree                          PASS
release blockers                        0
```

`conditional session tests = NOT_APPLICABLE` is valid only when the release candidate does not issue session IDs and none of the published qualified client tuples requires session state.

No release tag or publication SHALL be performed without separate authorization.

---

# Part X — Expected User Experience

## 50. Golden Path

A first-time user should be able to do:

```bash
git clone https://github.com/michaelegner/architecture-intelligence-platform.git
cd architecture-intelligence-platform
cp .env.example .env
examples/runtime-demo/mcp-demo.sh --serve
```

Then configure a supported client with:

```text
http://localhost:8000/mcp
```

Then ask:

```text
Use AIP to find architecture drift for service:order-service in the demo
environment between 2026-08-26T00:00:00Z and 2026-08-27T00:00:00Z.

For every finding, explain its qualification and resolve its evidence using
the same snapshot. Do not infer facts AIP does not establish.
```

The user should see AIP-backed architecture context equivalent to:

```text
LegacyPricingService
  OBSERVED_ONLY
  GET /pricing/{sku}
  evidence: OpenTelemetry

unused-q
  NOT_OBSERVED_IN_WINDOW
  evidence: AsyncAPI
  not "unused", "dead", or "obsolete"
```

The agent may add explanation, but the architecture claims themselves remain AIP's deterministic result.

---

## 51. Product Boundary

This release deliberately reinforces the AIP product boundary:

```text
Coding agent
    reason
    explain
    plan
    decide how to use context

AIP
    establish what architecture is supported by evidence
```

`v0.4.2` makes that boundary easier to consume.

It does not move the reasoning boundary.

---

## 52. Release Outcome

The release is successful when:

> **A new user can start AIP, connect a documented qualified Codex, Claude Code, Cursor, or VS Code client/platform tuple using standard MCP configuration, ask a real architecture question, receive the deterministic drift result, and resolve the evidence behind it — while the existing direct protocol, architecture semantics, snapshot guarantees, stateless-by-default transport posture, and read-only safety remain unchanged.**

A concise release statement is:

> **AIP v0.4.2 makes trusted architecture context directly usable from mainstream coding agents without changing what AIP considers architecturally established.**
