---
name: orient-the-environment
description: Systematic first-turn reconnaissance of a new terminal-bench task. Use at the very start of every task to discover files, existing tooling, hidden tests, available languages/versions, and anything the prompt didn't spell out. Prevents wasted turns building on wrong assumptions.
---

# Orient the Environment

The #1 reason tasks fail early is acting on assumptions instead of facts. Spend 1–3 turns establishing ground truth before attempting a fix.

## Minimum recon batch (first turn on any task)

```bash
pwd
ls -la /app/ 2>/dev/null
ls -la /tests/ 2>/dev/null
ls -la /  # sometimes tasks drop files elsewhere
```

Follow immediately with hints and verifier discovery:

```bash
# Hint files
for f in /app/README* /app/HACKING* /app/HINT* /app/NOTES* /app/INSTRUCTIONS*; do
  [ -f "$f" ] && echo "===== $f =====" && cat "$f"
done

# Verifier — see verify-before-submit skill for how to use this
[ -f /tests/test.sh ] && echo "===== /tests/test.sh =====" && cat /tests/test.sh
[ -f /tests/test_outputs.py ] && echo "===== /tests/test_outputs.py =====" && cat /tests/test_outputs.py
```

## For data / binary artifacts

```bash
file /app/<mystery_file>
head -c 200 /app/<mystery_file> | xxd | head
stat /app/<mystery_file>
```

For databases: `sqlite3 /app/db "SELECT name,sql FROM sqlite_master"`, `pg_dump --schema-only`, etc.

For archives: `tar tf`, `unzip -l`, `7z l`.

## For code repos

```bash
cd /app && ls -la
# Find build system
ls Makefile CMakeLists.txt setup.py pyproject.toml Cargo.toml package.json go.mod 2>/dev/null
# Tests already present?
find . -maxdepth 3 -name "test_*.py" -o -name "*_test.go" -o -name "test.sh" 2>/dev/null | head
# Recent changes (often the bug source in "I broke X" tasks)
git -C /app status 2>/dev/null
git -C /app log --oneline -20 2>/dev/null
git -C /app diff HEAD~1 2>/dev/null | head -200
```

## For "I broke X, fix it" tasks

The bug is usually in a recent diff. Always run `git log`, `git diff`, and `git blame` on suspect files before reading the whole codebase. The task often *is* "reverse the last commit's mistake".

## What to output after recon

Use the `analysis` field of your response to list the key findings — what files exist, what the verifier checks for, what tool versions are present, what surprised you vs. the prompt. That becomes the shared context for the next turn.

## Anti-patterns

- Running a 5-minute build before reading the prompt's hint file.
- Writing a solution before reading the verifier. You may be optimizing the wrong objective.
- Ignoring a git history in "something is broken" tasks.
- Assuming a tool is present. Run `which X && X --version` first.
