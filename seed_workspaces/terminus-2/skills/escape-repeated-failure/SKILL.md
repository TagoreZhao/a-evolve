---
name: escape-repeated-failure
description: Recover when the same command or approach has failed 2+ times in a row, or when you are running out of turn budget without progress. Forces a hard reset in strategy instead of stubborn retries. Use whenever you catch yourself about to re-run a failed command with only cosmetic changes.
---

# Escape Repeated Failure

Two symptoms mean you need to stop, not push harder:

1. The same error (or a trivially-reworded version of it) has appeared 2+ times.
2. You have burned a meaningful fraction of the turn budget without the verifier getting any closer to green.

## Hard reset protocol

When either symptom triggers, do **not** issue another fix attempt this turn. Instead, issue a diagnostic-only batch:

1. **Restate the problem from scratch in `analysis`.** What is the verifier actually checking? What does the prompt literally require? Often the second reading reveals a constraint you skipped.
2. **Gather evidence, not fixes.** Read the relevant source end-to-end (`sed -n '1,200p' file`, `grep -n <symbol> -r`), run the failing check with more verbosity (`-v`, `--trace`, `PYTHONTRACEMALLOC=1`, `strace -f`, `RUST_BACKTRACE=1`), print intermediate state, diff actual vs. expected.
3. **Enumerate alternatives.** Write out 2–3 distinct approaches in the `plan` field, not just variants of the one that failed. E.g. "Approach A: patch file X. Approach B: wrong layer — the bug is actually in Y. Approach C: pre-process the input before the buggy step." Pick the one with the strongest evidence.
4. **Shrink the problem.** If the full workload is slow (full build, full test suite), find the smallest reproducer — one test case, one file, one function. Iterate there until it passes, then re-expand.
5. **Check for invalidating assumptions.** Tool version mismatch? Wrong working directory? File being overwritten by a setup script? Environment variable unset? These kill tasks silently.

## Budget triage

If time is short:

- **Cut scope to what the verifier grades.** If the prompt asks for steps 1–6 but only step 4 is graded, do step 4 first.
- **Prefer hardcoded-but-correct over elegant-but-half-done.** A `/app/out.txt` with the right literal string beats a beautiful parser that segfaults.
- **Stop polishing a passing solution.** Once the verifier is green, submit.

## Anti-patterns to kill on sight

- "Let me try that same command with one flag tweaked" (for the 3rd time).
- Adding more print statements without reading the ones you already have.
- Going deeper into a rabbit hole (recompiling the toolchain, upgrading deps) when the bug is a one-line typo in the task files.
- Building for 5 minutes, getting the same error, building again.

## Sanity questions (ask before the next batch)

- Did I actually run the task's own verifier, or am I guessing what "success" means?
- Is the thing I'm editing even the thing the verifier reads?
- Has my last 3 turns' output *changed* at all? If no — stop, diagnose.
