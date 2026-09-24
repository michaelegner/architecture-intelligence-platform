| explorerClass microToolClass |

BlSpace userFontScale: 1.2.

microToolClass := Smalltalk at: #GtAipEphemeralMicroTool.

microToolClass
    compile: 'overviewRows
    | orderedRows priorityDependencies |
    orderedRows := OrderedCollection new.
    priorityDependencies := #(''unused-q'' ''payment-q'' ''LegacyPricingService'').
    priorityDependencies do: [ :dependency |
        self rows do: [ :row |
            (row at: ''dependency'' ifAbsent: [ nil ]) = dependency
                ifTrue: [ orderedRows add: row ] ] ].
    self rows do: [ :row |
        (priorityDependencies includes: (row at: ''dependency'' ifAbsent: [ nil ]))
            ifFalse: [ orderedRows add: row ] ].
    ^ orderedRows'
    classified: 'aip inspection'.

microToolClass
    compile: 'gtResultsFor: aView
    <gtView>
    | resultView |
    resultView := aView columnedList
        title: ''Results'';
        priority: 10;
        items: [ self overviewRows ].
    self columns do: [ :columnSpec |
        | label key |
        label := columnSpec at: ''label''.
        key := columnSpec at: ''key''.
        resultView column: label text: [ :row |
            | value |
            value := row at: key ifAbsent: [ '''' ].
            value ifNil: [ '''' ] ifNotNil: [ value asString ] ] ].
    ^ resultView'
    classified: 'aip inspection'.

microToolClass
    compile: 'gtAipDetailsFor: aView
    <gtView>
    ^ aView columnedList
        title: ''AIP details'';
        priority: 14;
        items: [ self rows ];
        column: ''Dependency'' text: [ :row | row at: ''dependency'' ifAbsent: [ '''' ] ];
        column: ''Claim ID'' text: [ :row | row at: ''claimId'' ifAbsent: [ '''' ] ];
        column: ''Claim evidence refs'' text: [ :row | (row at: ''claimEvidenceRefs'' ifAbsent: [ #() ]) asString ];
        column: ''Resolution evidence refs'' text: [ :row | (row at: ''resolutionEvidenceRefs'' ifAbsent: [ #() ]) asString ];
        column: ''Snapshot'' text: [ :row | row at: ''snapshotId'' ifAbsent: [ '''' ] ];
        column: ''Limitations'' text: [ :row | (row at: ''limitations'' ifAbsent: [ #() ]) asString ];
        column: ''Claim evidence'' text: [ :row | (row at: ''claimEvidence'' ifAbsent: [ #() ]) asString ];
        column: ''Resolution evidence'' text: [ :row | (row at: ''resolutionEvidence'' ifAbsent: [ #() ]) asString ];
        column: ''Missing evidence refs'' text: [ :row | (row at: ''missingEvidenceRefs'' ifAbsent: [ #() ]) asString ]'
    classified: 'aip inspection'.

explorerClass := Smalltalk
    at: #GtAipArchitectureExplorer
    ifAbsent: [
        Object
            subclass: #GtAipArchitectureExplorer
            instanceVariableNames: ''
            classVariableNames: ''
            package: 'AIP-GToolkit-Agentic' ].

explorerClass class
    compile: 'mcpEndpoint
    ^ ''http://127.0.0.1:8000/mcp'''
    classified: 'demo'.

explorerClass class
    compile: 'explorationInstructions
    ^ ''You are Architecture Explorer in Glamorous Toolkit. The developer asks ordinary architecture questions; handle the technical investigation yourself.

Use AIP MCP for architecture facts, qualifications, limitations, and provenance. Ask useful follow-up questions grounded in returned information. Keep supported AIP findings distinct from your interpretation. Label any investigation priority as your suggestion, never as an AIP priority. Do not invent architecture intent, qualification rules, or safety or migration conclusions. If your answer interprets detailed evidence, follow the returned claim evidence_refs and resolution_evidence_refs with get_evidence using the exact same AIP snapshot_id. Keep claim and resolution evidence in separate roles and report unresolved refs or lookup limitations. Deduplicate references and use batches of at most 20 per get_evidence request.


Present chat answers with short headings and bullets. Do not use Markdown pipe tables: the GT chat and Lepiter text page show them as literal markup. Put tabular comparisons into the ephemeral micro-tool Results view using its columns and rows, and summarize the findings in prose. Do not rely on a Markdown page to render a table.

After the first successful AIP investigation in this chat, create exactly one GtAipEphemeralMicroTool for a useful developer-facing follow-up question grounded in the returned claims. Obtain the AIP answer before creating the tool. If AIP fails or returns no relevant claims, explain that and do not invent or create an empty tool. In later turns, create another tool only when it adds a useful new lens or the developer asks for one. Use smalltalkCodeEvaluation only to instantiate, populate, and return the existing GtAipEphemeralMicroTool. Never compile or remove methods or classes, or write files.

Complete construction contract: instantiate GtAipEphemeralMicroTool new, set title:, question:, rationale:, columns:, rows:, sourceSnapshotId:, sourceTools:, sourceClaimIds:, promotionTarget:, and promotionIdea:, then return the object. Columns must be an Array of Dictionaries with string keys label and key. For this dependency follow-up view use exactly three columns in order: Dependency/dependency, AIP qualification/qualification, Follow-up question/followUpQuestion. Rows must be an Array of Dictionaries keyed by those three string keys. Present the matching dependency rows in this order: unused-q, payment-q, LegacyPricingService. Use these follow-up questions when the exact dependency and qualification pair appears in the answer: unused-q / NOT_OBSERVED_IN_WINDOW / Which service consumes this queue?; payment-q / NOT_OBSERVED_IN_WINDOW / Does a longer observation window show traffic on this queue?; LegacyPricingService / OBSERVED_ONLY / What declarations apply to this observed call?. The runtime demo can qualify payment-q as CONFIRMED; always copy the actual qualification and choose an appropriate question or omit that row. Never invent a row if AIP does not return its claim. Before creating the tool, resolve the represented rows returned evidence_refs and resolution_evidence_refs with get_evidence at the exact originating snapshot_id. Each row must also carry claimId, claimEvidenceRefs, resolutionEvidenceRefs, snapshotId, limitations, claimEvidence, resolutionEvidence, and missingEvidenceRefs for the separate GT AIP details view. Copy exact AIP values and keep the complete returned arrays; use an empty Array when a field is absent. Include answer-level limitations that apply to the row. Use get_evidence data.records, matched by record id, under claimEvidence or resolutionEvidence according to the rows corresponding reference array; the same complete record can appear in both roles when both reference it. Copy data.missing_evidence_refs into each affected rows missingEvidenceRefs and disclose lookup failures. Do not put evidence, snapshot, or limitations into the three overview columns. Return only the populated object from smalltalkCodeEvaluation.

Set sourceSnapshotId and each row snapshotId to the exact snapshot_id returned by AIP. Set sourceTools to AIP tools actually called, and sourceClaimIds to relevant claim IDs present in the AIP answer. Preserve claim evidence and resolution evidence as distinct roles where relevant. A promotion target or idea is advisory only; the developer controls permanent promotion. Do not copy snapshot-specific rows into permanent code.'''
    classified: 'demo'.

explorerClass class
    compile: 'demoContextInstructions
    ^ ''Default investigation context: service:order-service in environment demo, window start 2026-08-26T00:00:00Z, window end 2026-08-27T00:00:00Z. Knowledge source: AIP MCP. Exploration environment: Glamorous Toolkit. Reuse this context for follow-up questions unless the developer changes it. These are query inputs, not an AIP snapshot. Never hardcode a snapshot ID or claim reference.'''
    classified: 'demo'.

explorerClass class
    compile: 'modelDetailsFor: aModelChoice
    aModelChoice = #sol ifTrue: [ ^ { ''GPT 5.6 Sol''. ''gpt-5.6-sol'' } ].
    aModelChoice = #luna ifTrue: [ ^ { ''GPT 6 Luna''. ''gpt-6-luna'' } ].
    self error: ''Expected #sol or #luna'''
    classified: 'demo'.

explorerClass class
    compile: 'newDemoChat
    ^ self newDemoChatWithModel: #luna'
    classified: 'demo'.

explorerClass class
    compile: 'demoProviderForModel: aModelChoice
    | demoConnection modelDetails |
    modelDetails := self modelDetailsFor: aModelChoice.
    demoConnection := GtLConnectionRegistry uniqueInstance defaultConnection.
    demoConnection label: modelDetails first.
    (demoConnection optionNamed: #modelName)
        valueGenerator: [ { modelDetails second } ].
    ^ demoConnection buildProvider'
    classified: 'demo'.

explorerClass class
    compile: 'newDemoChatWithModel: aModelChoice
    | mcpClient aipTools allTools chat provider |
    provider := self demoProviderForModel: aModelChoice.
    mcpClient := GtLMcpClient new
        transport: (GtLMcpHttpTransport new url: self mcpEndpoint).
    aipTools := GtAipMcpStructuredFunctionTool toolsForClient: mcpClient.
    aipTools size = 3
        ifFalse: [ self error: ''Expected exactly three AIP MCP tools'' ].
    allTools := OrderedCollection new.
    allTools addAll: aipTools.
    allTools add: GtLMagritteToolForSmalltalkCodeEvaluation new.
    chat := GtLChat new.
    chat provider: provider.
    chat markdownResponse.
    chat tools: (GtLTools withAll: allTools).
    chat instruction: self explorationInstructions titled: ''Architecture Explorer''.
    chat instruction: self demoContextInstructions titled: ''Demo context''.
    ^ chat'
    classified: 'demo'.

explorerClass class
    compile: 'openDemo
    ^ self openDemoWithModel: #luna'
    classified: 'demo'.

explorerClass class
    compile: 'openDemoWithModel: aModelChoice
    | chat |
    BlSpace userFontScale: 1.2.
    chat := self newDemoChatWithModel: aModelChoice.
    chat inspect.
    BlSpace userFontScale: 1.2.
    ^ chat'
    classified: 'demo'.

explorerClass name
