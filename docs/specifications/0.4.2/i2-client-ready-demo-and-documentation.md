# AIP v0.4.2 I2 — Client-Ready Demo and Documentation

**Status:** Draft  
**Release:** `v0.4.2`  
**Increment:** I2  
**Parent specification:** `docs/specifications/0.4.2/specification.md`  
**Depends on:** I1 — Dual-Mode MCP Transport  
**Proposed repository path:** `docs/specifications/0.4.2/i2-client-ready-demo-and-documentation.md`

---

## 1. Purpose

I2 turns the transport capability established by I1 into a reproducible, client-ready local onboarding flow.

The increment SHALL make it possible for a new user to:

1. prepare AIP's deterministic architecture demo without consuming it through the scripted direct MCP walkthrough;
2. leave AIP running at the local `/mcp` endpoint;
3. configure a targeted coding-agent client from documented examples;
4. ask one stable architecture question;
5. know the deterministic AIP result that should be obtained;
6. understand the local/trusted-network and evidence/qualification boundaries.

The governing principle is:

> **I2 makes the existing Architecture Intelligence capability easy to consume; it does not broaden what AIP claims to know.**

I2 is complete when the repository provides one deterministic preparation command and clear opt-in setup instructions for Codex CLI, Claude Code, Cursor, and VS Code, without making an interoperability support claim that belongs to I3.

---

## 2. Baseline

I2 assumes I1 has completed successfully.

The I2 baseline therefore includes:

- one public MCP path: `/mcp`;
- preserved direct `2026-07-28` mode;
- pinned-SDK negotiated mode;
- stateless transport by default;
- exactly three read-only MCP tools;
- unchanged `ArchitectureAnswer` semantics;
- direct/negotiated semantic equivalence;
- zero graph writes through MCP;
- explicit non-POST rejection behavior;
- Origin/Host transport protection;
- `0.4.2` candidate version identity;
- ADR 0014.

I2 SHALL NOT redesign any of these contracts.


The client-ready demo host prerequisites remain:

```text
Docker with Compose
curl
jq
repository .env
```

Python is intentionally **not** a host prerequisite; all AIP-aware fixture classification runs inside the application container.

---

## 3. Scope

I2 SHALL deliver:

```text
examples/runtime-demo/mcp-demo.sh --serve

deterministic repeated-serve validation

examples/mcp-clients/
  README.md
  codex.md
  claude-code.md
  cursor.md
  vscode.md

verified current client configuration syntax
  for documentation purposes

root README:
  "Connect AIP to Your Coding Agent"

stable onboarding prompt

deterministic expected-result explanation

docs/mcp.md:
  current direct + negotiated behavior
  stateless-by-default transport
  HTTP method behavior
  local/trusted-network boundary

documentation/link tests as appropriate
```

---

## 4. Non-Goals

I2 SHALL NOT:

- declare Codex CLI generally supported;
- declare Claude Code generally supported;
- declare Cursor generally supported;
- declare VS Code generally supported;
- publish qualified client/platform tuples;
- substitute documentation syntax checks for real-client interoperability qualification;
- produce I3 actual-client protocol traces;
- perform the I3 GO / NO-GO release assessment;
- publish or tag `v0.4.2`;
- add MCP tools;
- alter tool schemas;
- alter `ArchitectureAnswer`;
- alter qualification semantics;
- alter snapshot semantics;
- add graph writes;
- add authentication or TLS;
- support public-internet MCP deployment;
- add agent orchestration;
- make LLM behavior part of AIP correctness;
- add architecture discovery sources.

---

## 5. I2 Exit Capability

At I2 completion:

> **A new user can prepare the deterministic AIP demo with `--serve`, leave the MCP endpoint running, and configure one of the targeted coding-agent clients from repository documentation using current verified setup syntax.**

This is an onboarding capability.

It is **not yet a supported-client claim**.

That claim requires I3 black-box qualification using the actual named clients.

---

# Part I — Client-Ready Runtime Demo

## 6. New `--serve` Mode

Extend:

```bash
examples/runtime-demo/mcp-demo.sh
```

with:

```bash
examples/runtime-demo/mcp-demo.sh --serve
```

`--serve` SHALL prepare the same deterministic architecture state used by the existing hero demo, but SHALL stop before the scripted MCP calls.

The intended flow is:

```text
user
  |
  |  mcp-demo.sh --serve
  v
AIP + Neo4j + OTel Collector
  |
  | deterministic declarations + frozen telemetry
  v
prepared architecture state
  |
  | stop here
  v
user connects coding-agent client
```

---

## 7. `--serve` Required Behavior

`--serve` SHALL execute these phases in order:

1. validate command-line arguments;
2. validate Docker availability;
3. validate Docker Compose availability;
4. validate `curl`;
5. validate `jq`;
6. validate repository `.env`;
7. start the required demo stack through Docker Compose;
8. wait explicitly for Neo4j readiness;
9. wait explicitly for AIP readiness;
10. run `"${COMPOSE[@]}" exec -T architecture-intelligence python examples/runtime-demo/check_fixture_state.py --json` and read its exact `EMPTY`, `COMPLETE`, or `PARTIAL_OR_INCOMPATIBLE` classification;
11. if `EMPTY`:
    - import the bundled declared architecture;
    - submit the timestamp-frozen telemetry fixture exactly once;
    - poll until every expected observed architecture relation has landed;
12. if `COMPLETE`:
    - skip declaration re-import;
    - skip telemetry submission;
    - perform no fixture mutation;
13. if `PARTIAL_OR_INCOMPATIBLE`:
    - fail non-zero;
    - print cleanup/retry guidance;
    - do not attempt implicit repair;
14. verify that the final deterministic demo state is complete and queryable;
15. verify the expected observation window;
16. stop **before** scripted `tools/list`;
17. stop **before** scripted `tools/call`;
18. leave the stack running;
19. print the client-ready connection information.

Docker Compose owns container dependency/start ordering. The specification owns the readiness gates and fixture-state checks that must pass before the next demo phase begins.

