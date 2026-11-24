#!/usr/bin/env bash
# One D1 collection chunk: run the sweep for BUDGET_MIN minutes, then snapshot the registry
# and this chunk's ORFS logs into data/ so they survive the ephemeral container.
#
# Usage: SILICONAI_HOME=workspace/d1 scripts/run_chunk.sh <spec.yaml> <budget-min> <chunk-name>
# Prerequisite: a running Docker daemon started shortly before (this container stops any
# background job, dockerd included, after 2 h).
set -euo pipefail
SPEC=${1:?spec}; BUDGET=${2:?budget minutes}; CHUNK=${3:?chunk name}
[[ "$CHUNK" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "bad chunk name"; exit 2; }
OUT=data/d1
docker info --format '{{.ServerVersion}}' >/dev/null
STAMP=$(mktemp)
siliconai sweep "$SPEC" --budget-min "$BUDGET" || echo "sweep exited non-zero (see above)"
siliconai export --out "$OUT/registry"
mkdir -p "$OUT/logs"
# ORFS step logs written during this chunk (text only; results/objects are pruned)
( cd "$SILICONAI_HOME/runs" && find logs -type f -newer "$STAMP" -name '*.log' -print0 \
    | tar --null -czf "$OLDPWD/$OUT/logs/$CHUNK.tar.gz" --files-from=- )
rm -f "$STAMP"
ls -la "$OUT/logs/$CHUNK.tar.gz"
