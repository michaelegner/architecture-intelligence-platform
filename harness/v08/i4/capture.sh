#!/usr/bin/env bash
# v0.8 I4 §5, §10: the operator's recordings. Every command goes through record/check (raw/ with
# .meta and .err), as in I3.
#   capture.sh b-r | a-r | a-k     a consumer-state capture with G before and G' after it
#   capture.sh helm before|after   the Catalog and Image deployments and their ConfigMaps (K7)
#   capture.sh mm2-config          the MirrorMaker 2 properties of every running MM2 container, and
#                                  config_checks.py static on them (§5)
#   capture.sh p1b                 P1b per applied pair: both topic listings, config_checks.py p1b
#   capture.sh images before|after the host's image inventory (audit.py IMAGE_ADDED)
#   capture.sh ground-truth        replication per applied pair, lag per consumer, the hand-off reads,
#                                  and ground_truth.py (needs package/agent-reported-handoff.json)
source "$(dirname "$0")/lib.sh"
WHAT="${1:?b-r, a-r, a-k, helm, mm2-config or ground-truth}"

capture() {  # capture NAME NN BROKER_ID HOST_BOOTSTRAP GROUP...
  local name="$1" nn="$2" broker_id="$3" bootstrap="$4"
  shift 4
  local groups=("$@") group args=() out="$PACKAGE/captures/$name"
  ground_truth() {
    for group in "${groups[@]}"; do
      if [[ "$broker_id" == kafka:sokol111-local ]]; then
        record "$nn" "$1-$group" -- rpk group describe "$group"
      else
        record "$nn" "$1-$group" -- ktool "$KAFKA" kafka-consumer-groups.sh --describe --group "$group"
        record "$nn" "$1-$group-state" -- ktool "$KAFKA" kafka-consumer-groups.sh --describe --state \
          --group "$group"
      fi
    done
  }
  mkdir -p "$out"
  for group in "${groups[@]}"; do args+=(--group "$group"); done
  ground_truth g
  if [[ "$name" == a-r ]]; then
    cat "$RAW/AR-g-ecommerce-catalog-service.txt" "$RAW/AR-g-ecommerce-image-service.txt" >"$RAW/AR-g-moved.txt"
    check AR moved-state --deadline "$GROUP_STATE_DEADLINE_SECONDS" -- state --describe "$RAW/AR-g-moved.txt" \
      --format rpk --group ecommerce-catalog-service --group ecommerce-image-service --allow Empty --allow Dead
  fi
  record "$nn" capture -- env KAFKA_BOOTSTRAP_SERVERS="$bootstrap" PYTHONPATH="$REPO" \
    uv run --project "$REPO" --with confluent-kafka==2.16.0 python "$REPO/harness/kafka-capture/capture.py" \
    --broker-id "$broker_id" --environment local "${args[@]}" --out "$out/kafka-consumer-state.json"
  ground_truth g-prime
}