I2 defines no separate OpenTelemetry Collector health endpoint or healthcheck. For a newly prepared fixture, **successful telemetry fixture submission plus arrival of every expected observed relation** is the functional readiness proof for the demo telemetry path.

The mode MUST NOT silently proceed after a failed phase.

---

## 8. Required `--serve` Output

Successful preparation SHALL print a concise final block containing at least:

```text
AIP demo is ready.

MCP endpoint:
http://localhost:8000/mcp

Service Explorer:
http://localhost:8000

Service:
service:order-service

Environment:
demo

Observation window:
2026-08-26T00:00:00Z
2026-08-27T00:00:00Z

Client setup:
examples/mcp-clients/README.md

Stop demo:
examples/runtime-demo/mcp-demo.sh --down
```

The exact formatting is implementation-owned.

The values are not.

The printed service identifier, environment, and observation window MUST match the onboarding prompt documented in the README.

---

## 9. Existing Demo Modes

Existing behavior SHALL remain available.

```text
mcp-demo.sh
  -> prepare deterministic demo state
  -> execute complete direct MCP walkthrough
  -> leave stack running

mcp-demo.sh --serve
  -> prepare deterministic demo state
  -> execute no scripted MCP client calls
  -> leave stack running

mcp-demo.sh --down
  -> docker compose down -v

unknown option
  -> print usage
  -> exit 2

conflicting modes/options
  -> print usage
  -> exit 2
```

I2 MUST NOT make `--serve` the default and MUST NOT change the existing no-argument hero-demo semantics.

---

## 10. Argument Contract

The script SHALL accept only the documented modes for this release.

At minimum:

```text
no argument
--serve
--down
```

Examples that MUST fail with exit code `2`:

```text
--serve --down
--unknown
serve
--serve extra
```

The usage output MUST remain short and deterministic.

---

## 11. No Scripted MCP Calls in `--serve`

After preparation succeeds, `--serve` MUST NOT issue:

```text
tools/list
get_service_dependencies
get_architecture_drift
get_evidence
```

or any other MCP call on behalf of the user.

Reason:

> The next MCP caller must be the user's coding-agent client.

A health/readiness probe that is not an MCP architecture-tool invocation MAY be used if required to prove service readiness.

---

# Part II — Deterministic Prepared State

## 12. Demo Fixture

I2 SHALL reuse the deterministic bundled demo used by the existing MCP hero walkthrough.

It SHALL continue to establish the architecture state needed for these two drift findings.

### 12.1 Observed-only dependency

```text
service:order-service
  -> LegacyPricingService

via:
GET /pricing/{sku}

qualification:
OBSERVED_ONLY
```

This relationship is established from the frozen OpenTelemetry observation.

### 12.2 Declared but not observed dependency

```text
service:order-service
  -> unused-q

qualification:
NOT_OBSERVED_IN_WINDOW
```

This relationship is established from the AsyncAPI declaration and the selected observation window.

AIP SHALL NOT reinterpret it as:

```text
unused
dead
obsolete
safe to remove
```

---

## 13. Existing Confirmed Dependencies

The prepared state SHALL continue to contain the existing confirmed demo relationships such as:

```text
ProductService
PaymentService / payment-q
```

where supported by both declared and observed evidence.

These confirmed matches are not drift findings and therefore need not be returned by `get_architecture_drift`.

They remain available through `get_service_dependencies`.

---

## 14. Frozen Observation Window

The client-ready demo SHALL use one deterministic, timestamp-frozen observation window.

The intended window is:

```text
2026-08-26T00:00:00Z
through
2026-08-27T00:00:00Z
```

If the fixture's canonical window changes before implementation, all of the following MUST change together:

- telemetry fixture;
- `--serve` printed output;
- README prompt;
- client guide prompt;
- expected-result documentation;
- deterministic tests.

A stale timestamp in onboarding documentation is a release defect.

---

## 15. Repeated `--serve` Idempotency and Exact Fixture Oracle

Repeated `--serve` MUST be idempotent by **detecting and reusing an exactly complete fixture**, not by re-ingesting the same telemetry.

This is required because repeated ingestion changes snapshot-relevant aggregate state such as `observation_count`.

I2 SHALL add:

```text
examples/runtime-demo/fixture-state.json
examples/runtime-demo/check_fixture_state.py
```

These two files define the single normative classification oracle.

### 15.1 Normative `fixture-state.json`

The manifest MUST freeze the complete acceptable one-seed demo state.

It SHALL contain exact values for at least:

```text
manifest_version
fixture_id
service_id
environment
window_start
window_end
seed_timestamp

expected_snapshot_id
total_node_count
total_relationship_count

declared_relations[]:
  relation_type
  source_id
  target_id
  evidence_ids

observed_relations[]:
  relation_type
  source_id
  target_id
  via identity where applicable
  evidence_ids

evidence[]:
  id
  evidence_type
  source_type
  source_locator
  environment where applicable
  bucket/window identity where applicable
  observation_count where applicable
  first_seen where applicable
  last_seen where applicable
  sample_trace_ids where snapshot-relevant

expected_drift_claims[]:
  subject
  target/dependency
  via
  qualification
  evidence_refs
```

Every listed value is exact.

The manifest MUST NOT use:

```text
>=
at least
non-empty
contains
wildcards
prefix-only evidence matching
```

for any field that can change the canonical snapshot or distinguish one seed from two.

The manifest MUST be produced from one clean demo preparation and reviewed against:

- the bundled `examples/` declarations;
- `seed_frozen_evidence.py`;
- the resulting canonical snapshot state.

It MUST then be committed and treated as a versioned fixture contract.

The runtime classifier MUST NOT rewrite or regenerate this manifest.

### 15.2 Whole-database ownership

The deterministic local demo owns its Neo4j target database.

`EMPTY` means exactly:

```text
total graph nodes = 0
total graph relationships = 0
```

Indexes/constraints are schema metadata and do not count as graph data.

Therefore a database containing unrelated graph data is **not** `EMPTY`.

`COMPLETE` means exactly:

