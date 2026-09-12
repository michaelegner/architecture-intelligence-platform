# AIP v0.4.2 I3 — Actual-Client Qualification, Release, and Post-Release Verification

**Status:** Draft 0.6 — release-artifact identity and verification hardened  
**Target release:** `v0.4.2`  
**Release increment:** I3  
**Target repository path:** `docs/specifications/0.4.2/i3-client-qualification-and-release-preparation.md`  
**Governing specification:** [`specification.md`](specification.md)  
**Preceding increments:** I1 — Dual-Mode MCP Transport; I2 — Client-Ready Demo and Documentation

---

## 1. Purpose

I1 establishes the dual-mode MCP transport.

I2 establishes the deterministic client-ready demo and setup guides.

I3 proves that real coding-agent clients can consume the existing AIP MCP surface without changing
architecture semantics, then qualifies the exact release candidate and, after separate owner
authorization, verifies the artifacts actually published.

I3 answers two questions:

> **Qualification:** Do named coding-agent clients interoperate with the exact `v0.4.2` candidate
> while preserving AIP's deterministic architecture result, snapshot/evidence continuity, and
> read-only boundary?

> **Publication:** If the owner authorizes publication, do the final tag, release workflow, source
> archive, and final GHCR image correspond to that qualified candidate and still pass the required
> golden path?

The lifecycle is:

```text
I1 + I2 complete
      |
      v
CANDIDATE_FROZEN
      |
      v
CLIENT_QUALIFIED
      |
      v
RELEASE_READY
      |
      | separate owner authorization
      v
PUBLISHED
      |
      v
SHIPPED_VERIFIED
```

A technical GO is `RELEASE_READY`. It is not publication authorization.

If publication occurs, I3 is not complete until the actual published artifacts are independently
verified.

The governing product rule remains:

> **AIP may help agents reason about architecture, but an agent must never become the source of
> architectural truth.**

---

## 2. Scope, Non-Goals, and Frozen Contract

### 2.1 I3 scope

I3 SHALL deliver:

```text
candidate-bound I1 completion evidence
I2 completion input

one qualified tuple for:
  Codex CLI
  Claude Code
  Cursor
  VS Code

sanitized actual-client evidence
cross-client semantic comparison
bounded prompt/direct-control attempt records

clean-checkout candidate qualification
release-version qualification
shell-lint qualification
conditional-session qualification
CI/security/dependency qualification

RELEASE_CANDIDATE_SHA
EVIDENCE_COMMIT_SHA
DECISION_COMMIT_SHA (externally resolved after decision commit)

qualified client matrix
GO / NO-GO
draft release notes
I3 completion record
```

After separate owner authorization, I3 SHALL additionally deliver:

```text
final tag verification
release-workflow audit
final GHCR digest
final-image security disposition
anonymous pull verification
published-image direct and negotiated golden paths
tagged-source verification
post-release documentation closure
POST_RELEASE_COMMIT_SHA (externally resolved after post-release commit)
```

### 2.2 Non-goals

I3 SHALL NOT add or change:

```text
MCP tools
ArchitectureAnswer schema
schema_version
Canonical Model entities or relations
qualification semantics
snapshot semantics
evidence applicability
graph write capability
authentication
TLS termination
multi-tenancy
public-internet deployment support
agent orchestration
MCP prompts/resources
generic Cypher
discovery adapters
Kubernetes discovery
Topic/Subscription semantics
Desired State
transformation
policy enforcement
assertion verification
```

A client interoperability failure does not authorize protocol expansion inside I3.

If support requires a transport change, the owning I1/ADR contract must be changed first, a new
candidate created, and affected qualification rerun.

### 2.3 Frozen public contract

I3 SHALL preserve:

```text
public MCP path:
  /mcp

tools:
  get_architecture_drift
  get_evidence
  get_service_dependencies

tool count:
  3

schema_version:
  "0.4"

MCP graph writes:
  0

AIP LLM API key required for deterministic correctness:
  false

dependency scope:
  direct dependencies only

qualification vocabulary:
  CONFIRMED
  OBSERVED_ONLY
  NOT_OBSERVED_IN_WINDOW
```

`NOT_OBSERVED_IN_WINDOW` MUST NOT be interpreted as unused, dead, obsolete, or safe to remove.

---

## 3. Entry Conditions

Release-gating actual-client qualification MUST NOT begin until this section is satisfied.

### 3.1 I1 completion evidence

The merged I1 specification did not make `i1-completion-record.md` mandatory.

Therefore I3 SHALL create, or identify an accepted equivalent of, a retrospective candidate-bound
record:

```text
docs/specifications/0.4.2/i1-completion-record.md
```

The record SHALL state that it is retrospective and SHALL bind its evidence to
`RELEASE_CANDIDATE_SHA`.

It SHALL record the candidate result of the existing I1 release-gating suite:

```text
direct mode
negotiated mode
malformed-body precedence
unsupported HTTP methods
Origin/Host enforcement
cross-mode semantic equivalence
conditional-session result
automated zero-write result
I1 blockers
```

I3 does not re-specify those I1 behaviors.

### 3.2 I2 completion evidence

Before the first client qualification:

```text
docs/specifications/0.4.2/i2-completion-record.md
```

MUST exist and report GO.

I3 consumes I2's fixture and demo contracts rather than duplicating them.

### 3.3 Entry gate

Required:

| Gate | Required result |
|---|---|
| I1 candidate-bound completion evidence | present |
| I1 blockers | `0` |
| I2 completion record | GO |
| I2 blockers | `0` |
| `/mcp` sole public MCP path | PASS |
| exactly three tools | PASS |
| `schema_version = "0.4"` | PASS |
| direct/negotiated semantic equivalence | PASS |
| I2 `--serve` deterministic fixture | PASS |
| I2 fixture classifier | PASS |
| I2 repeated-serve idempotency | PASS |
| shell lint | PASS |
| conditional session | PASS / NOT_APPLICABLE |

`NOT_APPLICABLE` is valid for the session gate only when:

```text
candidate issues no session IDs
AND
none of the qualified client tuples requires stateful sessions
```

---

## 4. Release Identity and Lifecycle

This section is the single normative owner of release/evidence identity.

### 4.1 Identity model

