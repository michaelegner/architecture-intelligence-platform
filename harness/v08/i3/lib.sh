#!/usr/bin/env bash
# v0.8 I3 (spec §5): shared helpers for the preflight and the runbook steps. Every script sources this
# file. Nothing here starts, stops or changes anything by itself.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
I3_DIR="$REPO/harness/v08/i3"
ENV_DIR="$REPO/docs/specifications/0.8.0/i3-evidence/environment"
RAW="${I3_RAW_DIR:?set I3_RAW_DIR to the raw/ directory of the run}"
mkdir -p "$RAW"

# MirrorMaker 2 cadence in seconds: equal to the committed property files (unit-tested). Every wait
# for replication, a checkpoint or an installed group offset uses this deadline, which is recorded
# with the wait: 3 x sync.group.offsets.interval.seconds + refresh.groups.interval.seconds.
MM2_INTERVAL_SECONDS=10
MM2_DEADLINE_SECONDS=$((3 * MM2_INTERVAL_SECONDS + MM2_INTERVAL_SECONDS))
POLL_SECONDS=5
# Waits that do not depend on MirrorMaker 2 have their own recorded deadlines:
# - a group's move to Empty or Dead depends on the consumer leaving (or its session timeout:
#   45 s, the Kafka client default; the upstream config sets none) plus a 30 s margin;
# - a stopped pod is gone after its termination grace period (30 s default) plus a 30 s margin;
# - step 8 waits for two restarted pods to join their groups (the images are already on the node).
GROUP_STATE_DEADLINE_SECONDS=$((45 + 30))
POD_STOP_DEADLINE_SECONDS=$((30 + 30))
APP_START_DEADLINE_SECONDS=120
# P4 waits for the freshly started broker to answer (KRaft start, no image pull: the image is local).
KAFKA_START_DEADLINE_SECONDS=60

# The single entry point for Compose (memory rule: compose run identity).
frozen_compose() {
  docker compose -p aip-v08-i3 --project-directory "$ENV_DIR" \
    -f "$ENV_DIR/docker-compose.i3.yml" --env-file /dev/null "$@"
}

# Redpanda runs in the Sokol111 stack (container `redpanda`); Kafka tools run inside our `kafka`
# service and can reach either broker by its network name.
rpk() { docker exec redpanda rpk "$@"; }
ktool() {  # ktool BOOTSTRAP TOOL ARGS...
  local bootstrap="$1" tool="$2"
  shift 2
  frozen_compose exec -T kafka "/opt/kafka/bin/$tool" --bootstrap-server "$bootstrap" "$@"
}
REDPANDA=redpanda:29092
KAFKA=kafka:29092

# record NN NAME -- COMMAND...: stdout to raw/NN-NAME.txt, stderr to .err (kept only when not
# empty), UTC + command + exit code to .meta. Returns the command's exit code.
record() {
  local nn="$1" name="$2"
  shift 3
  local base="$RAW/$nn-$name" rc=0
  "$@" >"$base.txt" 2>"$base.err" || rc=$?
  printf 'utc: %s\ncommand: %s\nexit: %d\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" "$rc" >"$base.meta"
  [[ -s "$base.err" ]] || rm -f "$base.err"
  return "$rc"
}

stop() {
  echo "STOP: $*" >&2
  exit 2
}

# require WHAT -- COMMAND...: a precondition; the step stops before acting when it fails.
require() {
  local what="$1"
  shift 2
  "$@" || stop "precondition failed: $what"
}

# check NN NAME [--collect FUNCTION] [--deadline SECONDS] -- CHECKER-ARGS...: run one checker rule
# within a deadline (default MM2_DEADLINE_SECONDS). FUNCTION, when given, records fresh raw/ input
# before each attempt. Exit 0 = PASSED, 3 = PENDING (polled again until the deadline), anything else
# = FAILED. The verdict file is raw/NN-NAME.check.json; the deadline is recorded in the verdict.
check() {
  local nn="$1" name="$2" collect="" deadline="$MM2_DEADLINE_SECONDS"
  shift 2
  while [[ "$1" != -- ]]; do
    case "$1" in
      --collect) collect="$2" ;;
      --deadline) deadline="$2" ;;
      *) stop "check: unknown option $1" ;;
    esac
    shift 2
  done
  shift
  local start=$SECONDS rc
  while true; do
    rc=0
    if [[ -n "$collect" ]]; then "$collect" || stop "check $nn-$name: collecting the input failed"; fi
    python3 "$I3_DIR/checker.py" "$@" --elapsed "$((SECONDS - start))" \
      --deadline "$deadline" --out "$RAW/$nn-$name.check.json" || rc=$?
    case "$rc" in
      0) return 0 ;;
      3) sleep "$POLL_SECONDS" ;;
      *) stop "check $nn-$name failed (see $RAW/$nn-$name.check.json)" ;;
    esac
  done
}

