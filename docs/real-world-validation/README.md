# AIP Real-World Validation

This directory holds the evidence for `v0.3.0` — Real-World Validation & Model Hardening (see
[`docs/specifications/0.3.0/specification.md`](../specifications/0.3.0/specification.md)). The
methodology below is frozen by Iteration 1
([`i1-real-world-validation-contract.md`](../specifications/0.3.0/i1-real-world-validation-contract.md))
and is used unchanged by every later system-specific validation:

```text
I2  Quarkus Super Heroes
I3  Apache Airflow
I4  Cross-System Model Hardening
I5  Release Qualification
```

I1 only establishes the method; I2 added `quarkus-super-heroes/` once its ground truth was frozen
and its qualifying comparison completed. I3 adds `apache-airflow/`: I3.1 froze its declaration-only
ground truth, I3.2 closed the one item I3.1 left provisional (the Celery messaging boundary) via
independent observability qualification, and I3.3 ran the first qualifying comparison — 9/9
`PROVIDES` facts `CORRECT`, 0 missing/incorrect, confirmed repeatable across two independent
clean-state runs (`results.md`, `findings.md`).

## Purpose

AIP `v0.1`/`v0.2` proved architecture intelligence exists and is reproducibly correct against
synthetic ground truth authored *for* AIP. `v0.3` checks whether the same Canonical Architecture
Model remains correct against systems that were **not** designed for AIP — without changing those
systems, or their expected architecture, to make AIP pass.

## The ground-truth independence rule

```text
AIP Input != AIP Expected Output
AIP Output MUST NOT define Ground Truth
```

The prohibited workflow:

```text
run AIP -> inspect its output -> search upstream source for confirmation -> write expected.yaml to match
```

The required workflow:

```text
upstream contracts / docs / config / source / independent runtime evidence
        |
        v
independent architecture dossier
        |
        v
freeze expected.yaml
        |
        v
run AIP
        |
        v
compare
```

A system's `expected.yaml` must be frozen — and its freeze point visible in the commit/PR
history — before the first qualifying AIP comparison run for that system. The following are **not**
independent ground-truth sources: AIP's own graph state, REST analysis output, generated Cypher
results, evaluation projections, or AIP-generated prose about the architecture.

Ground-truth source hierarchy, strongest first:

```text
1. official machine-readable contracts (OpenAPI, AsyncAPI, ...)
2. official architecture documentation
3. official deployment/runtime configuration
4. upstream source code
5. independently captured runtime evidence (e.g. raw OTLP traces)
```

## Finding vocabulary

Every material finding uses exactly one of six fixed classifications:

| Classification | Meaning |
| --- | --- |
| `CORRECT` | A supported expected fact is represented correctly. |
| `MISSING_SUPPORTED` | Independent evidence establishes an in-scope supported fact AIP does not represent (false negative). |
| `INCORRECT_SUPPORTED` | AIP emits a supported claim that contradicts independent ground truth — invented relation, wrong direction/target/sender/status/evidence (false positive). Release-critical when material. |
| `UNSUPPORTED` | The upstream system uses a mechanism outside AIP's current supported semantic scope. Not automatically a defect. |
| `UNRESOLVED_IDENTITY` | Independent evidence suggests a relationship, but AIP cannot safely resolve its canonical identity without guessing. Preferred over inventing one. |
| `INSUFFICIENT_EVIDENCE` | The dossier itself cannot establish the fact strongly enough to use as ground truth. Not an AIP defect. |

Severity (`CRITICAL`/`MAJOR`/`MINOR`/`INFO`) is a distinct concept from classification — see
`real_world_validation/model.py`'s `DEFAULT_SEVERITY` for the fixed default mapping used until a
system-specific dossier overrides it with real evidence.

The governing priority:

```text
correct but incomplete  >  complete-looking but wrong
```

Unsupported architecture is acceptable when explicit. Incorrectly represented supported
architecture is not.

## Dossier structure

Each validated system gets its own directory, using the template in
[`_template/`](_template/):

```text
docs/real-world-validation/
├── README.md                (this file)
├── _template/                dossier + decision-record skeleton, copy per system
├── quarkus-super-heroes/     (added by I2)
└── apache-airflow/           (added by I3)
```

Each system dossier keeps these five concerns separate:

```text
upstream.md        exact pinned upstream identity (repo, tag/commit, license)
profile.md         the bounded, reproducible validation profile actually exercised
ground-truth.md    the independent architecture dossier + evidence references
expected.yaml      the frozen, machine-comparable expected facts (see the schema below)
runbook.md         the ordered, reproducible steps from clean state to a qualifying comparison
results.md         the actual AIP result capture + summary counts for the qualifying run
findings.md        one entry per material finding, with a model-hardening decision record where needed
```

`expected.yaml`'s schema, and the comparator that consumes it, are documented in
[`real_world_validation/README.md`](../../real_world_validation/README.md) — that Python package
*is* this methodology's reference implementation:

```text
model.py        the six classifications, severity, and comparison records
loader.py       strict expected.yaml / actual-facts-capture parsing
comparator.py   deterministic classification + sort
reporter.py     plaintext report, no composite score
__main__.py     `uv run python -m real_world_validation compare --expected ... --actual ...`
```

## Reproducing a validation

1. Pin the upstream system to an exact tag/commit (`upstream.md`).
2. Define and document the bounded profile actually run (`profile.md`).
3. Build the independent dossier and freeze `expected.yaml` from evidence alone — before ever
   running AIP against this system (`ground-truth.md`).
4. Follow `runbook.md` end to end: start the system, enable telemetry, exercise the declared flows,
   import declared sources into AIP, capture AIP's actual facts.
5. Run `uv run python -m real_world_validation compare --expected expected.yaml --actual
   <captured-actual-facts>` and record the output in `results.md`.
6. Classify and disposition every material finding in `findings.md`, using the model-hardening
   decision-record template in `_template/decision-record.md` for anything that might change AIP.

## Supported scope vs. complete architecture

AIP is not required to model every mechanism a validated system uses. A mechanism outside AIP's
supported scope is legitimately `UNSUPPORTED` — provided AIP does not silently convert it into a
semantically incorrect supported fact instead. Coverage completeness is explicitly **not** a
release requirement; correctness of what AIP *does* claim is.