| Identity | Purpose | Executable release state? | Final tag target? | How identity is recorded |
|---|---|---:|---:|---|
| `RELEASE_CANDIDATE_SHA` | exact source/client-tested candidate | yes | **yes** | known before qualification and embedded in evidence |
| `EVIDENCE_COMMIT_SHA` | matrix, sanitized traces, qualification evidence | no | no | resolved after evidence commit; recorded in the later decision commit |
| `DECISION_COMMIT_SHA` | GO/NO-GO, README linkage, release-ready docs | no | no | resolved externally after decision commit; need not appear inside that commit |
| `POST_RELEASE_COMMIT_SHA` | final artifact verification and shipped-state closure | no | no | resolved externally after post-release commit; need not appear inside that commit |

The final `v0.4.2` tag MUST point to:

```text
RELEASE_CANDIDATE_SHA
```

It MUST NOT point to any documentation/evidence commit.

### 4.2 No self-referential commit identities

A Git commit cannot contain its own SHA because adding that SHA changes the commit identity.

Therefore:

```text
EVIDENCE_COMMIT_SHA
DECISION_COMMIT_SHA
POST_RELEASE_COMMIT_SHA
```

are **externally resolved identities**.

Normative rule:

> A commit identity SHALL be resolved from Git only after that commit exists. A commit is never
> required to embed its own SHA.

Required handling:

```text
EVIDENCE_COMMIT_SHA
  resolved after evidence commit
  recorded in the later GO/NO-GO decision artifact

DECISION_COMMIT_SHA
  resolved after decision commit
  verified from Git when publication is authorized
  MAY be recorded later in post-release verification
  need not be embedded in the decision commit

POST_RELEASE_COMMIT_SHA
  resolved after post-release commit
  verified from Git as the commit containing the final closure artifacts
  need not be embedded in the post-release commit
```

A canonical resolution command is:

```bash
git rev-parse <commit-or-ref>
```

The release evidence SHALL make the mapping independently verifiable from repository history.

No additional "self-attestation" commit is required merely to write a commit's own SHA into a file.

### 4.3 Candidate freeze

Before the first release-gating client run, record:

```text
RELEASE_CANDIDATE_SHA = <full 40-character SHA>
dirty_worktree = false

package_version = 0.4.2
producer.version = 0.4.2
producer.build_revision = RELEASE_CANDIDATE_SHA
MCP server version = 0.4.2
schema_version = 0.4

dependency-lock SHA-256
candidate image digest, where applicable
```

Every release-candidate and final-release image build SHALL inject the exact full
`RELEASE_CANDIDATE_SHA` at build time. The canonical build argument is:

```text
BUILD_REVISION=<RELEASE_CANDIDATE_SHA>
```

The application SHALL expose that value as `producer.build_revision` in every Architecture Answer
response that contains producer metadata. `unknown`, an abbreviated SHA, a branch name, or a dirty
worktree description fails candidate identity qualification.

The release workflow SHALL resolve the tag target and pass that exact commit identity into the final
image build. Workflow/ref metadata alone is not evidence that the running server contains that
revision.

A branch name is not candidate identity.

### 4.4 Allowed post-freeze changes

After candidate freeze, evidence-only changes MAY be committed without creating a new executable
candidate.

Examples:

```text
qualified matrix
sanitized traces
qualification reports
retrospective completion records
GO/NO-GO record
README links/support wording
ROADMAP/status wording
post-release verification
```

Such changes MUST NOT alter executable behavior or release build inputs.

Any executable or release-artifact-producing change creates a new candidate.

Examples include changes to:

```text
app/**
pyproject.toml
uv.lock
Dockerfile
release/build workflow logic
runtime configuration affecting behavior
tests/evaluation that define release qualification
runtime-demo executable scripts
fixture contracts
MCP transport implementation
tool schemas
ArchitectureAnswer schemas
dependencies
```

If a candidate-affecting change occurs:

```text
previous technical GO invalid
new RELEASE_CANDIDATE_SHA required
affected I1/I2/I3 gates reopen
affected actual-client runs rerun
new evidence commit required
new decision commit required
```

Tags SHALL NOT be moved to hide a candidate change.

### 4.5 Revision-scoped link validation

Link validation has two different moments: pre-decision validation and exact committed-revision
validation.

Before technical GO, validate:

```text
candidate-contained links
  -> exact RELEASE_CANDIDATE_SHA

matrix / trace / qualification links
  -> exact EVIDENCE_COMMIT_SHA

README / GO / release-ready links
  -> prospective decision-tree validation
```

**Prospective decision-tree validation** means validating the exact release-ready working tree that
will be committed as the decision revision, including the README, GO/NO-GO artifact, matrix links,
client-guide links, release-note links, and completion-record links.

It does not claim that `DECISION_COMMIT_SHA` already exists.

After the decision commit exists:

```text
resolve DECISION_COMMIT_SHA
checkout/inspect that exact commit
rerun decision-revision link validation
```

Required:

```text
exact decision-revision links = PASS
```

If exact decision-revision validation fails:

```text
that decision commit is invalid for publication
correct the documentation/link defect
create a replacement decision commit
resolve a new DECISION_COMMIT_SHA
rerun exact decision-revision link validation
```

This does **not** create a second definition of `RELEASE_READY`.

The technical GO decision remains defined only by §8.3. Exact decision-revision validation determines
whether a particular decision commit is an acceptable publication handoff.

If correcting the link defect changes any executable candidate input, evidence meaning, or §8.3 gate
result, the affected qualification MUST be reopened. Otherwise client qualification need not be
rerun.

After publication, published-release and shipped-state links SHALL likewise be validated against the
actual GitHub Release and the exact post-release closure revision.

`DECISION_COMMIT_SHA` and `POST_RELEASE_COMMIT_SHA` are resolved after those commits exist; their own
files do not need to contain those SHA values.

---

## 5. Qualified Client Tuple Contract

I3 qualifies exact tuples, not client families in the abstract.

### 5.1 Required client families

At least one tuple SHALL qualify for each:

```text
Codex CLI
Claude Code
Cursor
VS Code
```

### 5.2 Tuple identity

Every tuple SHALL record:

```text
client family
client product
client version

extension/plugin name + version where applicable
otherwise explicit:
  N/A — built in

OS
OS version where practical
CPU architecture

execution mode:
  native
  WSL
  container

client location
AIP location
network topology

configuration mechanism
transport
approval mode

candidate SHA
returned producer.build_revision
pinned MCP SDK version

observed initialization/protocol version
session IDs issued: yes/no
session IDs used: yes/no
session reuse observed: yes/no

qualification date
actual-client evidence reference
result
known limitations
```