```text
actual snapshot_id          = manifest expected_snapshot_id
actual total node count     = manifest total_node_count
actual relationship count   = manifest total_relationship_count
actual declared relations   = manifest declared_relations
actual observed relations   = manifest observed_relations
actual evidence records     = manifest evidence
actual drift claims         = manifest expected_drift_claims
additional graph state      = none
```

Set/list comparison SHALL use deterministic canonical ordering.

Anything else that can be queried successfully is:

```text
PARTIAL_OR_INCOMPATIBLE
```

That includes:

- unrelated nodes or relationships;
- incomplete import;
- incomplete telemetry ingestion;
- duplicated telemetry ingestion;
- `observation_count` different from the manifest;
- `first_seen` / `last_seen` different from the manifest;
- `sample_trace_ids` different from the manifest;
- an extra or missing evidence record;
- an extra or missing canonical relation;
- any snapshot mismatch.

### 15.3 Canonical checker

The checker SHALL be read-only and SHALL run inside the already running `architecture-intelligence` container.

The canonical invocation is:

```bash
"${COMPOSE[@]}" exec -T architecture-intelligence python examples/runtime-demo/check_fixture_state.py --json
```

where the demo script already defines:

```bash
COMPOSE=(docker compose -f "${REPO_ROOT}/docker-compose.demo.yml")
```

This boundary is normative. I2 MUST NOT add host Python, a host Neo4j driver, or host-installed AIP dependencies as prerequisites.

The application image provides Python and project dependencies, and `docker-compose.demo.yml` exposes the repository `examples/` tree inside that container at `/app/examples:ro`, so the checker and its manifest are available through the same Docker-only runtime boundary as the rest of the demo.

The machine-readable output SHALL contain:

```json
{
  "fixture_id": "runtime-demo-frozen-2026-08-26",
  "classification": "EMPTY | COMPLETE | PARTIAL_OR_INCOMPATIBLE",
  "expected_snapshot_id": "aip:snapshot:v1:...",
  "actual_snapshot_id": "aip:snapshot:v1:... | null",
  "mismatches": []
}
```

`mismatches` SHALL contain stable machine-readable mismatch codes plus bounded human-readable details for failed predicates.

At minimum define:

```text
UNEXPECTED_GRAPH_DATA
SNAPSHOT_MISMATCH
NODE_COUNT_MISMATCH
RELATIONSHIP_COUNT_MISMATCH
DECLARED_RELATION_MISMATCH
OBSERVED_RELATION_MISMATCH
EVIDENCE_MISMATCH
OBSERVATION_COUNT_MISMATCH
FIRST_SEEN_MISMATCH
LAST_SEEN_MISMATCH
TRACE_SAMPLE_MISMATCH
DRIFT_CLAIM_MISMATCH
```

The checker MUST:

- perform zero graph writes;
- never import declarations;
- never submit telemetry;
- never normalize or repair graph state;
- use the checked-in manifest as its expected state;
- return deterministic ordering.

### 15.4 `--serve` branching

Before any fixture mutation, `--serve` SHALL call the canonical checker through:

```bash
"${COMPOSE[@]}" exec -T architecture-intelligence python examples/runtime-demo/check_fixture_state.py --json
```

No host-side Python invocation is permitted.

Required branching:

```text
EMPTY
  -> import declarations once
  -> submit frozen telemetry once
  -> wait for expected observed relations
  -> rerun checker
  -> succeed only when checker returns COMPLETE

COMPLETE
  -> skip declaration re-import
  -> skip telemetry submission
  -> perform no fixture mutation
  -> reuse prepared state

PARTIAL_OR_INCOMPATIBLE
  -> fail non-zero
  -> no import
  -> no reseed
  -> print:
       examples/runtime-demo/mcp-demo.sh --down
  -> instruct user to prepare a clean fixture
```

For:

```bash
examples/runtime-demo/mcp-demo.sh --serve
examples/runtime-demo/mcp-demo.sh --serve
```

required:

```text
first run starts from EMPTY
first run ends COMPLETE
second run starts COMPLETE
fixture mutations on second run = 0
telemetry submissions on second run = 0
semantic mismatch count = 0
snapshot_after_run_1 = snapshot_after_run_2
```

---

## 16. Clean-State Determinism

I2 SHALL also prove:

```text
clean preparation A
clean preparation B
```

produce the same expected:

- service identity;
- drift qualifications;
- evidence meaning;
- observation context;
- architecture snapshot identity where the existing deterministic snapshot contract requires it.

This does not expand existing byte-identity claims beyond the already qualified surfaces.

---

# Part III — Failure Behavior

## 17. Failure Phases

At minimum, `--serve` SHALL detect and report:

- unsupported/invalid CLI arguments;
- Docker unavailable;
- Docker Compose unavailable;
- `curl` unavailable;
- `jq` unavailable;
- missing `.env`;
- invalid required `.env` configuration;
- Neo4j readiness timeout;
- AIP readiness timeout;
- deterministic fixture classified as `PARTIAL_OR_INCOMPATIBLE`;
- declaration import failure;
- telemetry fixture submission failure;
- expected observed relation timeout after successful telemetry submission;
- unexpected empty demo architecture state;
- failed deterministic state verification.

`--down` SHALL detect Docker Compose teardown failure, report it actionably, and exit non-zero.

There is no separate OpenTelemetry Collector readiness timeout in I2. The functional readiness oracle is successful fixture submission followed by arrival of every expected observed relation.

The script SHALL exit non-zero on failure.

---

## 18. Failure Message Requirements

Failure output SHALL identify the phase, for example:

```text
ERROR: AIP did not become healthy within 60s.
```

or:

```text
ERROR: frozen telemetry was submitted but the expected observed dependency did not appear.
```

Failure messages SHOULD tell the user the next useful local action when one is known.

They MUST NOT:

- claim the demo is ready;
- expose credentials;
- dump unbounded container logs;
- contain unrelated application output.

---

## 19. Partial State

A failed `--serve` run MAY leave containers running if preserving logs materially helps debugging.

If so, the failure output MUST print:

```bash
examples/runtime-demo/mcp-demo.sh --down
```

