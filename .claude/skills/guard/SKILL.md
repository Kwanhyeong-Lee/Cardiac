---
name: guard
description: Scan everything git tracks for patient data, MM-WHS-derived meshes, engine build output and secrets, and check whether HEAD is pushed. Use before every push and whenever unsure what a commit will contain.
---

1. `git status --short` and `git diff --cached --stat` -- show what would be committed.
2. `python3 tools/repo_guard.py` -- full scan of tracked files + behind/ahead of origin.
3. `git config core.hooksPath` must print `tools/git-hooks`. If it does not, run `sh tools/git-hooks/install.sh` (do not run `git config core.hooksPath ...` directly; it is denied on purpose).
4. Report: clean or not, each refused file with the reason, and whether the branch is ahead/behind origin.
5. If something is refused: propose the fix (unstage, `.gitignore` rule, move the file under `$CARDIAC_DATA`). Never bypass with `--no-verify`, never rewrite history; a genuine exception is a reviewed edit to the WHITELIST in `tools/repo_guard.py`, in its own commit, after the user agrees.