### 5.3 Support vocabulary

Allowed tuple results:

```text
QUALIFIED
FAILED
BLOCKED
NOT_EXECUTED
UNVERIFIED
```

Only `QUALIFIED` creates a published support row.

One tested tuple does not establish:

```text
all versions of that client
a minimum supported version
all operating systems
all extensions
all execution modes
```

### 5.4 Client-specific deltas

| Client | Additional required tuple detail |
|---|---|
| Codex CLI | exact CLI version |
| Claude Code | configuration scope |
| Cursor | configuration scope and reload/restart lifecycle where required |
| VS Code | MCP-providing extension name/version where applicable; otherwise `N/A — built in` |

No separate client-specific qualification algorithm exists. All four clients use §6.

---

## 6. Actual-Client Qualification Procedure

This section is the single normative owner of the actual-client workflow.

### 6.1 Isolation

For a demo image built from the candidate checkout, the demo launcher SHALL require the full
candidate revision and pass it to the container build. The `--serve` step in the default procedure
SHALL use this canonical contract:

```bash
export RELEASE_CANDIDATE_SHA="$(git rev-parse HEAD)"
BUILD_REVISION="$RELEASE_CANDIDATE_SHA" ./examples/runtime-demo/mcp-demo.sh --serve
```

`mcp-demo.sh` SHALL forward `BUILD_REVISION` as the image build argument of the same name and fail
before serving if it is missing, not a full commit SHA, or differs from `RELEASE_CANDIDATE_SHA`.

Default release-gating procedure:

```text
mcp-demo.sh --down
        |
        v
mcp-demo.sh --serve
        |
        v
fixture = COMPLETE
        |
        v
record snapshot S
record revision R
        |
        v
configure actual client
        |
        v
bounded client qualification
        |
        v
record revision R'
fixture = COMPLETE
snapshot = S
require R' = R
        |
        v
disconnect
        |
        v
mcp-demo.sh --down
```

A tuple MAY reuse an existing fixture only when the I2 fixture checker proves it is `COMPLETE`.

Fresh isolation per release-gating tuple is preferred.

### 6.2 Pre-client state

Run the I2 canonical checker:

```bash
"${COMPOSE[@]}" exec -T architecture-intelligence \
  python examples/runtime-demo/check_fixture_state.py --json
```

Required:

```text
classification = COMPLETE
mismatches = []
```

Record:

```text
fixture_id
snapshot_id = S
```

### 6.3 Revision-fence helper

I3 SHALL provide one read-only helper:

```text
examples/runtime-demo/read_revision_fence.py
```

Canonical invocation:

```bash
"${COMPOSE[@]}" exec -T architecture-intelligence \
  python examples/runtime-demo/read_revision_fence.py --json
```

Example output:

```json
{"revision": 42}
```

The helper SHALL use the production `read_revision` path and SHALL:

```text
perform no write
create no singleton
repair no state
fail safely on missing/invalid revision state
```

Record:

```text
revision_before = R
```

### 6.4 Client configuration

Use the I2 client guide and reverify its syntax against the current official client documentation
immediately before the qualification run.

Record:

```text
official documentation URL
verification date
client version
configuration command/file
scope
transport
```

Qualification MUST NOT depend on:

```text
undocumented custom headers
protocol-transforming proxy
request/response rewrite
AIP-specific client fork
```

Passive capture instrumentation is allowed.

### 6.5 Trigger and attempt accounting

I3 distinguishes:

```text
valid client attempt
    from
infrastructure-invalidated run
```

A **valid client attempt** is a run in which the I2 fixture/server/network prerequisites are healthy
enough for the named client to exercise its MCP behavior.

An **infrastructure-invalidated run** is a run that cannot validly assess client behavior because an
independent demo/server/network prerequisite failed.

Infrastructure-invalidated runs:

```text
MUST be recorded
MUST be classified separately
DO NOT consume the valid-client attempt budget
MUST NOT be hidden by reporting only the later successful run
```

#### Deterministic client control

Prefer an official client-native deterministic MCP control when one exists.

For that protocol-qualification path:

```text
maximum valid client attempts = 1
fresh client lifecycle = required
```

A client/control failure on that one valid attempt fails the tuple until the underlying defect or
configuration is corrected and qualification is restarted.

#### LLM-mediated client qualification

If the client exposes MCP only through an LLM-driven UI, use Appendix A.1.

For that protocol-qualification path:

```text
maximum valid client attempts = 2
fresh context per valid attempt = required
same client/model/config/approval mode = required
all valid attempts = recorded
```

A second valid client attempt is permitted only after:

```text
MODEL_TOOL_SELECTION_FAILURE
```

Do not retry until the model happens to use AIP.

#### Infrastructure retry budget

Infrastructure-invalidated runs have their own bounded retry policy:

```text
maximum infrastructure-invalidated runs before a valid attempt = 2
```

After one infrastructure-invalidated run:

```text
identify/correct the infrastructure cause
recreate or revalidate the deterministic fixture
record a fresh snapshot/revision baseline
rerun without consuming the valid-client attempt budget
```

If a second infrastructure-invalidated run occurs before a valid client attempt completes:

```text
stop the tuple qualification cycle
result = BLOCKED
record both invalidated runs and the infrastructure blocker
```

A later qualification cycle MAY begin only after the infrastructure remediation is explicitly
recorded. Previous invalidated runs remain part of the release evidence.

This policy prevents both accidental consumption of the client-attempt budget and unbounded
"infrastructure retry until success" behavior.

### 6.6 Failure taxonomy

Every unsuccessful run SHALL have one primary classification:

```text
MODEL_TOOL_SELECTION_FAILURE
CLIENT_CONTROL_FAILURE
APPROVAL_BLOCKED
TRANSPORT_FAILURE
SEMANTIC_FAILURE
INFRASTRUCTURE_FAILURE
```

Meaning:

```text
MODEL_TOOL_SELECTION_FAILURE
  prerequisites healthy and tools available, but the model did not issue the required AIP call

CLIENT_CONTROL_FAILURE
  prerequisites healthy, but official direct client control could not issue the required call

APPROVAL_BLOCKED
  prerequisites healthy, but client policy/approval state prevented the required call

TRANSPORT_FAILURE
  prerequisites healthy enough to assess the client, but initialization, protocol exchange,
  or reconnect failed

SEMANTIC_FAILURE
  AIP call completed but structuredContent violated the deterministic expected result

INFRASTRUCTURE_FAILURE
  demo/server/network prerequisite failed independently of client compatibility
```

