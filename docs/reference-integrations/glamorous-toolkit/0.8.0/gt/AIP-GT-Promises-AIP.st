Object subclass: #GtAipHostedClient
	instanceVariableNames: 'client transport expectedSnapshotId'
	classVariableNames: 'Session'
	package: 'AIP-GT-Promises-AIP'!

Object subclass: #GtAipBindingPicture
	instanceVariableNames: 'client data'
	classVariableNames: ''
	package: 'AIP-GT-Promises-AIP'!

Object subclass: #GtAipBindingRow
	instanceVariableNames: 'picture row'
	classVariableNames: ''
	package: 'AIP-GT-Promises-AIP'!

!GtAipHostedClient class methodsFor: 'frozen scope' stamp: '11/9/2026 18:00'!
url
	^ 'https' , '://mcp.daip.io/mcp'! !

!GtAipHostedClient class methodsFor: 'frozen scope' stamp: '11/9/2026 18:00'!
frozenSnapshotId
	^ 'aip:snapshot:v1:7f171aea2d3c5070e6be3dd9c6b53a234ad75934be5724681b95cd3e1705c413'! !

!GtAipHostedClient class methodsFor: 'frozen scope' stamp: '11/9/2026 18:00'!
scope
	^ {
		'bounded_context_id' -> 'catalog-management'.
		'environment' -> 'local'.
		'broker_ids' -> #('kafka:sokol111-local')
	} asDictionary! !

!GtAipHostedClient class methodsFor: 'session' stamp: '11/9/2026 21:00'!
session
	"The one client of this image's investigation. Its log holds every call made through it."
	^ Session ifNil: [ Session := self new ]! !

!GtAipHostedClient class methodsFor: 'session' stamp: '11/9/2026 21:00'!
resetSession
	Session := nil! !

!GtAipHostedClient class methodsFor: 'investigation page' stamp: '11/9/2026 18:00'!
createInvestigationPageIn: aCorpus condition: aConditionName
	^ GtAipInvestigationPage
		createPageIn: aCorpus
		condition: aConditionName
		extraSnippets: #('GtAipHostedClient session bindingPicture')! !

!GtAipHostedClient methodsFor: 'initialization' stamp: '11/9/2026 18:00'!
initialize
	super initialize.
	expectedSnapshotId := self class frozenSnapshotId.
	transport := GtLMcpHttpTransport new
		url: self class url;
		yourself.
	client := GtLMcpClient new.
	client transport: transport! !

!GtAipHostedClient methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
expectedSnapshotId: aString
	"For the smoke gate only: a wrong value must make every call fail."
	expectedSnapshotId := aString! !

!GtAipHostedClient methodsFor: 'calling' stamp: '11/9/2026 18:00'!
call: aRequestDictionary
	| result answer snapshotId |
	result := client
		callToolResult: 'get_binding_picture'
		withArguments: { 'request' -> aRequestDictionary } asDictionary.
	(result at: 'isError' ifAbsent: [ false ])
		ifTrue: [ Error signal: 'get_binding_picture returned isError=true' ].
	answer := result at: 'structuredContent'.
	snapshotId := (answer at: 'snapshot' ifAbsent: [ Dictionary new ])
		at: 'snapshot_id' ifAbsent: [ nil ].
	snapshotId = expectedSnapshotId
		ifFalse: [ Error signal: 'Snapshot mismatch: ' , snapshotId printString ].
	^ answer! !

!GtAipHostedClient methodsFor: 'calling' stamp: '11/9/2026 18:00'!
bindingPicture
	| request |
	request := self class scope copy.
	request at: 'mode' put: 'query'.
	^ GtAipBindingPicture new setClient: self data: (self call: request)! !

!GtAipHostedClient methodsFor: 'calling' stamp: '11/9/2026 18:00'!
evidenceFor: someRefs
	"All entries for the refs, fetched in sorted batches of at most 20. Never truncates."
	| sorted entries |
	sorted := someRefs asSet asSortedCollection asArray.
	entries := OrderedCollection new.
	1 to: sorted size by: 20 do: [ :start |
		| request answer |
		request := self class scope copy.
		request at: 'mode' put: 'evidence'.
		request at: 'snapshot_id' put: expectedSnapshotId.
		request at: 'evidence_refs'
			put: (sorted copyFrom: start to: (start + 19 min: sorted size)).
		answer := self call: request.
		entries addAll: ((answer at: 'data') at: 'entries') ].
	entries size = sorted size
		ifFalse: [ Error signal: 'Evidence answer has ' , entries size printString ,
			' entries for ' , sorted size printString , ' refs' ].
	^ entries asArray! !

!GtAipHostedClient methodsFor: 'log' stamp: '11/9/2026 18:00'!
messages
	^ transport instVarNamed: 'messages'! !

!GtAipHostedClient methodsFor: 'log' stamp: '11/9/2026 18:00'!
exportLogTo: aPathString
	"A record of the session's MCP messages as parsed objects; not byte evidence."
	aPathString asFileReference ensureDelete; writeStreamDo: [ :stream |
		stream nextPutAll: (NeoJSONWriter toStringPretty: self messages asArray) ].
	^ aPathString asFileReference! !

!GtAipHostedClient methodsFor: 'views' stamp: '11/9/2026 18:00'!
gtMessagesFor: aView
	<gtView>
	^ aView forward
		title: 'Messages';
		priority: 50;
		object: [ transport ];
		view: #gtMessagesFor:! !

!GtAipBindingPicture methodsFor: 'initialization' stamp: '11/9/2026 18:00'!
setClient: aClient data: aDictionary
	client := aClient.
	data := aDictionary! !

