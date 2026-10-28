#!/usr/bin/env bash
# v0.8 I4 §4.4, S4 step 1: the independence audit over both sessions, with every withheld location
# (every AIP worktree, the operator's Claude state, the run package) and both image inventories.
#   run_audit.sh            run it; exit 0 only when clean
#   run_audit.sh --print    print the audit command line and do not run it
set -euo pipefail
I4_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_HOME="${I4_RUN_HOME:?set I4_RUN_HOME to the run home}"
PACKAGE="$RUN_HOME/package"
source "$I4_DIR/withheld.sh"
args=(--images-before "$PACKAGE/images/before.txt" --images-after "$PACKAGE/images/after.txt")
args+=(--planning)
mapfile -t planning < <(find "$PACKAGE/transcripts/planning" -name '*.jsonl' 2>/dev/null | sort)
args+=("${planning[@]}" --execution)
mapfile -t execution < <(find "$PACKAGE/transcripts/execution" -name '*.jsonl' 2>/dev/null | sort)
args+=("${execution[@]}")
for path in "${WITHHELD[@]}" "${OPERATOR_STATE[@]}" "$PACKAGE"; do args+=(--withheld "$path"); done
args+=(--config-dir "$RUN_HOME/claude-planning" --config-dir "$RUN_HOME/claude-execution")
args+=(--out "$PACKAGE/audit.json" --requests-out "$PACKAGE/agent-requests.json")
if [[ "${1:-}" == --print ]]; then
  printf '%s\n' python3 "$I4_DIR/audit.py" "${args[@]}"
  exit 0
fi
[[ ${#planning[@]} -gt 0 ]] || { echo "STOP: no planning transcript in $PACKAGE/transcripts/planning" >&2; exit 2; }
exec python3 "$I4_DIR/audit.py" "${args[@]}"