`INFRASTRUCTURE_FAILURE` invalidates that run as client-compatibility evidence and is governed by the
separate infrastructure retry budget in §6.5.

It does not consume the valid-client attempt budget.

`TRANSPORT_FAILURE` and `SEMANTIC_FAILURE` are valid-client failures and fail the tuple until a
concrete defect is corrected and affected qualification is rerun.

For an LLM-mediated path, one `MODEL_TOOL_SELECTION_FAILURE` may be followed by one fresh valid
attempt. Two valid tool-selection failures exhaust the valid-client attempt budget.

### 6.7 Approval behavior

Approval prompts are part of the tuple.

Record:

```text
approval mode
approval requested: yes/no
manual approval required: yes/no
persistent allow enabled: yes/no
```

A normal approval click is not a retry.

Do not silently weaken the approval configuration after a failed attempt.

### 6.8 Required successful protocol workflow

A successful tuple SHALL prove:

```text
1. initialization / negotiation
2. tool discovery
3. exactly three AIP tools discovered
4. get_architecture_drift
5. deterministic structured drift result
6. get_evidence using returned evidence_refs
7. same snapshot used
8. disconnect/stop
9. reconnect/reinitialize
10. one read-only tool works after reconnect
```

For each Architecture Answer response that exposes producer metadata, require:

```text
producer.version = 0.4.2
producer.build_revision = RELEASE_CANDIDATE_SHA
```

The assertion SHALL be made against the response returned by the running server, not inferred from
the checkout, image tag, Compose configuration, or workflow metadata.

The actual named client MUST produce the traffic.

A generic harness cannot create a `QUALIFIED` named-client row.

### 6.9 Deterministic expected result

Request:

```text
service_id:
  service:order-service

environment:
  demo

window:
  2026-08-26T00:00:00Z
  through
  2026-08-27T00:00:00Z
```

Required findings:

```text
LegacyPricingService
  qualification = OBSERVED_ONLY
  via = GET /pricing/{sku}

unused-q
  qualification = NOT_OBSERVED_IN_WINDOW
```

Confirmed ProductService/PaymentService relationships remain omitted from drift.

The client may render the result differently.

AIP `structuredContent` is the semantic oracle.

### 6.10 Evidence drill-down

If drift returns:

```text
snapshot_id = S
evidence_refs = R
```

the client SHALL call:

```text
get_evidence(snapshot_id = S, evidence_refs = R)
```

Required:

```text
same snapshot preserved
evidence resolves
provenance preserved
```

A new current-state query that merely returns similar data is not sufficient.

### 6.11 Reconnect

The client SHALL disconnect or stop its MCP connection using normal client behavior, then reconnect
or reinitialize and successfully perform:

```text
tool discovery
AND
one read-only AIP tool call
```

For a stateless tuple, a fresh negotiated lifecycle is sufficient.

### 6.12 Post-client write/state gate

Read the revision fence again:

```text
revision_after = R'
```

Run the I2 fixture checker again.

Required:

```text
R' = R
fixture = COMPLETE
actual_snapshot_id = S
mismatches = []
```

Snapshot equality alone proves only final canonical-state equality.

The stronger zero-write evidence for an actual-client run is:

```text
revision_before = revision_after
```

The release-level zero-write claim is supported jointly by:

```text
actual-client revision fence unchanged
AND
automated direct/negotiated zero-write tests
```

If revision changed, the tuple fails even if the canonical snapshot later matches.

### 6.13 Actual-client evidence

For each qualified tuple, evidence SHALL prove:

```text
actual client identity/version
returned producer.build_revision = RELEASE_CANDIDATE_SHA
initialization
tool discovery
drift call
evidence call
same-snapshot continuity
reconnect
post-run revision equality
post-run fixture COMPLETE
```

Acceptable sources MAY include:

```text
client MCP log
client diagnostics
AIP request trace
passive HTTP capture
client UI evidence
server log correlated by timestamp/request
```

The chain must distinguish the actual client from the independent test harness.

### 6.14 Capture integrity

Capture MUST be observational.

It MUST NOT:

```text
insert missing headers
rewrite methods
rewrite protocol versions
rewrite request bodies
rewrite responses
simulate initialization
hold unsupported state
translate protocol behavior
```

### 6.15 Sanitization and raw capture

Committed evidence MUST NOT contain:

```text
authorization headers
bearer tokens
cookies
API keys
refresh tokens
account IDs
email addresses
personal user IDs
raw system prompts
unrelated conversation content
unrelated traffic
private local paths not required for proof
```

Use explicit redaction placeholders where needed.

Raw unsanitized capture MAY exist only ephemerally and MUST be deleted before tuple closure.

Committed trace artifacts SHALL record:

```text
tuple identity
candidate identity
capture method
sanitization statement
protocol sequence
tool/result summary
snapshot id
revision-before/after
reconnect result
fixture-check result
raw capture deleted/not retained
PASS / FAIL
```

---

## 7. Cross-Client Semantic Gate and UX Evidence

### 7.1 Cross-client semantic comparison

All four release-gating tuples SHALL use the same:

```text
fixture
service id
environment
observation window
AIP request
```

Normalize only transport/client-local metadata such as:

```text
JSON-RPC request id
client-local timestamps
diagnostic wrapper metadata
```

Do not normalize architecture content.

Across all qualified tuples, compare:

```text
outcome
claims
subject/object identities
dependency target
delivery/via identity
qualification
evidence_refs
observation_context
limitations
snapshot_id
schema_version
producer semantic version
producer build revision
```

Required:

```text
cross-client semantic mismatches = 0
evidence-meaning mismatches = 0
```

Agent prose is not part of this oracle.

### 7.2 Mandatory separate UX observation

The natural-language onboarding workflow is separate from protocol qualification.

This is the mandatory per-client onboarding-prompt experiment required by governing specification
§33; satisfying deterministic protocol controls does not satisfy or waive it.

It SHALL be executed and recorded for **all four required client families**:

```text
Codex CLI
Claude Code
Cursor
VS Code
```

This requirement applies even when the protocol-qualification tuple was qualified through a
deterministic client-native control rather than through an LLM-mediated path.

For each client family:

```text
start a fresh agent/chat context
use the qualified client configuration
run Appendix A.2 exactly once as the UX observation
record the exact prompt identity and observed behavior
```

