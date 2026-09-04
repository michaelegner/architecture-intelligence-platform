# Independent Ground Truth — `<system-id>`

Built **before** `expected.yaml` is frozen and before AIP is ever run against this system (I1
§5/§36). Every claim below should be traceable to one of the evidence sources in the hierarchy
below — never to AIP's own output.

## Evidence sources used, strongest first (I1 §6-7)

1. Official machine-readable contracts:
   <!-- e.g. OpenAPI/AsyncAPI files, exact path/URL within the pinned commit -->
2. Official architecture documentation:
   <!-- e.g. official architecture diagrams -->
3. Official deployment/runtime configuration:
   <!-- e.g. broker/executor configuration -->
4. Upstream source code:
   <!-- e.g. source showing a producer/consumer -->
5. Independently captured runtime evidence:
   <!-- e.g. raw or independently inspected OTLP traces -->

## Architecture facts established

<!-- One entry per fact this dossier independently establishes, each referencing the evidence
     above by source. This is prose/notes; the machine-comparable form goes in expected.yaml. -->

## Unknowns

<!-- Anything this dossier could not establish confidently. Record as UNRESOLVED_IDENTITY (AIP
     cannot safely resolve identity) or INSUFFICIENT_EVIDENCE (the dossier itself is not strong
     enough) in expected.yaml (I1 §38) — never guess. -->

## Change log

<!-- Ground truth may change after the qualifying run only when: independent evidence was wrong or
     incomplete, upstream scope changed, the pinned revision changed, the validation profile
     changed, or a documented evidence interpretation was corrected (I1 §37). It must never change
     merely because AIP disagreed. Record every post-freeze change here. -->
