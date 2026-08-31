# Results — Quarkus Super Heroes

Qualifying comparison for the pinned commit `8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce` (I2.3).
Executed by following [`runbook.md`](runbook.md) phases 1-9 for real against a freshly built,
freshly started stack, then capturing and comparing per phases 10-11.

**This is the second live run of this profile in this PR.** The first run (same upstream commit,
same images, same `expected.yaml`) used an earlier version of `real_world_validation/capture.py`
that did not query declared/observed evidence for `PROVIDES` facts. Building out that capture tool
initially led to an incorrect same-PR ground-truth edit (removing the frozen `declared: true`
assertion from `expected.yaml`'s `PROVIDES` facts to match the tool's omission) — this was reverted
after review (PR #41 review F1) once it was confirmed that AIP's own canonical/provenance model
*does* attach real `DECLARED` evidence to every `PROVIDES` relation
(`app/ingestion/openapi_adapter.py`). `capture.py` was corrected instead (PR #41 review F1/F2: it
now queries declared/observed evidence generically for AIP's complete canonical relation
vocabulary, `app.graph_schema.registry.RELATIONS`, not only the three relation types that also have
runtime *status* semantics), and the live profile was re-executed from clean state end to end so
the committed `actual.yaml`/comparison reflects the corrected tool, never a hand-patched capture. See
`ground-truth.md`'s "Change log" for the full account.

## Run identity

```text
upstream commit:    8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
image tags:         quarkus-super-heroes/<service>:8ea0337 (built from source, runbook.md phase 3)
environment:        quarkus-i2
window_start:       2026-08-31T15:18:25Z
window_end:         2026-08-31T15:18:40Z
```

All six required images were built from source once (containerized `maven:3.9.16-eclipse-temurin-25`,
no `quay.io/quarkus-super-heroes/*:java25-latest` pulled) and reused unmodified for both live runs
in this PR. For this (second, reported) run: the full compose stack
(`runtime/docker-compose.yml`) was started from clean state, the bounded readiness gate passed for
every service on the first pass, `POST /api/import` succeeded for all four declared services
(identical `nodes_written`/`relations_written` counts to the first run), `runtime/traffic.sh` ran
once inside the window above, and the phase-9 drain barrier confirmed AIP had persisted runtime
relations before capture began. The stack was torn down (`docker compose down -v`) after capture.

## Repeatability evidence

This PR includes three live executions of this profile, but only the second and third used the
final, corrected comparison contract (`capture.py` after the PR #41 review F1/F2 fix) — the first
run predates that fix and also ran while a since-reverted draft had temporarily weakened
`expected.yaml`, so it does not count as a qualifying run under the same contract as the other two
(PR #41 re-review N1). What the three runs *do* show: the same pinned commit and images, started
from clean state independently three times, produced the same service/operation identities, the
same relation counts, and the same traffic behavior (including the identical narration-fallback
observation below) every time — architecturally stable across restarts. The second run is this
document's reported qualifying comparison; the third was a diagnostic-only re-run (Collector
temporarily set to detailed verbosity, no comparator invoked) to investigate the Kafka finding in
`findings.md`'s `qsh-kafka-operation-type-gap`. I2.4 (below) supplies the second same-contract
comparator run, closing the I2 spec §43 requirement in full.

## Revalidation (I2.4)

A fourth live execution of this profile, run independently after I2.3 merged, using the exact same
frozen inputs and the exact same, unmodified `capture.py`/comparator contract — no production code,
`expected.yaml`, `docker-compose.yml`, `runbook.md`, or `traffic.sh` changes in between.

```text
upstream commit:    8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
image tags:         quarkus-super-heroes/<service>:8ea0337 (unmodified, reused — no rebuild)
environment:        quarkus-i2
window_start:       2026-08-31T16:35:00Z
window_end:         2026-08-31T16:35:10Z
```

Same procedure as the qualifying run above: clean-state compose stack, bounded readiness gate
passed for every service on the first pass, `POST /api/import` returned identical
`nodes_written`/`relations_written` counts (22/23, 14/16, 8/6, 14/16 for
fights/heroes/narration/villains), `traffic.sh` ran once, and the phase-9 drain barrier confirmed
persisted runtime relations before capture. One operational note: `window_end` here is recorded
with a wider margin than the raw `traffic.sh` completion timestamp (`16:35:02Z`) — the narration
call's OTel span landed at `16:35:02.826Z`, a few hundred milliseconds after that raw timestamp
(consistent with the narration-fallback startup delay already documented above), so the capture's
`--until` was widened to `16:35:10Z` to avoid an artificial `NOT_OBSERVED_IN_WINDOW` from a
too-tightly-drawn window boundary rather than a real difference in AIP's behavior. This is an
operator choice about how generously to draw the window (the runbook does not mandate an exact
width), not a change to the comparison contract itself.

Capture: 38 facts (identical composition to `artifacts/actual.yaml` — 35 `PROVIDES`
declared=true/observed=false, 3 `CALLS` all `CONFIRMED`/declared=true/observed=true), written to
[`artifacts/actual-revalidation.yaml`](artifacts/actual-revalidation.yaml).

Comparator result against the unmodified `expected.yaml`:

```text
Expected supported facts:      38
Correct:                       38
Missing supported:             0
Incorrect supported:           0
Unsupported constructs:        2
Unresolved identities:         0
Insufficient evidence:         0
Critical semantic errors:      0
```

Identical to the qualifying run's summary and every individual finding classification, including
`qsh-fights-calls-narration` again resolving `CORRECT`/`CONFIRMED`. This satisfies I2 spec §43's
repeatability requirement in full: two independent runs, same upstream SHA, same profile, same
frozen `expected.yaml`, same AIP candidate, same finding classifications, same summary counts.

## AIP result capture

[`artifacts/actual.yaml`](artifacts/actual.yaml) — captured via:

```bash
uv run python -m real_world_validation capture \
  --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j --neo4j-password <redacted> \
  --database neo4j --environment quarkus-i2 \
  --since 2026-08-31T15:18:25Z --until 2026-08-31T15:18:40Z \
  --scope-entities service:rest-fights,service:rest-heroes,service:rest-villains,service:rest-narration,service:event-statistics \
  --scope-relation-types PROVIDES,CALLS,SENDS,RECEIVES_FROM \
  --out artifacts/actual.yaml
```

38 facts captured: 35 `PROVIDES` (`declared=true, observed=false` — real `DECLARED` evidence from
the OpenAPI import, no runtime status concept applies to `PROVIDES`) + 3 `CALLS` (all `CONFIRMED`,
`declared=true, observed=true`). No `SENDS`/`RECEIVES_FROM` facts were captured despite both being
in scope — see "Kafka boundary" in `findings.md`.

## Summary

Two different counts appear in this dossier, and they measure different things — reported
separately here so neither headline is ambiguous (PR #41 final re-review F1).

**Comparator result** — `expected.yaml` vs. `artifacts/actual.yaml`, via `real_world_validation
compare` (below). `expected.yaml` declares no `insufficient_evidence:` entries, so the comparator
itself reports `0` for that field; this is not a claim that I2.3's overall investigation found
nothing insufficiently evidenced, only that nothing in the *frozen, pre-run* expected set was
pre-declared as such:

```text
Expected supported facts:      38
Correct:                       38
Missing supported:              0
Incorrect supported:            0
Unsupported constructs:         2
Unresolved identities:          0
Insufficient evidence:          0
Critical semantic errors:       0
```

**Overall I2.3 findings** — the comparator result above, plus one additional finding
(`qsh-kafka-operation-type-gap`) discovered by a separate diagnostic raw-telemetry inspection
*after* the comparator run, not by the comparator itself (`findings.md` has the full account):

```text
CORRECT:                 38
UNSUPPORTED:              2
INSUFFICIENT_EVIDENCE:    1
MISSING_SUPPORTED:        0
INCORRECT_SUPPORTED:      0
UNRESOLVED_IDENTITY:      0
Critical semantic errors: 0
```

## Comparator output

```bash
uv run python -m real_world_validation compare \
  --expected expected.yaml --actual artifacts/actual.yaml
```

```text
AIP Real-World Validation — I1 contract

[UNSUPPORTED/INFO] qsh-grpc-locations
[UNSUPPORTED/INFO] qsh-kafka-fights-topic

[CORRECT/INFO] qsh-fights-calls-heroes
Expected:
  CALLS
  service:rest-fights
    -> operation:service:rest-heroes:GET:/api/heroes/random
  status: None  evidence: declared=true observed=?
Actual:
  CALLS
  service:rest-fights
    -> operation:service:rest-heroes:GET:/api/heroes/random
  status: CONFIRMED  evidence: declared=true observed=true

[CORRECT/INFO] qsh-fights-calls-narration
Expected:
  CALLS
  service:rest-fights
    -> operation:service:rest-narration:POST:/api/narration
  status: None  evidence: declared=true observed=?
Actual:
  CALLS
  service:rest-fights
    -> operation:service:rest-narration:POST:/api/narration
  status: CONFIRMED  evidence: declared=true observed=true

[CORRECT/INFO] qsh-fights-calls-villains
Expected:
  CALLS
  service:rest-fights
    -> operation:service:rest-villains:GET:/api/villains/random
  status: None  evidence: declared=true observed=?
Actual:
  CALLS
  service:rest-fights
    -> operation:service:rest-villains:GET:/api/villains/random
  status: CONFIRMED  evidence: declared=true observed=true

[CORRECT/INFO] qsh-fights-provides-getAllFights
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-fights-provides-hello
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-fights-provides-helloHeroes
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/heroes
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/heroes
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-fights-provides-helloLocations
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/locations
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/locations
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-fights-provides-helloNarration
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/narration
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/narration
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-fights-provides-helloVillains
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/villains
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/villains
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-fights-provides-getRandomFighters
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/randomfighters
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/randomfighters
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-fights-provides-getRandomLocation
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/randomlocation
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/randomlocation
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-fights-provides-getFight
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/{id}
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/{id}
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-fights-provides-performFight
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:POST:/api/fights
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:POST:/api/fights
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-fights-provides-narrateFight
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:POST:/api/fights/narrate
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:POST:/api/fights/narrate
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-fights-provides-generateImageFromNarration
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:POST:/api/fights/narrate/image
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:POST:/api/fights/narrate/image
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-heroes-provides-deleteAllHeroes
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:DELETE:/api/heroes
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:DELETE:/api/heroes
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-heroes-provides-deleteHero
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:DELETE:/api/heroes/{id}
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:DELETE:/api/heroes/{id}
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-heroes-provides-getAllHeroes
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-heroes-provides-hello
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes/hello
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes/hello
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-heroes-provides-getRandomHero
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes/random
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes/random
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-heroes-provides-getHero
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes/{id}
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes/{id}
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-heroes-provides-partiallyUpdateHero
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:PATCH:/api/heroes/{id}
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:PATCH:/api/heroes/{id}
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-heroes-provides-createHero
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:POST:/api/heroes
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:POST:/api/heroes
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-heroes-provides-replaceAllHeroes
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:PUT:/api/heroes
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:PUT:/api/heroes
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-heroes-provides-fullyUpdateHero
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:PUT:/api/heroes/{id}
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:PUT:/api/heroes/{id}
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-narration-provides-hello
Expected:
  PROVIDES
  service:rest-narration
    -> operation:service:rest-narration:GET:/api/narration/hello
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-narration
    -> operation:service:rest-narration:GET:/api/narration/hello
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-narration-provides-narrate
Expected:
  PROVIDES
  service:rest-narration
    -> operation:service:rest-narration:POST:/api/narration
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-narration
    -> operation:service:rest-narration:POST:/api/narration
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-narration-provides-generateImageFromNarration
Expected:
  PROVIDES
  service:rest-narration
    -> operation:service:rest-narration:POST:/api/narration/image
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-narration
    -> operation:service:rest-narration:POST:/api/narration/image
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-villains-provides-deleteAllVillains
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:DELETE:/api/villains
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:DELETE:/api/villains
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-villains-provides-deleteVillain
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:DELETE:/api/villains/{id}
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:DELETE:/api/villains/{id}
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-villains-provides-getAllVillains
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-villains-provides-hello
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains/hello
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains/hello
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-villains-provides-getRandomVillain
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains/random
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains/random
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-villains-provides-getVillain
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains/{id}
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains/{id}
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-villains-provides-partiallyUpdateVillain
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:PATCH:/api/villains/{id}
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:PATCH:/api/villains/{id}
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-villains-provides-createVillain
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:POST:/api/villains
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:POST:/api/villains
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-villains-provides-replaceAllVillains
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:PUT:/api/villains
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:PUT:/api/villains
  status: None  evidence: declared=true observed=false

[CORRECT/INFO] qsh-villains-provides-fullyUpdateVillain
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:PUT:/api/villains/{id}
  status: None  evidence: declared=true observed=?
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:PUT:/api/villains/{id}
  status: None  evidence: declared=true observed=false

Expected supported facts:      38
Correct:                       38
Missing supported:              0
Incorrect supported:            0
Unsupported constructs:         2
Unresolved identities:          0
Insufficient evidence:          0
Critical semantic errors:       0
```

## Notable runtime observation (non-material — does not change any finding above)

`rest-fights`' response body for `POST /api/fights/narrate` was the exact, word-for-word fallback
text hardcoded in its own `fight.narration.fallback-narration` config property, not narration text
generated by `rest-narration` — observed identically in **both** live runs of this profile.
`rest-narration`'s own logs show several `BlockedThreadChecker` warnings during its ~14s startup
window immediately before the call, consistent with its narration `@Timeout`/`@Fallback`/
`@CircuitBreaker` chain (30s timeout) engaging rather than the call failing outright. This did
**not** prevent AIP from correctly recording `rest-fights -> rest-narration` as
`CALLS`/`CONFIRMED`/`declared=true,observed=true` in either run — the architectural interaction (an
HTTP call was made and observed) is independent of whether `rest-narration`'s own business logic
produced a real vs. fallback narration. See `findings.md` for why this stays a non-material
observation rather than a finding.

## Kafka telemetry-recognition gap (material — see `findings.md`'s `qsh-kafka-operation-type-gap`)

`0 SENDS`/`0 RECEIVES_FROM` in the capture above is real, but PR #41's re-review correctly identified
that it does not by itself prove AIP safely refuses to map the Kafka `fights` topic onto Queue
semantics — the current production messaging resolver (`app/telemetry/adapter.py`) has no
Kafka-topic-specific safety logic at all; it converts *any* span with a recognized
`messaging.operation.type` into a `SENDS`/`RECEIVES_FROM` fact. A dedicated diagnostic re-run (same
pinned commit/images, the Collector temporarily set to `verbosity: detailed` for this inspection
only, no committed file changed, no comparator invoked) captured the real span `rest-fights` exports
for its Kafka publish and found it uses the legacy `messaging.operation: publish` attribute, not
`messaging.operation.type` — the only attribute name AIP's allowlist recognizes — so the span is
silently skipped before ever reaching the resolver, and no consumer-side (`event-statistics`) span
was observed at all in this window. The "0" result therefore reflects a telemetry-recognition gap
between AIP's allowlist and this specific OTel instrumentation, not a validated safe rejection. Full
evidence: `evidence/messaging.md`; disposition: `decisions/qsh-kafka-operation-type-gap.md`
(`DEFER`, per `findings.md`).

## Exit code

```text
0  (no release-blocking / CRITICAL-severity finding)
```
