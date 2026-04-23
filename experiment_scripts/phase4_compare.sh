#!/usr/bin/env bash
# Phase 4 — print side-by-side comparison of pre/post metrics and show
# what the evolver actually changed. No LLM calls, no Docker; purely
# reads results.jsonl files written by Phases 1-3.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_common.sh"

banner "Phase 4 — Comparison and diff"

cd "$REPO_ROOT"

print_pass_rate() {
  local label="$1"
  local jsonl="$2"
  if [ ! -f "$jsonl" ]; then
    printf "  %-12s  %s\n" "$label:" "(missing: $jsonl)"
    return
  fi
  local total passed
  total=$(python -c "import json; print(sum(1 for l in open('$jsonl') if l.strip()))")
  passed=$(python -c "import json; print(sum(1 for l in open('$jsonl') if l.strip() and json.loads(l).get('passed')))")
  printf "  %-12s  %d / %d\n" "$label:" "$passed" "$total"
}

print_per_task() {
  local jsonl="$1"
  if [ ! -f "$jsonl" ]; then return; fi
  python -c "
import json
for line in open('$jsonl'):
    if not line.strip(): continue
    r = json.loads(line)
    print(f\"    {'PASS' if r.get('passed') else 'FAIL':4}  {r['task_name']}\")
"
}

echo
echo "── Pass rates ──────────────────────────────────────────────────"
echo "TRAIN set:"
print_pass_rate "pre"  "$RUN_DIR/pre_train/results.jsonl"
print_pass_rate "post" "$RUN_DIR/post_train/results.jsonl"
echo
echo "TEST set:"
print_pass_rate "pre"  "$RUN_DIR/pre_test/results.jsonl"
print_pass_rate "post" "$RUN_DIR/post_test/results.jsonl"

echo
echo "── Per-task details ────────────────────────────────────────────"
for phase in pre_train post_train pre_test post_test; do
  f="$RUN_DIR/$phase/results.jsonl"
  if [ -f "$f" ]; then
    echo
    echo "  $phase:"
    print_per_task "$f"
  fi
done

echo
echo "── What the evolver changed ────────────────────────────────────"
EVOLVED_WS="$RUN_DIR/train_evolve/workspace"
if [ -d "$EVOLVED_WS/.git" ]; then
  echo "Mutation lineage:"
  git -C "$EVOLVED_WS" log --oneline --tags | head -20
  echo
  echo "Files changed (evo-0 to latest):"
  git -C "$EVOLVED_WS" diff --stat evo-0..HEAD -- prompts/ skills/ 2>/dev/null || echo "  (no evo-0 tag found)"
  echo
  echo "Skills added (latest):"
  ls "$EVOLVED_WS/skills/" 2>/dev/null | sed 's/^/  /' || echo "  (none)"
  echo
  echo "To see the full prompt/skill diff:"
  echo "  git -C $EVOLVED_WS diff evo-0..HEAD -- prompts/ skills/"
else
  echo "  (no .git dir at $EVOLVED_WS — Phase 2 not run or workspace missing)"
fi

echo
echo "── Raw metrics files ───────────────────────────────────────────"
for phase in pre_train post_train pre_test post_test; do
  f="$RUN_DIR/$phase/results.metrics.json"
  [ -f "$f" ] && echo "  $f"
done
