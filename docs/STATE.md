# STATE — 지금 어디까지 왔나

두 기계(alex0 / wjsdm)가 공유하는 유일한 상태 기록. 세션 시작 때 읽고, 끝날 때 `/wrap-up`이 갱신한다. 짧게, 최신이 위로.

마지막 갱신: **2026-10-05**, Cowork → Claude Code 이관 때 작성 (이전 기록: `docs/HANDOFF_FROM_COWORK_2026-10-05.md`).

## 현재 상태

| 트랙 | 상태 | 다음 한 걸음 |
|---|---|---|
| **GPU 기계 셋업** (wjsdm) | torch+CUDA·PINN READY. venv가 miniforge Python 3.14로 만들어져 `triangle` 미설치. MM-WHS `ct_train`과 1009 형상 팩은 아직 그 기계에 없음 | ① `CARDIAC_RECREATE_VENV=1 bash tools/setup/setup_wsl.sh` ② 사용자가 OneDrive 웹에서 `PINN heart/MM-WHS/ct_train` 폴더와 `_handover/sync_2026-09-17/sync_assets_2026-09-17.zip`을 Downloads로 → `bash tools/setup/unpack_transfer.sh /mnt/c/Users/wjsdm/Downloads --unreal` ③ `/setup-check` |
| **형상 파이프라인** | 1–31단계 완료(1009 전체, 1001 전 단계 검증). 20례 배치는 아직 | GPU 기계에서 `/batch` |
| **PINN GPU** | gpu_smoke로 프로젝트 모델 합성 학습 확인(샌드박스 CPU 예행). GPU 실학습은 아직 | `/pinn-gpu` |
| **Unreal HeartTeach** | C++ 모듈·에디터 Python·SPEC 초안. 빌드해 본 적 없음. UE·VS 미설치 | 사용자가 UE 5.4+와 VS2022(C++ 워크로드) 설치 → `/unreal-m1` |
| **Paper B** | 실험 완료, 결론 동결, 본문 집필 남음 | 변화 없음 |
| **실물 출력** | 아무것도 출력하지 않음 | `fusion_ready/EDUCATION_PACK.md` 항목 2′(4방 절개 반절)부터 |

## 열린 문제

- `pinn_hamiltonian_v5.DrugPerturbationSimulator.simulate()` — `torch.no_grad()` 안에서 모델을 부르는데 `forward()`가 ∂H/∂q를 autograd로 계산하므로
  모든 장치에서 실패한다. 고치면 다음으로 `dq`/`dp`가 CPU에 생성돼 GPU에서 실패한다. 수정안은 `tools/setup/TASK_PINN_GPU.md` — **사용자 승인 대기**.
- 1009 관상동맥: 나무 밖 밝은 관형 후보 3개(HU 413–424, 좌심방 부근) 미확정. PDA 미확인 → 우세형 미확정("좌우세 의심").
- Unreal C++은 UE 헤더 없이 쓴 초안 — 첫 빌드에서 컴파일 수정이 나올 것(`SPEC.md` 7절에 깨질 만한 API 목록).
- 팬텀 코어를 CT 혈액풀(1.5 mm closing)로 교체 — 미착수.
- IVC·대동맥궁을 TotalSegmentator로 채우기 — 미착수.

## 최근 결정 (사용자)

- 2026-10-05: 10월 6일부터 모든 작업을 Claude Code로, 모델은 Opus 5.5.
- 2026-09-30: GitHub 클라우드 실행 대신 3060 기계 로컬 실행을 유지(데이터가 기계 밖으로 나가면 안 되므로). CI 워크플로는 만들지 않기로.
- 2026-09-29: 3060 기계(wjsdm)에서 형상 배치·PINN GPU·Unreal 셋 다. 그 기계엔 OneDrive가 없으므로 코드는 git, 데이터는 드라이브/OneDrive 웹.
- 2026-09-17: Unreal은 데스크톱 앱(VR·웹 아님), 에셋 팩 먼저 → C++·에디터 Python 전부 작성까지.