as the cleanup command.

The script MUST NOT report a partial preparation as successful.

---

# Part IV — Client Documentation

## 20. Directory

Create:

```text
examples/mcp-clients/
```

with:

```text
examples/mcp-clients/
├── README.md
├── codex.md
├── claude-code.md
├── cursor.md
└── vscode.md
```

The directory contains documentation and opt-in examples only.

I2 SHALL NOT commit active root-level configuration that silently connects a developer's client to AIP.

Examples of files that MUST NOT be added merely for documentation:

```text
/.cursor/mcp.json
/.vscode/mcp.json
/.mcp.json
```

unless a later explicit product decision chooses committed project configuration.

---

## 21. Documentation Status Language

Until I3 completes actual-client qualification, the I2 documentation MUST use wording such as:

```text
Candidate setup
Configuration syntax verified against current official documentation
Interoperability qualification pending I3
```

It MUST NOT use unqualified wording such as:

```text
Supported on all platforms
Works with every version
Minimum supported version
Fully compatible
Certified
```

I2 verifies onboarding syntax and documentation coherence.

I3 verifies real client interoperability.

---

## 22. Client Guide README

`examples/mcp-clients/README.md` SHALL contain:

1. prerequisite: I1-capable AIP `v0.4.2` candidate;
2. start command:
   ```bash
   examples/runtime-demo/mcp-demo.sh --serve
   ```
3. MCP endpoint:
   ```text
   http://localhost:8000/mcp
   ```
4. links to:
   - Codex CLI;
   - Claude Code;
   - Cursor;
   - VS Code;
5. the stable onboarding prompt;
6. deterministic expected findings;
7. local/trusted-network caveat;
8. hosted/cloud-agent localhost caveat;
9. statement that configuration syntax is verified but support qualification belongs to I3;
10. teardown command.

I2 client documentation SHALL link only to the candidate setup guides in `examples/mcp-clients/`.

It MUST NOT publish or link a qualified client/platform compatibility matrix.

I3 owns that matrix and MUST add the qualified-matrix link to the README/client documentation after actual-client qualification is complete.

---

## 23. Client Syntax Verification Rule

Client setup syntax is external and version-sensitive.

Therefore:

> **Every command and configuration fragment documented by I2 MUST be checked against the official stable documentation for that client immediately before implementation and recorded as verified.**

Verification SHALL be repeated during I3 release qualification.

The verification evidence MUST be recorded in:

```text
docs/specifications/0.4.2/i2-completion-record.md
```

For every documented client family, that record MUST contain:

```text
client
official documentation source URL
verification date
stable client version observed/documented where available
configuration syntax verified
scope semantics verified where applicable
verification result: PASS / FAIL
candidate commit SHA
notes
```

The source URL, verification date, candidate SHA, and result are mandatory.

Syntax verification is not interoperability qualification.

---

## 24. Codex CLI Guide

The Codex guide SHALL document the simplest current stable HTTP MCP setup verified from official documentation.

The parent specification currently carries this candidate:

```bash
codex mcp add aip --url http://localhost:8000/mcp
codex mcp list
```

and candidate configuration:

```toml
[mcp_servers.aip]
url = "http://localhost:8000/mcp"
```

I2 SHALL NOT copy these blindly.

Before committing the guide:

1. verify current official Codex CLI MCP documentation;
2. use the current stable syntax;
3. document where the configuration is stored or scoped if relevant;
4. include removal/cleanup instructions if the client changes persistent user configuration;
5. state that actual interoperability qualification is pending I3.

---

## 25. Claude Code Guide

The preferred onboarding SHOULD avoid committing shared project configuration during the first run.

The parent specification's candidate is:

```bash
claude mcp add --transport http --scope local aip http://localhost:8000/mcp
```

I2 SHALL verify current official Claude Code documentation before using it.

The guide SHALL explain the selected scope.

Preferred principle:

> **The first AIP onboarding should be local/private unless the user explicitly wants a shared project configuration.**

If current Claude Code terminology differs, use the current official terminology.

The guide SHALL include cleanup/removal instructions.

---

## 26. Cursor Guide

The parent specification currently identifies this candidate project configuration location:

```text
.cursor/mcp.json
```

with candidate content:

```json
{
  "mcpServers": {
    "aip": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

I2 SHALL reverify:

- the current filename/location;
- required top-level keys;
- HTTP transport fields;
- whether project-local and user-local forms differ;
- whether a reload/restart is required.

The repository SHALL show the fragment in documentation, not create an active `.cursor/mcp.json` by default.

---

## 27. VS Code Guide

The parent specification currently identifies this candidate:

```text
.vscode/mcp.json
```

with:

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

I2 SHALL reverify current official VS Code MCP documentation.

The guide SHALL explicitly distinguish:

- VS Code version;
- any GitHub Copilot/agent extension requirement relevant to MCP;
- workspace/project configuration;
- user configuration if documented;
- reload/activation steps where required.

The repository SHALL not create an active workspace MCP file for users merely to provide the example.

---

# Part V — Stable Onboarding Workflow

## 28. Canonical User Flow

All four guides SHOULD converge on the same AIP-side workflow:

```text
1. clone / enter repository
2. cp .env.example .env
3. run mcp-demo.sh --serve
4. configure client -> http://localhost:8000/mcp
5. use supplied architecture prompt
6. inspect the two deterministic drift findings
7. resolve evidence
8. optionally inspect Service Explorer
9. tear down with --down
```

Client-specific mechanics may differ.

AIP semantics MUST not.

---

## 29. Stable Prompt

The canonical onboarding prompt SHALL be:

```text
Use AIP to find architecture drift for service:order-service in the demo
environment between 2026-08-26T00:00:00Z and 2026-08-27T00:00:00Z.

For every finding:
1. explain its qualification;
2. resolve its evidence using the same snapshot;
3. identify what AIP actually established;
4. do not infer facts AIP does not establish.
```

If the demo observation window changes, this prompt MUST change atomically with the fixture and printed `--serve` output.

---

## 30. Expected Result

Documentation SHALL tell the user what deterministic AIP data should be available, without pretending that an LLM will phrase it identically.

### Finding A

```text
dependency:
LegacyPricingService

