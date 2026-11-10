GtLMcpServer subclass: #GtAipMcpServer
	instanceVariableNames: 'bindAddress'
	classVariableNames: ''
	package: 'AIP-GT-Promises-MCP'!

GtLAbstractMagritteFunctionTool subclass: #GtAipToolForViewItem
	instanceVariableNames: ''
	classVariableNames: ''
	package: 'AIP-GT-Promises-MCP'!

GtLAbstractMagritteFunctionTool subclass: #GtAipToolForViewText
	instanceVariableNames: ''
	classVariableNames: ''
	package: 'AIP-GT-Promises-MCP'!

Object subclass: #GtAipViewText
	instanceVariableNames: 'stream'
	classVariableNames: ''
	package: 'AIP-GT-Promises-MCP'!

Object subclass: #GtAipCorpusDirectory
	instanceVariableNames: 'root directory'
	classVariableNames: ''
	package: 'AIP-GT-Promises-MCP'!

Object subclass: #GtAipCorpusFile
	instanceVariableNames: 'root file'
	classVariableNames: ''
	package: 'AIP-GT-Promises-MCP'!

!GtAipMcpServer class methodsFor: 'instance creation' stamp: '11/9/2026 22:00'!
on: anAddressString port: aPortNumber
	"A server with only the four read-only navigation tools, listening on one address.
	getViewText replaces the stock getViewContent, which returns a view only as a screenshot."
	^ self new
		bindAddress: anAddressString;
		port: aPortNumber;
		addTools: {
			GtLToolForObjectStorageList new.
			GtAipToolForViewText new.
			GtAipToolForViewItem new.
			GtLToolForLepiterPageContents new };
		yourself! !

!GtAipMcpServer methodsFor: 'accessing' stamp: '11/9/2026 22:00'!
bindAddress: anAddressString
	bindAddress := ((anAddressString substrings: '.') collect: [ :each | each asNumber ]) asByteArray.
	bindAddress size = 4 ifFalse: [ Error signal: 'Not an IPv4 address' ]! !

!GtAipMcpServer methodsFor: 'actions' stamp: '11/9/2026 22:00'!
start
	"As GtLMcpServer>>start, but bound to one address."
	bindAddress ifNil: [ Error signal: 'Set bindAddress: first' ].
	server := ZnMultiThreadedServer new
		port: port;
		bindingAddress: bindAddress;
		delegate: (ZnDispatcherDelegate new
			map: '/'
			to: [ :request :response | self handleRequest: request ]).
	server start! !

!GtAipMcpServer methodsFor: 'seeding' stamp: '11/9/2026 22:00'!
seed: anObject as: aName
	^ self objectStorage addNewObject: anObject reasonString: aName! !

!GtAipToolForViewItem methodsFor: 'accessing' stamp: '11/9/2026 22:00'!
name
	^ 'selectViewItem'! !

!GtAipToolForViewItem methodsFor: 'accessing' stamp: '11/9/2026 22:00'!
description
	^ 'Selects item number itemIndex (1-based) in the view viewSelector of a stored object, stores the selected object and returns its object id'! !

!GtAipToolForViewItem methodsFor: 'accessing' stamp: '11/9/2026 22:00'!
objectIdDescription
	<magritteDescription>
	^ MAStringDescription new
		label: 'Object Id';
		accessor: #objectId;
		beRequired! !

!GtAipToolForViewItem methodsFor: 'accessing' stamp: '11/9/2026 22:00'!
viewSelectorDescription
	<magritteDescription>
	^ MAStringDescription new
		label: 'View Selector';
		accessor: #viewSelector;
		beRequired! !

!GtAipToolForViewItem methodsFor: 'accessing' stamp: '11/9/2026 22:00'!
itemIndexDescription
	<magritteDescription>
	^ MAStringDescription new
		label: 'Item Index';
		accessor: #itemIndex;
		beRequired! !