helm_state() {  # helm_state before|after
  local phase="$1" dir="$PACKAGE/helm/$1" deployment name
  mkdir -p "$dir"
  for deployment in "${MOVED_GROUPS[@]}"; do
    record "HELM-$phase" "$deployment" -- kubectl -n dev get deployment "$deployment" -o json
    cp "$RAW/HELM-$phase-$deployment.txt" "$dir/$deployment.deployment.json"
    for name in $(python3 -c 'import json, sys; sys.path.insert(0, sys.argv[2]); import helm_checks
print("\n".join(helm_checks.configmap_refs(json.load(open(sys.argv[1])))))' \
      "$dir/$deployment.deployment.json" "$I4_DIR"); do
      record "HELM-$phase" "configmap-$name" -- kubectl -n dev get configmap "$name" -o json
      cp "$RAW/HELM-$phase-configmap-$name.txt" "$dir/configmap-$name.json"
    done
  done
  if [[ "$phase" == after ]]; then
    python3 "$I4_DIR/helm_checks.py" "$PACKAGE/helm" --out "$PACKAGE/applied-helm.json" || true
  fi
}

mm2_config() {
  # Every running container's processes (docker top), so a flow started as a container's command and
  # one started with `docker exec` (the task card's kafka image includes MirrorMaker 2) are both found.
  local dir="$PACKAGE/applied-mm2" id file n=0 files=()
  mkdir -p "$dir"
  record MM2 containers -- docker ps --no-trunc --format '{{.ID}} {{.Names}}'
  while read -r id _; do
    record MM2 "$id-top" -- docker top "$id" -eo pid,args
    while read -r file; do
      [[ -n "$file" ]] || continue  # a container without MirrorMaker 2 prints one empty line
      n=$((n + 1))
      record MM2 "$id-properties-$n" -- docker cp "$id:$file" -
      tar -xOf "$RAW/MM2-$id-properties-$n.txt" >"$dir/$id-$n.properties"
      files+=("$dir/$id-$n.properties")
    done < <(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import config_checks
print("\n".join(config_checks.mm2_properties(open(sys.argv[2]).read())))' "$I4_DIR" "$RAW/MM2-$id-top.txt")
  done <"$RAW/MM2-containers.txt"
  [[ ${#files[@]} -gt 0 ]] || stop "no running MirrorMaker 2 process"
  python3 "$I4_DIR/config_checks.py" --out "$PACKAGE/applied-mm2.json" static "${files[@]}" || true
}

ground_truth_reads() {
  local applied="$PACKAGE/applied-mm2.json" pair
  [[ -f "$applied" ]] || stop "run capture.sh mm2-config first"
  [[ -f "$PACKAGE/agent-reported-handoff.json" ]] || stop "transcribe the agent-reported (c) first (README, S4)"
  # Replication per applied pair (source side), with the pair's own offsets topic. The pairs come in
  # on fd 3: `docker compose exec` forwards stdin and would read the rest of the list (I4b S4).
  while IFS=$'\t' read -r -u 3 pair source target offsets topics; do
    local src_boot tgt_boot fmt
    [[ "$source" == redpanda ]] && { src_boot="$REDPANDA" tgt_boot="$KAFKA" fmt=rpk; } ||
      { src_boot="$KAFKA" tgt_boot="$REDPANDA" fmt=kafka; }
    record GT "$pair-offsets" -- dump_topic "$tgt_boot" "$offsets"
    if [[ "$fmt" == rpk ]]; then
      # shellcheck disable=SC2086
      record GT "$pair-source-end" -- rpk_end $topics
    else
      record GT "$pair-source-end" -- ktool "$KAFKA" kafka-get-offsets.sh --topic-partitions \
        "$(tr ' ' '|' <<<"$topics" | sed 's/\./\\./g')"
    fi
    local topic_args=() topic
    for topic in $topics; do topic_args+=(--topic "$topic"); done
    verdict GT "$pair-replication" -- replication --offsets "$RAW/GT-$pair-offsets.txt" \
      --source-end "$RAW/GT-$pair-source-end.txt" --format "$fmt" "${topic_args[@]}"
  done 3< <(python3 -c 'import json, sys
for p in json.load(open(sys.argv[1]))["pairs"]:
    print("\t".join([p["pair"], p["source"], p["target"], p["offsets"], " ".join(p["topics"])]))' "$applied")
  # Lag: the remaining Redpanda consumers on the catalog topics; the moved groups on Kafka.
  local group
  for group in ecommerce-product-query-service ecommerce-category-query-service; do
    record GT "$group-describe" -- rpk group describe "$group"
    verdict GT "$group-lag" -- lag --describe "$RAW/GT-$group-describe.txt" --format rpk --group "$group" \
      $( [[ $group == *product* ]] && echo "--topic catalog.product.events" || echo "--topic catalog.category.events") \
      --topic catalog.attribute.events
  done
  for group in "${MOVED_GROUPS[@]}"; do
    record GT "$group-kafka-describe" -- ktool "$KAFKA" kafka-consumer-groups.sh --describe --group "$group"
    verdict GT "$group-kafka-lag" -- lag --describe "$RAW/GT-$group-kafka-describe.txt" --format kafka \
      --group "$group" --topic "$TENANT_TOPIC" $([[ $group == *image* ]] && echo "--topic catalog.product.events")
  done
  # The hand-off reads (a), checkpoint history, offset syncs and the Kafka positions now.
  local flow_a checkpoints syncs syncs_on
  read -r flow_a checkpoints syncs syncs_on < <(python3 -c 'import json, sys
for p in json.load(open(sys.argv[1]))["pairs"]:
    if (p["source"], p["target"]) == ("redpanda", "kafka"):
        print(p["pair"], p["checkpoints"], p["offset_syncs"], p["offset_syncs_on"]); break' "$applied")
  [[ -n "${flow_a:-}" ]] || stop "no applied Redpanda -> Kafka pair"
  record GT handoff-source-groups -- rpk group describe "${MOVED_GROUPS[@]}"
  record GT handoff-checkpoints -- dump_topic "$KAFKA" "$checkpoints" CheckpointFormatter
  record GT handoff-target-groups -- ktool "$KAFKA" kafka-consumer-groups.sh --describe \
    --group ecommerce-catalog-service --group ecommerce-image-service
  record GT handoff-offset-syncs -- dump_topic "$([[ $syncs_on == source ]] && echo "$REDPANDA" || echo "$KAFKA")" \
    "$syncs" OffsetSyncFormatter
  python3 "$I4_DIR/ground_truth.py" --agent-reported "$PACKAGE/agent-reported-handoff.json" \
    --source-groups "$RAW/GT-handoff-source-groups.txt" --checkpoints "$RAW/GT-handoff-checkpoints.txt" \
    --target-groups "$RAW/GT-handoff-target-groups.txt" --offset-syncs "$RAW/GT-handoff-offset-syncs.txt" \
    --out "$PACKAGE/handoff-after.json" || true
}

# P1b for every applied pair (owner review of the I4b plan): both brokers' topic listings once, then
# config_checks.py p1b per pair into p1b-<source>-to-<target>.json.
p1b_reads() {
  local applied="$PACKAGE/applied-mm2.json" pair
  [[ -f "$applied" ]] || stop "run capture.sh mm2-config first"
  record P1B kafka-topics -- ktool "$KAFKA" kafka-topics.sh --describe
  record P1B redpanda-topics -- rpk topic list
  while read -r pair; do
    python3 "$I4_DIR/config_checks.py" --out "$PACKAGE/p1b-${pair/->/-to-}.json" p1b --static "$applied" \
      --pair "$pair" "$RAW/P1B-kafka-topics.txt" "$RAW/P1B-redpanda-topics.txt" || true
  done < <(python3 -c 'import json, sys
print("\n".join(p["pair"] for p in json.load(open(sys.argv[1]))["pairs"]))' "$applied")
}

case "$WHAT" in
  b-r) capture b-r BR kafka:sokol111-local localhost:9092 "${REDPANDA_GROUPS[@]}" ;;
  a-r) capture a-r AR kafka:sokol111-local localhost:9092 "${REDPANDA_GROUPS[@]}" ;;
  a-k) capture a-k AK kafka:sokol111-kafka localhost:19092 "${MOVED_GROUPS[@]}" ;;
  helm) helm_state "${2:?before or after}" ;;
  images)
    mkdir -p "$PACKAGE/images"
    record "IMAGES" "${2:?before or after}" -- docker image ls -a --no-trunc --format '{{.ID}} {{.Repository}}:{{.Tag}}'
    cp "$RAW/IMAGES-$2.txt" "$PACKAGE/images/$2.txt"
    ;;
  mm2-config) mm2_config ;;
  p1b) p1b_reads ;;
  ground-truth) ground_truth_reads ;;
  *) stop "unknown: $WHAT" ;;
esac
echo "capture.sh $WHAT done"
