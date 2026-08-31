# Results — Quarkus Super Heroes

First qualifying comparison for the pinned commit `8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce`
(I2.3). Executed by following [`runbook.md`](runbook.md) phases 1-9 for real against a freshly
built, freshly started stack, then capturing and comparing per phases 10-11.

## Run identity

```text
upstream commit:    8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
image tags:         quarkus-super-heroes/<service>:8ea0337 (built from source, runbook.md phase 3)
environment:        quarkus-i2
window_start:       2026-08-31T14:45:03Z
window_end:         2026-08-31T14:46:36Z
```

All six required images were built from source inside this session (containerized
`maven:3.9.16-eclipse-temurin-25`, no `quay.io/quarkus-super-heroes/*:java25-latest` pulled), the
full compose stack (`runtime/docker-compose.yml`) was started from clean state, the bounded
readiness gate passed for every service on the first pass, `POST /api/import` succeeded for all
four declared services, `runtime/traffic.sh` ran once inside the window above, and the phase-9
drain barrier confirmed AIP had persisted runtime relations before capture began. The stack was
torn down (`docker compose down -v`) after capture.

## AIP result capture

[`artifacts/actual.yaml`](artifacts/actual.yaml) — captured via:

```bash
uv run python -m real_world_validation capture \
  --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j --neo4j-password <redacted> \
  --database neo4j --environment quarkus-i2 \
  --since 2026-08-31T14:45:03Z --until 2026-08-31T14:46:36Z \
  --scope-entities service:rest-fights,service:rest-heroes,service:rest-villains,service:rest-narration,service:event-statistics \
  --scope-relation-types PROVIDES,CALLS,SENDS,RECEIVES_FROM \
  --out artifacts/actual.yaml
```

38 facts captured: 35 `PROVIDES` (identity only) + 3 `CALLS` (all `CONFIRMED`, `declared=true,
observed=true`). No `SENDS`/`RECEIVES_FROM` facts were captured despite both being in scope — see
"Kafka boundary" below.

## Summary

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
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights

[CORRECT/INFO] qsh-fights-provides-hello
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello

[CORRECT/INFO] qsh-fights-provides-helloHeroes
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/heroes
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/heroes

[CORRECT/INFO] qsh-fights-provides-helloLocations
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/locations
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/locations

[CORRECT/INFO] qsh-fights-provides-helloNarration
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/narration
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/narration

[CORRECT/INFO] qsh-fights-provides-helloVillains
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/villains
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/hello/villains

[CORRECT/INFO] qsh-fights-provides-getRandomFighters
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/randomfighters
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/randomfighters

[CORRECT/INFO] qsh-fights-provides-getRandomLocation
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/randomlocation
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/randomlocation

[CORRECT/INFO] qsh-fights-provides-getFight
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/{id}
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:GET:/api/fights/{id}

[CORRECT/INFO] qsh-fights-provides-performFight
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:POST:/api/fights
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:POST:/api/fights

[CORRECT/INFO] qsh-fights-provides-narrateFight
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:POST:/api/fights/narrate
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:POST:/api/fights/narrate

[CORRECT/INFO] qsh-fights-provides-generateImageFromNarration
Expected:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:POST:/api/fights/narrate/image
Actual:
  PROVIDES
  service:rest-fights
    -> operation:service:rest-fights:POST:/api/fights/narrate/image

[CORRECT/INFO] qsh-heroes-provides-deleteAllHeroes
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:DELETE:/api/heroes
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:DELETE:/api/heroes

[CORRECT/INFO] qsh-heroes-provides-deleteHero
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:DELETE:/api/heroes/{id}
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:DELETE:/api/heroes/{id}

[CORRECT/INFO] qsh-heroes-provides-getAllHeroes
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes

[CORRECT/INFO] qsh-heroes-provides-hello
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes/hello
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes/hello

[CORRECT/INFO] qsh-heroes-provides-getRandomHero
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes/random
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes/random

[CORRECT/INFO] qsh-heroes-provides-getHero
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes/{id}
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:GET:/api/heroes/{id}

[CORRECT/INFO] qsh-heroes-provides-partiallyUpdateHero
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:PATCH:/api/heroes/{id}
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:PATCH:/api/heroes/{id}

[CORRECT/INFO] qsh-heroes-provides-createHero
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:POST:/api/heroes
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:POST:/api/heroes