scale() {  # scale DEPLOYMENT REPLICAS
  kubectl -n dev scale "deployment/$1" --replicas="$2"
}
# stopped NN DEPLOYMENT: wait until no pod of the deployment exists (terminating pods included), so
# a stopped service can no longer produce or consume. Records the last pod listing.
stopped() {
  local nn="$1" deployment="$2" start=$SECONDS
  until record "$nn" "$deployment-pods" -- kubectl -n dev get pods \
    -l "app.kubernetes.io/name=$deployment" -o name && [[ ! -s "$RAW/$nn-$deployment-pods.txt" ]]; do
    (( SECONDS - start < POD_STOP_DEADLINE_SECONDS )) ||
      stop "$deployment still has pods after $POD_STOP_DEADLINE_SECONDS s"
    sleep "$POLL_SECONDS"
  done
}

# The dump helpers below print broker-tool output in the formats checker.py reads.
rpk_end() {  # rpk_end TOPIC...: per-partition high watermarks of Redpanda topics
  local topic
  for topic in "$@"; do
    echo "# topic: $topic"
    rpk topic describe -p "$topic"
  done
}
dump_topic() {  # dump_topic BOOTSTRAP TOPIC [FORMATTER]: every record, keys tab-separated
  local bootstrap="$1" topic="$2" formatter="${3:-}"
  local args=(--topic "$topic" --from-beginning --timeout-ms 10000
    --property print.key=true --property "key.separator=$(printf '\t')")
  [[ -n "$formatter" ]] && args+=(--formatter "org.apache.kafka.connect.mirror.formatters.$formatter")
  ktool "$bootstrap" kafka-console-consumer.sh "${args[@]}" || true
}
passed() {  # passed NN-NAME: an earlier verdict file exists and PASSED
  python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["result"] == "PASSED" else 1)' \
    "$RAW/$1.check.json"
}
recorded_ok() {  # recorded_ok NN-NAME: an earlier recorded command exited 0
  grep -qx 'exit: 0' "$RAW/$1.meta"
}
# listed KIND NAME: 0 = NAME is listed, 1 = it is not, 2 = the listing itself failed. A failed
# listing is never read as absence: `absent` and `present` succeed only on a confirmed answer, so a
# broker or Compose error stops a precondition and never permits a deletion.
# KIND: redpanda-topic, kafka-topic, redpanda-group, kafka-group; container (any state) or running
# for a Compose service of this project.
listed() {
  local kind="$1" name="$2" out
  case "$kind" in
    redpanda-topic) out="$(rpk topic list)" || return 2; out="$(awk 'NR > 1 {print $1}' <<<"$out")" ;;
    kafka-topic) out="$(ktool "$KAFKA" kafka-topics.sh --list)" || return 2 ;;
    redpanda-group) out="$(rpk group list)" || return 2; out="$(awk 'NR > 1 {print $2}' <<<"$out")" ;;
    kafka-group) out="$(ktool "$KAFKA" kafka-consumer-groups.sh --list)" || return 2 ;;
    container) out="$(frozen_compose ps -a -q "$name")" || return 2; [[ -n "$out" ]]; return ;;
    running) out="$(frozen_compose ps -q --status running "$name")" || return 2; [[ -n "$out" ]]; return ;;
    *) stop "listed: unknown kind $kind" ;;
  esac
  grep -qxF -- "$name" <<<"$out"
}
absent() {  # absent KIND NAME: confirmed not listed
  local rc=0
  listed "$@" || rc=$?
  [[ $rc -eq 1 ]]
}
present() {  # present KIND NAME: confirmed listed
  local rc=0
  listed "$@" || rc=$?
  [[ $rc -eq 0 ]]
}
not_running() { absent running "$1"; }  # not_running SERVICE: confirmed no running container
# P1b: after a flow's first start, every internal topic of the flow exists with RF 1.
p1b() {  # p1b NN FLOW TARGET-KIND
  local nn="$1" flow="$2" target_kind="$3"
  local target="$RAW/$nn-$flow-kafka-topics.txt" source="$RAW/$nn-$flow-redpanda-topics.txt"
  [[ "$target_kind" == redpanda ]] && { target="$RAW/$nn-$flow-redpanda-topics.txt"; source="$RAW/$nn-$flow-kafka-topics.txt"; }
  _p1b_listings() {
    record "$nn" "$flow-kafka-topics" -- ktool "$KAFKA" kafka-topics.sh --describe &&
      record "$nn" "$flow-redpanda-topics" -- rpk topic list
  }
  check "$nn" "$flow-p1b" --collect _p1b_listings -- p1b --flow "$flow" --target-listing "$target" \
    --source-listing "$source" --target-kind "$target_kind"
}
# Tilt is stopped: no process is named `tilt`. Matching the process name, not the command line,
# keeps a shell that only carries the text "tilt up" (this check's own, for one) from matching.
tilt_stopped() { ! pgrep -x tilt >/dev/null; }
