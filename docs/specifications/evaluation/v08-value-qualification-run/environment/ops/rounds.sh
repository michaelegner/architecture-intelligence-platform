#!/usr/bin/env bash
# Rounds 2 and 3 (T-, T+, F-, F+ each). Stops at the first failed preflight or error turn.
set -euo pipefail
source "<run home>/package/ops/env.sh"
source <operator tmp>/-<home>-code-ArchitectureIntelligencePlatform/c4caff3d-3b9e-4824-90b7-b9bb9398c339/scratchpad/aip-neo4j.env
O=$VQ_RUN_HOME/package/ops; L=$O/sessions.log
printf '%s\trounds 2-3 start (harness %s)\n' "$(date -u +%FT%TZ)" "$(git -C $AIPW rev-parse --short HEAD)" | tee -a $L
for round in 2 3; do
  for step in "down T-" "up T+" "down F-" "up F+"; do
    set -- $step
    $VQ/vq_aip.sh $VQ_RUN_HOME $1 | tail -1 | tee -a $L
    $O/run_session.sh $2 $round
  done
done
printf '%s\trounds 2-3 end\n' "$(date -u +%FT%TZ)" | tee -a $L
