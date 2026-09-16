---
name: specification-driven-implementation
description: Use when implementing or reviewing substantial work against an AIP release or increment specification (the release specification or its iN-*.md increment specs) - producing a reviewed plan before changing production code, persisting it, implementing without altering normative semantics, reconciling the result against the retained plan, and driving PR reviews to a clear approval decision. Not needed for small maintenance changes that don't touch public contracts, identity, evidence, qualification, reconciliation, or release semantics.
---

# Specification-driven implementation

This skill is **procedural, not normative**. It cannot override
[product doctrine](../../../docs/product-doctrine-and-strategic-direction.md),
[`ROADMAP.md`](../../../ROADMAP.md) boundaries, or any specification under
[`docs/specifications/`](../../../docs/specifications/). Where this skill and a specification
disagree, the specification wins — stop and flag the conflict rather than following this skill
past it. See [`AGENTS.md`](../../../AGENTS.md) for the mandatory-behavior list this skill executes.

**Tests are evidence, not qualification.** Agent-authored tests demonstrate that an implementation
does what the plan says it does — they are implementation evidence. They are never independent
qualification of the specification itself, and passing tests can never resolve a specification
ambiguity. If the specification is ambiguous about what "correct" means here, no amount of green
tests answers that question — only a specification decision does.

**Stop on unstated semantic decisions.** If implementing the plan requires a decision the
specification doesn't state — a precedence rule, an identity formula, a conflict-resolution
outcome, an unsupported-case behavior — stop and return the decision to the specification (ask the
human, or propose a specific, disclosed specification amendment). Do not silently pick a default
and continue.

**Small-change exemption.** A maintenance change that doesn't alter public contracts, identity
rules, evidence/provenance semantics, qualification behavior, reconciliation logic, or release
semantics does not need this full workflow. When genuinely uncertain whether a change qualifies,
treat it as substantial and run the full workflow anyway.

## The nine phases

1. **Resolve the governing specification and revision.** Identify the exact release and increment
   spec (or parent spec) this work is governed by, and its exact revision/draft marker (e.g. "Draft
   0.3, amended during PR3b — see its own §12 amendment note"). Read the product doctrine and
   `ROADMAP.md` context around it, not just the increment file in isolation.

2. **Inspect the current repository and relevant prior implementation.** Read what already exists:
   related modules, prior completion records (`iN-completion-record.md` for earlier increments in
   the same release), existing tests, existing utilities. Reuse existing patterns and functions
   before proposing new ones — a fresh module that duplicates something already in `app/` is a
   planning failure, not a stylistic choice.

3. **Identify ambiguities or conflicts before planning.** Surface anything the specification leaves
   unstated or that conflicts with product doctrine/roadmap/another spec *now*, before writing the
   plan — not mid-implementation, when a stop-and-ask costs a throwaway diff instead of a throwaway
   sentence.

4. **Produce the bounded implementation plan**, using the template below. Bounded means explicit
   non-goals, not just an explicit scope.

5. **Wait for human review before any production-code change.** The plan is not authorization to
   start; it's a draft for the human to approve, redirect, or reject.

6. **Persist the approved plan, verbatim, in the GitHub issue or the initial PR description.** This
   is the record of what was promised — it must survive independent of any later summary.

7. **Implement without changing normative semantics.** The plan bounds scope; it does not license
   reinterpreting the specification along the way. If the plan itself turns out to be wrong once
   implementation starts, that's a return to phase 3, not a silent in-flight redefinition.

8. **Execute the specified validation and qualification steps** — the plan's own "Validation
   Commands" section, run in full (this repo's real `tests/unit`/`tests/integration` suites, lint,
   format — not a hand-picked subset).

9. **Reconcile the final implementation against the *retained* original plan**, using the
   reconciliation template below. This is a diff against what was promised, not a fresh
   retrospective that quietly replaces the plan — both documents should remain visible together.

## Checking for review feedback

Before treating a "findings check" as complete — whether re-reviewing a PR or responding to
feedback on one you implemented — enumerate every comment surface, not just the first one found:
top-level PR review submissions (each reviewer's own review body, including bot reviewers like
Copilot), inline/line-level review comments, and plain issue-level PR comments. These are separate
API surfaces and separate UI sections; checking one does not surface the others. A comment from a
second reviewer (human or automated) can arrive close in time to a bot's and raise different
findings that don't overlap at all — cross-reference the full list before concluding the fixes
already made cover everything raised, not just the first source checked.

## PR review convergence

For a specification-governed PR review, make the first substantive review as complete and
acceptance-oriented as the available evidence permits. Include the reviewed head SHA and consolidate
all known material blockers in one comment. For each blocker, cite the governing requirement, point
to concrete implementation evidence, state the required outcome without unnecessarily prescribing
the implementation, and identify the regression test or qualification evidence needed. End with an
explicit approval condition.

Re-reviews are limited to:

- resolving the recorded blockers;
- checking the requested evidence and CI; and
- identifying material correctness, security, interoperability, release-validity, or explicit-gate
  regressions introduced by the fixes.

Maintain a clear disposition of prior blockers, distinguish genuinely new blockers from unresolved
ones, and explain why any new blocker was not reasonably identifiable earlier. Do not extend the
review with cosmetic, procedural, or merely preferable changes; record worthwhile out-of-scope work
separately. Once the blocker list is empty and required evidence is green, approve or explicitly
report no blocking findings.

Use this compact comment shape when useful:

```markdown
**Review of head `<sha>`**

Previous blockers: <resolved/remaining summary>.
New blockers: <none, or material findings with governing requirement and evidence>.
Required evidence: <tests, qualification, and CI>.

**Exit condition:** <specific conditions after which the PR will be approved, unless their fixes
introduce a material regression>.
```

## Plan template

```markdown
## Governing Specification
<path + exact revision/draft marker>

## Scope & Non-Goals
<bounded scope> / <explicit non-goals>

## Affected Components
<modules, files, expected change surface>

## Requirement -> Task Mapping
<specification requirement -> implementation task, one row per requirement>

## Acceptance Criteria -> Test/Evidence Mapping
<acceptance criterion -> test(s) or evidence that will prove it>

## Validation Commands
<exact commands to run, e.g. `uv run pytest tests/unit`, `uv run pytest tests/integration`,
`uv run ruff check .`, `uv run ruff format --check .`>

## Open Questions / Assumptions / Stop Conditions
<anything unresolved, any assumption made explicit, any condition that should halt implementation
and return to the specification>
```

## Reconciliation template

```markdown
## Completed As Planned
<what matches the plan exactly>

## Deviations & Justification
<what changed from the plan, and why>

## Specification Questions Discovered
<any ambiguity or gap surfaced during implementation, and how it was resolved (or that it's still
open)>

## Deferred Work
<what was explicitly out of scope or pushed to a later increment>

## Test/Qualification Evidence
<the actual validation-command results, e.g. exact pass counts>

## Remaining Limitations
<what this implementation does not cover, disclosed rather than silently omitted>
```
