# CLAUDE.md — cardiac pH-PINN workbench

2026-10-06부터 이 저장소의 모든 작업은 Claude Code에서 한다. 모델은 `.claude/settings.json`에 `claude-opus-5-5`로 고정돼 있다
(세션 시작 헤더에 설정 파일 이름이 뜬다; `/status`로 확인).
응답은 한국어로, 짧게. 사용자에게 **다른 기계나 Windows 쪽에서 할 일**을 줄 때는 그 창에 그대로 붙여 넣을 수 있는 블록으로 준다.

## 1. 무엇이 어디에

| 무엇 | 어디 |
|---|---|
| 지금 상태·열린 일·최근 결정 (두 기계가 공유) | **`docs/STATE.md`** — 세션 시작 때 읽고, 끝날 때 `/wrap-up`으로 갱신 |
| 지금까지의 결정 이유와 교훈 (Cowork 시기 ~2026-10-05) | `docs/HANDOFF_FROM_COWORK_2026-10-05.md` |
| 저장소 색인, 데이터 위치·자격, 갈래별 상태 | `HANDOVER.md` |
| 형상 파이프라인 1–31단계 (입력→출력→검증 수치) | `fusion_ready/PIPELINE.md` |
| 교육 키트, 모형을 보여줄 때 말할 문장 | `fusion_ready/EDUCATION_PACK.md` |
| Unreal 앱 설계 (좌표계·머티리얼·관류 색) | `fusion_ready/UNREAL/HeartTeach/SPEC.md` |
| 새 기계 셋업, 태스크 프롬프트 | `tools/setup/SETUP.md`, `TASK_BATCH.md`, `TASK_PINN_GPU.md`, `TASK_UNREAL.md` |
| Paper B | `waveform_pinn/SUMMARY.md`, `PAPER_B_OUTLINE.md`, `RESULTS_v6`–`v10` |

스킬(직접 호출만): `/setup-check` `/guard` `/batch` `/pinn-gpu` `/unreal-m1` `/wrap-up`

## 2. 기계

| | Windows 사용자 | 있는 것 | 여기서 하는 일 |
|---|---|---|---|
| **WORK** | `alex0` | 저장소, OneDrive 프로젝트 폴더(보관), MM-WHS 원본(OneDrive) | 코드·문서, 커밋 |
| **GPU** | `wjsdm` | RTX 3060 12 GB(+RX 5700 화면용), 32 GB. **OneDrive 없음** | MM-WHS 20례 배치, PINN GPU 학습, Unreal |

- 두 기계 모두 저장소는 `C:\work\Cardiac` = `/mnt/c/work/Cardiac`. Python은 `~/.venvs/cardiac`(3.10–3.12), 별칭 `cardiac`.
- **기계 사이에 공유되는 건 git뿐이다.** Claude Code의 자동 메모리는 기계마다 따로 있어서 저쪽에서 안 보인다 → 상태는 `docs/STATE.md`에 적는다.
- OneDrive의 `260421 (심장) - main` 폴더는 **보관용**이다. 코드는 저장소에서만 고친다(OneDrive 사본은 일부 파일이 이미 저장소보다 오래됐다).

## 3. 환경변수

- `CARDIAC_DATA` = 데이터 **루트**(`/mnt/d/data` 또는 `~/data`). MM-WHS는 `$CARDIAC_DATA/MM-WHS/ct_train`. `MMWHS_CT`로 직접 지정 가능.
- `CARDIAC_REPO`, `CARDIAC_OUT`(기본값 있음), `HEART_PACK`(Unreal 에셋 팩, 기본 `fusion_ready/UNREAL/1009`).

## 4. 절대 규칙

1. **데이터는 git에 넣지 않는다.** MIMIC-IV·eICU·INSPIRE·VitalDB·PIC, MM-WHS 영상, 환자 단위 파생 표. MM-WHS 파생 메시(STL/PLY/VTP/GLB/npz)도
   재배포 금지라 커밋·공개하지 않는다(렌더 그림·집계 표는 된다). pre-commit 가드(`tools/repo_guard.py`)가 막는다 — `--no-verify`로 우회하지 않는다.
