# TB2 Generalization Experiment Scripts

Four-phase experiment measuring whether a-evolve's skill/prompt mutations
generalize beyond the tasks they were trained on. Uses Harbor's stock
Terminus-2 agent as the solver and Claude Code (subscription) as the evolver.

## Layout

```
experiment_scripts/
├── _common.sh              # shared env vars, task splits, health checks
├── phase1_baseline.sh      # pre-eval on TRAIN + TEST (no evolution)
├── phase2_evolve.sh        # run 2 evolution cycles on TRAIN
├── phase3_posteval.sh      # post-eval on TRAIN + TEST with evolved workspace
├── phase4_compare.sh       # print side-by-side pass rates + mutation diff
└── README.md               # this file
```

## Quick start

```bash
# Optional: give this run a memorable name (default is a timestamp)
export EXPT=my_first_run

# Run phases in order (total ~3h wall clock)
bash experiment_scripts/phase1_baseline.sh
bash experiment_scripts/phase2_evolve.sh
bash experiment_scripts/phase3_posteval.sh
bash experiment_scripts/phase4_compare.sh
```

Each phase writes under `/data/shared_data/harness/results/a-evolve/$EXPT/`.

**Important:** use the same `EXPT` value for all four phases so they share a folder.
If you don't set `EXPT`, each phase will pick its own timestamp and they won't find each other's outputs.

## Skipping phase 1

If you trust the prior Terminus-2 full-run data (score=0 for all 15 chosen
tasks), you can skip phase 1 to save ~90 min. Phase 4 will just show
`(missing)` for the pre-baseline entries — the post-evolution numbers still
land, and you can eyeball whether they improved relative to the prior zeros.

## Customizing task splits

Edit `TRAIN_TASKS` and `TEST_TASKS` in `_common.sh`, or override at the CLI:

```bash
TRAIN_TASKS="taskA,taskB,taskC" TEST_TASKS="taskD,taskE" \
  bash experiment_scripts/phase2_evolve.sh
```

Keep train/test disjoint. The current defaults are 10 Nemotron failures
for train and 5 held-out failures for test, with paired "cousin" tasks
across sets (e.g. `polyglot-c-py` in train, `polyglot-rust-c` in test).

## Retargeting model / endpoint

Environment variables (with defaults in `_common.sh`):

| Var | Default | Purpose |
|---|---|---|
| `SOLVER_MODEL` | `nemotron-super-120b` | vLLM served-model-name |
| `SOLVER_BASE_URL` | `http://localhost:29413/v1` | vLLM endpoint |
| `EVOLVER_MODEL` | `claude-code:claude-opus-4-7` | Claude Code subscription |
| `SEED_WORKSPACE` | `seed_workspaces/terminus-2` | Stock Terminus-2 seed |
| `TRAIN_BATCH_SIZE` | `5` | batch size on train (10/5 = 2 evo cycles) |
| `TEST_BATCH_SIZE` | `5` | batch size on test |
| `WORKERS` | `1` | parallel task solvers |
| `A_EVOLVE_DIR` | `/data/shared_data/harness/results/a-evolve` | run root |

## Resumability

All three data-producing phases (1, 2, 3) are resumable: rerunning the same
command skips tasks already in `--output`. Evolution cycles themselves
cannot resume mid-cycle — if phase 2 is interrupted during the
`--- Evolution cycle N ---` block, re-run phase 2 and the partial mutation
is rolled back by a-evolve's gating machinery.

## Reading phase 4 output

Four numbers tell the story:

|              | pre (T0) | post (T1) | signal |
|---|---|---|---|
| Train (seen) | `X / 10` | `Y / 10` | `Y > X`: evolver fit training |
| Test (unseen)| `A / 5`  | `B / 5`  | `B > A`: real generalization |

- **Best**: `Y > X` and `B > A` — skills transferred.
- **Overfit**: `Y >> X` but `B ≈ A` — skills too task-specific.
- **No effect**: both equal — check `git diff evo-0..HEAD` to see if the
  evolver mutated at all.
- **Negative**: `Y < X` or `B < A` — evolution hurt. Inspect the skill
  contents under `train_evolve/workspace/skills/`.
