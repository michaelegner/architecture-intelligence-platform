#!/usr/bin/env bash
# v0.8 value qualification (spec §4, §6.2): prepares one planning session.
#   vq_setup_session.sh RUN_HOME TYPE ROUND     TYPE is F+, F-, T+ or T-; ROUND is 1, 2 or 3
# Creates RUN_HOME/sessions/<TYPE>_r<ROUND>/ with a new workspace and a new, empty config dir. The
# workspace gets the clones of the setting from RUN_HOME/src (all 16 in F, the team repositories in
# T), the card variant as TASK.md, its schemas, and `.mcp.json` only in `+`. The settings come from the
# frozen template of the type (vq_settings.py), with every withheld location denied.
set -euo pipefail

VQ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
I4_DIR="$(cd "$VQ_DIR/../i4" && pwd)"
REPO="$(cd "$VQ_DIR/../../.." && pwd)"
EVIDENCE="$REPO/docs/specifications/evaluation/v08-value-qualification-evidence"
RUN_HOME="${1:?RUN_HOME}"
TYPE="${2:?F+, F-, T+ or T-}"
ROUND="${3:?round 1, 2 or 3}"
stop() { echo "STOP: $*" >&2; exit 2; }

case "$TYPE" in F+|F-|T+|T-) ;; *) stop "unknown type $TYPE" ;; esac
[[ "$ROUND" =~ ^[1-9]$ ]] || stop "round must be a digit"
[[ -d "$RUN_HOME" ]] || stop "$RUN_HOME does not exist"
RUN_HOME="$(cd "$RUN_HOME" && pwd -P)"

source "$I4_DIR/withheld.sh"
for tree in "${WITHHELD[@]}"; do
  tree="$(cd "$tree" 2>/dev/null && pwd -P || echo "$tree")"
  case "$RUN_HOME/" in "$tree"/*) stop "$RUN_HOME is inside the AIP worktree $tree" ;; esac
  case "$tree/" in "$RUN_HOME"/*) stop "the AIP worktree $tree is inside $RUN_HOME" ;; esac
done
# The operator state is denied to the session: a run home inside it would deny its own workspace.
for state in "${OPERATOR_STATE[@]}"; do
  case "$RUN_HOME/" in "$state"/*) stop "$RUN_HOME is inside the operator state $state" ;; esac
done

# A replacement session (spec §6.5) takes the next free attempt suffix: T-_r2, T-_r2b, T-_r2c, ...
SESSION="${TYPE}_r${ROUND}"
for suffix in "" b c d e; do
  [[ -e "$RUN_HOME/sessions/${TYPE}_r${ROUND}${suffix}" ]] || { SESSION="${TYPE}_r${ROUND}${suffix}"; break; }
done
SESSION_DIR="$RUN_HOME/sessions/$SESSION"
[[ ! -e "$SESSION_DIR" ]] || stop "$SESSION_DIR already exists"
WORKSPACE="$SESSION_DIR/workspace"
CONFIG="$SESSION_DIR/claude"
[[ -d "$RUN_HOME/src" ]] || stop "$RUN_HOME/src (the Sokol111 clones) is missing"

mapfile -t OTHER_SESSIONS < <(find "$RUN_HOME/sessions" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)
mkdir -p "$WORKSPACE/src" "$CONFIG"

mapfile -t REPOSITORIES < <(python3 - "$EVIDENCE/catalogue/r2-list.json" "$TYPE" "$RUN_HOME/src" <<'EOF'
import json, os, sys
listing, card_type, src = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3]
names = listing["team_scoped"] if card_type.startswith("T") else sorted(os.listdir(src))
print("\n".join(names))
EOF
)
for name in "${REPOSITORIES[@]}"; do
  [[ -d "$RUN_HOME/src/$name/.git" ]] || stop "$RUN_HOME/src/$name is not a clone"
  cp -a "$RUN_HOME/src/$name" "$WORKSPACE/src/$name"
done

CARD="$EVIDENCE/cards/task-card.$TYPE.md"
cp "$CARD" "$WORKSPACE/TASK.md"
SCHEMAS=(plan-schema answers-schema)
[[ "$TYPE" == T* ]] && SCHEMAS+=(requests-schema)
for name in "${SCHEMAS[@]}"; do
  (cd "$VQ_DIR" && python3 -c 'import json, sys, vq_format; print(json.dumps(vq_format.schema(sys.argv[1], sys.argv[2]), indent=2))' "$name" "$CARD") \
    >"$WORKSPACE/${name%-schema}.schema.json"
done
[[ "$TYPE" == *+ ]] && cp "$I4_DIR/agent/mcp.json" "$WORKSPACE/.mcp.json"

if [[ -f "$HOME/.claude/.credentials.json" ]]; then
  install -m 600 "$HOME/.claude/.credentials.json" "$CONFIG/.credentials.json"
fi
python3 - "$VQ_DIR" "$EVIDENCE/settings/settings.$TYPE.json" "$CONFIG/settings.json" "$RUN_HOME" "$WORKSPACE" "$CONFIG" \
  "${#WITHHELD[@]}" "${WITHHELD[@]}" "${#OPERATOR_STATE[@]}" "${OPERATOR_STATE[@]}" "${OTHER_SESSIONS[@]}" <<'EOF'
import json, sys
vq_dir, template, out, run_home, workspace, config, *rest = sys.argv[1:]
sys.path.insert(0, vq_dir)
import vq_settings
n = int(rest[0]); withheld = rest[1 : 1 + n]; rest = rest[1 + n :]
m = int(rest[0]); operator_state = rest[1 : 1 + m]; other_sessions = rest[1 + m :]
settings = vq_settings.render(
    json.load(open(template)), run_home=run_home, workspace=workspace, config=config,
    withheld=withheld, operator_state=operator_state, other_sessions=other_sessions,
)
open(out, "w").write(json.dumps(settings, indent=2) + "\n")
EOF

python3 - "$SESSION_DIR/session.json" "$TYPE" "$ROUND" "$SESSION" "$CARD" "${REPOSITORIES[@]}" <<'EOF'
import datetime, hashlib, json, sys
out, card_type, round_, session, card, *repositories = sys.argv[1:]
record = {
    "session": session, "type": card_type, "round": int(round_),
    "created_utc": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "card_sha256": hashlib.sha256(open(card, "rb").read()).hexdigest(),
    "repositories": repositories,
}
open(out, "w").write(json.dumps(record, indent=2) + "\n")
EOF

echo "session $SESSION ready. Next: $VQ_DIR/vq_preflight.py $RUN_HOME $SESSION"
