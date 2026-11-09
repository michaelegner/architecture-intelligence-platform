Object subclass: #GtAipPromiseCorpus
	instanceVariableNames: 'directory contracts'
	classVariableNames: ''
	package: 'AIP-GT-Promises'!

Object subclass: #GtAipPromiseContract
	instanceVariableNames: 'corpus path data'
	classVariableNames: ''
	package: 'AIP-GT-Promises'!

Object subclass: #GtAipInvestigationPage
	instanceVariableNames: ''
	classVariableNames: ''
	package: 'AIP-GT-Promises'!

!GtAipPromiseCorpus class methodsFor: 'instance creation' stamp: '11/9/2026 18:00'!
onDirectory: aPathString
	^ self new setDirectory: aPathString asFileReference! !

!GtAipPromiseCorpus methodsFor: 'initialization' stamp: '11/9/2026 18:00'!
setDirectory: aFileReference
	(aFileReference / 'task.md') exists
		ifFalse: [ Error signal: 'Not a participant corpus: task.md is missing' ].
	(aFileReference / 'contracts.json') exists
		ifFalse: [ Error signal: 'Not a GT participant corpus: contracts.json is missing' ].
	directory := aFileReference! !

!GtAipPromiseCorpus methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
directory
	^ directory! !

!GtAipPromiseCorpus methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
task
	^ (directory / 'task.md') contents! !

!GtAipPromiseCorpus methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
contracts
	"All five contracts, ordered by file path only."
	| rendered all |
	contracts ifNotNil: [ ^ contracts ].
	rendered := NeoJSONReader fromString: (directory / 'contracts.json') contents.
	all := OrderedCollection new.
	rendered keysAndValuesDo: [ :file :fields |
		all add: (GtAipPromiseContract new
			setCorpus: self path: 'contracts/' , file data: fields) ].
	(directory / 'contracts') files do: [ :each |
		each extension = 'md' ifTrue: [
			all add: (GtAipPromiseContract new
				setCorpus: self
				path: 'contracts/' , each basename
				data: nil) ] ].
	^ contracts := (all asSortedCollection: [ :a :b | a path <= b path ]) asArray! !

!GtAipPromiseCorpus methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
pinnedShaFor: aRepositoryName
	(directory / 'REPOS.txt') exists ifFalse: [ ^ nil ].
	(directory / 'REPOS.txt') contents lines do: [ :line |
		| parts |
		parts := line substrings.
		(parts size = 2 and: [ parts second = aRepositoryName ])
			ifTrue: [ ^ parts first ] ].
	^ nil! !

!GtAipPromiseCorpus methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
localFileFor: aUrlString
	"The corpus file for a pinned https://github.com/Sokol111/<repo>/(blob|tree)/<sha>/<path> link, or nil."
	| parts repository sha file |
	(aUrlString beginsWith: 'https://github.com/Sokol111/') ifFalse: [ ^ nil ].
	parts := (aUrlString allButFirst: 'https://github.com/' size) substrings: '/'.
	parts size < 4 ifTrue: [ ^ nil ].
	repository := parts second.
	sha := parts fourth.
	(self pinnedShaFor: repository) = sha ifFalse: [ ^ nil ].
	file := directory / 'sokol111' / repository.
	(parts allButFirst: 4) do: [ :segment |
		(segment isEmpty or: [ segment = '.' or: [ segment = '..' or: [ segment includes: $\ ] ] ])
			ifTrue: [ ^ nil ].
		file := file / segment ].
	^ file exists ifTrue: [ file ] ifFalse: [ nil ]! !

!GtAipPromiseCorpus methodsFor: 'views' stamp: '11/9/2026 18:00'!
gtContractsFor: aView
	<gtView>
	^ aView columnedList
		title: 'Contracts';
		priority: 10;
		items: [ self contracts ];
		column: 'Id' text: [ :each | each id ];
		column: 'Promiser' text: [ :each | each promiser ] weight: 2;
		column: 'Kind' text: [ :each | each kind ];
		column: 'Audience' text: [ :each | each audience ] weight: 2;
		column: 'File' text: [ :each | each path ] weight: 2! !

!GtAipPromiseCorpus methodsFor: 'views' stamp: '11/9/2026 18:00'!
gtTaskFor: aView
	<gtView>
	^ aView textEditor
		title: 'Task';
		priority: 20;
		text: [ self task ]! !

!GtAipPromiseContract methodsFor: 'initialization' stamp: '11/9/2026 18:00'!
setCorpus: aCorpus path: aPathString data: aDictionaryOrNil
	corpus := aCorpus.
	path := aPathString.
	data := aDictionaryOrNil! !

!GtAipPromiseContract methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
path
	^ path! !

!GtAipPromiseContract methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
file
	^ (path substrings: '/')
		inject: corpus directory
		into: [ :directory :segment | directory / segment ]! !

!GtAipPromiseContract methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
raw
	^ self file contents! !

!GtAipPromiseContract methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
markdownField: aLabel
	"The value of a '**Label:** value' line in a Markdown contract."
	| prefix |
	prefix := '**' , aLabel , ':**'.
	self raw lines do: [ :line |
		(line beginsWith: prefix)
			ifTrue: [ ^ (line allButFirst: prefix size) trimBoth ] ].
	^ ''! !