The UX observation is **non-gating in outcome**:

```text
agent chooses AIP perfectly     -> useful evidence
agent partially uses AIP        -> useful evidence
agent ignores/misexplains AIP   -> useful evidence
```

AIP semantic correctness MUST NOT depend on that probabilistic behavior.

However:

```text
executing the separate UX observation = mandatory
recording its result             = mandatory
the quality/outcome              = non-gating
```

Record whether the agent:

```text
selected AIP
called get_architecture_drift
found LegacyPricingService
preserved OBSERVED_ONLY
found unused-q
preserved NOT_OBSERVED_IN_WINDOW
called get_evidence
preserved the same snapshot
distinguished evidence from inference
avoided unused/dead/obsolete overclaim
```

Use:

```text
YES
NO
PARTIAL
NOT_OBSERVED
```

Where visible, also record:

```text
model/provider
agent mode
tool approval mode
```

If the UX run is invalidated by an independent infrastructure failure, record that invalidated run,
restore the deterministic environment, and execute the one required valid UX observation.

Do not retry merely to obtain a better agent answer.

These UX fields do not become part of the support tuple unless transport behavior materially depends
on them.

---

## 8. Candidate Qualification Gates

This section is the **single normative release-gate table**.

Other sections SHALL reference this table rather than restating all gates.

### 8.1 Clean state

Qualification SHALL use a fresh clone or isolated clean worktree at `RELEASE_CANDIDATE_SHA`.

Required:

```text
git status --porcelain = empty
```

Qualification MUST NOT depend on:

```text
uncommitted files
maintainer-local graph state
old demo volumes
hidden client registration
manual Cypher repair
private test data
OPENAI_API_KEY for deterministic AIP correctness
```

### 8.2 Reference candidate commands

At minimum run the current repository equivalents of:

```bash
uv sync --locked

uv run ruff check .
uv run ruff format --check .

uv run pytest tests/unit -q
uv run pytest tests/integration -q

uv run python -m evaluation run
uv run python -m evaluation answers --candidate-sha <RELEASE_CANDIDATE_SHA>

uv run --with pip-audit pip-audit
```

Also run the parent-required shell-lint gate.

Use the committed repository shell-lint command if one exists; otherwise record the exact standard
linter command/tool version used.

### 8.3 Normative release-gate table

This table is the **single exhaustive pre-publication definition of technical release readiness**.

No other section may add independent `RELEASE_READY` criteria.

| Gate | Required result | Evidence owner |
|---|---|---|
| §3 entry conditions | PASS | I3 qualification record |
| `RELEASE_CANDIDATE_SHA` frozen and clean | PASS | candidate qualification |
| Candidate version/build identity | PASS | candidate qualification |
| Running candidate `producer.build_revision` | `RELEASE_CANDIDATE_SHA` | tuple traces + candidate golden path |
| I1 candidate-bound regression | PASS | I1 completion evidence |
| I2 deterministic demo regression | PASS | I2 completion evidence |
| Codex CLI tuple | QUALIFIED | client matrix + trace |
| Claude Code tuple | QUALIFIED | client matrix + trace |
| Cursor tuple | QUALIFIED | client matrix + trace |
| VS Code tuple | QUALIFIED | client matrix + trace |
| All §6 mandatory client-procedure steps for each published tuple | PASS | tuple traces |
| All bounded client qualification attempts recorded | PASS | tuple traces |
| Infrastructure-invalidated runs recorded and within §6.5 retry budget | PASS | tuple traces |
| Separate Appendix A.2 UX observation executed and recorded for Codex, Claude, Cursor, and VS Code | PASS | UX observation record |
| Cross-client semantic mismatches | `0` | client qualification report |
| Evidence-meaning mismatches | `0` | client qualification report |
| Actual-client revision changes | `0` | tuple traces |
| Post-client fixture mismatches | `0` | tuple traces |
| Actual-client evidence attribution | PASS | tuple traces |
| Trace sanitization + raw-capture deletion | PASS | tuple traces |
| Qualified client matrix exists | PASS | evidence commit |
| `EVIDENCE_COMMIT_SHA` externally resolved | PASS | Git + decision preparation |
| README → qualified matrix link | PASS | decision preparation |
| I2 client guides → qualified matrix link | PASS | decision preparation |
| `docs/mcp.md` matches release candidate | PASS | documentation qualification |
| Draft `v0.4.2` release notes exist and are bounded | PASS | release preparation |
| I3 completion record prepared for technical decision | PASS | release preparation |
| Ruff lint | PASS | clean-checkout record |
| Ruff format check | PASS | clean-checkout record |
| Shell lint | PASS | clean-checkout record |
| Unit tests | PASS | clean-checkout record |
| Integration tests | PASS | clean-checkout record |
| Relation-fact evaluator | PASS | clean-checkout record |
| Architecture Answers | `23/23 PASS` | clean-checkout record |
| Architecture Answers repeatability | PASS | clean-checkout record |
| Dependency audit | PASS or explicit accepted disposition | clean-checkout record |
| Release-version consistency | PASS | clean-checkout record |
| Conditional-session result | PASS / NOT_APPLICABLE | I1/I3 evidence |
| Direct hero demo | PASS | candidate qualification |
| I2 `--serve` | PASS | candidate qualification |
| Direct MCP regression | PASS | I1 suite |
| Negotiated MCP regression | PASS | I1 suite |
| Cross-mode snapshot/evidence | PASS | I1 suite |
| Automated zero-write tests | PASS | I1/AI service tests |
| Candidate CI/security checks | PASS | exact-SHA CI evidence |
| Repository hygiene | PASS | qualification record |
| Candidate links validated at `RELEASE_CANDIDATE_SHA` | PASS | qualification record |
| Evidence links validated at `EVIDENCE_COMMIT_SHA` | PASS | evidence record |
| Prospective decision-tree link validation | PASS | decision preparation |
| Release blockers | `0` | GO/NO-GO preparation |

Test counts SHALL be recorded as evidence but are not permanent contract constants.

The `DECISION_COMMIT_SHA` is deliberately **not** a prerequisite in this table: the decision commit is
the artifact that records the result of evaluating this table. Its SHA is resolved only after that
commit exists.

Likewise, exact validation of the committed decision revision occurs after the decision commit exists
under §4.5/§10.2. That post-commit check accepts or rejects the decision revision as a publication
handoff; it does not add a second `RELEASE_READY` definition.
### 8.4 Version identity

