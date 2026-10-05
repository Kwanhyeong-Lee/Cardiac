---
name: setup-check
description: Check whether this machine is ready for the geometry pipeline, PINN GPU training and the Unreal app, and say exactly what is missing. Use at the start of work on a machine, after installing something, or when a script fails for environment reasons.
---

Run the repository's read-only readiness checks and report them; change nothing.

1. `source ~/.venvs/cardiac/bin/activate 2>/dev/null; python tools/setup/check_setup.py --fetch`
2. If the `pinn` line is READY, also run `python tools/setup/gpu_smoke.py` and report the three stage results.
   `[KNOWN]` lines are pre-existing code issues (see docs/STATE.md), not setup failures.
3. Show the three verdict lines (geometry / pinn / unreal) and NEXT STEPS exactly as printed.
4. For each NOT READY item, say who has to act:
   - things I can do myself (pip packages, re-running a setup step) -> offer to do them
   - things only the user can do (Windows installers, sudo, logins, downloading data from OneDrive web, copying from a drive)
     -> give them as a block the user can paste as-is (the user's standing preference), with the exact path to use.
5. Never substitute a missing input by re-running the pipeline or generating data; ask where the input is.

Machine map, paths and rules: CLAUDE.md. Setup procedure: tools/setup/SETUP.md.
