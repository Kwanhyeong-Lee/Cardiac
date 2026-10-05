---
name: batch
description: Run the MM-WHS 20-case geometry pipeline (fusion_ready/batch_cases.py) on the RTX 3060 machine and commit only the summaries.
disable-model-invocation: true
---

Read `tools/setup/TASK_BATCH.md` and carry out the prompt in its "Claude Code 프롬프트" block, step by step.

Ground rules that apply on top of it (from CLAUDE.md):
- Run `/setup-check` first if you have not in this session; the geometry line must be READY.
- The batch is long: start it with nohup (as the task says) so it survives the session, and report progress from the log.
- Commit only SUMMARY.md / SUMMARY.csv / summary.png and per-case JSON/MD (+ PNGs of 2-3 representative cases). The pre-commit guard refuses meshes and volumes; if it refuses something, fix the cause, never bypass.
- Report results with their limits stated (IVC mostly absent in arterial phase, arch often outside FOV, coronaries trustworthy proximal-mid only, low-contrast cases flagged).
- Finish with `/wrap-up`.
