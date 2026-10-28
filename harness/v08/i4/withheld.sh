#!/usr/bin/env bash
# v0.8 I4 §4.2: the withheld locations, derived once for the session settings (setup_workspace.sh)
# and the audit (run_audit.sh). Sourced; sets WITHHELD (every AIP worktree) and OPERATOR_STATE (the
# operator's Claude state: ~/.claude, ~/.claude.json and the per-worktree /tmp/claude-<uid>/ dirs).
I4_DIR="${I4_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
REPO="${REPO:-$(cd "$I4_DIR/../../.." && pwd)}"
mapfile -t WITHHELD < <(git -C "$REPO" worktree list --porcelain | sed -n 's/^worktree //p')
[[ ${#WITHHELD[@]} -gt 0 ]] || { echo "STOP: cannot list the AIP worktrees" >&2; exit 2; }
OPERATOR_STATE=("$HOME/.claude" "$HOME/.claude.json")
for tree in "${WITHHELD[@]}"; do
  OPERATOR_STATE+=("/tmp/claude-$(id -u)/${tree//\//-}")
done
