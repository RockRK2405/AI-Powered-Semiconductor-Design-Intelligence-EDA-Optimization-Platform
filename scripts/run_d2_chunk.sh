#!/usr/bin/env bash
# One D2 collection chunk: run the fault-injection plan for BUDGET_MIN minutes, then copy the
# run records and this chunk's logs (step logs + console) into data/d2 so they survive the
# ephemeral container.
#
# Usage: SILICONAI_HOME=workspace/d2 scripts/run_d2_chunk.sh <spec.yaml> <budget-min> <chunk-name>
# Prerequisite: a Docker daemon started shortly before (background jobs are stopped after 2 h).
set -euo pipefail
SPEC=${1:?spec}; BUDGET=${2:?budget minutes}; CHUNK=${3:?chunk name}
[[ "$CHUNK" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "bad chunk name"; exit 2; }
[[ "$BUDGET" =~ ^[0-9]+$ ]] || { echo "bad budget"; exit 2; }
OUT=data/d2
docker info --format '{{.ServerVersion}}' >/dev/null
STAMP=$(mktemp)
python -m siliconai.log_intelligence.corpus "$SPEC" --budget-min "$BUDGET" || echo "collect exited non-zero"
mkdir -p "$OUT/logs"
cp "$SILICONAI_HOME/d2_records.jsonl" "$OUT/records.jsonl"
( cd "$SILICONAI_HOME/runs" && find logs console -type f -newer "$STAMP" -name '*.log' -print0 \
    | tar --null -czf "$OLDPWD/$OUT/logs/$CHUNK.tar.gz" --files-from=- )
rm -f "$STAMP"
ls -la "$OUT/logs/$CHUNK.tar.gz"