The candidate SHALL identify consistently as:

```text
0.4.2
```

At minimum across:

```text
pyproject.toml
root project version in uv.lock
app.version.package_version()
MCP server advertised version
Producer.version
Producer.build_revision = RELEASE_CANDIDATE_SHA in running-server responses
Architecture Answers evaluator producer
active release-version fixtures
```

`schema_version` remains:

```text
0.4
```

Historical documentation MUST NOT be rewritten merely to remove old version strings.

### 8.5 CI identity

Candidate CI SHALL be verified against the exact `RELEASE_CANDIDATE_SHA`.

Record:

```text
check/workflow name
run/check identity
candidate SHA
status
conclusion
```

A green older commit does not qualify the candidate.

### 8.6 Repository hygiene

Before candidate/evidence closure, scan for accidental workstation metadata, including ignored files.

At minimum prohibit:

```text
*:Zone.Identifier
.DS_Store
Thumbs.db
raw unsanitized traces
credentials
personal MCP configuration
temporary packet captures/logs
```

Because `*:Zone.Identifier` may be ignored by Git, use an explicit worktree scan such as:

```bash
find . -type f -name '*:Zone.Identifier' -print
```

Required:

```text
no matches
```

---

## 9. Evidence Artifacts and Documentation

### 9.1 Required artifacts

| Artifact | Purpose |
|---|---|
| `docs/specifications/0.4.2/i1-completion-record.md` | retrospective/equivalent candidate-bound I1 evidence |
| `docs/release-validation/v0.4.2-client-qualification.md` | tuple matrix + cross-client result |
| `docs/release-validation/v0.4.2-client-traces/codex-cli.md` | Codex actual-client evidence |
| `docs/release-validation/v0.4.2-client-traces/claude-code.md` | Claude Code actual-client evidence |
| `docs/release-validation/v0.4.2-client-traces/cursor.md` | Cursor actual-client evidence |
| `docs/release-validation/v0.4.2-client-traces/vscode.md` | VS Code actual-client evidence |
| `docs/release-validation/v0.4.2-go-no-go.md` | technical decision |
| `docs/release-validation/v0.4.2-release-notes.md` | draft release notes |
| `docs/specifications/0.4.2/i3-completion-record.md` | I3 closure record |
| `docs/release-validation/v0.4.2-post-release-verification.md` | only after publication |

The same fact SHOULD have one artifact owner and be linked from other artifacts.

### 9.2 Qualified matrix

The normative compatibility matrix lives in:

```text
docs/release-validation/v0.4.2-client-qualification.md
```

Minimum columns:

```text
Client
Client version
Extension/plugin version where applicable
OS
Execution mode
AIP location
Network topology
Transport
Candidate SHA
Returned producer build revision
SDK version
Initialization result
Session behavior
Drift/evidence result
Revision unchanged
Reconnect result
Actual-client trace
Result
Limitations
```

### 9.3 README qualified-matrix handoff

Before technical GO, README SHALL contain a working link to:

```text
docs/release-validation/v0.4.2-client-qualification.md
```

This handoff is mandatory and is a §8.3 release gate.

README MAY additionally say:

> **Qualified client/platform combinations are listed in the v0.4.2 compatibility matrix. Other
> combinations are unverified unless listed.**

Avoid broad family/version claims not established by the matrix.

Before actual publication, README MUST NOT say `v0.4.2` is shipped.
### 9.4 Client guides

After I3 qualification, each I2 client guide SHALL:

```text
retain setup instructions
link to qualified matrix
preserve candidate/setup versus qualification distinction
avoid broad support claims
```

### 9.5 `docs/mcp.md`

Before technical GO, verify that `docs/mcp.md` matches the candidate:

```text
/mcp sole public path
direct mode
negotiated mode
stateless default
same three tools
HTTP method contract
conditional session semantics
Origin/Host boundary
read-only tools
same architecture semantics
```

I3 does not duplicate those protocol rules.

### 9.6 Draft release notes

Create:

```text
docs/release-validation/v0.4.2-release-notes.md
```

Status before publication:

```text
Draft — not a published release
```

Release story:

> **v0.4.2 makes the existing read-only Architecture Intelligence MCP surface directly consumable by
> qualified coding-agent clients without changing architecture semantics.**

Release notes SHALL NOT claim:

```text
all MCP clients supported
all versions of a qualified client supported
public-internet MCP security
authentication
multi-tenancy
stateful sessions unless actually qualified
write capabilities
generic graph query
transitive dependency analysis
Desired State
architecture transformation
agent-generated architecture as truth
```

---

## 10. Technical GO / NO-GO

### 10.1 GO artifact

Create:

```text
docs/release-validation/v0.4.2-go-no-go.md
```

The artifact SHALL record:

```text
RELEASE_CANDIDATE_SHA
EVIDENCE_COMMIT_SHA

candidate producer.build_revision result

I1 completion evidence
I2 completion evidence

§8.3 gate-table result
four qualified tuple results
all qualification attempts
cross-client mismatch count
revision-fence results
trace sanitization status

known limitations
blocker ledger

technical decision:
  RELEASE_READY / NO_GO

publication authorization:
  NOT_GRANTED / GRANTED_SEPARATELY

final tag target:
  RELEASE_CANDIDATE_SHA
```

After this artifact and the associated README/release-ready documentation are committed,
`DECISION_COMMIT_SHA` SHALL be resolved externally from Git.

The GO artifact MUST NOT attempt to contain `DECISION_COMMIT_SHA` of the commit that contains it.
### 10.2 Technical GO rule and decision-revision acceptance

`RELEASE_READY` has exactly one normative definition:

```text
every mandatory gate in §8.3 = satisfied
```

The GO/NO-GO artifact records the result of that evaluation.

No other section adds independent `RELEASE_READY` conditions.

After committing the GO/NO-GO artifact and associated release-ready documentation:

```text
resolve DECISION_COMMIT_SHA
rerun exact decision-revision link validation at that SHA
```

If that exact committed-revision validation passes:

```text
decision revision = ACCEPTED FOR PUBLICATION HANDOFF
```

If it fails:

```text
decision revision = INVALID FOR PUBLICATION HANDOFF
```

Then correct the documentation/link defect, create a replacement decision commit, resolve its SHA,
and rerun the exact-revision check as defined in §4.5.

