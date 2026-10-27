#!/usr/bin/env bash
# Step 7: start flow B (the catalog topics, Kafka -> Redpanda). The producers are stopped and the
# Redpanda history is drained, so no catalog record is duplicated.
source "$(dirname "$0")/../lib.sh"
require "the offset hand-off passed (step 6)" -- passed 06-handoff
require "flow B is stopped" -- not_running mm2-flow-b
record 07 flow-b-up -- frozen_compose --profile mm2-flow-b up -d mm2-flow-b
p1b 07 mm2-flow-b redpanda
echo "step 7 done"
