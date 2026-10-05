#!/bin/sh
# Turn on the repository's pre-commit guard for this clone (idempotent).  Run once per clone:  sh tools/git-hooks/install.sh
# Claude Code is denied `git config core.hooksPath` directly (so no session can switch the guard off); this script is the way on.
top=$(git rev-parse --show-toplevel) || exit 1
git -C "$top" config core.hooksPath tools/git-hooks && echo "pre-commit guard enabled for $top (core.hooksPath=tools/git-hooks)"
