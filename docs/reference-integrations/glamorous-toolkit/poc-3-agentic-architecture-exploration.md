# PoC 3 — Agentic Architecture Exploration

**Result:** PASS

## Purpose

PoC 3 changed the starting point from a preloaded GT object to a natural-language architecture question.

```text
architecture question
        ↓
GT-hosted agent
        ↓
agent chooses AIP capability
        ↓
AIP MCP tools
        ↓
qualified answer
        ↓
optional follow-up AIP call
        ↓
GT presentation
```

The agent received only the AIP MCP tool surface:

- `get_service_dependencies`
- `get_architecture_drift`
- `get_evidence`

## Dependency exploration

Asked for the direct dependencies of `service:order-service`, the agent selected `get_service_dependencies` and preserved AIP's returned semantics, including:

- `PARTIAL` outcome,
- `CONFIRMED`,
- `OBSERVED_ONLY`,
- `NOT_OBSERVED_IN_WINDOW`,
- `DIRECT_TARGET_FALLBACK`,
- `UNRESOLVED_IDENTITY`.

The agent explicitly preserved the boundary:

> `NOT_OBSERVED_IN_WINDOW` does not establish absence of activity.

## Agentic evidence chaining

Asked which dependency was `OBSERVED_ONLY` and what evidence supported it, the agent selected:

```text
get_service_dependencies
        ↓
get_evidence
```

The second request reused:

- the exact claim evidence ref,
- the exact resolution evidence ref,
- the exact originating snapshot.

AIP returned two OpenTelemetry records and no missing evidence refs.

This demonstrated real agentic chaining rather than a pre-scripted second call.

## Heterogeneous evidence reasoning

For `ProductService`, the agent correctly preserved:

```text
CLAIM evidence
  MANIFEST / DECLARED
  OPENTELEMETRY / OBSERVED

RESOLUTION evidence
  OPENAPI / DECLARED
```

It did not collapse the three evidence sources into one semantic role.

## Drift capability selection

Asked for architecture drift, the agent selected `get_architecture_drift` rather than defaulting to dependency exploration.

The response preserved:

- `PARTIAL`,
- drift classifications,
- fallback semantics,
- unresolved-identity limitations.

## Qualification-derivation boundary

Asked:

> Why exactly did AIP classify LegacyPricingService as OBSERVED_ONLY, and which rule/version caused it?

the agent correctly separated:

1. facts AIP exposes,
2. interpretation,
3. information not exposed by the current contract.

It explicitly refused to invent:

- rule ID,
- rule version,
- evaluation trace,
- missing-evidence conditions,
- promotion conditions.

It also correctly noted that AIP producer version `0.4.2` is not a qualification-rule version.

## Prescriptive boundary

Asked which dependency should be removed first, the agent stated that the available AIP tools do not establish a prescriptive answer.

It could summarize relevant facts, but did not attribute a migration recommendation to AIP.

## Result

PoC 3 validated:

```text
semantic tool selection        ✓
multi-step evidence chaining   ✓
snapshot-bound follow-up       ✓
evidence-role preservation     ✓
drift capability selection     ✓
knowing when AIP cannot answer ✓
```

> The agent can choose the questions and reason over AIP answers without becoming the source of architecture knowledge.
