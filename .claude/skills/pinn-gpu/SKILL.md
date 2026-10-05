---
name: pinn-gpu
description: Verify PINN training on the RTX 3060 and prepare real experiments, under the patient-data and frozen-results rules.
disable-model-invocation: true
---

Read `tools/setup/TASK_PINN_GPU.md` and carry out the prompt in its "Claude Code 프롬프트" block, step by step.

Ground rules that apply on top of it (from CLAUDE.md):
- Patient-level data (MIMIC-IV, eICU, INSPIRE, VitalDB, PIC and anything derived per patient) is processed by scripts on this machine only. Never open, print, head or cat its rows; report shapes, counts and aggregate metrics only. Never commit per-patient outputs.
- Paper B conclusions are frozen (H1 and H2 refuted under a pre-registered protocol). Re-running on a GPU does not reopen them; a new experiment needs a new pre-registration document first. Do not search for a third benefit axis. Keep the `[AUDIT-n]` trail and `*_PREAUDIT_discard.json` files.
- Synthetic data only proves the loop runs. Never tune or fix a physiological constant on synthetic fit quality; label such constants "FIXED placeholder".
- Paper code (e.g. `pinn_hamiltonian_v5.py`) is changed only after the user approves the diff.
- Finish with `/wrap-up`.
