#!/usr/bin/env bash
# Operator: one value-qualification session (harness README "Run", step 2).
#   run_session.sh TYPE ROUND
# AIP must already be up (+) or removed (-). Needs env.sh sourced.
set -euo pipefail
TYPE="${1:?type}"; ROUND="${2:?round}"
RH="$VQ_RUN_HOME"; PY="$AIPW/.venv/bin/python"
CLAUDE=<home>/.local/bin/claude
MODEL=claude-opus-5-5
FIRST='Read TASK.md. Plan the move as TASK.md describes. Write plan.json, plan.md and answers.json in the workspace, then stop.'
LOG="$RH/package/ops/sessions.log"
log() { printf '%s\t%s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG"; }

out="$("$VQ/vq_setup_session.sh" "$RH" "$TYPE" "$ROUND")"; echo "$out"
SESSION="$(sed -n 's/^session \([^ ]*\) ready.*/\1/p' <<<"$out")"
SD="$RH/sessions/$SESSION"
log "$SESSION setup"
"$PY" "$VQ/vq_preflight.py" "$RH" "$SESSION" || { log "$SESSION preflight FAILED"; exit 2; }
log "$SESSION preflight clean"

launch() {  # launch N ARGS...: one claude -p call, stream to stream-N.jsonl
  local n="$1"; shift
  (cd "$SD/workspace" && env -i "HOME=$HOME" "PATH=$RH/bin:/usr/local/bin:/usr/bin:/bin" \
    "KUBECONFIG=$RH/kube/config" CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 "CLAUDE_CONFIG_DIR=$SD/claude" \
    "$CLAUDE" -p "$@" --model "$MODEL" --output-format stream-json --verbose) >"$SD/stream-$n.jsonl" 2>"$SD/stream-$n.err" || true
  [[ -s "$SD/stream-$n.err" ]] || rm -f "$SD/stream-$n.err"
}
result() {  # result N FIELD
  "$PY" -c 'import json,sys
r=[json.loads(l) for l in open(sys.argv[1]) if l.strip().startswith("{")]
r=[x for x in r if x.get("type")=="result"]
v=r[-1].get(sys.argv[2], "") if r else ""
print(v if isinstance(v,str) else json.dumps(v))' "$SD/stream-$1.jsonl" "$2"
}

log "$SESSION turn 1 start"
launch 1 "$FIRST"
ID="$(result 1 session_id)"; log "$SESSION turn 1 end (session $ID, is_error $(result 1 is_error))"
[[ "$(result 1 is_error)" == false ]] || { log "$SESSION turn 1 error: stop"; exit 3; }
n=1
while [[ "$TYPE" == T* ]] && grep -q 'OPERATOR: please answer requests.json' <<<"$(result $n result)"; do
  [[ $n -lt 12 ]] || { log "$SESSION turn cap reached"; break; }
  "$PY" "$VQ/vq_requests.py" answer "$RH" "$SESSION" | tee -a "$LOG"
  reply="$(ls -t "$SD/replies"/*.txt | head -1)"
  n=$((n + 1)); log "$SESSION turn $n start (reply $(basename "$reply"))"
  launch "$n" --resume "$ID" "$(cat "$reply")"
  log "$SESSION turn $n end (is_error $(result $n is_error))"
  [[ "$(result $n is_error)" == false ]] || { log "$SESSION turn $n error: stop"; exit 3; }
done

mkdir -p "$SD/transcripts" && cp -a "$SD/claude/projects/." "$SD/transcripts/"
mapfile -t T < <(find "$SD/transcripts" -name '*.jsonl' | sort)
"$PY" "$VQ/vq_audit.py" "$RH" "$SESSION" "${T[@]}" | tee -a "$LOG" || true
"$PY" "$VQ/vq_score.py" "$RH" "$SESSION" "${T[@]}" | tail -3 | tee -a "$LOG" || true
ls -la "$SD/workspace" | tee -a "$LOG"
log "$SESSION done"