qualification:
OBSERVED_ONLY

via:
GET /pricing/{sku}

evidence:
OpenTelemetry observation
```

Meaning:

> A runtime dependency was observed for which AIP has no corresponding declaration.

### Finding B

```text
dependency:
unused-q

qualification:
NOT_OBSERVED_IN_WINDOW

evidence:
AsyncAPI declaration
```

Meaning:

> The dependency is declared but was not observed in the selected runtime window.

The documentation SHALL explicitly state:

```text
NOT_OBSERVED_IN_WINDOW
!=
unused
!=
dead
!=
obsolete
!=
safe to remove
```

---

## 31. Evidence Drill-Down

The onboarding path SHALL make the expected evidence workflow explicit:

```text
get_architecture_drift
        |
        | snapshot S
        | evidence refs R
        v
get_evidence(snapshot S, R)
```

The user-facing explanation SHOULD emphasize:

> **The evidence call is not a second independent guess. It resolves provenance for the claim at the same architecture snapshot.**

No onboarding guide shall recommend resolving evidence without preserving the returned snapshot identity.

---

## 32. Probabilistic Client Behavior

The supplied prompt is intended to encourage an agent to use AIP correctly.

However:

- an LLM may choose tools differently;
- an LLM may phrase explanations differently;
- an LLM may need a follow-up instruction;
- client model behavior is not deterministic.

I2 documentation MUST distinguish:

```text
deterministic:
AIP tool semantics and demo data

probabilistic:
whether/how the coding agent chooses and explains those tools
```

I2 completion MUST NOT depend on a model producing one exact natural-language answer.

---

# Part VI — Root README

## 33. New Section

Add a compact root README section:

```markdown
## Connect AIP to Your Coding Agent
```

The section SHALL appear after the five-minute demo's visible proof/result and before the detailed MCP reference.

The exact final placement MAY account for the current README structure, but the intended conversion flow is:

```text
see proof
  ↓
run deterministic demo
  ↓
prepare --serve
  ↓
connect coding agent
  ↓
ask architecture question
  ↓
inspect evidence
```

---

## 34. README Size Budget

The root README MUST remain a landing page.

The new section SHOULD contain only:

- `--serve` command;
- endpoint;
- one compact Codex example;
- one compact Claude Code example;
- Cursor/VS Code links or collapsed examples;
- stable prompt;
- short deterministic expected result;
- link to `examples/mcp-clients/`.

Detailed troubleshooting MUST remain outside the root README.

I2 SHOULD avoid adding more than approximately 50–70 visible lines to the README before collapsed content.

This is a presentation budget, not a semantic contract.

---

## 35. README Example Shape

A suitable structure is:

```markdown
## Connect AIP to Your Coding Agent

Prepare the deterministic demo without running the scripted MCP calls:

```bash
examples/runtime-demo/mcp-demo.sh --serve
```

AIP is now available at:

`http://localhost:8000/mcp`

### Codex CLI
...

### Claude Code
...

<details>
<summary>Cursor / VS Code</summary>
...
</details>

Ask:

> Use AIP to find architecture drift for ...

Expected AIP findings:

- `LegacyPricingService` — `OBSERVED_ONLY`
- `unused-q` — `NOT_OBSERVED_IN_WINDOW`

[Detailed client setup →](examples/mcp-clients/README.md)
```

The final README copy SHALL use only client syntax verified under §23.

---

## 36. README Support Language

Before I3 completes, the README MUST NOT imply a broader support guarantee than exists.

Permitted:

> “Configure a targeted coding-agent client using the examples below.”

Permitted:

> “Client setup syntax is verified; release qualification is recorded separately.”

Avoid before I3:

> “AIP supports every Codex/Claude/Cursor/VS Code installation.”

I2 SHALL link only to candidate setup guides.

When I3 completes actual-client qualification, I3 MUST update the README to point to the qualified client/platform tuple matrix.

---

# Part VII — MCP Documentation

## 37. `docs/mcp.md`

I2 SHALL update `docs/mcp.md` to reflect the I1 transport contract.

It SHALL distinguish:

### Direct mode

```text
strict AIP direct per-request contract
direct-envelope markers
2026-07-28 direct path
no downgrade after direct intent
```

### Negotiated mode

```text
pinned SDK initialization
recognized negotiated follow-up protocol header
stateless by default
session lifecycle only if explicitly required/qualified
```

---

## 38. HTTP Method Documentation

`docs/mcp.md` SHALL state the current stateless method contract:

```text
POST /mcp
  supported

GET /mcp
DELETE /mcp
PUT /mcp
PATCH /mcp
OPTIONS /mcp
other non-POST methods
  -> HTTP 405
  -> Allow: POST
  -> bounded sanitized JSON
  -> rejected before SDK invocation

HEAD /mcp
  -> HTTP 405
  -> Allow: POST
  -> empty body
  -> rejected before SDK invocation
```

The documentation MUST NOT describe GET/SSE or DELETE lifecycle support unless the actual release contract changes.

---

## 39. Three-Tool Boundary

`docs/mcp.md` and all onboarding documentation SHALL continue to expose exactly:

```text
get_service_dependencies
get_architecture_drift
get_evidence
```

No I2 documentation may invent:

- generic Cypher tools;
- transitive dependency tools;
- write tools;
- policy tools;
- assertion-verification tools.

---

## 40. Local Security Boundary

All client documentation SHALL state clearly:

- the demo is for local/trusted-network use;
- `/mcp` has no public-internet authentication in `v0.4.2`;
- do not expose the endpoint directly to an untrusted network;
- AIP needs no LLM API key for its deterministic MCP correctness path;
- the coding-agent client may require its own account or model access.

---

## 41. Localhost Boundary

The documentation SHALL distinguish local clients from hosted agents.

Required message:

> **A client running on the user's machine can normally reach `http://localhost:8000/mcp`. A hosted/cloud agent usually cannot reach the user's localhost without an explicit networking mechanism, which is outside the v0.4.2 scope.**

