# PoC 4 — Dynamic Moldable Tools

**Result:** PASS

## Purpose

PoC 4 tested whether an agent could move beyond presenting an AIP answer and derive a new developer-facing inspection lens.

```text
AIP context
        ↓
agent derives a useful question
        ↓
agent creates an ephemeral GT micro-tool
        ↓
developer inspects it
        ↓
developer decides whether to promote the idea
```

The key boundary was:

```text
agent proposes the lens
developer controls permanence
AIP remains the source of architecture facts
```

## Bounded implementation

The agent was **not** allowed to compile GT methods or classes.

A stable human-authored class, `GtAipEphemeralMicroTool`, provided the GT views. The agent could only instantiate and populate it with:

- title,
- question,
- rationale,
- column specification,
- result rows,
- AIP snapshot ID,
- source tool names,
- source claim IDs,
- advisory promotion target and idea.

This kept runtime creation bounded:

```text
agent creates data + presentation specification
        ↓
existing GT class renders it
```

rather than allowing autonomous permanent code changes.

## First derived micro-tool

The agent first obtained AIP context and then derived:

> Which OrderService direct-dependency claims in the demo window resolve to services, and which remain a direct target with an unresolved identity?

The generated view compared:

- destination,
- delivery,
- operation/queue,
- destination resolution,
- qualification,
- coverage,
- AIP limitation.

It surfaced the distinction between:

```text
unused-q
  DIRECT_TARGET_FALLBACK
  NOT_OBSERVED_IN_WINDOW
  PARTIAL
  UNRESOLVED_IDENTITY

and

resolved service dependencies
  RESOLVED_SERVICE
  with their own independent qualifications
```

The tool preserved:

- exact AIP snapshot lineage,
- actual source tool,
- represented claim IDs,
- explicit `Ephemeral = true`,
- advisory-only promotion text.

Its GT views rendered successfully:

- result table,
- Question,
- AIP provenance,
- Promotion.

## Construction-contract finding

The first generated version used positional arrays for columns and rows, while the GT view expected dictionaries.

The contract was tightened to require:

```text
columns = array of { label, key } dictionaries
rows    = array of dictionaries using those keys
```

After that change, the generated micro-tool rendered successfully.

This is an important integration finding:

> Giving an agent the ability to instantiate a bounded tool is not enough; the construction contract must itself be explicit and machine-checkable.

## Second evidence/provenance micro-tool

A second run deliberately focused on evidence and provenance.

The agent derived:

> How does claim-versus-destination-resolution evidence provenance differ between the OBSERVED_ONLY LegacyPricingService dependency and the CONFIRMED ProductService dependency?

It selected:

```text
get_service_dependencies
        ↓
get_evidence
        ↓
ephemeral GT micro-tool
```

The resulting lens compared:

- claim evidence vs. resolution evidence,
- `DECLARED` vs. `OBSERVED`,
- `MANIFEST`,
- `OPENTELEMETRY`,
- `OPENAPI`.

The agent explicitly stated that provenance differences do not establish why either qualification was chosen.

## Human-controlled promotion

Two developer decisions were recorded:

### Destination-resolution lens

`PROMOTE_IDEA`

Reason: the question expresses a reusable architecture lens independent of the current snapshot.

Promotion means promoting the **question and reusable live query**, not the current rows.

### Evidence-provenance comparison

`KEEP_AS_EXPERIMENT`

Reason: the evidence-role distinction is useful, but the specific comparison was still tied to two concrete claims. A future promotion should first generalize it into a per-claim evidence/provenance lens.

## Promotion boundary

Permanent promotion follows:

```text
ephemeral question
        ↓
stable GT domain object
        ↓
Contextual Playground
        ↓
reconstruct query over live data
        ↓
developer review
        ↓
permanent method / <gtView>
```

Snapshot-specific rows are never copied into permanent code.

## Result

PoC 4 validated:

- AIP context obtained before tool creation.
- Agent-derived question not limited to payload restatement.
- Ephemeral GT object creation.
- AIP lineage preservation.
- New contextual lens over existing AIP knowledge.
- Separate second lens over evidence/provenance.
- No autonomous permanent code mutation.
- Developer-controlled promotion.

> The agent can propose a new way to inspect AIP knowledge; the developer decides what becomes permanent.