[CORRECT/INFO] qsh-heroes-provides-replaceAllHeroes
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:PUT:/api/heroes
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:PUT:/api/heroes

[CORRECT/INFO] qsh-heroes-provides-fullyUpdateHero
Expected:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:PUT:/api/heroes/{id}
Actual:
  PROVIDES
  service:rest-heroes
    -> operation:service:rest-heroes:PUT:/api/heroes/{id}

[CORRECT/INFO] qsh-narration-provides-hello
Expected:
  PROVIDES
  service:rest-narration
    -> operation:service:rest-narration:GET:/api/narration/hello
Actual:
  PROVIDES
  service:rest-narration
    -> operation:service:rest-narration:GET:/api/narration/hello

[CORRECT/INFO] qsh-narration-provides-narrate
Expected:
  PROVIDES
  service:rest-narration
    -> operation:service:rest-narration:POST:/api/narration
Actual:
  PROVIDES
  service:rest-narration
    -> operation:service:rest-narration:POST:/api/narration

[CORRECT/INFO] qsh-narration-provides-generateImageFromNarration
Expected:
  PROVIDES
  service:rest-narration
    -> operation:service:rest-narration:POST:/api/narration/image
Actual:
  PROVIDES
  service:rest-narration
    -> operation:service:rest-narration:POST:/api/narration/image

[CORRECT/INFO] qsh-villains-provides-deleteAllVillains
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:DELETE:/api/villains
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:DELETE:/api/villains

[CORRECT/INFO] qsh-villains-provides-deleteVillain
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:DELETE:/api/villains/{id}
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:DELETE:/api/villains/{id}

[CORRECT/INFO] qsh-villains-provides-getAllVillains
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains

[CORRECT/INFO] qsh-villains-provides-hello
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains/hello
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains/hello

[CORRECT/INFO] qsh-villains-provides-getRandomVillain
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains/random
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains/random

[CORRECT/INFO] qsh-villains-provides-getVillain
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains/{id}
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:GET:/api/villains/{id}

[CORRECT/INFO] qsh-villains-provides-partiallyUpdateVillain
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:PATCH:/api/villains/{id}
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:PATCH:/api/villains/{id}

[CORRECT/INFO] qsh-villains-provides-createVillain
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:POST:/api/villains
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:POST:/api/villains

[CORRECT/INFO] qsh-villains-provides-replaceAllVillains
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:PUT:/api/villains
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:PUT:/api/villains

[CORRECT/INFO] qsh-villains-provides-fullyUpdateVillain
Expected:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:PUT:/api/villains/{id}
Actual:
  PROVIDES
  service:rest-villains
    -> operation:service:rest-villains:PUT:/api/villains/{id}

Expected supported facts:      38
Correct:                       38
Missing supported:             0
Incorrect supported:           0
Unsupported constructs:        2
Unresolved identities:         0
Insufficient evidence:         0
Critical semantic errors:      0
```

## Notable runtime observation (non-material — does not change any finding above)

`rest-fights`' response body for `POST /api/fights/narrate` during this run was the exact,
word-for-word fallback text hardcoded in its own `fight.narration.fallback-narration` config
property, not narration text generated by `rest-narration` — `rest-narration`'s own logs show
several `BlockedThreadChecker` warnings during its ~14s startup window immediately before the
call, consistent with its narration `@Timeout`/`@Fallback`/`@CircuitBreaker` chain (30s timeout)
engaging rather than the call failing outright. This did **not** prevent AIP from correctly
recording `rest-fights -> rest-narration` as `CALLS`/`CONFIRMED`/`declared=true,observed=true` —
the architectural interaction (an HTTP call was made and observed) is independent of whether
`rest-narration`'s own business logic produced a real vs. fallback narration. See `findings.md`
for why this stays a non-material observation rather than a finding.

## Exit code

```text
0  (no release-blocking / CRITICAL-severity finding)
```

## Known limitation of this run

This single run was not independently re-executed from clean state a second time in this session
to verify literal run-to-run repeatability (I2 spec §43). The comparator's own determinism (fixed
sort key, `real_world_validation.comparator`) is unit- and integration-tested independently of this
run, and the captured `actual.yaml` reproduces the identical comparator output on repeated
invocation — but a full second live build-and-run was not performed here. Recommended before
`v0.3.0-alpha.2` is finalized (I2.4, if needed, or as part of I5 release qualification).
