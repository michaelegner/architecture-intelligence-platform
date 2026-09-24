# Independent Ground Truth — `<system-id>` (v0.5.0)

This is drafted from upstream evidence only, **before** any qualifying AIP output for this system is
inspected. The owner reviews it, and merging the dossier PR freezes it (I5 §6).

## Rules

- Every fact cites its upstream source: a file and line at the pinned commit, a doc URL, or a config
  key.
- AIP graph contents, API responses, comparator output, and generated prose never determine a fact.
- A dossier PR never contains or references qualifying AIP output for this target.

## Evidence sources used, strongest first

1. Official machine-readable contracts (OpenAPI/AsyncAPI, upstream Kubernetes manifests):
2. Official architecture documentation:
3. Official deployment/runtime configuration:
4. Upstream source code:
5. Independently captured runtime evidence:

## Architecture facts established

<!-- One entry per fact, each with its citation. The machine-comparable form goes in
     expected.yaml, including forbidden facts and DEPLOYED_AS outcomes. -->

| Fact | Citation |
| --- | --- |
| <e.g. rest-fights CALLS GET /api/heroes/random> | <path:line at pin> |

## Unknowns

<!-- Record as UNRESOLVED_IDENTITY or INSUFFICIENT_EVIDENCE in expected.yaml. Never guess. -->

## Change log

<!-- A post-freeze change needs a cited upstream-evidence correction, a new freeze revision, and
     reruns of the affected comparisons. Changing expectations to make AIP pass is prohibited. -->
