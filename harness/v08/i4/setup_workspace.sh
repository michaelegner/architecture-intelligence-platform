#!/usr/bin/env bash
# v0.8 I4 §4.1-4.2, §4.4: prepares one agent session.
#   setup_workspace.sh RUN_HOME planning    new workspace + new config dir claude-planning
#   setup_workspace.sh RUN_HOME execution   the same workspace + new config dir claude-execution
# RUN_HOME must lie outside every worktree of the AIP checkout; it holds the Sokol111 clones in src/.
# Each session gets its own new, empty config dir (no memory, no CLAUDE.md, no plugins). Only the
# login (.credentials.json) is copied from the operator's ~/.claude. The settings go into the config
# dir, where the session's deny rules keep the agent from writing them.
set -euo pipefail

I4_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$I4_DIR/../../.." && pwd)"
RUN_HOME="${1:?RUN_HOME}"
SESSION="${2:?planning or execution}"
stop() { echo "STOP: $*" >&2; exit 2; }

[[ "$SESSION" == planning || "$SESSION" == execution ]] || stop "unknown session $SESSION"
[[ -d "$RUN_HOME" ]] || stop "$RUN_HOME does not exist"
RUN_HOME="$(cd "$RUN_HOME" && pwd -P)"

# Every worktree of the checkout holds the specifications: all of them are withheld, as is the
# operator's own Claude state (withheld.sh).
source "$I4_DIR/withheld.sh"
for tree in "${WITHHELD[@]}"; do
  tree="$(cd "$tree" 2>/dev/null && pwd -P || echo "$tree")"
  case "$RUN_HOME/" in "$tree"/*) stop "$RUN_HOME is inside the AIP worktree $tree" ;; esac
  case "$tree/" in "$RUN_HOME"/*) stop "the AIP worktree $tree is inside $RUN_HOME" ;; esac
done

WORKSPACE="$RUN_HOME/workspace"
CONFIG="$RUN_HOME/claude-$SESSION"
[[ ! -e "$CONFIG" ]] || stop "$CONFIG already exists: every session starts with a new config dir"

if [[ "$SESSION" == planning ]]; then
  [[ -d "$RUN_HOME/src" ]] || stop "$RUN_HOME/src (the Sokol111 clones) is missing"
  [[ ! -e "$WORKSPACE" ]] || stop "$WORKSPACE already exists"
  mkdir -p "$WORKSPACE"
  cp -a "$RUN_HOME/src" "$WORKSPACE/src"
  cp "$REPO/docs/specifications/0.8.0/i4-evidence/task-card.md" "$WORKSPACE/TASK.md"
  cp "$I4_DIR/agent/mcp.json" "$WORKSPACE/.mcp.json"
  (cd "$I4_DIR" && python3 -c 'import json, plan_format; print(json.dumps(plan_format.schema("plan-schema"), indent=2))') \
    >"$WORKSPACE/plan.schema.json"
else
  [[ -f "$WORKSPACE/plan.json" && -f "$WORKSPACE/plan.md" ]] || stop "the frozen plan is missing"
  [[ -f "$RUN_HOME/plan-freeze.txt" ]] || stop "record the plan freeze (README, S2) first"
fi

mkdir -p "$CONFIG"
if [[ -f "$HOME/.claude/.credentials.json" ]]; then
  install -m 600 "$HOME/.claude/.credentials.json" "$CONFIG/.credentials.json"
fi
# The operator's own Claude state holds the plan key's content (session transcripts, memory, plans,
# scratchpads). A directory is denied with everything under it.
DENIED_STATE=()
for path in "${OPERATOR_STATE[@]}"; do
  [[ "$path" == *.json ]] && DENIED_STATE+=("$path") || DENIED_STATE+=("$path/**")
done
python3 - "$I4_DIR/agent/settings.$SESSION.json" "$CONFIG/settings.json" "$RUN_HOME" \
  "${#WITHHELD[@]}" "${WITHHELD[@]}" "${DENIED_STATE[@]}" <<'EOF'
import json, sys
template, out, run_home, count, *rest = sys.argv[1:]
withheld, operator_state = rest[: int(count)], rest[int(count) :]
settings = json.load(open(template))
rules = []
for rule in settings["permissions"]["deny"]:
    if "__AIP_CHECKOUT__" in rule:
        rules += [rule.replace("/__AIP_CHECKOUT__", "/" + tree) for tree in withheld]
    elif "__OPERATOR_STATE__" in rule:
        rules += [rule.replace("/__OPERATOR_STATE__", "/" + path) for path in operator_state]
    else:
        rules.append(rule.replace("/__RUN_HOME__", "/" + run_home))
settings["permissions"]["deny"] = rules
open(out, "w").write(json.dumps(settings, indent=2) + "\n")
EOF

echo "session $SESSION ready:"
echo "  cd $WORKSPACE && CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 CLAUDE_CONFIG_DIR=$CONFIG claude --model <the recorded model id>"
echo "  first message: see TASK.md, section Sessions"