2. **환자 단위 데이터는 모델에게 보여주지 않는다.** 행을 열거나 출력하지 않는다(Read/head/cat/print 금지). 스크립트가 이 기계에서 처리하고
   모양·개수·집계 지표만 출력한다. PhysioNet DUA는 온라인 서비스(LLM 포함)를 통한 제3자 노출을 허용하지 않는다.
3. **git**: force push·이력 재작성·`--no-verify` 금지. 토큰·비밀번호·로그인·sudo는 사용자 몫 — 명령을 보여주고 맡긴다.
4. **합성 데이터는 가동 여부만 본다.** 생리 상수를 합성 적합도에 맞춰 고치지 않는다(그런 상수는 "FIXED placeholder"로 표시).
5. **Paper B 결론은 동결.** H1(표본 효율)·H2(임상 가치)는 사전 등록 하에 기각됐다. 세 번째 이득 축을 찾지 않는다. 새 실험은 새 사전 등록부터.
   `[AUDIT-n]` 표식과 `*_PREAUDIT_discard.json`은 지우지 않는다(TMLR용 감사 기록).
6. **형상은 출처를 정직하게.** 환자 CT / 파라메트릭(판막 첨판·건삭 경로) / 합성(RV·심방·혈관 벽 두께)을 섞어 말하지 않는다.
   한계도 같이: IVC 없음(동맥기), 대동맥궁 FOV 밖, 관상동맥은 근위–중간부만 신뢰, 1009는 PDA 미확인.
7. **좌우.** frame A를 "고치지" 않는다. `cardiac_meshes/`는 거울상이다. Unreal은 정면에서 좌심실이 화면 오른쪽 — 음수 스케일로 때우지 않는다.
8. MM-WHS 형상이 들어간 Unreal **패키지 빌드는 공개 배포 불가**(교내 설치·시연·스크린샷은 된다).
9. **논문 코드**(`pinn_hamiltonian_v5.py` 등)와 이미 낸 결과를 만든 코드는 사용자가 diff를 승인한 뒤에만 고친다.
10. 필요한 입력(데이터·에셋)이 없으면 **어디 있는지 묻는다.** 파이프라인을 다시 돌리거나 데이터를 만들어서 대신하지 않는다.

## 5. 넘어지기 쉬운 곳

- OneDrive "클라우드 전용" 파일은 WSL에서 `Invalid argument`로 실패한다 → Windows에서 "항상 이 장치에 유지", 또는 `$CARDIAC_DATA`로 복사.
- NTFS 클론은 `core.filemode=false`, `core.autocrlf=input`(setup_wsl.sh가 설정). `.sh`는 LF(`tools/setup/.gitattributes`).
- STL은 `trimesh.load(..., process=True)`로 읽어야 모서리 위상이 생긴다(안 그러면 Triangle이 중복점으로 segfault).
- conda/miniforge의 3.13·3.14가 PATH 앞에 있으면 venv가 범위 밖으로 만들어진다 → setup_wsl.sh가 3.10–3.12를 고른다(`CARDIAC_RECREATE_VENV=1`).
- 임시 폴더 생성이 실패하면 `unzip -d ''`는 현재 폴더(= 저장소)에 푼다. 저장소에 떨어질 수 있는 작업을 mktemp에 의존하지 않는다.
- 오래 걸리는 작업(배치 등)은 `nohup ... &`로 띄우고 로그로 진행을 본다.

## 6. 작업 습관

- 세션 시작: `docs/STATE.md`를 읽는다. 새 기계거나 환경이 의심되면 `/setup-check`.
- 커밋 전: `/guard`. 세션 끝: `/wrap-up`(STATE.md 갱신 → 커밋 → 푸시는 사용자 승인).
- 결과는 수치와 한계를 같이 말한다. 확인하지 않은 것은 확인하지 않았다고 말한다.
