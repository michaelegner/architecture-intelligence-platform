#!/usr/bin/env bash
# P3 (I3 spec §4): the flow A and flow B topic allow-lists are disjoint (no loops, parent §4.1).
source "$(dirname "$0")/../lib.sh"
check P3 p3 -- p3 "$ENV_DIR/mm2-flow-a.properties" "$ENV_DIR/mm2-flow-b.properties"
