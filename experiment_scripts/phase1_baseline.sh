#!/usr/bin/env bash
# Phase 1 — pre-evolution baseline on TRAIN and TEST sets using the stock
# Terminus-2 seed (no mutation). Gives us T0_train and T0_test to compare
# against the post-evolution numbers from Phase 3.
#
# Time: ~90 min total for 15 tasks. Can be skipped if you trust prior
# Terminus-2 full-run data — they all scored 0 there.
#
# Resumable: rerunning skips already-completed tasks (same --output file).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_common.sh"

banner "Phase 1 — Pre-evolution baseline (train + test, no evolution)"

check_vllm
check_docker

cd "$REPO_ROOT"

# ── Pre-baseline: TRAIN ──────────────────────────────────────────────
echo
echo "--- Phase 1a: baseline on TRAIN (${TRAIN_TASKS}) ---"
python examples/tb_examples/batch_evolve_terminal.py \
  "${COMMON_ARGS[@]}" \
  --no-evolve \
  --tasks "$TRAIN_TASKS" \
  --batch-size "$TRAIN_BATCH_SIZE" \
  --seed-workspace "$SEED_WORKSPACE" \
  --work-dir "$RUN_DIR/pre_train/workspace" \
  --log-dir  "$RUN_DIR/pre_train/logs" \
  --output   "$RUN_DIR/pre_train/results.jsonl" \
  --errors   "$RUN_DIR/pre_train/errors.jsonl" \
  2>&1 | tee "$RUN_DIR/pre_train/stdout.log"

# ── Pre-baseline: TEST ───────────────────────────────────────────────
echo
echo "--- Phase 1b: baseline on TEST (${TEST_TASKS}) ---"
python examples/tb_examples/batch_evolve_terminal.py \
  "${COMMON_ARGS[@]}" \
  --no-evolve \
  --tasks "$TEST_TASKS" \
  --batch-size "$TEST_BATCH_SIZE" \
  --seed-workspace "$SEED_WORKSPACE" \
  --work-dir "$RUN_DIR/pre_test/workspace" \
  --log-dir  "$RUN_DIR/pre_test/logs" \
  --output   "$RUN_DIR/pre_test/results.jsonl" \
  --errors   "$RUN_DIR/pre_test/errors.jsonl" \
  2>&1 | tee "$RUN_DIR/pre_test/stdout.log"

echo
echo "Phase 1 complete. Results:"
echo "  Pre-train: $RUN_DIR/pre_train/results.jsonl"
echo "  Pre-test:  $RUN_DIR/pre_test/results.jsonl"
echo
echo "Next: bash $SCRIPT_DIR/phase2_evolve.sh"
