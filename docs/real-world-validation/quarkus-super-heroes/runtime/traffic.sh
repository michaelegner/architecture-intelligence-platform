#!/usr/bin/env bash
# Deterministic traffic script for the Quarkus Super Heroes I2 validation profile (I2 spec §19).
#
# Exercises, in order: hero+villain retrieval (both triggered by one rest-fights call), the
# grpc-locations dependency, a fight (persists + publishes to Kafka topic "fights", picked up by
# event-statistics), and a narration request. Request bodies are the pinned upstream OpenAPI's own
# documented examples (rest-fights/src/main/resources/openapi/openapi.yml @
# 8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce) - not invented payloads.
#
# Calls only the upstream system's own endpoints - never an AIP-specific endpoint (I2 spec §19).
# Run this between the runbook's "start observation window" and "end observation window" steps.

set -euo pipefail

FIGHTS_URL="${FIGHTS_URL:-http://localhost:8082}"

echo "==> GET /api/fights/randomfighters (triggers rest-heroes + rest-villains calls)"
curl -sS -f "${FIGHTS_URL}/api/fights/randomfighters" | tee /dev/stderr
echo

echo "==> GET /api/fights/randomlocation (triggers grpc-locations - UNSUPPORTED boundary)"
curl -sS -f "${FIGHTS_URL}/api/fights/randomlocation" | tee /dev/stderr
echo

echo "==> POST /api/fights (persists the fight, publishes to Kafka topic \"fights\")"
curl -sS -f -X POST "${FIGHTS_URL}/api/fights" \
  -H 'Content-Type: application/json' \
  -d '{
    "hero": {
      "name": "Luke Skywalker",
      "level": 10,
      "powers": "Uses light sabre, The force",
      "picture": "https://raw.githubusercontent.com/quarkusio/quarkus-super-heroes/characterdata/images/luke-skywalker-2563509063968639219.jpg"
    },
    "villain": {
      "name": "Darth Vader",
      "level": 3,
      "powers": "Uses light sabre, dark side of the force",
      "picture": "https://raw.githubusercontent.com/quarkusio/quarkus-super-heroes/characterdata/images/anakin-skywalker--8429855148488965479.jpg"
    },
    "location": {
      "name": "Gotham City",
      "description": "An American city rife with corruption and crime, the home of its iconic protector Batman.",
      "picture": "https://raw.githubusercontent.com/quarkusio/quarkus-super-heroes/characterdata/images/locations/gotham_city.jpg"
    }
  }' | tee /dev/stderr
echo

echo "==> POST /api/fights/narrate (triggers rest-narration call)"
curl -sS -f -X POST "${FIGHTS_URL}/api/fights/narrate" \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "653bea9d188984908cd12429",
    "fightDate": "2075-10-27T16:51:41.787Z",
    "winnerName": "Luke Skywalker",
    "winnerLevel": 10,
    "winnerPowers": "Uses light sabre, The force",
    "winnerPicture": "https://raw.githubusercontent.com/quarkusio/quarkus-super-heroes/characterdata/images/luke-skywalker-2563509063968639219.jpg",
    "winnerTeam": "Heroes",
    "loserName": "Darth Vader",
    "loserLevel": 3,
    "loserPowers": "Uses light sabre, dark side of the force",
    "loserPicture": "https://raw.githubusercontent.com/quarkusio/quarkus-super-heroes/characterdata/images/anakin-skywalker--8429855148488965479.jpg",
    "loserTeam": "Villains",
    "location": {
      "name": "Gotham City",
      "description": "An American city rife with corruption and crime, the home of its iconic protector Batman.",
      "picture": "https://raw.githubusercontent.com/quarkusio/quarkus-super-heroes/characterdata/images/locations/gotham_city.jpg"
    }
  }' | tee /dev/stderr
echo

echo "==> traffic complete"
