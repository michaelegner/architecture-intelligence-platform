# PoC 2 — Moldable Exploration of Architecture Evidence

**Result:** PASS

## Purpose

PoC 2 moved from:

> What qualified architecture state does AIP expose?

to:

> What evidence and provenance support a selected AIP claim?

The integration path was:

```text
dependency claim
        ↓
evidence_refs
+
resolution_evidence_refs
        ↓
same originating snapshot
        ↓
get_evidence
        ↓
GT evidence domain objects
        ↓
contextual micro-tools
```

## GT evidence model

The integration introduced:

- `GtAipEvidenceCase`
- `GtAipEvidenceRecord`

The model keeps claim evidence and destination-resolution evidence separate.

Contextual micro-tools included:

- Evidence overview
- Claim evidence
- Resolution evidence
- Supported relations
- Provenance
- Missing evidence
- Claim limitations
- Raw drill-down

## LegacyPricingService case

For the seeded `OrderService → LegacyPricingService` dependency, AIP returned:

- qualification: `OBSERVED_ONLY`
- relation: `CALLS`
- target operation: `GET /pricing/{sku}`

Claim evidence:

```text
OrderService
    --CALLS-->
LegacyPricingService pricing operation
```

Resolution evidence:

```text
LegacyPricingService
    --PROVIDES-->
pricing operation
```

Both records were:

- `evidence_type = OBSERVED`
- `source_type = OPENTELEMETRY`
- `correlation_mode = CLIENT_SERVER`

The evidence lookup reused the exact originating AIP snapshot and returned no missing refs.

## ProductService heterogeneous-evidence case

A second case verified that the GT model was not specialized to OpenTelemetry-only evidence.

For `ProductService`, AIP returned:

- qualification: `CONFIRMED`
- claim evidence from:
  - `MANIFEST / DECLARED`
  - `OPENTELEMETRY / OBSERVED`
- destination-resolution evidence from:
  - `OPENAPI / DECLARED`

This validated that GT could preserve:

```text
claim evidence role
resolution evidence role
evidence type
source type
supported relation
snapshot binding
```

without flattening heterogeneous evidence into one generic bucket.

## Moldable-development step

A concrete evidence question was explored interactively in the Contextual Playground:

> Which evidence records are client/server-correlated observations?

The useful query was then promoted into a contextual micro-tool.

This validated the intended Moldable Development loop:

```text
live AIP evidence object
        ↓
concrete question
        ↓
Contextual Playground query
        ↓
useful answer
        ↓
promoted micro-tool
```

## Epistemic boundary

The PoC explicitly verified:

```text
evidence provenance
        ≠
qualification derivation
```

The available AIP contract exposed:

- evidence records,
- source provenance,
- supported relations,
- snapshot binding,
- qualification value.

It did not expose, for this claim:

- qualification-rule ID,
- qualification-rule version,
- rule predicates,
- evaluation trace,
- promotion conditions.

The GT integration therefore did not reconstruct those elements probabilistically.

## Result

> GT can make AIP architecture evidence moldable and explorable while preserving the distinction between evidence provenance and qualification derivation.
