---
name: unreal-m1
description: Build the HeartTeach Unreal app (milestone M1) on the RTX 3060 machine from WSL, following the project SPEC.
disable-model-invocation: true
---

Read `fusion_ready/UNREAL/HeartTeach/SPEC.md` first, then `tools/setup/TASK_UNREAL.md`, and carry out the prompt in its "Claude Code 프롬프트" block, step by step.

Ground rules that apply on top of it (from CLAUDE.md):
- SPEC.md sections 2 (coordinate frame), 4 (material) and 5 (perfusion colours = data) are not changed without the user.
- Acceptance gate: from the default view the thick dark-red left ventricle must be on the viewer's RIGHT. If not, stop and report -- never fix it with a negative scale (the project once shipped silently mirrored meshes).
- The four visual checks are done by the user in the editor; you record what they report in `fusion_ready/UNREAL/HeartTeach/BUILD_NOTES.md`.
- Never commit .glb, Binaries/, Intermediate/, Saved/, DerivedDataCache/, Content/. No public packaged build: the geometry is MM-WHS-derived.
- Finish with `/wrap-up`.