!GtAipToolForViewItem methodsFor: 'private' stamp: '11/9/2026 22:00'!
privatePerformToolCall: aToolCall inContext: anExecutionContext
	| arguments object selected failure newId |
	arguments := aToolCall arguments ifNil: [ Dictionary new ].
	object := anExecutionContext objectStorage
		objectAt: (arguments at: 'objectId' ifAbsent: [ '' ]) trimBoth
		ifPresent: [ :stored | stored ]
		ifAbsent: [ ^ GtLMissingDomainObject new objectName: 'objectId' ].
	failure := nil.
	selected := [ object
		gtAipSelect: (arguments at: 'viewSelector' ifAbsent: [ '' ]) trimBoth asSymbol
		index: (arguments at: 'itemIndex' ifAbsent: [ '' ]) asString trimBoth asNumber ]
		on: Error
		do: [ :anError |
			failure := 'Not selectable: ' , anError messageText asString.
			anError return: nil ].
	"A plain String result reaches the agent as empty content, so wrap every message."
	failure ifNotNil: [ ^ GtLString forString: failure ].
	(selected isKindOf: String) ifTrue: [ ^ GtLString forString: selected ].
	newId := anExecutionContext objectStorage
		addNewObject: selected
		reasonString: 'selected item'.
	^ GtLObjectStorageItems new items: {
		GtLObjectStorageItem new
			objectId: newId;
			objectValue: selected;
			reason: (GtLStoredObjectStringReason text: 'selected item');
			yourself }! !

!GtAipToolForViewText methodsFor: 'accessing' stamp: '11/10/2026 09:30'!
name
	^ 'getViewText'! !

!GtAipToolForViewText methodsFor: 'accessing' stamp: '11/10/2026 09:30'!
description
	^ 'Returns a view of a stored object as text: every row of a list with its column values, or the full text of a text view. Row numbers are the item indexes for selectViewItem. Use viewSelector views to list the view selectors of the object.'! !

!GtAipToolForViewText methodsFor: 'accessing' stamp: '11/10/2026 09:30'!
objectIdDescription
	<magritteDescription>
	^ MAStringDescription new
		label: 'Object Id';
		accessor: #objectId;
		beRequired! !

!GtAipToolForViewText methodsFor: 'accessing' stamp: '11/10/2026 09:30'!
viewSelectorDescription
	<magritteDescription>
	^ MAStringDescription new
		label: 'View Selector';
		accessor: #viewSelector;
		beRequired! !

!GtAipToolForViewText methodsFor: 'private' stamp: '11/10/2026 09:30'!
privatePerformToolCall: aToolCall inContext: anExecutionContext
	| arguments object selector text |
	arguments := aToolCall arguments ifNil: [ Dictionary new ].
	object := anExecutionContext objectStorage
		objectAt: (arguments at: 'objectId' ifAbsent: [ '' ]) trimBoth
		ifPresent: [ :stored | stored ]
		ifAbsent: [ ^ GtLMissingDomainObject new objectName: 'objectId' ].
	selector := (arguments at: 'viewSelector' ifAbsent: [ '' ]) trimBoth.
	text := [ selector = 'views'
			ifTrue: [ GtAipViewText viewListOf: object ]
			ifFalse: [ GtAipViewText textOf: object viewSelector: selector asSymbol ] ]
		on: Error
		do: [ :anError | anError return: 'View failed: ' , anError messageText asString ].
	^ GtLString forString: text! !

