#!/usr/bin/env bash
# Shared configuration for the TB2 generalization experiment.
# Sourced by phase1/2/3/4 scripts. Edit here to change task splits or paths.
#
# Usage pattern:
#   export EXPT=my_run_name        # optional; defaults to a timestamp
#   bash experiment_scripts/phase1_baseline.sh
#   bash experiment_scripts/phase2_evolve.sh
#   bash experiment_scripts/phase3_posteval.sh
#   bash experiment_scripts/phase4_compare.sh
#
# All four phases MUST use the same EXPT env var so they share a folder.

set -euo pipefail

# ── Experiment identity ──────────────────────────────────────────────
: ${EXPT:=tb2_gen_$(date +%Y%m%d_%H%M)}
export EXPT

# ── Paths ────────────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
A_EVOLVE_DIR="${A_EVOLVE_DIR:-/data/shared_data/harness/results/a-evolve}"
RUN_DIR="$A_EVOLVE_DIR/$EXPT"
mkdir -p "$RUN_DIR"

# ── Solver / evolver config (edit to retarget) ───────────────────────
SOLVER_MODEL="${SOLVER_MODEL:-nemotron-super-120b}"
SOLVER_BASE_URL="${SOLVER_BASE_URL:-http://localhost:29413/v1}"
EVOLVER_MODEL="${EVOLVER_MODEL:-claude-code:claude-opus-4-7}"
SEED_WORKSPACE="${SEED_WORKSPACE:-$REPO_ROOT/seed_workspaces/terminus-2}"

# ── Task splits ──────────────────────────────────────────────────────
# Known failures from the prior terminus-2 full run (Nemotron-Super-120B).
# Edit these lists to explore different domains; keep train/test disjoint.
TRAIN_TASKS="${TRAIN_TASKS:-break-filter-js-from-html,regex-chess,fix-code-vulnerability,fix-ocaml-gc,polyglot-c-py,query-optimize,sqlite-db-truncate,password-recovery,gcode-to-text,db-wal-recovery}"
TEST_TASKS="${TEST_TASKS:-filter-js-from-html,polyglot-rust-c,sqlite-with-gcov,crack-7z-hash,sanitize-git-repo}"

# ── Batching ─────────────────────────────────────────────────────────
TRAIN_BATCH_SIZE="${TRAIN_BATCH_SIZE:-5}"    # 10 train tasks / 5 = 2 evo cycles
TEST_BATCH_SIZE="${TEST_BATCH_SIZE:-5}"      # one eval batch
WORKERS="${WORKERS:-1}"

# ── Common CLI fragment ──────────────────────────────────────────────
COMMON_ARGS=(
  --solver harbor_terminus2
  --workers "$WORKERS"
  --solver-model "$SOLVER_MODEL"
  --solver-base-url "$SOLVER_BASE_URL"
)

# ── Health checks ────────────────────────────────────────────────────
check_vllm() {
  if ! curl -sf "${SOLVER_BASE_URL%/v1}/health" > /dev/null 2>&1; then
    echo "ERROR: vLLM server not healthy at $SOLVER_BASE_URL"
    echo "  Start it with: bash /home/gost/repo/meta-harness/scripts/vllm.sh start"
    return 1
  fi
}

check_docker() {
  if ! docker ps > /dev/null 2>&1; then
    echo "ERROR: cannot talk to Docker daemon."
    return 1
  fi
}

banner() {
  echo
  echo "========================================================================"
  echo "  $1"
  echo "========================================================================"
  echo "  Experiment: $EXPT"
  echo "  Run dir:    $RUN_DIR"
  echo "  Train:      $TRAIN_TASKS"
  echo "  Test:       $TEST_TASKS"
  echo "========================================================================"
  echo
}
