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

## Task Selection and Rationale

The 15 tasks below are drawn from the 62 Terminal-Bench-2 tasks that Nemotron-Super-120B
scored `reward=0.0` on during a prior full-run under stock Harbor Terminus-2
(result at `/data/shared_data/harness/results/terminalbench/agent-comparison/agent-cmp-terminus2/result.json`).
Training on known failures guarantees the evolver sees failure signal to learn from — training
on tasks Nemotron already passes would give the evolver nothing to fix, and a-evolve's
`AdaptiveSkillEngine` tends to return `no mutation` on all-passing batches.

### Selection criteria (why 15 of 62)

We excluded 47 of the 62 failures because they are **model-capability-bound**, not
**skill-bound** — no amount of prompt or skill evolution can reasonably flip them under
a 10-minute timeout:

- **ML training / heavy model work** (skipped): `caffe-cifar-10`, `train-fasttext`,
  `torch-pipeline-parallelism`, `torch-tensor-parallelism`, `mteb-leaderboard`, `mteb-retrieve`,
  `pytorch-model-recovery`, `sam-cell-seg`, `mcmc-sampling-stan`, `protein-assembly`,
  `gpt2-codegolf`. These are wall-clock-bound or need GPU resources the agent can't orchestrate.
- **Heavy compilation / native-toolchain tasks** (skipped): `compile-compcert`,
  `build-pov-ray`, `make-doom-for-mips`, `make-mips-interpreter`, `make-pov-ray`.
  Compilation itself exhausts the timeout before agent strategy matters.
- **Vision / video** (skipped): `extract-moves-from-video`, `video-processing`,
  `path-tracing`, `path-tracing-reverse`, `schemelike-metacircular-eval`.
  The stock Terminus-2 prompt flow doesn't provide image inputs.
- **Hardware / VM installs** (skipped): `install-windows-3-11`, `qemu-startup`,
  `qemu-alpine-ssh`. Environment-bound, not skill-bound.

The 15 we kept span debugging, security, scripting, SQL, file-operations, and text
manipulation — categories where careful tool use, systematic debugging, or a well-scoped
learned procedure could plausibly move a failure to a pass.

### TRAIN set (10 tasks, 2 evolution cycles at batch size 5)

Descriptions are paraphrased from each task's own `eval.yaml` (`variants.default.prompt`).

| Task | Category | Difficulty | Expert time | What it tests |
|---|---|---|---|---|
| `break-filter-js-from-html` | security | medium | 20 min | Craft HTML that still fires `alert()` after the bundled XSS filter strips JS |
| `regex-chess` | software-engineering | hard | 1440 min | Write a JSON of regex replacements that enumerate legal next chess positions from a FEN |
| `fix-code-vulnerability` | security | hard | 120 min | Identify and patch a CWE vulnerability in a Bottle web-framework repo |
| `fix-ocaml-gc` | software-engineering | hard | 1440 min | Debug an OCaml compiler that crashes during bootstrap after a GC sweep change |
| `polyglot-c-py` | software-engineering | medium | 20 min | Write `main.py.c` that runs as both Python3 and gcc C to print the nth Fibonacci |
| `query-optimize` | data-science | medium | 60 min | Rewrite an unoptimized SQL query on the Open English Wordnet SQLite DB |
| `sqlite-db-truncate` | debugging | medium | 60 min | Recover rows from a binary-truncated SQLite file into JSON |
| `password-recovery` | security | hard | 100 min | Forensic recovery of a deleted `launchcode.txt` containing a 23-char password |
| `gcode-to-text` | file-operations | medium | 60 min | Parse a Prusa MK4s gcode file and determine what text the printer would draw |
| `db-wal-recovery` | file-operations | medium | 45 min | Repair a corrupt/encrypted SQLite WAL file and extract all 11 rows |

### TEST set (5 held-out tasks)

These are *also* failures from the prior full run, but the evolver never sees them during
Phase 2. Each one either shares a domain with a train task (the "paired" column) or tests
whether a generic strategy improvement transfers to a new domain.

| Task | Category | Difficulty | Expert time | What it tests | Paired train task / hypothesis |
|---|---|---|---|---|---|
| `filter-js-from-html` | security | medium | 45 min | Write a Python filter that strips JS from HTML while preserving structure | Inverse of `break-filter-js-from-html` — if the evolver learned XSS attack patterns on the offensive side, it should sharpen the defensive filter |
| `polyglot-rust-c` | software-engineering | hard | 180 min | Write `main.rs` that compiles under both rustc and g++ (as C++) to print Fibonacci | Same polyglot-construction skill as `polyglot-c-py`, different language pair |
| `sqlite-with-gcov` | system-administration | medium | 30 min | Compile SQLite from a vendored tarball with gcov instrumentation and expose it on PATH | SQLite familiarity from `query-optimize` + `sqlite-db-truncate` — **weaker** transfer signal (this is a build task, not a data task) |
| `crack-7z-hash` | security | medium | 5 min | Extract a password-protected file from a `.7z` archive and save its contents | Adjacent security/forensic domain to `password-recovery` |
| `sanitize-git-repo` | security | medium | 30 min | Scan a git repo, find hard-coded API keys, replace with placeholder values | No direct cousin — tests whether generic "careful pattern-search + file edit" skills the evolver might learn transfer to a new domain |

### Distribution balance

Category and difficulty balance across the two splits (showing the comparison is not confounded
by wildly different tasks):

```
                   TRAIN (n=10)    TEST (n=5)
  security            3               3
  software-eng        3               1
  data-science        1               0
  debugging           1               0
  file-operations     2               0
  system-admin        0               1

  medium              6               4
  hard                4               1
```

### Honest caveats (things mentors will ask about)

- **Two weak pairings.** `sqlite-with-gcov` shares only vocabulary with train's SQLite tasks
  (build vs. query); `sanitize-git-repo` has no direct cousin in train. These stress whether
  skills generalize beyond narrow task clones — if they improve, the evolver found something
  general; if only the tight cousins improve, the skills are task-specific.
- **Test is slightly easier than train.** 1 hard / 4 medium vs. train's 4 hard / 6 medium.
  Post-evolution test gains could partly reflect the easier tasks, not just generalization.
  One way to control for this is to re-run the same test set with the un-evolved workspace
  (that's Phase 1b) — the delta, not the absolute rate, is the signal.
- **Expert time range is 5–1440 min; the solver's per-task timeout is 600 s.** The hardest
  train tasks (`regex-chess` at 24 hours expert time, `fix-ocaml-gc` at 24 hours) cannot
  realistically be solved by *any* prompt/skill edit under 10 minutes. They are in the
  train set to generate **rich failure trajectories** that the evolver can mine for
  debugging heuristics, not as tasks we expect to eventually pass. Mentors should interpret
  the train pass rate as "fraction of tasks where evolution flipped a solvable-in-timeout
  failure", not "fraction of tasks the agent can now do."
- **n=5 test is small.** A single lucky pass is 20 percentage points. Results at this scale
  are directional only; widen the test set if the signal looks promising.

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