I2 MUST NOT introduce tunneling or public endpoint instructions as a workaround.

---

# Part VIII — Verification

## 42. Script Tests

Automated or deterministic shell-level tests SHALL cover at least:

```text
no args                existing hero flow preserved
--serve on EMPTY       prepare once and stop-before-MCP behavior
--serve on COMPLETE    no reseed / no mutation / same snapshot
--serve on PARTIAL     non-zero, no implicit repair
--down                 successful teardown
--down teardown error  non-zero with actionable failure message
unknown option         exit 2
conflict               exit 2
missing .env           non-zero
missing command        non-zero where feasibly testable
```

The exact shell test framework is implementation-owned.

---

## 43. `--serve` No-MCP Assertion

I2 SHALL provide executable evidence that `--serve` does not perform scripted MCP tool calls.

Acceptable strategies include:

- test-double endpoint;
- captured request log;
- shell function interception;
- deterministic server request audit.

The proof MUST distinguish ordinary health/API setup requests from MCP `tools/list` / `tools/call`.

---

## 44. Prepared-State Verification

After `--serve`, a deterministic test/harness SHALL verify the expected AIP-side state.

At minimum:

```text
service:order-service exists

LegacyPricingService
  OBSERVED_ONLY
  via GET /pricing/{sku}

unused-q
  NOT_OBSERVED_IN_WINDOW

expected observation context exists
```

This verification MAY use the deterministic MCP harness established by I1.

It SHALL NOT rely on a coding agent or LLM.

---

## 44.1 Checker Runtime Boundary Test

I2 SHALL prove that fixture classification works on a clean host that satisfies only the documented demo prerequisites:

```text
Docker + Docker Compose
curl
jq
.env
```

The test MUST invoke the checker through:

```bash
"${COMPOSE[@]}" exec -T architecture-intelligence python examples/runtime-demo/check_fixture_state.py --json
```

It MUST NOT rely on:

```text
host python
host uv
host neo4j driver
host project virtualenv
```

The same container-bound command SHALL be used by `mcp-demo.sh --serve`, deterministic fixture tests, and the completion qualification.

---

## 45. Repeated-Serve Test

A deterministic test SHALL:

1. start from an `EMPTY` fixture;
2. run `--serve`;
3. prove the fixture is now `COMPLETE`;
4. record snapshot/expected architecture result;
5. run `--serve` again without teardown;
6. prove the second run classified the fixture as `COMPLETE`;
7. prove the second run submitted no telemetry and performed no fixture mutation;
8. record snapshot/expected architecture result again;
9. compare.

Required:

```text
telemetry submissions on first run = 1
telemetry submissions on second run = 0
fixture mutations on second run = 0
semantic mismatch count = 0
unexpected duplicate facts = 0
unexpected duplicate relations = 0
snapshot_after_run_1 = snapshot_after_run_2
```

Negative classifier tests SHALL prove at least:

```text
one unrelated graph node                    -> PARTIAL_OR_INCOMPATIBLE
partial declared fixture                    -> PARTIAL_OR_INCOMPATIBLE
partial observed fixture                    -> PARTIAL_OR_INCOMPATIBLE
double-seeded observation_count             -> PARTIAL_OR_INCOMPATIBLE
changed first_seen/last_seen                 -> PARTIAL_OR_INCOMPATIBLE
changed sample_trace_ids                     -> PARTIAL_OR_INCOMPATIBLE
extra canonical relation                     -> PARTIAL_OR_INCOMPATIBLE
missing expected evidence                    -> PARTIAL_OR_INCOMPATIBLE
```

For every `PARTIAL_OR_INCOMPATIBLE` case, `--serve` MUST fail non-zero without attempting repair, declaration import, or telemetry reseeding.

---

## 46. Documentation Link Validation

I2 SHALL verify that newly added links resolve inside the repository.

At minimum:

- root README → `examples/mcp-clients/README.md`;
- root README → individual client guides if linked;
- client README → all four guides;
- client guides → referenced demo docs;
- `docs/mcp.md` → relevant ADR/spec references where used.

Broken documentation links block I2 completion.

---

## 47. Client Syntax Verification

For each client family, I2 SHALL record:

```text
Codex CLI     verified / not verified
Claude Code   verified / not verified
Cursor        verified / not verified
VS Code       verified / not verified
```

I2 cannot complete while any documented command/configuration fragment is known to be stale or unverified.

The verification concerns **current official syntax**.

It does not establish end-to-end AIP interoperability.

---

## 48. Documentation Coherence Test

The following values SHALL be checked for consistency across:

```text
mcp-demo.sh --serve output
README onboarding
examples/mcp-clients/README.md
individual client guides
docs/mcp.md where applicable
```

Values:

```text
MCP endpoint
service id
environment
observation start
observation end
tool count
tool names
teardown command
local/trusted-network caveat
```

Any mismatch is an I2 defect.

---

# Part IX — Implementation Guidance

## 49. Expected Files

Expected implementation areas include:

```text
examples/runtime-demo/mcp-demo.sh
examples/runtime-demo/fixture-state.json
examples/runtime-demo/check_fixture_state.py

examples/mcp-clients/README.md
examples/mcp-clients/codex.md
examples/mcp-clients/claude-code.md
examples/mcp-clients/cursor.md
examples/mcp-clients/vscode.md

README.md
docs/mcp.md

tests/
```

Additional helper files MAY be introduced where justified.

I2 SHOULD remain documentation/demo focused.

---

## 50. Shell Design Guidance

The demo script SHOULD keep preparation phases explicit rather than becoming one large opaque function.

A suitable conceptual structure is:

```text
validate_prerequisites
start_stack
wait_for_core_services
run_fixture_state_checker
prepare_fixture_if_empty
wait_for_runtime_evidence_after_submission
rerun_fixture_state_checker
print_client_ready_summary
```

The existing direct walkthrough may continue after preparation in no-argument mode.

`--serve` SHALL exit the workflow immediately after `print_client_ready_summary`.

---

## 51. Reuse Existing Demo Logic

