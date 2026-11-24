#!/usr/bin/env bash
# Phase 1 pilot (TODO P1-09): measure real flow cost per design and run-to-run noise.
# Runs sequentially (concurrency 1) so runtime labels are not distorted by contention.
# Resumable: runs already recorded as success are skipped.
set -euo pipefail

SI="${SI:-siliconai}"
TIMEOUT="${TIMEOUT:-3600}"

# 1) Cost per design: one run each at default config.
for cfg in \
  ./designs/nangate45/gcd/config.mk \
  ./designs/nangate45/aes/config.mk \
  ./designs/nangate45/ibex/config.mk \
  ./designs/nangate45/jpeg/config.mk \
  ./designs/sky130hd/gcd/config.mk \
  ./designs/sky130hd/aes/config.mk; do
  "$SI" orfs-run --design-config "$cfg" --timeout "$TIMEOUT" || echo "FAILED: $cfg"
done

# 2) Noise floor: 3 repeats of the same config (repeat 0 already exists from step 1).
for cfg in ./designs/nangate45/gcd/config.mk ./designs/nangate45/aes/config.mk; do
  "$SI" orfs-run --design-config "$cfg" --repeat 2 --repeat-start 1 --timeout "$TIMEOUT" \
    || echo "FAILED: $cfg repeats"
done

# 3) Config sensitivity: a small utilization sweep on aes, 3 repeats each.
for util in 30 50; do
  "$SI" orfs-run --design-config ./designs/nangate45/aes/config.mk \
    --set "CORE_UTILIZATION=$util" --repeat 3 --timeout "$TIMEOUT" \
    || echo "FAILED: aes util=$util"
done