This acceptance step does not change the semantic definition of `RELEASE_READY`; it validates the
integrity of the concrete decision artifact handed to publication.

### 10.3 NO-GO

A NO-GO record SHALL identify:

```text
blocking gate
owner
required remediation
which earlier increment reopens if applicable
which evidence becomes invalid
```

Unexecuted is:

```text
NOT_EXECUTED
```

not PASS.

### 10.4 Publication authorization

Technical GO does not authorize:

```text
RC tag creation
final tag creation
GitHub prerelease
GitHub final release
release publication
```

Those require explicit repository-owner authorization.

---

## 11. Authorized Publication and Post-Release Verification

This section applies only after the owner explicitly authorizes publication.

### 11.1 Preconditions

Required:

```text
technical state = RELEASE_READY
RELEASE_CANDIDATE_SHA recorded
EVIDENCE_COMMIT_SHA recorded in decision artifact
DECISION_COMMIT_SHA externally resolved from Git
exact decision-revision link validation = PASS
decision revision = ACCEPTED FOR PUBLICATION HANDOFF
owner authorization recorded
```

`release blockers = 0` is already part of the exhaustive §8.3 gate and is not a second independent
publication-readiness definition.
### 11.2 Publication verification flow

After publication, perform exactly this release-verification flow:

```text
1. verify v0.4.2 tag -> RELEASE_CANDIDATE_SHA

2. record all final release-workflow attempts
   require final required workflow = success
   require unexpected duplicate release workflows = 0

3. record final GHCR digest

4. resolve final-image security results and disposition
   bind scan/report evidence to the final workflow run and final GHCR digest
   require unresolved release-blocking findings = 0

5. anonymously pull the final image
   require pulled digest = final GHCR digest

6. start the pulled image by immutable digest in a fresh environment
   health = PASS
   producer.build_revision = RELEASE_CANDIDATE_SHA
   import the deterministic topology fixture
   seed the frozen telemetry fixture required for the observation window
   fixture classifier = COMPLETE with mismatches = []
   record snapshot S and revision R

7. run the direct MCP golden path against that prepared pulled image
   tools/list = exactly 3 tools
   get_architecture_drift = §6.9 deterministic result
   LegacyPricingService = OBSERVED_ONLY
   get_evidence = same snapshot S with evidence continuity
   producer.build_revision = RELEASE_CANDIDATE_SHA

8. run the negotiated MCP golden path against that same prepared pulled image
   initialization / protocol negotiation = PASS
   tools/list = exactly 3 tools
   get_architecture_drift = §6.9 deterministic result
   get_evidence = same snapshot S with evidence continuity
   disconnect = PASS
   reconnect / reinitialize = PASS
   one read-only tool works after reconnect
   producer.build_revision = RELEASE_CANDIDATE_SHA

9. verify final published-image state
   revision after = R
   fixture classifier = COMPLETE with mismatches = []
   snapshot = S
   direct/negotiated semantic equivalence = PASS
   read-only invariant = PASS

10. fresh-checkout v0.4.2 tagged source
   tag SHA = RELEASE_CANDIDATE_SHA
   package version = 0.4.2
   release-version consistency = PASS
   required tagged-source verification = PASS

11. verify GitHub Release identity and links

12. commit post-release verification and shipped-state documentation
```

A locally rebuilt image is not a substitute for step 6.

The final image MUST be identified by immutable digest.

An RC image does not waive verification of the final image.

Import without the frozen telemetry seed is not a valid final-image fixture preparation because it
cannot establish the required `LegacyPricingService = OBSERVED_ONLY` result.

### 11.3 Release-workflow attempts

Record every final-publication workflow attempt:

```text
workflow name/id
run id
trigger
tag/ref
source SHA
attempt number
start/end time
conclusion
artifact/image digest where applicable
injected BUILD_REVISION
```

If rerun, preserve all attempts and explain why.

### 11.4 Final-image security disposition

A successful publication workflow is necessary but not sufficient for shipped verification when a
security scanner is non-blocking.

Before `SHIPPED_VERIFIED`, collect the final-image scan/report evidence and record:

```text
workflow name and run/attempt identity
source SHA and tag/ref
final GHCR digest
scanner name and version
scan database/update identity where available
scan completion/result
every release-blocking finding
disposition, owner, rationale, and evidence for each finding
unresolved release-blocking finding count
```

Every finding classified as release-blocking by the repository security policy SHALL be either:

```text
remediated and verified against the same final digest
OR
resolved by an authorized-owner risk acceptance that records why it does not block this release
```

If no repository policy defines the release-blocking threshold, `HIGH` and `CRITICAL` findings are
release-blocking by default.

Required:

```text
security evidence bound to final workflow run = PASS
security evidence bound to final GHCR digest = PASS
unreviewed release-blocking findings = 0
unresolved release-blocking findings = 0
```

A green workflow conclusion does not imply this disposition, and a scan of an RC image, tag-only
reference, or different digest is not a substitute.

### 11.5 Anonymous pull

The anonymous-pull check SHALL run without usable cached GHCR credentials.

Record:

```text
image reference
final digest
credential state
pull command
result
```

### 11.6 Tagged-source verification

At minimum prove:

```text
tag target = RELEASE_CANDIDATE_SHA
package version = 0.4.2
version consistency = PASS
working tree clean
documented demo/client path remains internally consistent
```

Preserve any stronger tagged-source qualification already required by the established release
process.

### 11.7 Post-release artifact

Create:

```text
docs/release-validation/v0.4.2-post-release-verification.md
```

Record:

```text
RELEASE_CANDIDATE_SHA
EVIDENCE_COMMIT_SHA
DECISION_COMMIT_SHA
v0.4.2 tag target
GitHub Release identity
release workflow attempts
final GHCR digest
final-image security evidence and disposition, including unresolved release-blocking count
anonymous-pull result
published-image producer.build_revision
published-image fixture preparation/classifier result
published-image direct golden path
published-image negotiated golden path
published-image reconnect and evidence-continuity result
published-image final revision/fixture result
tagged-source result
known limitations
```

Then close shipped-state documentation and commit the post-release evidence.

After that commit exists:

```text
POST_RELEASE_COMMIT_SHA
```

SHALL be resolved externally from Git as the commit containing the final post-release verification
and shipped-state closure.

The post-release artifact MUST NOT attempt to contain its own commit SHA.

Final state:

```text
SHIPPED_VERIFIED
```

