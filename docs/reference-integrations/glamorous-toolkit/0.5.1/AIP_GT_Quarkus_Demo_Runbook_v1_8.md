# AIP + Glamorous Toolkit: Quarkus Super Heroes Demo Runbook

**Version:** 1.8 · 27 September 2026  
**Target:** official Glamorous Toolkit (GT) **1.1.601**; published AIP **v0.5.1**  
**Integration:** GT's upstream **gt4llm MCP client** against AIP's standard `POST /mcp` endpoint  
**Task:** before changing image narration in `service:rest-fights`, inspect qualified architecture knowledge and its evidence.  
**Status:** reproducible setup instructions and acceptance criteria, **not a claim that the GT/Quarkus end-to-end workflow has already been executed**.

## 0. Start from a fresh official GT 1.1.601 image (new baseline)

**This is a new baseline, not an upgrade of the GT 1.1.590 order-service image.** Download the official distribution from [GT v1.1.601](https://github.com/feenkcom/gtoolkit/releases/tag/v1.1.601) for your operating system. Extract it into a new folder, for example `gt-1.1.601-aip-quarkus/`, and launch that image. Keep a pristine extracted copy before adding any AIP code. Do not install the old `AIP-GToolkit-2026-09-20.st` file into this image, clone your fork of gt4llm into it, or copy an old GT `.image` / `.changes` file over it.

The upstream fix is [feenkcom/gt4llm PR #12](https://github.com/feenkcom/gt4llm/pull/12), merge `fd91bfa60f1663e71f17361fbab4c0ab5e926e39`: full MCP `inputSchema`, complete `tools/call` result including `structuredContent`, and `GtLMcpFunctionTool`. GT v1.1.601 pins **gt4llm v0.7.304** in [`.baseline-metadata.ston`](https://github.com/feenkcom/gtoolkit/blob/v1.1.601/.baseline-metadata.ston); Git ancestry confirms the fix is included. **No fork, manual gt4llm patch or baseline upgrade is necessary.**

After §§3–5 pass, follow §6 from step 6.1 to create or verify the **two-class** `AIP-GToolkit-Quarkus` object/Inspector layer. The optional agent chat uses official upstream gt4llm without importing historical AIP-specific classes. A new, pristine GT image does not include any AIP-specific classes. Keep the old GT 1.1.590 image archived; do not bulk-import its REST package or local adapter.

Record the baseline before changes:

```text
GT release:           v1.1.601 (official fresh image)
Bundled gt4llm:       v0.7.304 (includes upstream PR #12)
AIP release:          v0.5.1
AIP source ref:       v0.5.1
GT extension package: AIP-GToolkit-Quarkus (created in §6)
Historical reference:  docs/reference-integrations/glamorous-toolkit/0.4.2/
New reference work:   docs/reference-integrations/glamorous-toolkit/0.5.1/
```

## 1. Run the published AIP Quarkus replay

From a checkout at the published `v0.5.1` tag (use another clone/worktree if you want to leave your development tree alone):

```bash
git clone https://github.com/michaelegner/architecture-intelligence-platform.git
cd architecture-intelligence-platform
git checkout v0.5.1
# Ensure Docker + Docker Compose v2 and curl are installed and host ports 8000/4318 are free.
examples/quarkus-super-heroes-demo/run.sh
```

Expected: **“Quarkus Super Heroes demo is ready”**, MCP URL `http://localhost:8000/mcp`, and `.aip-qsh-demo/prompt.txt`. It imports the qualified dossier and disclosed operator-authored AsyncAPI overlay, replays the frozen telemetry once, then **stops the OpenTelemetry Collector**; AIP and Neo4j stay running. It does **not** start Quarkus, Kafka or a Kubernetes cluster. Do not ingest anything else into this graph during the demo, since that invalidates snapshot-bound references.

Check connectivity from the **same machine/network context where GT runs**:

```bash
curl -fsS http://127.0.0.1:8000/health
# An HTTP GET of /mcp is NOT a health check; the endpoint is POST-only.
```

If GT runs in a VM/container, replace `127.0.0.1` with an accessible host address and validate network reachability; never assume localhost crosses machine/container boundaries.

### Frozen query values (reference only — do not paste as Smalltalk)

The following values describe the **published, untouched AIP replay**. They are *not executable GT Playground code*. Sections **3–5** contain complete Smalltalk snippets that construct the request; do not copy this table or Markdown fences into GT. For actual code, copy the contents of the fenced block as plain text, not a rich-text rendition that turns URL strings into `[text](link)`.

| Parameter | Value |
|---|---|
| MCP endpoint | `http://127.0.0.1:8000/mcp` |
| `service_id` | `service:rest-fights` |
| `environment` | `quarkus-i5` |
| `window_start` | `2026-09-25T13:06:47Z` |
| `window_end` | `2026-09-25T13:06:54Z` |

The expected clean-replay snapshot is:

```text
aip:snapshot:v1:dc21e13dcf235b7526433318104531fc1edd944359a6a12b05d4843e4f4120fc
```

Treat this ID as an **assertion for the untouched frozen replay**, not a query input or a general constant. Always send the *actual returned* snapshot ID to `get_evidence`. The snapshot value above is not intended to be evaluated as Smalltalk.

**After completing §6A (steps 6.1–6.8)**, a single executable GT Playground expression is sufficient to load the demo object (copy only the content within the code fence, not the Markdown backticks):

```smalltalk
| profile |
profile := GtAipMcpClient new quarkusFights.
profile
```

To check the frozen result, run this **separately**, again after §6A:

```smalltalk
| profile expectedSnapshot |
profile := GtAipMcpClient new quarkusFights.
expectedSnapshot := 'aip:snapshot:v1:dc21e13dcf235b7526433318104531fc1edd944359a6a12b05d4843e4f4120fc'.
{
    profile outcome.
    profile snapshotId = expectedSnapshot.
    profile httpClaims size.
    profile messagingClaims size.
    profile deploymentClaims size.
    profile limitations size
}
```

Expected: `#('PARTIAL' true 7 1 1 1)` conceptually (GT may display a brace-array representation). If the snapshot check is false, first verify that the replay has not changed. **Do not** override the returned snapshot merely to satisfy this assertion.

## 2. Check the upstream gt4llm fix inside GT 1.1.601

Open GT's Playground and **Inspect** each expression:

```smalltalk
Smalltalk globals includesKey: #GtLMcpFunctionTool
```

Expected: `true`. Next:

```smalltalk
GtLMcpClient canUnderstand: #callToolResult:withArguments:
```

Expected: `true`. The upstream self-contained regression example can be executed without AIP:

```smalltalk
GtLMcpClientExamples new
    llmFunctionToolPreservesInputSchemaAndCompleteResult
```

It must finish without an assertion failure; it verifies the nested input schema, `GtLMcpFunctionTool`, and complete result preservation. Also available: `callToolResultPreservesStructuredContent`.

If any are missing, verify the **actual running GT image** is 1.1.601. Do not silently file in an old local gt4llm fork or change the archived 1.1.590 baseline.

## 3. MCP compatibility gate in the Playground

**Copy/paste safety:** Copy only the text inside a `smalltalk` code block, paste it as **plain text** into GT (Windows: `Ctrl+Shift+V` where supported), and evaluate the **whole** snippet in a fresh Playground. Do not paste Markdown backticks, rendered hyperlinks, or HTML entities such as `&#x20;`. The MCP URL is deliberately built as two Smalltalk string fragments to stop rich-text editors from converting it into a clickable Markdown link. Code in Sections 3–5 is independent: no local temporary variable from another Playground evaluation is required.

GT 1.1.601's `GtLMcpClient` uses `transport:` to initialize the MCP connection; its HTTP transport is `GtLMcpHttpTransport`. The following method names and result path have been checked against **gt4llm v0.7.304**. Evaluate the whole block as one Playground snippet and **Inspect the last expression**:

```smalltalk
| transport client toolNames |

transport := GtLMcpHttpTransport new.
transport url: ('http' , '://127.0.0.1:8000/mcp').

client := GtLMcpClient new.
client transport: transport.

toolNames := client listTools collect: [ :tool |
    tool at: 'name' ].

toolNames
```

Expected order (three read-only tools):

```text
get_architecture_drift
get_evidence
get_service_dependencies
```

**Connection gate:** If `transport:` fails during `initializeSession`, stop here rather than debugging domain-object views. The bundled client currently offers MCP protocol version `2024-11-05`; AIP v0.5.1 uses negotiated MCP and documents `2025-11-25` for direct calls. Confirm the negotiated version and transport behavior in the actual GT image. If incompatible, use a standard compliant MCP client to compare the server response and file a minimal gt4llm compatibility issue; **do not claim this integration passed or bypass the public MCP contract**. No private AIP endpoint is a substitute for passing this gate.

To inspect the fixed input schema before calling a tool, evaluate this **independent, complete** block in a fresh Playground:

```smalltalk
| transport client depTool |

transport := GtLMcpHttpTransport new.
transport url: ('http' , '://127.0.0.1:8000/mcp').
client := GtLMcpClient new.
client transport: transport.

depTool := client llmFunctionTools detect: [ :each |
    each name = 'get_service_dependencies' ].

depTool parametersJsonSchemaDictionary
```

Expected: an object schema with a **required nested `request` property**, not a flattened list of argument names. The connection is recreated intentionally because Playground temporary variables are local to their evaluation.

## 4. Query AIP through MCP — retain the whole result

Run as a single Playground snippet. Here `callToolResult:withArguments:` is important: the older `callTool:withArguments:` intentionally returns **only `content`** and would lose `structuredContent`.

```smalltalk
| transport client context arguments result answer |

transport := GtLMcpHttpTransport new.
transport url: ('http' , '://127.0.0.1:8000/mcp').
client := GtLMcpClient new.
client transport: transport.

context := {
    'environment' -> 'quarkus-i5'.
    'window_start' -> '2026-09-25T13:06:47Z'.
    'window_end' -> '2026-09-25T13:06:54Z'
} asDictionary.

arguments := {'request' -> {
    'service_id' -> 'service:rest-fights'.
    'observation_context' -> context
} asDictionary} asDictionary.

result := client
    callToolResult: 'get_service_dependencies'
    withArguments: arguments.

(result at: 'isError' ifAbsent: [ false ])
    ifTrue: [ Error signal: 'MCP tool returned isError=true' ].

answer := result at: 'structuredContent'.
answer
```

The **required** check is `isError` not true. The last expression should be a Dictionary-shaped architecture answer, not an array of text blocks. It must contain `snapshot`, `claims`, `outcome`, `data`, `limitations` and `evidence_refs`. For this replay, dependencies outcome is `PARTIAL`, and the schema version is `0.5` (producer version `0.5.1`).

For a compact inspection of the result, **Inspect the complete `answer` Dictionary returned by the executable block above** and expand its `outcome`, `snapshot`, `claims` and `limitations` keys. This is not a separate Playground code sample; you do not need to retain temporary variables across evaluations.

**Expected semantics:** seven `CALLS` (3 `CONFIRMED`, 4 `NOT_OBSERVED_IN_WINDOW`), one `DEPLOYED_AS` resolved as `RESOLVED_CONFIGURED`, and one `PUBLISHES_TO` Topic `fights` (`NOT_OBSERVED_IN_WINDOW`, `PARTIAL` coverage, `DIRECT_TARGET_FALLBACK`, no evidenced Subscription). One answer limitation: `UNRESOLVED_IDENTITY` for the Topic claim. This is **nine claims in total**; do not flatten it into just three target-service edges.

## 5. Verify snapshot-bound evidence drill-down

This is an **independent Playground snippet**. It queries dependencies again and then resolves their aggregate references using the **returned** snapshot. It does not assume that temporary variables from Section 4 remain in scope:

```smalltalk
| transport client context args result answer snapshotId evidenceResult evidence |

transport := GtLMcpHttpTransport new.
transport url: ('http' , '://127.0.0.1:8000/mcp').
client := GtLMcpClient new.
client transport: transport.

context := {
    'environment' -> 'quarkus-i5'.
    'window_start' -> '2026-09-25T13:06:47Z'.
    'window_end' -> '2026-09-25T13:06:54Z'
} asDictionary.
args := {'request' -> {
    'service_id' -> 'service:rest-fights'.
    'observation_context' -> context
} asDictionary} asDictionary.

result := client
    callToolResult: 'get_service_dependencies'
    withArguments: args.
(result at: 'isError' ifAbsent: [ false ])
    ifTrue: [ Error signal: 'Dependency tool returned isError=true' ].
answer := result at: 'structuredContent'.
snapshotId := (answer at: 'snapshot') at: 'snapshot_id'.

evidenceResult := client
    callToolResult: 'get_evidence'
    withArguments: {'request' -> {
        'snapshot_id' -> snapshotId.
        'evidence_refs' -> (answer at: 'evidence_refs')
    } asDictionary} asDictionary.
(evidenceResult at: 'isError' ifAbsent: [ false ])
    ifTrue: [ Error signal: 'Evidence tool returned isError=true' ].
evidence := evidenceResult at: 'structuredContent'.

{
    evidence at: 'outcome'.
    (evidence at: 'snapshot') at: 'snapshot_id'.
    ((evidence at: 'data') at: 'missing_evidence_refs').
    ((evidence at: 'data') at: 'records') size
}
```

Expected: `ANSWERED`, same snapshot, empty `missing_evidence_refs`, and **9 resolved evidence records** for the clean published replay. Verify record IDs match `answer at: 'evidence_refs'` (compare sets, not incidental order). For a claim-level evidence view, take the selected claim's `evidence_refs` **and** `resolution_evidence_refs` as applicable; deduplicate, and resolve at the same answer snapshot. `get_evidence` accepts **1–20 references** per call; do not send an empty set.

To inspect drift, use the **independent complete Playground block in step 6.8**, once the client class has been created. It returns `PARTIAL` with five declared-but-not-observed claims and no deployment claims.

## 6. Build the GT object explorer, then optionally enable the agent — complete sequence

**Start here with a fresh official GT 1.1.601 working image.** Sections 1–5 must first have passed against the Quarkus demo running from the checked-out AIP v0.5.1 source (the version and demo contract currently on `main`, as checked on 27 September 2026). In particular, Section 3 must show all three AIP MCP tools and Section 5 must resolve the evidence at the **returned** snapshot. Do not proceed if MCP negotiation fails. Nothing below installs or changes gt4llm: GT 1.1.601 already bundles the generic fix from feenkcom/gt4llm PR #12.

This section has **two independent completion points**:

- **Step 6A, no LLM needed:** a working, inspectable `GtAipArchitectureAnswer` with four GT Inspector views and snapshot-bound evidence drill-down. Complete steps 6.1–6.8.
- **Step 6B, optional LLM:** let a GT-hosted agent inspect the same object and/or call AIP MCP tools. Complete optional step 6.9 **only after 6A passes**. It uses upstream gt4llm; no archived AIP classes or local gt4llm adapter are required.

**Where to type:** A block labeled **Coder method** is a complete instance-side method definition: add it as a *separate method* in the class named above, **not** in Playground. A block labeled **Playground** is an independent expression: paste its entire contents into a **fresh** GT Playground and choose **Inspect** on the last expression. Do not include Markdown backticks. Use plain text, not a rendered rich-text hyperlink. No Playground block depends on temporary variables from any previous block.

### 6.1 Prepare the GT image and confirm what is already installed

1. Close GT after saving any work, make a filesystem copy of the official extracted 1.1.601 directory, and open the **working copy**. Keep the pristine copy untouched. Do not open the old 1.1.590 image or copy its `.image` / `.changes` files into the new folder.
2. On GT's World screen open Spotter/Search, search for **Coder**, and open it. You will use Coder to create one package and two classes. A Playground can be opened from GT World (search **Playground**) or as a contextual pane in Coder.
3. In a fresh Playground evaluate the following **complete** inventory. The upstream entries must be `true`. On a completely untouched GT 1.1.601 image the two `GtAip...` entries will initially be `false`; if you have already completed this runbook's previous Section 6, they can be `true` — **inspect before overwriting methods**.

**Playground — independent:**

```smalltalk
{
    #GtLMcpClient -> (Smalltalk globals includesKey: #GtLMcpClient).
    #GtLMcpHttpTransport -> (Smalltalk globals includesKey: #GtLMcpHttpTransport).
    #GtLMcpFunctionTool -> (Smalltalk globals includesKey: #GtLMcpFunctionTool).
    #GtAipMcpClient -> (Smalltalk globals includesKey: #GtAipMcpClient).
    #GtAipArchitectureAnswer -> (Smalltalk globals includesKey: #GtAipArchitectureAnswer)
}
```

**Pass condition:** the first three values are `true`. If either AIP-specific class already exists, open it in Coder and compare its instance slots and methods with steps 6.2–6.6; fill gaps, do not create a duplicate class.

### 6.2 Create the package and two classes in Coder

In Coder choose the **add package** action and enter `AIP-GToolkit-Quarkus`. Add these two classes to that package, **both with superclass `Object`**:

| Class to create | Exact instance slots | Class-side slots |
|---|---|---|
| `GtAipMcpClient` | `client` | none |
| `GtAipArchitectureAnswer` | `data`, `client` | none |

Use Coder's instance-side class/slots editor, not the class-side editor. Keep all methods below on the **instance side**. Do not create `GtLMcpClient`, `GtLMcpFunctionTool` or `GtLMcpHttpTransport`: they are upstream classes already present. Do not import the historical REST-based `AIP-GToolkit` package.

**Playground — independent class/slot check, after creating them:**

```smalltalk
{
    GtAipMcpClient superclass.
    GtAipMcpClient allInstVarNames.
    GtAipArchitectureAnswer superclass.
    GtAipArchitectureAnswer allInstVarNames
}
```

**Pass condition:** both superclasses are `Object`; the first class has `client`, the second has `data` and `client`. Stop and correct the slots before pasting methods.

### 6.3 Add the transport and generic tool call to `GtAipMcpClient`

In Coder select `GtAipMcpClient`, instance side. Use **Add method** four times; paste **one complete method at a time**, compile/save it, then continue. The endpoint is assembled as two Smalltalk strings solely to prevent rich-text link conversion during copying. It resolves to `http://127.0.0.1:8000/mcp` on the same host as GT.

**Coder method 1 — `GtAipMcpClient>>initialize`:**

```smalltalk
initialize
    super initialize.
    client := GtLMcpClient new.
    client transport: (GtLMcpHttpTransport new
        url: ('http' , '://127.0.0.1:8000/mcp');
        yourself)
```

**Coder method 2 — `GtAipMcpClient>>call:request:`:**

```smalltalk
call: toolName request: aDictionary
    | result |
    result := client
        callToolResult: toolName
        withArguments: {'request' -> aDictionary} asDictionary.
    (result at: 'isError' ifAbsent: [ false ])
        ifTrue: [ Error signal: 'AIP MCP tool returned isError=true' ].
    ^ result at: 'structuredContent'
```

**Coder method 3 — `GtAipMcpClient>>quarkusContext`:**

```smalltalk
quarkusContext
    ^ {
        'environment' -> 'quarkus-i5'.
        'window_start' -> '2026-09-25T13:06:47Z'.
        'window_end' -> '2026-09-25T13:06:54Z'
    } asDictionary
```

**Coder method 4 — `GtAipMcpClient>>dependenciesFor:`:**

```smalltalk
dependenciesFor: serviceId
    | rawAnswer answer |
    rawAnswer := self
        call: 'get_service_dependencies'
        request: {
            'service_id' -> serviceId.
            'observation_context' -> self quarkusContext
        } asDictionary.
    answer := GtAipArchitectureAnswer new.
    answer data: rawAnswer client: self.
    ^ answer
```

The fourth method refers to the class that you created in step 6.2. Its method `data:client:` is added in step 6.5, so **do not execute the client yet**.

### 6.4 Add the Quarkus entry point and evidence/drift operations to `GtAipMcpClient`

Continue in the **same class**, instance side. Add and compile these three **individual complete methods**.

**Coder method 5 — `GtAipMcpClient>>quarkusFights`:**

```smalltalk
quarkusFights
    ^ self dependenciesFor: 'service:rest-fights'
```

**Coder method 6 — `GtAipMcpClient>>evidenceRefs:snapshotId:`:**

```smalltalk
evidenceRefs: references snapshotId: snapshotId
    references ifEmpty: [
        Error signal: 'No evidence references supplied' ].
    references size > 20 ifTrue: [
        Error signal: 'get_evidence accepts at most 20 refs per call' ].
    ^ self
        call: 'get_evidence'
        request: {
            'evidence_refs' -> references.
            'snapshot_id' -> snapshotId
        } asDictionary
```

**Coder method 7 — `GtAipMcpClient>>driftFor:`:**

```smalltalk
driftFor: serviceId
    ^ self
        call: 'get_architecture_drift'
        request: {
            'service_id' -> serviceId.
            'observation_context' -> self quarkusContext
        } asDictionary
```

No agent/LLM is involved. These methods call only AIP's three published read-only MCP tools. The returned `structuredContent` is kept intact. The evidence method refuses empty and over-limit requests rather than silently discarding refs. The generic integration can later add batching; the frozen Quarkus aggregate has nine refs and needs none.

### 6.5 Add the raw-answer accessors to `GtAipArchitectureAnswer`

In Coder switch to `GtAipArchitectureAnswer`, instance side. **Each code fence below is a separate complete Coder method**, not a Playground script. The model retains the original AIP response; it does not replace it with a guessed service-edge graph.

**Coder method 1 — assign raw data and client:**

```smalltalk
data: aDictionary client: aClient
    data := aDictionary.
    client := aClient
```

**Coder method 2 — AIP outcome:**

```smalltalk
outcome
    ^ data at: 'outcome'
```

**Coder method 3 — exact originating snapshot:**

```smalltalk
snapshotId
    ^ (data at: 'snapshot') at: 'snapshot_id'
```

**Coder method 4 — complete claims:**

```smalltalk
claims
    ^ data at: 'claims'
```

**Coder method 5 — explicit AIP limitations:**

```smalltalk
limitations
    ^ data at: 'limitations'
```

**Coder method 6 — separate dependency claims:**

```smalltalk
dependencyClaims
    ^ self claims select: [ :claim |
        (claim at: 'predicate') = 'DIRECT_DEPENDENCY' ]
```

**Coder method 7 — separate deployment claims:**

```smalltalk
deploymentClaims
    ^ self claims select: [ :claim |
        (claim at: 'predicate') = 'DEPLOYED_AS' ]
```

**Coder method 8 — HTTP calls, each operation retained:**

```smalltalk
httpClaims
    ^ self dependencyClaims select: [ :claim |
        ((claim at: 'delivery') at: 'relation_type') = 'CALLS' ]
```

**Coder method 9 — Topic publication claims:**

```smalltalk
messagingClaims
    ^ self dependencyClaims select: [ :claim |
        ((claim at: 'delivery') at: 'relation_type') = 'PUBLISHES_TO' ]
```

**Coder method 10 — independent deployment reconciliation data:**

```smalltalk
deploymentResolutions
    ^ (data at: 'data') at: 'deployment_resolutions'
```

**Coder method 11 — resolve a selected claim's evidence, including destination-resolution evidence if present:**

```smalltalk
evidenceForClaim: aClaim
    | refs evidence |
    refs := (aClaim at: 'evidence_refs') asOrderedCollection.
    refs addAll: (aClaim
        at: 'resolution_evidence_refs'
        ifAbsent: [ #() ]).
    refs := refs asSet asArray.
    evidence := client
        evidenceRefs: refs
        snapshotId: self snapshotId.
    ((evidence at: 'snapshot') at: 'snapshot_id') = self snapshotId
        ifFalse: [ Error signal: 'Evidence snapshot mismatch' ].
    ^ evidence
```

A `DEPLOYED_AS` claim has **no** `resolution_evidence_refs`; the `ifAbsent:` above is deliberate. This method returns AIP's complete evidence answer, including `records` and `missing_evidence_refs`. Claim evidence and resolution evidence remain separate in the original claim dictionary even though the lookup deduplicates the set for efficiency.

### 6.6 Test the two-class object layer **before** adding any Inspector views

Open a **new GT Playground**. Copy/evaluate the entire code fence, then **Inspect** the last expression. This invokes `GtAipMcpClient>>initialize`, so a network/protocol error belongs to the MCP gate in Section 3, not to this data model.

**Playground — independent:**

```smalltalk
| profile |
profile := GtAipMcpClient new quarkusFights.
{
    profile outcome.
    profile claims size.
    profile httpClaims size.
    profile messagingClaims size.
    profile deploymentClaims size.
    profile limitations size
}
```

**Expected:** `#('PARTIAL' 9 7 1 1 1)` conceptually. If it fails, inspect a **fresh** raw answer with the complete Section 4 snippet and compare the actual keys; do not change expected claims to force the demo to pass.

Now verify claim-level evidence using a **different complete Playground block**. This tests the exact operation and the snapshot used by the object model; it does not reuse a previous Playground's `profile` temporary.

**Playground — independent:**

```smalltalk
| profile claim evidence |
profile := GtAipMcpClient new quarkusFights.
claim := profile httpClaims detect: [ :each |
    (((each at: 'delivery') at: 'via') at: 'name')
        = 'GET /api/heroes/random' ].
evidence := profile evidenceForClaim: claim.
{
    claim at: 'qualification'.
    evidence at: 'outcome'.
    ((evidence at: 'data') at: 'missing_evidence_refs') size.
    ((evidence at: 'data') at: 'records') size.
    (evidence at: 'snapshot') at: 'snapshot_id'
}
```

**Expected:** `CONFIRMED`, `ANSWERED`, `0` missing refs, `3` records (manifest declaration + observed OTel + target OpenAPI resolution), and the same snapshot returned by the profile. Do not embed a frozen snapshot constant in this lookup.

### 6.7 Add four Inspector views to `GtAipArchitectureAnswer`

Return to **Coder**, select `GtAipArchitectureAnswer` → **instance side**. Add these **four complete methods one at a time**. No extra view/claim classes are needed; selecting a row initially opens the original claim Dictionary. The tab code does **not** call MCP again; it projects the already-held answer.

**Coder method 12 — HTTP operations, expected 7 rows:**

```smalltalk
gtOperationsFor: aView
    <gtView>
    ^ aView columnedList
        title: 'HTTP operations';
        priority: 10;
        items: [ self httpClaims ];
        column: 'Target' text: [ :claim |
            (claim at: 'object') at: 'name' ];
        column: 'Operation' text: [ :claim |
            ((claim at: 'delivery') at: 'via') at: 'name' ];
        column: 'Qualification' text: [ :claim |
            claim at: 'qualification' ];
        column: 'Coverage' text: [ :claim |
            (claim at: 'coverage') ifNil: [ '' ] ]
```

**Coder method 13 — Messaging, expected 1 Topic row:**

```smalltalk
gtMessagingFor: aView
    <gtView>
    ^ aView columnedList
        title: 'Messaging';
        priority: 11;
        items: [ self messagingClaims ];
        column: 'Topic' text: [ :claim |
            ((claim at: 'delivery') at: 'via') at: 'name' ];
        column: 'Qualification' text: [ :claim |
            claim at: 'qualification' ];
        column: 'Resolution' text: [ :claim |
            claim at: 'destination_resolution' ];
        column: 'Subscription' text: [ :claim |
            ((claim at: 'delivery') at: 'subscription' ifAbsent: [ nil ])
                ifNil: [ 'Not resolved' ]
                ifNotNil: [ :sub | sub at: 'name' ] ]
```

**Coder method 14 — deployment claims, expected 1 row:**

```smalltalk
gtDeploymentsFor: aView
    <gtView>
    ^ aView columnedList
        title: 'Deployment claims';
        priority: 12;
        items: [ self deploymentClaims ];
        column: 'Workload' text: [ :claim |
            (claim at: 'object') at: 'name' ];
        column: 'Namespace' text: [ :claim |
            (claim at: 'object') at: 'namespace' ];
        column: 'Resolution' text: [ :claim |
            claim at: 'resolution_method' ]
```

**Coder method 15 — AIP limitations, expected 1 row:**

```smalltalk
gtLimitationsFor: aView
    <gtView>
    ^ aView columnedList
        title: 'Limitations';
        priority: 13;
        items: [ self limitations ];
        column: 'Code' text: [ :each |
            each at: 'code' ];
        column: 'Explanation' text: [ :each |
            each at: 'message' ] weight: 3
```

After compiling all four, open a **fresh Playground** and evaluate:

**Playground — independent:**

```smalltalk
| profile |
profile := GtAipMcpClient new quarkusFights.
profile
```

Choose **Inspect**, not Print. You should have tabs **HTTP operations**, **Messaging**, **Deployment claims**, and **Limitations**. Open each and check row counts `7/1/1/1`. If a tab is absent, verify its `gt...For:` method was compiled on the **instance side**, includes `<gtView>`, and has no compilation errors.

### 6.8 Reproduce a second service and the drift question, without hidden variables

Use these two additional **independent** Playground blocks. They demonstrate that the model and client aren't hardcoded to falsely resolve all service deployments or to show deployment claims in drift.

**Playground — `rest-narration` independent request:**

```smalltalk
| profile |
profile := GtAipMcpClient new
    dependenciesFor: 'service:rest-narration'.
{
    profile outcome.
    profile claims size.
    profile deploymentClaims size.
    profile deploymentResolutions size.
    profile limitations size
}
```

**Expected:** `ANSWERED`, then four zeros. A same-named offline Kubernetes Deployment does not establish a service-to-workload mapping.

**Playground — drift independent request:**

```smalltalk
| drift |
drift := GtAipMcpClient new driftFor: 'service:rest-fights'.
{
    drift at: 'outcome'.
    (drift at: 'claims') size.
    (drift at: 'claims') collect: [ :claim |
        claim at: 'qualification' ]
}
```

**Expected:** `PARTIAL`, five claims, all `NOT_OBSERVED_IN_WINDOW`. There are no `DEPLOYED_AS` drift claims. **Checkpoint: 6A is finished here.** Save the working GT image using GT's normal Save action before moving on.

### 6.9 Optional: launch the GT agent over the existing Quarkus object

Only perform this optional step if you want natural-language agent exploration. Configure a **default LLM connection** using GT's normal connection UI first; AIP itself needs no LLM credentials. Open a **fresh** GT Playground and evaluate the **whole** block below. It verifies the connection, constructs a default-provider chat, loads the current Quarkus MCP answer, stores that exact object in GT's object storage, and exposes GT's built-in object-exploration tools alongside the three public AIP MCP tools. It does not require any archived class, old installer or previous Playground variable. GT object-execution tools can evaluate Smalltalk: use a trusted provider and review agent actions; natural-language instructions are not a sandbox.

**Playground — independent, optional LLM:**

```smalltalk
| connection provider mcpClient transport allTools chat profile storedId |

connection := GtLConnectionRegistry uniqueInstance defaultConnection.
connection ifNil: [
    Error signal: 'Configure a default GT LLM connection first' ].
provider := connection buildProvider.

transport := GtLMcpHttpTransport new.
transport url: ('http' , '://127.0.0.1:8000/mcp').
mcpClient := GtLMcpClient new.
mcpClient transport: transport.

allTools := OrderedCollection new.
allTools addAll: mcpClient llmFunctionTools.
allTools addAll: GtLTools gtObjectsExecution.

profile := GtAipMcpClient new quarkusFights.
chat := GtLChat new.
chat provider: provider.
chat markdownResponse.
chat tools: (GtLTools withAll: allTools).
chat instruction: 'AIP MCP structuredContent is the architecture knowledge source. Inspect the stored Quarkus object and use the three read-only AIP MCP tools for additional service/drift/evidence questions. Reuse the returned snapshot_id for get_evidence. Keep declared vs observed and claim evidence vs resolution evidence distinct. Never infer an unused operation from NOT_OBSERVED_IN_WINDOW; do not invent a Kafka Subscription/consumer or deployment identity from matching names. Agent suggestions are not AIP facts. Do not compile or remove methods/classes, mutate AIP, or write files.' titled: 'Architecture investigation boundaries'.
chat instruction: 'Default AIP query: service:rest-fights, environment quarkus-i5, window_start 2026-09-25T13:06:47Z, window_end 2026-09-25T13:06:54Z. This is query context, never a hardcoded snapshot. Start from the stored GT profile when possible.' titled: 'Quarkus demo context'.
storedId := chat
    addNewObject: profile
    reasonString: 'Quarkus Fights API: evidence-qualified AIP architecture answer'.
chat inspect
```

**Pass condition:** GT opens a chat; inspect its object storage and verify that the just-created `GtAipArchitectureAnswer` is present. The chat may use the three AIP tools and GT object tools. If provider initialization fails, fix the GT LLM connection independently; a successful AIP MCP check does not configure a model for you.

Ask these questions **one by one in this new chat**, inspecting the tool trace after each one:

1. `Inspect the stored Quarkus architecture object. What are its exact outcome, snapshot, and operation-level HTTP claims?` Expected: `PARTIAL`, seven CALLS, three confirmed/four not observed; preserve operation identity.
2. `Compare POST /api/narration with POST /api/narration/image in the stored object. What evidence is available for each? Resolve refs at the originating snapshot.` Expected: the first is confirmed, the second declared but not observed in this window; evidence provenance remains explicit.
3. `Where is rest-fights deployed, and does the same-named rest-narration Deployment establish the same identity? Query rest-narration separately.` Expected: configured mapping for fights; no qualified deployment claim/resolution for narration.
4. `Does the system publish to Topic fights, and which consumer is evidenced?` Expected: declared operator overlay; no evidenced Subscription/consumer; explicit `UNRESOLVED_IDENTITY`.
5. `Before changing image narration, separate AIP findings, dossier context, and your suggested investigations.` Expected: no invented safety verdict, missing gRPC support clearly distinguished from an AIP limitation.

**Trace checks:** An architecture claim comes from the stored AIP object or an actual AIP MCP tool result, never from chat prose alone. When discussing detailed evidence, verify an actual `get_evidence` call using the originating snapshot. Avoid claiming that this new v0.5.1 agent integration passed just because the older v0.4.2 PoC passed.

### 6.10 Save the new baseline and verify completion

After **6A** works, use GT's normal **Save** action and then, in a **new Playground**, export just the newly authored package:

**Playground — independent:**

```smalltalk
#'AIP-GToolkit-Quarkus' asPackage fileOut.
FileLocator imageDirectory
```

Find the exported `.st` in the displayed image directory and retain it alongside your runbook. Keep a copy of the full working GT image, separate from the untouched official 1.1.601 extraction. If you also completed the optional agent chat, record the model/provider used, exact AIP main/tag commit, and the observed MCP/evidence/agent test outcomes. Do not claim pass for steps not actually executed.

**Final gate:** official GT 1.1.601 and upstream gt4llm only; MCP tools 3; AIP answer `PARTIAL` with `9` claims (`7 CALLS`, `1 PUBLISHES_TO`, `1 DEPLOYED_AS`) and one `UNRESOLVED_IDENTITY`; four working GT views; evidence resolved at the returned snapshot with no missing refs; no name-based deployment or consumer inference. The agent chat is optional, not a prerequisite for a correct, useful GT object explorer.

## 7. Demo acceptance checklist

- [ ] GT image identifies as 1.1.601 and `GtLMcpFunctionTool` exists.
- [ ] Upstream `llmFunctionToolPreservesInputSchemaAndCompleteResult` example passes.
- [ ] Published AIP v0.5.1 demo prints “ready”; GT reaches `127.0.0.1:8000`.
- [ ] GT's MCP initialization succeeds; `listTools` returns exactly the three tools.
- [ ] Advertised input schema retains required nested `request`.
- [ ] `callToolResult:withArguments:` returns `structuredContent`; result is not discarded or parsed from rendered prose.
- [ ] Dependencies are `PARTIAL` and preserve seven HTTP operations, the configured deployment claim and the declared Topic.
- [ ] `get_evidence` is `ANSWERED`, with the answer's *same* snapshot and no missing refs (9/9 in frozen replay).
- [ ] `get_architecture_drift` lists five `NOT_OBSERVED_IN_WINDOW` claims; the distinction from `CONFIRMED` is retained.
- [ ] GT does not resolve `rest-narration` by name, invent Kafka consumers, treat missing traffic as unused, or hide the operator overlay provenance.
- [ ] The newly created/verified two-class §6A MCP layer loads nine claims and shows four contextual views. The optional GT chat (step 6.9) is separately checked if used. No old PoC classes or local gt4llm adapter are imported; the archived GT 1.1.590 reference remains untouched.

## 8. Teardown and repeatability

```bash
examples/quarkus-super-heroes-demo/run.sh --down
```

This deletes the `aip-qsh-demo` Compose project data and `.aip-qsh-demo/` run state; it **does not** remove GT's image or package changes. Re-run `run.sh` for a fresh snapshot after any graph mutation. If the AIP demo prints **NOT ready**, inspect its listed differences first; do not change expected values to make the demonstration green. If port 8000 is occupied by the older minimal demo, stop that demo via `examples/runtime-demo/mcp-demo.sh --down` before starting Quarkus.

### Troubleshooting order

1. AIP health/replay readiness (host, Docker, ports).
2. Network path from GT to AIP; `/mcp` is POST-only.
3. GT version and upstream gt4llm examples.
4. Actual MCP `initialize`/protocol negotiation and JSON/SSE decoding; do not bypass by REST while describing the connection as MCP.
5. Tools, complete nested `request`, `structuredContent`, same-snapshot evidence.
6. Only then debug the GT object wrappers, Inspector views and optional GT chat.

### Primary references

- [AIP v0.5.1 demo README](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.1/examples/quarkus-super-heroes-demo/README.md)
- [Task walkthrough Q1–Q8](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.1/examples/quarkus-super-heroes-demo/walkthrough.md)
- [AIP MCP contract](https://github.com/michaelegner/architecture-intelligence-platform/blob/v0.5.1/docs/mcp.md)
- [gt4llm v0.7.304 client](https://github.com/feenkcom/gt4llm/blob/v0.7.304/src/Gt4LlmCore/GtLMcpClient.class.st) and [HTTP transport](https://github.com/feenkcom/gt4llm/blob/v0.7.304/src/Gt4LlmCore/GtLMcpHttpTransport.class.st)
- [gt4llm PR #12 regression examples](https://github.com/feenkcom/gt4llm/blob/v0.7.304/src/Gt4LlmCore-Examples/GtLMcpClientExamples.class.st)
- [AIP × GT historical reference (0.4.2)](https://github.com/michaelegner/architecture-intelligence-platform/tree/main/docs/reference-integrations/glamorous-toolkit/0.4.2) and [new integration (0.5.1)](https://github.com/michaelegner/architecture-intelligence-platform/tree/main/docs/reference-integrations/glamorous-toolkit/0.5.1) (directory migration merged in PR #276)