!GtAipViewText class methodsFor: 'accessing' stamp: '11/10/2026 09:30'!
viewSelectorsOf: anObject
	"The <gtView> methods of the object's own classes, without the generic views of Object."
	| selectors class |
	selectors := Set new.
	class := anObject class.
	[ class notNil and: [ class ~~ Object ] ] whileTrue: [
		class methods do: [ :each |
			(each hasPragmaNamed: #gtView) ifTrue: [ selectors add: each selector ] ].
		class := class superclass ].
	^ selectors asSortedCollection asArray! !

!GtAipViewText class methodsFor: 'accessing' stamp: '11/10/2026 09:30'!
viewListOf: anObject
	| selectors |
	selectors := self viewSelectorsOf: anObject.
	^ String streamContents: [ :aStream |
		aStream nextPutAll: 'Object: '; nextPutAll: anObject printString; nextPut: Character lf.
		selectors do: [ :each |
			aStream nextPutAll: each; nextPut: Character lf ] ]! !

!GtAipViewText class methodsFor: 'accessing' stamp: '11/10/2026 09:30'!
textOf: anObject viewSelector: aSelector
	^ self new
		renderObject: anObject viewSelector: aSelector;
		contents! !

!GtAipViewText methodsFor: 'initialization' stamp: '11/10/2026 09:30'!
initialize
	super initialize.
	stream := WriteStream on: String new! !

!GtAipViewText methodsFor: 'accessing' stamp: '11/10/2026 09:30'!
contents
	^ stream contents! !

!GtAipViewText methodsFor: 'private' stamp: '11/10/2026 09:30'!
newLine
	stream nextPut: Character lf! !

!GtAipViewText methodsFor: 'private' stamp: '11/10/2026 09:30'!
oneLine: aString
	^ aString collect: [ :each |
		(each = Character cr or: [ each = Character lf ])
			ifTrue: [ Character space ]
			ifFalse: [ each ] ]! !

!GtAipViewText methodsFor: 'rendering' stamp: '11/10/2026 09:30'!
renderObject: anObject viewSelector: aSelector
	((GtAipViewText viewSelectorsOf: anObject) includes: aSelector)
		ifFalse: [ ^ Error signal: 'Not a view of this object: ' , aSelector ].
	self renderView: (anObject perform: aSelector with: GtPhlowView empty)! !

!GtAipViewText methodsFor: 'rendering' stamp: '11/10/2026 09:30'!
renderView: aView
	stream nextPutAll: 'View: '; nextPutAll: (aView title ifNil: [ '' ]) asString.
	self newLine.
	(aView isKindOf: GtPhlowColumnedListView) ifTrue: [ ^ self renderColumnedList: aView ].
	(aView isKindOf: GtPhlowListView) ifTrue: [ ^ self renderList: aView ].
	(aView isKindOf: GtPhlowTextEditorView) ifTrue: [ ^ self renderTextEditor: aView ].
	(aView isKindOf: GtPhlowForwarderView) ifTrue: [ ^ self renderForward: aView ].
	(aView isKindOf: GtPhlowEmptyView) ifTrue: [ stream nextPutAll: '(empty)'. ^ self newLine ].
	stream nextPutAll: 'Unsupported view type: ' , aView class name.
	self newLine! !

!GtAipViewText methodsFor: 'rendering' stamp: '11/10/2026 09:30'!
renderColumnedList: aView
	| items columns |
	items := aView itemsProviderComputation value asArray.
	columns := aView columns asArray.
	stream nextPutAll: '#'.
	columns do: [ :each |
		stream nextPutAll: ' | '; nextPutAll: (each title ifNil: [ '' ]) asString ].
	self newLine.
	items withIndexDo: [ :item :row |
		stream print: row.
		columns withIndexDo: [ :column :index |
			stream
				nextPutAll: ' | ';
				nextPutAll: (self cellText: column item: item row: row column: index) ].
		self newLine ]! !

!GtAipViewText methodsFor: 'rendering' stamp: '11/10/2026 09:30'!
cellText: aColumn item: anItem row: aRow column: anIndex
	| cell text |
	cell := aColumn itemComputation
		ifNil: [ anItem ]
		ifNotNil: [ :computation | computation phlowValue: anItem withEnoughArguments: { aRow. anIndex } ].
	text := ((aColumn respondsTo: #formatComputation) and: [ aColumn formatComputation notNil ])
		ifTrue: [ aColumn formatComputation phlowValue: cell withEnoughArguments: { aRow. anIndex } ]
		ifFalse: [ cell gtDisplayString ].
	^ self oneLine: text asString! !

!GtAipViewText methodsFor: 'rendering' stamp: '11/10/2026 09:30'!
renderList: aView
	aView itemsProviderComputation value asArray withIndexDo: [ :item :row |
		| text |
		text := aView itemComputation
			ifNil: [ item gtDisplayString ]
			ifNotNil: [ :computation | computation phlowValue: item withEnoughArguments: { row } ].
		stream print: row; nextPutAll: ' | '; nextPutAll: (self oneLine: text asString).
		self newLine ]! !

!GtAipViewText methodsFor: 'rendering' stamp: '11/10/2026 09:30'!
renderTextEditor: aView
	stream nextPutAll: aView textBuilder value asString.
	self newLine! !

!GtAipViewText methodsFor: 'rendering' stamp: '11/10/2026 09:30'!
renderForward: aView
	| target |
	target := aView object value.
	stream nextPutAll: 'Shows: '; nextPutAll: target printString.
	self newLine.
	self renderView: (target perform: aView viewSymbol with: GtPhlowView empty)! !

!Object methodsFor: '*AIP-GT-Promises-MCP' stamp: '11/9/2026 22:00'!
gtAipSelect: aViewSelector index: anIndex
	Error signal: 'this view has no selectable items'! !

!GtAipPromiseCorpus methodsFor: '*AIP-GT-Promises-MCP' stamp: '11/9/2026 22:00'!
gtFilesFor: aView
	<gtView>
	^ aView forward
		title: 'Files';
		priority: 30;
		object: [ GtAipCorpusDirectory new setRoot: directory directory: directory ];
		view: #gtChildrenFor:! !

!GtAipPromiseCorpus methodsFor: '*AIP-GT-Promises-MCP' stamp: '11/9/2026 22:00'!
gtAipSelect: aViewSelector index: anIndex
	aViewSelector = #gtContractsFor: ifTrue: [ ^ self contracts at: anIndex ].
	aViewSelector = #gtFilesFor: ifTrue: [
		^ (GtAipCorpusDirectory new setRoot: directory directory: directory) childAt: anIndex ].
	^ super gtAipSelect: aViewSelector index: anIndex! !

!GtAipPromiseContract methodsFor: '*AIP-GT-Promises-MCP' stamp: '11/9/2026 22:00'!
gtAipSelect: aViewSelector index: anIndex
	| source local |
	aViewSelector = #gtEvidenceFor: ifFalse: [ ^ super gtAipSelect: aViewSelector index: anIndex ].
	source := (self evidence at: anIndex) at: 'source'.
	local := corpus localFileFor: source.
	local ifNil: [ ^ 'Not in corpus: ' , source ].
	^ GtAipCorpusFile new setRoot: corpus directory file: local! !

!GtAipCorpusDirectory methodsFor: 'initialization' stamp: '11/9/2026 22:00'!
setRoot: aRootReference directory: aDirectoryReference
	root := aRootReference.
	directory := aDirectoryReference! !

!GtAipCorpusDirectory methodsFor: 'accessing' stamp: '11/9/2026 22:00'!
isInsideRoot: aReference
	^ (aReference resolve fullName beginsWith: root resolve fullName)! !

!GtAipCorpusDirectory methodsFor: 'accessing' stamp: '11/9/2026 22:00'!
children
	"Directories first, then files, each by name; no .git directories; nothing outside the root."
	| entries byName |
	entries := directory children reject: [ :each |
		each basename = '.git' or: [ (self isInsideRoot: each) not ] ].
	byName := [ :a :b | a basename <= b basename ].
	^ ((entries select: [ :each | each isDirectory ]) asSortedCollection: byName) asArray
		, ((entries reject: [ :each | each isDirectory ]) asSortedCollection: byName) asArray! !

!GtAipCorpusDirectory methodsFor: 'accessing' stamp: '11/9/2026 22:00'!
childAt: anIndex
	| child |
	child := self children asArray at: anIndex.
	^ child isDirectory
		ifTrue: [ GtAipCorpusDirectory new setRoot: root directory: child ]
		ifFalse: [ GtAipCorpusFile new setRoot: root file: child ]! !

!GtAipCorpusDirectory methodsFor: 'accessing' stamp: '11/9/2026 22:00'!
gtAipSelect: aViewSelector index: anIndex
	aViewSelector = #gtChildrenFor: ifTrue: [ ^ self childAt: anIndex ].
	^ super gtAipSelect: aViewSelector index: anIndex! !

!GtAipCorpusDirectory methodsFor: 'printing' stamp: '11/9/2026 22:00'!
printOn: aStream
	directory = root ifTrue: [ ^ aStream nextPutAll: 'corpus root' ].
	aStream nextPutAll: (directory relativeTo: root) printString! !

!GtAipCorpusDirectory methodsFor: 'views' stamp: '11/9/2026 22:00'!
gtChildrenFor: aView
	<gtView>
	^ aView columnedList
		title: 'Children';
		priority: 10;
		items: [ self children asArray ];
		column: 'Name' text: [ :each | each basename , (each isDirectory ifTrue: [ '/' ] ifFalse: [ '' ]) ] weight: 3;
		column: 'Size' text: [ :each | each isDirectory ifTrue: [ '' ] ifFalse: [ each size printString ] ]! !

!GtAipCorpusFile methodsFor: 'initialization' stamp: '11/9/2026 22:00'!
setRoot: aRootReference file: aFileReference
	root := aRootReference.
	file := aFileReference! !

!GtAipCorpusFile methodsFor: 'printing' stamp: '11/9/2026 22:00'!
printOn: aStream
	aStream nextPutAll: (file relativeTo: root) printString! !

!GtAipCorpusFile methodsFor: 'views' stamp: '11/9/2026 22:00'!
gtContentsFor: aView
	<gtView>
	^ aView textEditor
		title: 'Contents';
		priority: 10;
		text: [ file contents ]! !
