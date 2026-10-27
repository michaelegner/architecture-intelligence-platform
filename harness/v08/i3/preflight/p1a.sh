#!/usr/bin/env bash
# P1a + P2 (I3 spec §4): before any flow starts, each property file sets the §3 worker state,
# replication factor 1 (mirrored data topics included), the identity policy, the flags and short
# explicit intervals.
source "$(dirname "$0")/../lib.sh"
check P1a p1a -- p1a "$ENV_DIR/mm2-flow-a.properties" "$ENV_DIR/mm2-flow-b.properties" \
  "$ENV_DIR/mm2-probe.properties"