I2 SHOULD reuse existing functions and fixture preparation from the current hero demo.

It SHOULD NOT fork a second, subtly different architecture fixture merely for coding-agent onboarding.

Required principle:

> **One deterministic demo state, two consumers: scripted direct walkthrough and external coding-agent client.**

---

## 52. No New Correctness Oracle

Client documentation and README text are not a new correctness oracle.

Expected results SHALL trace back to the same existing deterministic demo/evaluation semantics.

Do not generate expected architecture outcomes from an LLM.

Do not create an onboarding-only set of architectural truths.

---

# Part X — Security and Repository Hygiene

## 53. No Secrets in Client Examples

Client example files MUST NOT contain:

- API keys;
- access tokens;
- cookies;
- account identifiers;
- private repository URLs;
- machine-specific secrets;
- personal file paths.

Placeholders MUST be visibly placeholders.

The AIP demo endpoint itself requires no credential in the local/trusted-network posture.

---

## 54. Persistent Client Configuration

Where a client setup command changes persistent user state, the guide SHALL say so.

It SHALL also document the current official cleanup/removal mechanism when one exists.

The onboarding SHOULD minimize persistent global changes.

This is particularly important for the first-run Claude Code example, where a local/private scope is preferred if current official client behavior supports it.

---

## 55. Repository Hygiene

Before I2 completion, the worktree MUST contain no accidental operating-system metadata such as:

```text
*:Zone.Identifier
.DS_Store
Thumbs.db
```

Client example directories MUST not contain generated logs, temporary traces, or personal configuration copied from the developer's machine.

---

# Part XI — Definition of Done

## 56. Demo

- [ ] `mcp-demo.sh --serve` exists.
- [ ] `--serve` validates prerequisites.
- [ ] `--serve` starts the deterministic AIP demo stack.
- [ ] `fixture-state.json` exists and freezes the exact one-seed state, including snapshot-relevant evidence aggregates.
- [ ] `check_fixture_state.py` exists, is read-only, and the canonical container-bound invocation deterministically returns exactly one classifier state.
- [ ] fixture classification requires no host Python or host-installed project/Neo4j dependencies.
- [ ] `EMPTY` requires zero graph nodes and zero graph relationships.
- [ ] `COMPLETE` requires exact manifest equality and permits no additional graph state.
- [ ] polluted, partial, and double-seeded states classify as `PARTIAL_OR_INCOMPATIBLE`.
- [ ] an `EMPTY` fixture imports declarations and submits frozen telemetry exactly once.
- [ ] a `COMPLETE` fixture skips declaration re-import and telemetry reseeding.
- [ ] a `PARTIAL_OR_INCOMPATIBLE` fixture fails without implicit repair.
- [ ] after first-time telemetry submission, every expected observed relation is awaited as the functional telemetry readiness proof.
- [ ] demo state is verified before success.
- [ ] `--serve` performs no scripted MCP tool calls.
- [ ] stack remains running after successful `--serve`.
- [ ] MCP endpoint is printed.
- [ ] Service Explorer URL is printed.
- [ ] service id is printed.
- [ ] environment is printed.
- [ ] frozen observation window is printed.
- [ ] client guide path is printed.
- [ ] teardown command is printed.
- [ ] repeated `--serve` on a `COMPLETE` fixture performs zero telemetry submissions and zero fixture mutations.
- [ ] repeated `--serve` does not change the deterministic architecture snapshot.
- [ ] no-argument hero demo still works unchanged.
- [ ] successful `--down` still works.
- [ ] teardown failure is tested, reported actionably, and exits non-zero.
- [ ] invalid/conflicting arguments exit `2`.

---

## 57. Client Documentation

- [ ] `examples/mcp-clients/README.md` exists.
- [ ] `codex.md` exists.
- [ ] `claude-code.md` exists.
- [ ] `cursor.md` exists.
- [ ] `vscode.md` exists.
- [ ] every setup syntax fragment was checked against current official documentation.
- [ ] verification status/date/source is recorded.
- [ ] examples are opt-in and do not activate client configuration automatically.
- [ ] no guide overclaims support before I3.
- [ ] persistent configuration side effects are described where applicable.
- [ ] cleanup instructions exist where applicable.
- [ ] no client example contains secrets or personal configuration.

---

## 58. Onboarding Semantics

- [ ] one canonical onboarding prompt is used.
- [ ] prompt timestamps match `--serve`.
- [ ] prompt service id matches `--serve`.
- [ ] prompt environment matches `--serve`.
- [ ] `LegacyPricingService` expected result is documented as `OBSERVED_ONLY`.
- [ ] `GET /pricing/{sku}` is documented.
- [ ] OTel provenance is documented.
- [ ] `unused-q` is documented as `NOT_OBSERVED_IN_WINDOW`.
- [ ] documentation explicitly preserves `non-observation != absence`.
- [ ] evidence drill-down uses the same snapshot.
- [ ] deterministic AIP behavior is distinguished from probabilistic agent behavior.

---

## 59. README

- [ ] `Connect AIP to Your Coding Agent` exists.
- [ ] it is placed near the existing five-minute proof/demo flow.
- [ ] root README remains compact.
- [ ] `--serve` is shown.
- [ ] `/mcp` endpoint is shown.
- [ ] at least Codex and Claude Code have concise setup entry points.
- [ ] Cursor and VS Code are linked or compactly shown.
- [ ] stable prompt is present.
- [ ] both deterministic drift findings are summarized.
- [ ] detailed setup links to `examples/mcp-clients/`.
- [ ] local/trusted-network caveat is visible.
- [ ] hosted-agent localhost limitation is visible.
- [ ] README does not claim broader support than I3 has qualified.

---

## 60. MCP Documentation

- [ ] `docs/mcp.md` documents direct mode.
- [ ] `docs/mcp.md` documents negotiated mode.
- [ ] stateless-by-default behavior is explicit.
- [ ] negotiated follow-up requirement is accurate.
- [ ] non-POST 405 behavior is accurate.
- [ ] exactly three tools are documented.
- [ ] zero-write boundary remains explicit.
- [ ] local/trusted-network boundary remains explicit.
- [ ] no historical v0.4 specification is rewritten.

