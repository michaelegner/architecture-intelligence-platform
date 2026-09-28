Object subclass: #GtAipArchitectureAnswer
	instanceVariableNames: 'client data'
	classVariableNames: ''
	package: 'AIP-GToolkit-Quarkus'!

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:58'!
data: aDictionary client: aClient
    data := aDictionary.
    client := aClient! !

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:58'!
outcome
    ^ data at: 'outcome'! !

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:58'!
snapshotId
    ^ (data at: 'snapshot') at: 'snapshot_id'! !

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:58'!
claims
    ^ data at: 'claims'! !

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:58'!
limitations
    ^ data at: 'limitations'! !

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:59'!
dependencyClaims
    ^ self claims select: [ :claim |
        (claim at: 'predicate') = 'DIRECT_DEPENDENCY' ]! !

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:59'!
deploymentClaims
    ^ self claims select: [ :claim |
        (claim at: 'predicate') = 'DEPLOYED_AS' ]! !

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:59'!
httpClaims
    ^ self dependencyClaims select: [ :claim |
        ((claim at: 'delivery') at: 'relation_type') = 'CALLS' ]! !

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:59'!
messagingClaims
    ^ self dependencyClaims select: [ :claim |
        ((claim at: 'delivery') at: 'relation_type') = 'PUBLISHES_TO' ]! !

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:59'!
deploymentResolutions
    ^ (data at: 'data') at: 'deployment_resolutions'! !

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:59'!
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
    ^ evidence! !

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 20:00'!
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
            (claim at: 'coverage') ifNil: [ '' ] ]! !

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 20:01'!
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
                ifNotNil: [ :sub | sub at: 'name' ] ]! !

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 20:01'!
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
            claim at: 'resolution_method' ]! !

!GtAipArchitectureAnswer methodsFor: 'as yet unclassified' stamp: '9/27/2026 20:01'!
gtLimitationsFor: aView
    <gtView>
    ^ aView columnedList
        title: 'Limitations';
        priority: 13;
        items: [ self limitations ];
        column: 'Code' text: [ :each |
            each at: 'code' ];
        column: 'Explanation' text: [ :each |
            each at: 'message' ] weight: 3! !



Object subclass: #GtAipMcpClient
	instanceVariableNames: 'client'
	classVariableNames: ''
	package: 'AIP-GToolkit-Quarkus'!

!GtAipMcpClient methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:56'!
initialize
    super initialize.
    client := GtLMcpClient new.
    client transport: (GtLMcpHttpTransport new
        url: ('http' , '://127.0.0.1:8000/mcp');
        yourself)! !

!GtAipMcpClient methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:56'!
call: toolName request: aDictionary
    | result |
    result := client
        callToolResult: toolName
        withArguments: {'request' -> aDictionary} asDictionary.
    (result at: 'isError' ifAbsent: [ false ])
        ifTrue: [ Error signal: 'AIP MCP tool returned isError=true' ].
    ^ result at: 'structuredContent'! !

!GtAipMcpClient methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:56'!
quarkusContext
    ^ {
        'environment' -> 'quarkus-i5'.
        'window_start' -> '2026-09-25T13:06:47Z'.
        'window_end' -> '2026-09-25T13:06:54Z'
    } asDictionary! !

!GtAipMcpClient methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:56'!
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
    ^ answer! !

!GtAipMcpClient methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:57'!
quarkusFights
    ^ self dependenciesFor: 'service:rest-fights'! !

!GtAipMcpClient methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:57'!
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
        } asDictionary! !

!GtAipMcpClient methodsFor: 'as yet unclassified' stamp: '9/27/2026 19:57'!
driftFor: serviceId
    ^ self
        call: 'get_architecture_drift'
        request: {
            'service_id' -> serviceId.
            'observation_context' -> self quarkusContext
        } asDictionary! !