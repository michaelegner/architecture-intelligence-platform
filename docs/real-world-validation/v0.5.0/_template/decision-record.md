# Finding `<id>`

Model-hardening decision record template (I1 §24). Author this before or together with the
corresponding production fix, for any finding that may change AIP semantics.

## System

<system>

## Independent evidence

<references into ground-truth.md / upstream evidence>

## Current AIP behavior

<description>

## Classification

<CORRECT | MISSING_SUPPORTED | INCORRECT_SUPPORTED | UNSUPPORTED | UNRESOLVED_IDENTITY | INSUFFICIENT_EVIDENCE>

## Severity

<CRITICAL | MAJOR | MINOR | INFO>

## Decision

<FIX | DOCUMENT_UNSUPPORTED | DEFER | NO_CHANGE>

A change is justified only when all of (I1 §26): independent real-system evidence demonstrates the
problem; current AIP behavior is materially incorrect or blocks an important supported use case;
the correction is general rather than system-specific; the corrected semantic can be stated
precisely; deterministic regression coverage can be added. A richer possible model is not
sufficient justification on its own.

## Rationale

<why>

## Canonical-model impact

<none / description>

## Compatibility impact

<none / description>

## Required implementation change

<description>

## Regression coverage

<test/fixture>