---

## 61. Verification

- [ ] script behavior tests pass.
- [ ] no-MCP-in-`--serve` assertion passes.
- [ ] prepared-state verification passes.
- [ ] repeated-serve idempotency passes.
- [ ] documentation links pass.
- [ ] client syntax verification is complete for all four target families.
- [ ] `docs/specifications/0.4.2/i2-completion-record.md` exists and contains mandatory source URLs, verification dates, candidate SHA, and results.
- [ ] documentation coherence check passes.
- [ ] full existing direct hero demo regression passes.
- [ ] relevant unit/integration tests pass.
- [ ] Architecture Answer evaluation remains green.
- [ ] worktree contains no accidental metadata artifacts.

---

# Part XII — I2 Blockers

## 62. Release-Increment Blockers

Any of the following blocks I2 completion:

```text
--serve invokes scripted MCP tools

--serve reports ready before expected runtime evidence exists

--serve changes qualification relative to the existing deterministic demo

--serve reseeds telemetry when the fixture is already COMPLETE

--serve attempts implicit repair/reseed of PARTIAL_OR_INCOMPATIBLE fixture state

fixture-state.json is missing exact snapshot-relevant evidence aggregates

fixture checker requires host Python or host-installed AIP/Neo4j dependencies

fixture checker is invoked outside the architecture-intelligence container by --serve or qualification tests

fixture checker treats unrelated graph data as EMPTY

fixture checker accepts partial, polluted, or double-seeded state as COMPLETE

fixture checker uses wildcard/lower-bound/non-empty predicates for snapshot-relevant state

repeated --serve creates duplicate semantic architecture state

repeated --serve changes snapshot solely due to re-preparation

teardown failure returns success or lacks an actionable error

existing no-argument hero demo regresses

client syntax is copied without current official verification

i2-completion-record.md is missing or lacks mandatory source URL/date/candidate-SHA/result evidence

client documentation claims support before I3 qualification

README prompt timestamps differ from demo timestamps

README/client docs disagree on service id or environment

documentation describes NOT_OBSERVED_IN_WINDOW as unused/dead/obsolete

evidence walkthrough drops snapshot continuity

docs/mcp.md contradicts I1 transport behavior

root README becomes the primary troubleshooting manual

client examples silently activate repository/user configuration

secrets or personal configuration are committed

broken onboarding links remain

*:Zone.Identifier or equivalent OS metadata is committed
```

---

# Part XIII — Evidence of Completion

## 63. I2 Completion Record

I2 MUST create and commit:

```text
docs/specifications/0.4.2/i2-completion-record.md
```

This file is the auditable completion record for the increment and is REQUIRED for I2 completion.

It MUST capture at least:

```text
candidate commit SHA
record creation / verification date

I1 dependency:
  completed commit / PR

demo:
  fixture manifest path/hash
  fixture checker path
  fixture checker command: "${COMPOSE[@]}" exec -T architecture-intelligence python examples/runtime-demo/check_fixture_state.py --json
  host Python required: false
  expected snapshot_id
  EMPTY strict-zero classifier PASS/FAIL
  COMPLETE exact-manifest classifier PASS/FAIL
  polluted-state rejection PASS/FAIL
  double-seeded-state rejection PASS/FAIL
  --serve from EMPTY PASS/FAIL
  COMPLETE fixture reuse / no reseed PASS/FAIL
  PARTIAL_OR_INCOMPATIBLE rejection PASS/FAIL
  no-arg regression PASS/FAIL
  --down PASS/FAIL
  teardown-failure path PASS/FAIL
  repeated-serve PASS/FAIL
  second-run telemetry submissions = 0
  second-run fixture mutations = 0
  snapshot equality result
  no-scripted-MCP assertion PASS/FAIL

prepared state:
  LegacyPricingService OBSERVED_ONLY PASS/FAIL
  unused-q NOT_OBSERVED_IN_WINDOW PASS/FAIL
  observation window PASS/FAIL

documentation:
  root README PASS/FAIL
  docs/mcp.md PASS/FAIL
  client README PASS/FAIL

client syntax verification:
  Codex CLI:
    official source URL
    verification date
    observed/documented version where available
    candidate SHA
    result PASS/FAIL
  Claude Code:
    official source URL
    verification date
    observed/documented version where available
    candidate SHA
    result PASS/FAIL
  Cursor:
    official source URL
    verification date
    observed/documented version where available
    candidate SHA
    result PASS/FAIL
  VS Code:
    official source URL
    verification date
    observed/documented version where available
    candidate SHA
    result PASS/FAIL

link validation:
  PASS/FAIL

security/hygiene:
  no secrets PASS/FAIL
  no active client config accidentally committed PASS/FAIL
  no OS metadata artifacts PASS/FAIL

regression:
  hero demo PASS/FAIL
  relevant tests PASS/FAIL
  Architecture Answer evaluation PASS/FAIL
```

For all four client syntax-verification entries, the official source URL, verification date, candidate SHA, and result are mandatory.

The record MUST state clearly:

```text
Actual-client interoperability qualification:
PENDING I3
```

unless I3 has already been completed separately.

---

## 64. Final I2 Outcome

I2 succeeds when this user journey is true:

```text
git clone ...
cd architecture-intelligence-platform
cp .env.example .env

examples/runtime-demo/mcp-demo.sh --serve

        ↓

AIP prints:
  http://localhost:8000/mcp
  service:order-service
  demo
  frozen window

        ↓

user opens:
  examples/mcp-clients/README.md

        ↓

user selects:
  Codex / Claude Code / Cursor / VS Code

        ↓

user applies currently verified setup syntax

        ↓

user has a deterministic prompt and knows
the evidence-qualified AIP result to expect
```

At that point the repository is client-ready.

The next increment, I3, establishes which concrete client/platform tuples are actually qualified for the `v0.4.2` release, creates the qualified client/platform matrix, and adds the matrix link to the README/client documentation.
