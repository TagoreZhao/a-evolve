#!/usr/bin/env bash
# Phase 3 — evaluate the EVOLVED workspace (produced by Phase 2) on both
# TRAIN and TEST sets with --no-evolve. This gives us T1_train and T1_test.
#
# Phase 3a (TRAIN) answers: did the evolver improve on tasks it trained on?
# Phase 3b (TEST)  answers: did learned skills/prompt generalize to unseen
#                           failures?
#
# Time: ~90 min for 15 tasks.
#
# REQUIRES: Phase 2 must have completed — an evolved workspace must exist
# at $RUN_DIR/train_evolve/workspace.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_common.sh"

banner "Phase 3 — Post-evolution evaluation (train + test, no evolution)"

EVOLVED_WS="$RUN_DIR/train_evolve/workspace"
if [ ! -d "$EVOLVED_WS" ]; then
  echo "ERROR: evolved workspace not found at $EVOLVED_WS"
  echo "  Run Phase 2 first: bash $SCRIPT_DIR/phase2_evolve.sh"
  exit 1
fi

check_vllm
check_docker

cd "$REPO_ROOT"

# ── Post-eval: TRAIN ─────────────────────────────────────────────────
echo
echo "--- Phase 3a: post-eval on TRAIN (${TRAIN_TASKS}) ---"
echo "  Using evolved workspace: $EVOLVED_WS"
python examples/tb_examples/batch_evolve_terminal.py \
  "${COMMON_ARGS[@]}" \
  --no-evolve \
  --tasks "$TRAIN_TASKS" \
  --batch-size "$TRAIN_BATCH_SIZE" \
  --seed-workspace "$EVOLVED_WS" \
  --work-dir "$RUN_DIR/post_train/workspace" \
  --log-dir  "$RUN_DIR/post_train/logs" \
  --output   "$RUN_DIR/post_train/results.jsonl" \
  --errors   "$RUN_DIR/post_train/errors.jsonl" \
  2>&1 | tee "$RUN_DIR/post_train/stdout.log"

# ── Post-eval: TEST ──────────────────────────────────────────────────
echo
echo "--- Phase 3b: post-eval on TEST (${TEST_TASKS}) ---"
echo "  Using evolved workspace: $EVOLVED_WS"
python examples/tb_examples/batch_evolve_terminal.py \
  "${COMMON_ARGS[@]}" \
  --no-evolve \
  --tasks "$TEST_TASKS" \
  --batch-size "$TEST_BATCH_SIZE" \
  --seed-workspace "$EVOLVED_WS" \
  --work-dir "$RUN_DIR/post_test/workspace" \
  --log-dir  "$RUN_DIR/post_test/logs" \
  --output   "$RUN_DIR/post_test/results.jsonl" \
  --errors   "$RUN_DIR/post_test/errors.jsonl" \
  2>&1 | tee "$RUN_DIR/post_test/stdout.log"

echo
echo "Phase 3 complete. Results:"
echo "  Post-train: $RUN_DIR/post_train/results.jsonl"
echo "  Post-test:  $RUN_DIR/post_test/results.jsonl"
echo
echo "Next: bash $SCRIPT_DIR/phase4_compare.sh"