!GtAipPromiseContract methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
display: aValue
	aValue ifNil: [ ^ '' ].
	aValue isString ifTrue: [ ^ aValue ].
	(aValue isCollection and: [ aValue isDictionary not ])
		ifTrue: [ ^ String cr join: (aValue collect: [ :each | self display: each ]) ].
	^ NeoJSONWriter toStringPretty: aValue! !

!GtAipPromiseContract methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
field: aKey
	data ifNil: [ ^ '' ].
	^ self display: (data at: aKey ifAbsent: [ nil ])! !

!GtAipPromiseContract methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
id
	"A Markdown contract's id is the first word of its '# ' heading."
	data ifNil: [ ^ (self raw lines first allButFirst: 2) substrings first ].
	^ self field: 'id'! !

!GtAipPromiseContract methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
promiser
	data ifNil: [ ^ self markdownField: 'Modeled offeror' ].
	^ self field: 'promiser'! !

!GtAipPromiseContract methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
kind
	data ifNil: [ ^ 'external contract' ].
	^ self field: 'kind'! !

!GtAipPromiseContract methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
audience
	data ifNil: [ ^ self markdownField: 'Audience' ].
	^ (self field: 'audience') copyReplaceAll: String cr with: '; '! !

!GtAipPromiseContract methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
evidence
	data ifNil: [ ^ #() ].
	^ data at: 'evidence' ifAbsent: [ #() ]! !

!GtAipPromiseContract methodsFor: 'printing' stamp: '11/9/2026 18:00'!
printOn: aStream
	aStream nextPutAll: self id! !

!GtAipPromiseContract methodsFor: 'views' stamp: '11/9/2026 18:00'!
gtFieldsFor: aView
	<gtView>
	data ifNil: [ ^ aView empty ].
	^ aView columnedList
		title: 'Fields';
		priority: 10;
		items: [ data keys asSortedCollection asArray ];
		column: 'Field' text: [ :key | key ];
		column: 'Value' text: [ :key | self field: key ] weight: 5! !

!GtAipPromiseContract methodsFor: 'views' stamp: '11/9/2026 18:00'!
gtRawFor: aView
	<gtView>
	^ aView textEditor
		title: 'Raw';
		priority: 20;
		text: [ self raw ]! !

!GtAipPromiseContract methodsFor: 'views' stamp: '11/9/2026 18:00'!
gtEvidenceFor: aView
	<gtView>
	data ifNil: [ ^ aView empty ].
	^ aView columnedList
		title: 'Evidence';
		priority: 30;
		items: [ self evidence ];
		column: 'Source' text: [ :each | each at: 'source' ] weight: 4;
		column: 'Supports' text: [ :each | each at: 'supports' ] weight: 3;
		column: 'In corpus' text: [ :each |
			(corpus localFileFor: (each at: 'source'))
				ifNil: [ 'no' ] ifNotNil: [ 'yes' ] ];
		send: [ :each |
			(corpus localFileFor: (each at: 'source'))
				ifNil: [ 'Not in corpus: ' , (each at: 'source') ] ]! !

!GtAipInvestigationPage class methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
titlePrefix
	^ 'GT 0.8.0 investigation'! !

!GtAipInvestigationPage class methodsFor: 'accessing' stamp: '11/9/2026 18:00'!
answerHeadings
	"The five 'Your answer' items of task.md, verbatim."
	^ #(
	'1. Your first impression: a provisional recommendation in one or two sentences. Write it **before** you open any contract, source file or tool, and do not change it later.'
	'2. Your findings. For each finding, cite its source (a Promise Contract, a file at its revision, or a tool answer).'
	'3. Your recommendation, and the commitments or agreements you propose, if any. Name who would make each one and under which conditions.'
	'4. What remains uncertain.'
	'5. Whether your recommendation changed during the investigation, and which finding changed it.')! !

!GtAipInvestigationPage class methodsFor: 'instance creation' stamp: '11/9/2026 18:00'!
createPageIn: aCorpus condition: aConditionName
	^ self createPageIn: aCorpus condition: aConditionName extraSnippets: #()! !

!GtAipInvestigationPage class methodsFor: 'instance creation' stamp: '11/9/2026 18:00'!
createPageIn: aCorpus condition: aConditionName extraSnippets: someCodeStrings
	"Create the empty investigation page for one condition, or return it if it exists.
	Refuse when this database holds another condition's page."
	| database title page |
	database := LeDatabasesRegistry defaultPrimaryDatabase.
	title := self titlePrefix , ' - ' , aConditionName.
	(database pages anySatisfy: [ :each |
		(each title beginsWith: self titlePrefix) and: [ each title ~= title ] ])
		ifTrue: [ Error signal: 'This database holds another condition''s investigation page' ].
	database pageNamed: title ifPresent: [ :existing | ^ existing ] ifAbsent: [ ].
	page := LePage named: title.
	"The first impression comes before any snippet that opens a contract, source or tool."
	page addSnippet: (LeTextSnippet string: aCorpus task).
	page addSnippet: (LeTextSnippet string: self answerHeadings first).
	page addSnippet: (LePharoSnippet code:
		'GtAipPromiseCorpus onDirectory: ''' , aCorpus directory fullName , '''').
	someCodeStrings do: [ :each | page addSnippet: (LePharoSnippet code: each) ].
	self answerHeadings allButFirst do: [ :each |
		page addSnippet: (LeTextSnippet string: each) ].
	database addPage: page.
	^ page! !
