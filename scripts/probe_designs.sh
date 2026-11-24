#!/usr/bin/env bash
# Phase 2 cost probe: one default-config run per candidate design, cheapest-first,
# under a hard deadline (this container limits a background job to 2 h, including dockerd).
# Usage: SILICONAI_HOME=workspace/d1 scripts/probe_designs.sh <deadline-epoch-seconds>
set -u
DEADLINE=${1:?deadline epoch seconds}
MAX_RUN_S=${MAX_RUN_S:-1800}
DESIGNS=(
  asap7/gcd gf180/gcd ihp-sg13g2/gcd ihp-sg13g2/spi asap7/uart
  asap7/aes gf180/aes ihp-sg13g2/aes
  nangate45/dynamic_node nangate45/picorv32
  asap7/ibex gf180/ibex ihp-sg13g2/ibex sky130hd/ibex
  asap7/riscv32i gf180/riscv32i ihp-sg13g2/riscv32i sky130hd/riscv32i
  asap7/jpeg gf180/jpeg ihp-sg13g2/jpeg sky130hd/jpeg
  nangate45/tinyRocket
)
for d in "${DESIGNS[@]}"; do
  remaining=$(( DEADLINE - $(date +%s) - 120 ))
  if (( remaining < 180 )); then echo "DEADLINE: stopping before $d"; break; fi
  t=$(( remaining < MAX_RUN_S ? remaining : MAX_RUN_S ))
  design=${d#*/}
  siliconai orfs-run --design-config "./designs/$d/config.mk" --timeout "$t" \
    --design-group "$design" || echo "NOT SUCCESS: $d (timeout was ${t}s)"
done
