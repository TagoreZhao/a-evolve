---
name: verify-before-submit
description: Run the task's own verifier/tests before marking a task complete. Almost every terminal-bench task ships an acceptance check at /tests/test_outputs.py or /tests/test.sh; the task prompt often spells out exactly how to run it (e.g. "you can run /app/test_outputs.py" or "run pytest -rA"). Use this skill any time you are about to call submit / set task_complete=true, or whenever a prompt contains the phrases "verify", "test", "ensure", "make all test cases pass".
---

# Verify Before Submit

Submitting without verifying is the single biggest failure mode on terminal-bench. Fix it by making verification the last step of every run.

## Where to look for a verifier

Check each of these, in order, before submitting:

1. **Explicit prompt instructions.** If the task says "run X to verify" or "make all tests pass", X is the verifier. Obey it literally.
2. `/tests/test.sh` — shell-level driver. `bash /tests/test.sh` or `cat /tests/test.sh` to see what it runs.
3. `/tests/test_outputs.py` — pytest-style output check. Run with `pytest -rA /tests/test_outputs.py` or `python /tests/test_outputs.py` depending on how it's written.
4. `/app/test_outputs.py` — sometimes in /app instead of /tests.
5. Project-level tests: `pytest -rA` from the repo root, `make test`, `cargo test`, `go test ./...`, `npm test`, etc.

```bash
ls -la /tests/ /app/ 2>/dev/null | grep -E "test|spec"
cat /tests/test.sh 2>/dev/null
cat /tests/test_outputs.py 2>/dev/null
```

## Rules

- **Never modify files under `/tests/`.** Those are the grading oracles. If a test fails, fix your solution, not the test.
- **Read the verifier source at least once.** Knowing exactly what it asserts (e.g. "file exists at /app/out.txt and equals 'HELLO WORLD'") usually makes the rest of the task trivial — it converts an open-ended problem into a concrete target.
- **Reproduce the check manually before running the verifier.** If the verifier checks a JSON file at /app/recovered.json, `cat` that file and eyeball it against the assertions first; that's cheaper than a full verifier run and easier to debug.
- **A passing verifier is the only green light.** If you cannot run the verifier (e.g. it requires a hidden grader), reconstruct its logic from the task prompt and self-check against that.
- **If the verifier fails, do not submit.** Diagnose, patch, re-run. Only set `task_complete: true` after you have *seen* the verifier pass in terminal output within the current session.

## Worked pattern

```bash
# 1. Find the verifier
ls /tests/ /app/
cat /tests/test_outputs.py

# 2. (Do the actual task.)

# 3. Dry-run the acceptance check
python /tests/test_outputs.py   # or: pytest -rA /tests/test_outputs.py
#  -> all tests pass  =>  now submit
#  -> failure          =>  read the assertion, fix, re-run. Do NOT submit yet.
```
