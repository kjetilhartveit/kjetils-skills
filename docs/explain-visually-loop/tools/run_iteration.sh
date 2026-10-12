#!/usr/bin/env bash
# Runs the benchmark runs of one iteration one after another (in parallel they ran the machine out of memory).
# Usage: run_iteration.sh <iteration> [model] [runs]
ITER="$1"; MODEL="${2:-sonnet}"; RUNS="${3:-2}"; DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /c/git/evloop-runs
for r in $(seq 1 "$RUNS"); do
  bash "$DIR/run_explainer.sh" "$ITER" "$r" "$MODEL" >"/c/git/evloop-runs/iter$ITER-run$r.log" 2>&1
  tail -1 "/c/git/evloop-runs/iter$ITER-run$r.log"
done