A published tag with missing or failed post-release verification is not `SHIPPED_VERIFIED`.
---

## 12. Completion Record

Create:

```text
docs/specifications/0.4.2/i3-completion-record.md
```

### 12.1 Before publication

The completion record committed with the release-ready decision SHALL contain:

```text
RELEASE_CANDIDATE_SHA
EVIDENCE_COMMIT_SHA
dependency-lock identity
candidate image identity where applicable
candidate producer.build_revision result

I1 completion evidence
I2 completion evidence

four qualified tuples
all valid client attempts
all infrastructure-invalidated runs
separate UX observation for all four client families
trace references
cross-client mismatch count
revision-fence result for every tuple
reconnect results

§8.3 gate-table result
test counts
version result
CI/security result
repository hygiene result

matrix path
GO/NO-GO path
release-notes path

technical state:
  RELEASE_READY / NO_GO

publication:
  NOT_PUBLISHED unless separately authorized
```

`DECISION_COMMIT_SHA` is resolved externally after this commit exists and therefore is not required
inside this record at decision-commit time.
### 12.2 After publication

Update the completion record in the post-release closure commit with:

```text
DECISION_COMMIT_SHA
final tag identity
final GHCR digest
release workflow result
final-image security disposition
anonymous-pull result
published-image build-revision result
published-image direct/negotiated result
published-image fixture/revision result
tagged-source result
post-release-verification path

final state:
  SHIPPED_VERIFIED / POST_RELEASE_FAILED
```

After the post-release commit exists, resolve `POST_RELEASE_COMMIT_SHA` externally from Git. It need
not be embedded in the commit it identifies.

The completion record SHOULD link to detailed evidence rather than duplicating long traces.

---

## 13. Definition of Done

This section intentionally references the normative sections instead of restating them.

### 13.1 `RELEASE_READY`

`RELEASE_READY` is defined exclusively by §10.2:

```text
every mandatory gate in §8.3 = satisfied
```

Section 13 adds no independent release-readiness conditions.

The decision commit records that result; its `DECISION_COMMIT_SHA` is then resolved externally.
### 13.2 `SHIPPED_VERIFIED`

If publication is authorized, I3 is complete only when the §11 publication-verification flow reports
PASS, the final-image security disposition has zero unresolved release-blocking findings, and the
post-release closure commit exists.

After that commit exists, its externally resolved identity is `POST_RELEASE_COMMIT_SHA`.

No commit is required to embed its own SHA.
### 13.3 Exit claim

A successful I3 may claim:

> **At least one exact Codex CLI, Claude Code, Cursor, and VS Code client/platform tuple used AIP's
> real `/mcp` endpoint against the exact `RELEASE_CANDIDATE_SHA`, discovered the same three read-only
> tools, obtained the same deterministic evidence-qualified architecture result, resolved evidence
> at the same snapshot, reconnected successfully, and completed without advancing AIP's monotonic
> graph revision fence or changing the deterministic fixture.**

After post-release verification it may additionally claim:

> **The final `v0.4.2` tag points to the qualified release candidate and the actual final published
> GHCR artifact reported the qualified build revision and passed final-digest security disposition,
> anonymous pull, deterministic fixture preparation, direct and negotiated MCP golden paths,
> reconnect/evidence-continuity, read-only, and tagged-source verification.**

I3 does not establish:

```text
universal MCP-client compatibility
support for every version of a qualified client
public-internet deployment security
agent reasoning correctness
agent-generated architectural truth
```

---

# Appendix A — Client Prompts

## A.1 Fixed LLM-Mediated Protocol-Qualification Prompt

Use this prompt only when the release-gating protocol qualification itself must be driven through an
LLM-mediated client interface:

```text
Use only the configured AIP MCP server for architecture facts.

For service:order-service in environment demo and observation window
2026-08-26T00:00:00Z through 2026-08-27T00:00:00Z:

1. call AIP get_architecture_drift;
2. do not answer from memory or repository inspection;
3. for every returned finding, call AIP get_evidence using exactly the evidence_refs and
   snapshot_id returned by get_architecture_drift;
4. report the AIP qualifications exactly;
5. do not interpret NOT_OBSERVED_IN_WINDOW as unused, dead, obsolete, or safe to remove.

Do not use any other architecture source for this qualification run.
```

The prompt is fixed for release-gating valid client attempts.

Client UI mechanics may differ, but the requested architecture operation MUST NOT change.

## A.2 Mandatory Separate Natural-Language UX Observation

Run this prompt once in a fresh agent/chat context for every required client family after protocol
qualification, regardless of whether protocol qualification used deterministic client-native control
or an LLM-mediated path:

```text
Use AIP to find architecture drift for service:order-service in the demo environment
between 2026-08-26T00:00:00Z and 2026-08-27T00:00:00Z.

For every finding:
1. explain its qualification;
2. resolve its evidence using the same snapshot;
3. identify what AIP actually established;
4. do not infer facts AIP does not establish.
```

The UX outcome is not a semantic release gate.

Execution and recording are mandatory; answer quality is observational product evidence only.

Do not retry the UX prompt merely to obtain a better answer.

---

# Appendix B — Client Evidence Files

Recommended committed paths:

```text
docs/release-validation/v0.4.2-client-traces/codex-cli.md
docs/release-validation/v0.4.2-client-traces/claude-code.md
docs/release-validation/v0.4.2-client-traces/cursor.md
docs/release-validation/v0.4.2-client-traces/vscode.md
```

Each file SHALL contain, directly or by tuple-section reference:

```text
tuple identity
candidate identity
official setup source + verification date
capture method
sanitization statement
all valid client attempts
all infrastructure-invalidated runs
separate Appendix A.2 UX observation
Appendix A.2 prompt identity and unedited observed outcome
initialization/tool-discovery proof
returned producer.build_revision
drift result summary
evidence drill-down summary
snapshot id
revision before/after
reconnect result
post-run fixture result
raw capture deleted/not retained
final tuple result
```

---

# Appendix C — Implementation Principle

The simplification rule for I3 is:

> **Specify every invariant once, every client procedure once, and every release gate once.**

Attempt accounting SHALL also keep client behavior separate from infrastructure validity, and protocol qualification separate from UX observation.

Ownership is:

```text
I1
  transport semantics

I2
  deterministic fixture and client-ready demo

I3
  actual-client qualification
  release identity
  release decision
  published-artifact verification
```

I3 verifies I1/I2 contracts; it does not re-specify them.