!GtAipBindingPicture methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
client
	^ client! !

!GtAipBindingPicture methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
data
	^ data! !

!GtAipBindingPicture methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
rows
	^ ((data at: 'data') at: 'rows') collect: [ :each |
		GtAipBindingRow new setPicture: self row: each ]! !

!GtAipBindingPicture methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
display: aValue
	aValue ifNil: [ ^ '' ].
	aValue isString ifTrue: [ ^ aValue ].
	^ NeoJSONWriter toString: aValue! !

!GtAipBindingPicture methodsFor: 'views' stamp: '11/9/2026 18:00'!
gtRowsFor: aView
	<gtView>
	^ aView columnedList
		title: 'Rows';
		priority: 10;
		items: [ self rows ];
		column: 'Consumer' text: [ :each | each at: 'consumer_service_id' ] weight: 2;
		column: 'Topic' text: [ :each | each at: 'topic_name' ] weight: 2;
		column: 'Broker' text: [ :each | each at: 'broker_id' ] weight: 1.5;
		column: 'Crossing' text: [ :each | each at: 'crossing' ];
		column: 'Status' text: [ :each | each at: 'status' ] weight: 1.5;
		column: 'Reason' text: [ :each | each at: 'reason' ] weight: 1.5;
		column: 'Captured at' text: [ :each | each at: 'captured_at' ] weight: 1.5;
		column: 'Refs' text: [ :each | each refsSummary ] weight: 1.5! !

!GtAipBindingPicture methodsFor: 'views' stamp: '11/9/2026 18:00'!
gtAnswerFor: aView
	<gtView>
	^ aView columnedList
		title: 'Answer';
		priority: 20;
		items: [ (data keys reject: [ :key | key = 'data' ]) asSortedCollection asArray ,
			(((data at: 'data') keys reject: [ :key | key = 'rows' ]) asSortedCollection
				collect: [ :key | 'data.' , key ]) asArray ];
		column: 'Field' text: [ :key | key ];
		column: 'Value' text: [ :key |
			self display: ((key beginsWith: 'data.')
				ifTrue: [ (data at: 'data') at: (key allButFirst: 5) ]
				ifFalse: [ data at: key ]) ] weight: 5! !

!GtAipBindingPicture methodsFor: 'views' stamp: '11/9/2026 18:00'!
gtLimitationsFor: aView
	<gtView>
	^ aView columnedList
		title: 'Limitations';
		priority: 30;
		items: [ data at: 'limitations' ifAbsent: [ #() ] ];
		column: 'Code' text: [ :each | each at: 'code' ifAbsent: [ '' ] ];
		column: 'Message' text: [ :each | each at: 'message' ifAbsent: [ self display: each ] ] weight: 4! !

!GtAipBindingPicture methodsFor: 'views' stamp: '11/9/2026 18:00'!
gtCapturesFor: aView
	<gtView>
	^ aView columnedList
		title: 'Captures';
		priority: 40;
		items: [ (data at: 'data') at: 'capture_sources' ifAbsent: [ #() ] ];
		column: 'Capture' text: [ :each | self display: each ]! !

!GtAipBindingRow methodsFor: 'initialization' stamp: '11/9/2026 18:00'!
setPicture: aPicture row: aDictionary
	picture := aPicture.
	row := aDictionary! !

!GtAipBindingRow methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
at: aKey
	^ picture display: (row at: aKey ifAbsent: [ nil ])! !

!GtAipBindingRow methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
refRoles
	"Every '<role>_evidence_refs' field of the row, by role."
	^ (row keys select: [ :key | key endsWith: '_evidence_refs' ]) asSortedCollection asArray! !

!GtAipBindingRow methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
allRefs
	^ (self refRoles flatCollect: [ :role | row at: role ]) asSet asArray! !

!GtAipBindingRow methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
roleOf: aRef
	^ ', ' join: ((self refRoles select: [ :role | (row at: role) includes: aRef ])
		collect: [ :role | role copyReplaceAll: '_evidence_refs' with: '' ])! !

!GtAipBindingRow methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
refsSummary
	^ ' ' join: (self refRoles collect: [ :role |
		(role copyReplaceAll: '_evidence_refs' with: '') , ':' , (row at: role) size printString ])! !

!GtAipBindingRow methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
evidence
	^ picture client evidenceFor: self allRefs! !

!GtAipBindingRow methodsFor: 'printing' stamp: '11/9/2026 18:00'!
printOn: aStream
	aStream
		nextPutAll: (self at: 'consumer_service_id');
		nextPutAll: ' x ';
		nextPutAll: (self at: 'topic_name')! !

!GtAipBindingRow methodsFor: 'views' stamp: '11/9/2026 18:00'!
gtFieldsFor: aView
	<gtView>
	^ aView columnedList
		title: 'Fields';
		priority: 10;
		items: [ row keys asSortedCollection asArray ];
		column: 'Field' text: [ :key | key ];
		column: 'Value' text: [ :key | self at: key ] weight: 5! !

!GtAipBindingRow methodsFor: 'views' stamp: '11/9/2026 18:00'!
gtEvidenceFor: aView
	<gtView>
	^ aView columnedList
		title: 'Evidence';
		priority: 20;
		items: [ self evidence ];
		column: 'Role' text: [ :each | self roleOf: (each at: 'ref') ];
		column: 'Kind' text: [ :each | each at: 'kind' ifAbsent: [ '' ] ] weight: 1.5;
		column: 'Status' text: [ :each | each at: 'status' ifAbsent: [ '' ] ];
		column: 'Evidence' text: [ :each | picture display: (each at: 'evidence' ifAbsent: [ nil ]) ] weight: 5! !
