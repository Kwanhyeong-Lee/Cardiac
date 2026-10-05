---
name: wrap-up
description: End a work session by recording what changed in docs/STATE.md and committing it, so the other machine (and the next session) starts from the real state.
---

Claude Code's own memory stays on each machine; the two machines only share what is in git. So every session ends here.

1. Update `docs/STATE.md` -- edit in place, keep it short, newest first:
   - the "현재 상태" table rows that changed (date, machine: alex0 or wjsdm, one line each)
   - decisions the user made this session, in their words where possible
   - open items: add new ones, strike or remove finished ones (do not leave stale items)
   - the single next step for each track
   Do not paste logs or long output; link the file that has it.
2. `/guard` -- must be clean.
3. Commit only what this session meant to change: `docs/STATE.md` plus the session's own files. Message: what changed, in one line.
4. Push (the permission prompt will ask the user). If the push is refused because the remote moved: `git pull --rebase` is NOT allowed on its own -- show `git status` / `git log --oneline -5 origin/main` and ask.
5. Tell the user in two or three lines what was recorded and what the other machine should do next (as a paste-ready block if it involves commands there).
