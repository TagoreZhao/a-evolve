#!/usr/bin/env bash
# Phase 2 — evolve on the TRAIN set. Runs 2 evolution cycles (10 tasks /
# batch_size 5). After each batch, Claude Code (the evolver) reads the
# trajectories and mutates prompts/system.md and/or skills/*/SKILL.md
# in the workspace. Each mutation is git-tagged evo-1, evo-2.
#
# Time: ~60 min. Watch Claude Code rate limits on Opus.
#
# Resumable: rerunning skips already-completed tasks (same --output file),
# but evolution cycles don't resume mid-cycle — if interrupted during
# evolution, the partial mutation is rolled back by a-evolve's gating.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_common.sh"

banner "Phase 2 — Evolution on TRAIN (2 cycles)"

check_vllm
check_docker

# Verify claude CLI is logged in (evolver uses subscription via claude-agent-sdk)
if ! command -v claude > /dev/null 2>&1; then
  echo "WARNING: \`claude\` CLI not on PATH. If ClaudeCodeProvider fails on login,"
  echo "  run \`claude\` once to authenticate, then retry."
fi

cd "$REPO_ROOT"

echo
echo "--- Phase 2: evolve on TRAIN (${TRAIN_TASKS}) ---"
echo "  Evolver: $EVOLVER_MODEL"
echo "  Batches: 10/$TRAIN_BATCH_SIZE = $((10 / TRAIN_BATCH_SIZE)) evo cycle(s)"
echo

python examples/tb_examples/batch_evolve_terminal.py \
  "${COMMON_ARGS[@]}" \
  --tasks "$TRAIN_TASKS" \
  --batch-size "$TRAIN_BATCH_SIZE" \
  --evolver-model "$EVOLVER_MODEL" \
  --seed-workspace "$SEED_WORKSPACE" \
  --work-dir "$RUN_DIR/train_evolve/workspace" \
  --log-dir  "$RUN_DIR/train_evolve/logs" \
  --output   "$RUN_DIR/train_evolve/results.jsonl" \
  --errors   "$RUN_DIR/train_evolve/errors.jsonl" \
  2>&1 | tee "$RUN_DIR/train_evolve/stdout.log"

echo
echo "Phase 2 complete. Evolved workspace at:"
echo "  $RUN_DIR/train_evolve/workspace"
echo
echo "Mutation lineage:"
git -C "$RUN_DIR/train_evolve/workspace" log --oneline --tags 2>/dev/null | head -20 || true
echo
echo "Files changed across cycles:"
git -C "$RUN_DIR/train_evolve/workspace" diff --stat evo-0..HEAD -- prompts/ skills/ 2>/dev/null || true
echo
echo "Next: bash $SCRIPT_DIR/phase3_posteval.sh"
