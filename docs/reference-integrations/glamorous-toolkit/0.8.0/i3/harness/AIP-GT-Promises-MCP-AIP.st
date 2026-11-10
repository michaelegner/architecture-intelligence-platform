!GtAipHostedClient methodsFor: '*AIP-GT-Promises-MCP' stamp: '11/9/2026 22:00'!
gtQueriesFor: aView
	<gtView>
	^ aView list
		title: 'Queries';
		priority: 10;
		items: [ #('binding picture') ]! !

!GtAipHostedClient methodsFor: '*AIP-GT-Promises-MCP' stamp: '11/9/2026 22:00'!
gtAipSelect: aViewSelector index: anIndex
	(aViewSelector = #gtQueriesFor: and: [ anIndex = 1 ]) ifTrue: [ ^ self bindingPicture ].
	^ super gtAipSelect: aViewSelector index: anIndex! !

!GtAipBindingPicture methodsFor: '*AIP-GT-Promises-MCP' stamp: '11/9/2026 22:00'!
gtAipSelect: aViewSelector index: anIndex
	aViewSelector = #gtRowsFor: ifTrue: [ ^ self rows at: anIndex ].
	^ super gtAipSelect: aViewSelector index: anIndex! !
