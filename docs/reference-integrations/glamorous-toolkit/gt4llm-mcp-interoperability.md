# gt4llm MCP Interoperability Finding

**Status:** validated locally; upstream discussion recommended  
**Scope:** GT client-side integration finding, not an AIP semantic defect

## Summary

The AIP × GT reference integration uncovered two issues in the current `GtLMcpClient` convenience path used by gt4llm.

At the tested gt4llm revision, `GtLMcpClient>>callTool:withArguments:` returns only:

```text
result.content
```

which discards MCP `structuredContent`.

At the same revision, `GtLMcpClient>>llmFunctionTools`:

1. creates the legacy `GtLlmFunctionTool`,
2. reduces the MCP `inputSchema` to only its top-level property names.

The current OpenAI provider path expects the current function-tool model and calls `parametersJsonSchemaDictionary`, producing an incompatibility when the legacy tool object is used.

## Observed failure

The agent bridge failed before AIP was called with:

```text
GtLlmFunctionTool(Object)>>doesNotUnderstand:
    #parametersJsonSchemaDictionary
```

This was a GT-side adapter incompatibility, not an AIP MCP-server failure.

## Local compatibility adapter

A local `GtAipMcpStructuredFunctionTool` based on the current GT function-tool hierarchy was introduced.

The adapter preserves:

```text
MCP tools/list
    ↓
full inputSchema
    ↓
current GT function-tool model
    ↓
raw tools/call
    ↓
structuredContent
    ↓
GtLPlainJson
    ↓
agent/provider path
```

This adapter was validated through the later reference-integration PoCs, including:

- agent-selected MCP calls,
- dependency → evidence chaining,
- snapshot-bound provenance,
- heterogeneous evidence,
- dynamic creation of inspectable GT objects.

## Recommended generic gt4llm patch direction

The AIP-specific adapter should not be upstreamed as-is.

A generic gt4llm solution would likely include:

### 1. Full-result MCP API

Add a method that returns the complete MCP tool result while preserving the existing content-only API for compatibility.

Conceptually:

```smalltalk
callToolResult: aString withArguments: anObject
    ^ (self
        sendMethod: 'tools/call'
        withParams: {
            'name' -> aString.
            'arguments' -> anObject
        } asDictionary)
        at: 'result'
```

The existing content-oriented method can remain as a compatibility wrapper.

### 2. Current-model MCP function tool

Introduce a generic current-model MCP function tool that preserves:

```smalltalk
parametersJsonSchemaDictionary
    ^ toolDefinition at: 'inputSchema'
```

rather than flattening the schema to top-level property names.

### 3. Preserve structured tool results

The generic implementation should preserve `structuredContent` when available while remaining compatible with MCP tools that return ordinary `content` only.

### 4. Tests

At minimum:

- nested MCP `inputSchema` survives unchanged,
- `structuredContent` survives `tools/call`,
- content-only results remain supported,
- current OpenAI provider accepts the generated tool object,
- no `#parametersJsonSchemaDictionary` MNU,
- existing content-only client behavior remains compatible.

## AIP conclusion

The integration did not justify changing AIP's MCP semantics.

AIP negotiation, structured answers, snapshot binding, and evidence drill-down worked through the raw/current-model path. The defect was at the GT convenience-adapter boundary.

This makes the finding a good candidate for an upstream gt4llm contribution rather than an AIP v0.5 feature.
