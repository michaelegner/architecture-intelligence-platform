#!/usr/bin/env bash
# Clean offline replay of a rehearsal recording (v0.6.0 I2.6a; I1 capture runbook §6 and §9).
#
# Three clean AIP states, each from an empty database:
#   off-c1  scoped evidence off, C1 selected: the v1 baseline (E6)
#   on-c1   scoped evidence on,  C1 selected: E1-E3, E6, E7
#   on-c2   scoped evidence on,  C2 selected: E4, E5, E7
# C1 and C2 each carry expectedPriorInventoryRevision: null (a first import), so each is imported
# into its own clean state rather than C2 reimported over C1; no recorded artifact is edited.
#
# Usage: harness/locality-capture/replay/run-replay.sh ARTIFACT_DIR
# ARTIFACT_DIR holds otlp.jsonl, identities.env, c1/, c2/ (rehearse.sh's output).
# IMPORT_ONLY=1 stops after the first import and records the accepted Operation ids (runbook §7).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
ART="$(cd "$1" && pwd)"
# shellcheck disable=SC1091
source "$ART/identities.env"
export NEO4J_PASSWORD="${NEO4J_PASSWORD:-replay-$(date +%s)}"
COMPOSE=(docker compose -p aip-locality-replay -f "$HERE/compose.yaml")

python3 "$HERE/analyze.py" "$ART/otlp.jsonl" "$ART/identities.env" > "$ART/analysis.json"
LINES=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["lines"])' "$ART/analysis.json")

run_state() { # $1=name $2=true|false (scoped evidence) $3=c1|c2
    local name=$1 dir
    dir="$(mktemp -d)"
    sed -e "s/\${CLUSTER_UID}/$CLUSTER_UID/" -e "s/\${SCOPED_ENABLED}/$2/" \
        "$HERE/config.template.yaml" > "$dir/config.yaml"
    cp -r "$HERE/../declarations" "$dir/declarations"
    cp -r "$ART/$3" "$dir/capture"
    chmod -R a+rX "$dir"  # mktemp -d is 0700; AIP's container runs as a non-root user
    export REPLAY_DIR="$dir"
    "${COMPOSE[@]}" down -v >/dev/null 2>&1 || true
    "${COMPOSE[@]}" up -d --build --wait >/dev/null 2>&1
    curl -sf -X POST http://localhost:18000/api/import > "$ART/import-$name.json"
    python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); assert r.get("committed") is True, r' \
        "$ART/import-$name.json"
    if [[ -n "${IMPORT_ONLY:-}" ]]; then
        # Runbook §7: the accepted Operation ids come from the import report, before any
        # evaluation - so expected.md can be authored and committed first.
        "${COMPOSE[@]}" exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" --format plain \
            "MATCH (o:Operation) RETURN o.id AS id ORDER BY id" > "$ART/accepted-operations.txt"
        "${COMPOSE[@]}" down -v >/dev/null 2>&1
        rm -rf "$dir"
        echo "import-only: $ART/import-$name.json, $ART/accepted-operations.txt"
        exit 0
    fi
    (cd "$REPO" && uv run python "$HERE/replay.py" "$ART/otlp.jsonl") > "$ART/replay-$name.json"
    local received
    received=$("${COMPOSE[@]}" logs architecture-intelligence 2>/dev/null \
        | grep -c '"POST /v1/traces HTTP/1.1" 200' || true)
    "${COMPOSE[@]}" exec -T -e PYTHONPATH=/app architecture-intelligence \
        python /app/rehearsal-tools/evaluate.py "$DAY" "$P1_UID" "$P2_UID" > "$ART/state-$name.json"
    printf '{"state": "%s", "lines": %s, "aip_post_200": %s}\n' "$name" "$LINES" "$received" \
        > "$ART/wire-$name.json"
    "${COMPOSE[@]}" down -v >/dev/null 2>&1
    rm -rf "$dir"
    [[ "$received" == "$LINES" ]] || { echo "gate 2: AIP received $received POSTs for $LINES lines"; exit 1; }
    echo "state $name: $LINES lines replayed, AIP accepted $received"
}

run_state off-c1 false c1
run_state on-c1 true c1
run_state on-c2 true c2
