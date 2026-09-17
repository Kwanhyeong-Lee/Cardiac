# HANDOVER — cardiac pH-PINN workbench (2026-09-16)

이 문서 하나로 새 컴퓨터(또는 새 사람)가 프로젝트를 이어받을 수 있어야 한다. 무엇이 어디에 있고,
어디까지 됐고, 무엇이 남았고, 어디를 밟으면 넘어지는지. 코드는 이 저장소에, 데이터는 저장소 밖에.

## 0. 30초 요약

한 사람의 프로젝트가 세 갈래로 자랐다.

| 갈래 | 한 줄 | 상태 | 진입점 |
|---|---|---|---|
| **A. pH-PINN 심장 디지털 트윈** (Paper A) | MIMIC·EchoNet·UCI로 검증한 port-Hamiltonian PINN, Ees/에너지 추정 | 원고 완성, 별도 공개 저장소 `Kwanhyeong-Lee/pH-PINN-cardiac` | 루트 `pinn_cardiac.py`, `calibrated_pinn.py`, `PINN_Cardiac_Ees_Manuscript_CMBM_Final.docx`, `manuscript/` |
| **B. 구조 제약의 가치 벤치마크** (Paper B) | "아키텍처 제약은 공짜·실재·정확히 그 범위까지; 매개변수화가 부과보다 중요" — MIMIC + eICU + INSPIRE (+VitalDB), 5 과제 | 실험 종료, 결과 v1–v10 문서화, 개요 v2. **집필 남음.** 목표 TMLR | `waveform_pinn/PAPER_B_OUTLINE.md` → `RESULTS_v*.md` → `models.py` |
| **C. 환자 형상 → 프린트·팬텀·CFD** | MM-WHS case 1009에서 수밀 솔리드·절개 모형·lost-core 실리콘 팬텀·CFD 도메인 | 16단계 파이프라인 완성, **v4(환자 내부)** 산출. **실물 출력은 아직.** | `fusion_ready/PIPELINE.md`, `fusion_ready/METHODS_DRAFT.md` |
| (D) CFD 케이스 | OpenFOAM pimpleFoam, 라벨 형상 + 윈드케셀 | patient/anatomical 케이스 실행 완료(결과 JSON/PNG 보존, 필드 데이터는 제외) | `lv_cfd_patient/run_patient_cfd.sh` |

## 1. 저장소 구조

레이아웃은 원본 폴더를 **그대로** 옮긴 것이다(상대 경로를 깨지 않기 위해). 루트가 평평하고 파일이 많다 —
정리하고 싶으면 §9의 제안을 보되, 먼저 돌아가는 것을 확인한 뒤에.

```
.
├── HANDOVER.md                 ← 이 문서 (색인)
├── README.md                   ← 짧은 소개 + 이 문서로 링크
├── GIT_SETUP.md, .gitignore    ← 무엇을 커밋하면 안 되는지
├── *.py *.sh *.js *.sql        ← Paper A 파이프라인·데이터 추출·문서 빌더 (루트, 평평함)
├── *.json                      ← Paper A/3 결과·요약 (집계값만; 환자 단위 없음)
├── *.md                        ← 로드맵·상태 문서 (ROADMAP_INDEX.md 부터)
├── *.png, *.html               ← 논문 그림, 3D 뷰어
├── manuscript/                 ← JBHI 투고 자료, LaTeX zip, R 스크립트, QA 기록
├── waveform_pinn/              ← Paper B 전체 (코드 19 + 문서 21). CSV(환자 파생)는 제외됨
├── fusion_ready/               ← 갈래 C 전체. STL/npz/blend 제외됨 — PIPELINE.md로 재생성
│   ├── PIPELINE.md, METHODS_DRAFT.md, FINDINGS.md, README.md
│   ├── *.py (16단계), *.json (각 단계 판정), *.png (검증 그림)
│   ├── BLENDER_OUT/*.json, *.png     PHANTOM/*.json, cfd/*.json, *.txt     CT/*.json
├── lv_cfd/, lv_cfd_patient/, lv_cfd_anatomical/, lv_cfd_anatomical_v2_configs/
│   └── system/, constant/*Dict, 0/, run*.sh, postprocess*.py, 결과 json/png  (폴리메시·시간 디렉토리 제외)
├── external_datasets/DATASET_REGISTRY.md   ← 공개 데이터 출처 목록 (데이터 자체는 제외)
├── heart_failure_clinical_records.csv      ← UCI 공개 데이터 (루트 스크립트 4개가 읽음). 유일하게 포함된 CSV
└── package.json                             ← 문서 빌더(docx-js)용
```

## 2. 갈래별 상태

### A. Paper A — pH-PINN cardiac digital twin
- 공개 재현 패키지: https://github.com/Kwanhyeong-Lee/pH-PINN-cardiac (이 저장소에는 **포함하지 않음** — 중첩 저장소가 되므로. 필요하면 옆에 따로 clone).
- 루트의 `pinn_cardiac.py`, `PINN_cardiac_true.py`, `calibrated_pinn.py`, `pinn_hamiltonian_v5.py`, `echonet_experiment.py`, `hfpef_analysis.py`, `ees_validation.py`, `noise_robustness_clinical.py`, `ef_matched_analysis.py`, `quality_enhancement.py`, `mimic_validation_pipeline.py`, `external_validation.py`, `pig_edpvr_validation.py`, `windkessel_phpinn_bridge.py`가 실험 코드. 결과는 같은 이름의 `*_results.json`, `*_metrics.json`.
- 원고: `PINN_Cardiac_Ees_Manuscript_CMBM_Final.docx`(루트), JBHI 판은 `manuscript/`(`pH_PINN_JBHI_*`, `REVISION_PLAN.md`, `CRITICAL_AUDIT_2026-07-30.md`). 투고 상태는 `manuscript/pH_PINN_JBHI_SUBMISSION_CHECKLIST.md`를 믿을 것.
- 원고 버전 시리즈(v2–v11, 총 ~45 MB)는 저장소 밖 아카이브(§8).

### B. Paper B — `waveform_pinn/`
- 읽는 순서: `PAPER_B_OUTLINE.md`(v2, 8개 기여) → `SUMMARY.md` → `RESULTS_v6_capacity_match.md`, `RESULTS_v7_port_rollout.md`, `RESULTS_v8_inspire.md`, `RESULTS_v9_H1_sample_efficiency.md`, `RESULTS_v10_H2_downstream.md` → `PROTOCOL.md`, `PROTOCOL_v2_benefit.md`(사전 등록된 판정 규칙) → `DISCARDED.md`(버린 것과 이유).
- 모델: `models.py` — A(hard) / B(MLP) / C(no structure) / D(soft penalty) / E(출력 제약, 결함 발견) / E2(용량 일치) / E3(고정 역표준화로 진짜 아키텍처 보장); 동역학 P(LLᵀ) / Pm(diag softplus, 성장 차수 일치 대조군) / U / F.
- 확정된 결론(바꾸지 말 것, 바꾸려면 새 사전 등록으로): 제약은 전체 데이터에서 공짜(정확도 동일), 데이터가 적을 때는 **더 나쁨**(H1 역효과), 임상 하류 가치 증분 없음(H2 기각), 수동성 위반 0/106,007 이동 스텝(정확), 시뮬레이터 유계성은 제약이 아니라 **매개변수화**가 결정(Pm 대조군). 그래서 "물리 제약이 더 믿을 만하다"는 논문은 쓸 수 없고, 범위를 정확히 밝히는 논문을 쓴다. 목표지는 TMLR(JBHI는 임상 증분이 없어 부적합 — 이미 확인한 판단).
- 데이터: MIMIC-IV 파형, eICU, INSPIRE v1.4.2(zip), VitalDB. 추출 코드 `extract_*.py`, `inspire_extract.py`, `build_cohort4.py`. **추출된 CSV 8개는 환자 단위라 저장소에 없다** — 데이터가 있는 PC에서 재추출(§3).
- 남은 것: 본문 집필, 그림 최종본(`make_figures_v2.py`가 FigB4·B5까지 만듦), 부록에 H1/H2 기각을 있는 그대로.

### C. 형상 파이프라인 — `fusion_ready/`
- `PIPELINE.md`가 16단계 표(입력→출력→검증 기록→실행 환경). `METHODS_DRAFT.md`가 논문용 Methods 골격 + Limitations.
- 핵심 사실: 원본 메시 16개는 단위(m/mm)와 프레임 4개가 섞여 있었고 **frame A만 일관**; `cardiac_meshes/`는 **좌우 거울상**(X 반사 0.044 mm, 비대칭 랜드마크 검사 3/3 위반); 판막 생성기는 LV 축이 60° 틀어져 있었고 시트는 두께 0; 라벨 500은 유두근·육주를 삼켰음(15–18 mL) → **원본 CT로 재분할해서 회수**(영상→frame A 평행이동만, 0.19 mm).
- 산출물(재생성 가능, 저장소엔 없음): `BLENDER_OUT/hollow_ventricle_v4_CT.stl`(권장 — 벽·내막·육주·유두근 = 환자; 첨판·판·건삭 경로 = 파라메트릭), 절개 모형 A/B, `PHANTOM/`(lost-core 코어 + 주형 상자, 포트 Ø19/Ø15.8), `PHANTOM/cfd/`(inlet/outlet/LV 패치, m 단위).
- **2026-09-17 추가**: (1) **관상동맥** — 원본 CT(동맥기 CTA)에서 자체 Frangi + 이중 문턱 + 골격 그래프 가지치기로 LM/LAD/LCx/RCA 근위–중간부 추출 (`ct_coronary_*.py` → `CT/coronary/`, PIPELINE 18단계; 신뢰 구간은 CPR·단면 그림으로 표시). (2) **표면 품질** — 이진 마스크 대신 연속 필드 등위면(`ct_hires_lv.py`, PIPELINE 19단계) → 부품 거칠기 1/3, 노이즈 섬 790개 제거 → **v5** `hollow_ventricle_v5_CT_hires.stl`이 권장 조립. (3) SimVascular 0단계(`SV/*.vtp`, 로드맵), 쇼케이스 렌더, 사업성 모델 `business/`, 친구 공유용 `share/`. (4) **관류 영역 지도**(20단계), **N례 일반화**(`case_paths.py`, `CASE=<id>`; 21단계), **전심장+관상동맥 교육 모형**(22단계), **배치 실행기** `batch_cases.py`(23단계; 1001 검증), **대혈관 CT 연장**(24단계), **속 빈 전심장 + 4방 절개**(25단계) → **리마스터 v2 + 부위별 분할 16종 + 삼첨·폐동맥판 + 관상동맥 누락 점검**(26–28단계, `CT/whole_heart_hollow/`, `parts_manifest.json`, `CT/coronary/coronary_checklist.md`). 교육 키트 목록·말할 문장·1차 범위: `fusion_ready/EDUCATION_PACK.md`.
- 남은 것: 팬텀 코어를 CT 혈액풀(1.5 mm closing)로 교체, **실물 출력·주형·계측**(아직 아무것도 출력 안 함), 판막은 4D CT 없이는 더 못 감.

### D. CFD
- `lv_cfd_patient/`: 라벨 형상, pimpleFoam, 윈드케셀 결과 `cfd_windkessel_results.json`, `ph_pinn_mapping.py`(CFD↔pH-PINN 파라미터 연결). 유입면을 blockMesh 윗면 박스로 잘라 만든 탓에 면적 8.23 cm²/속도 0.34배 스케일 — 팬텀 도메인(`fusion_ready/PHANTOM/cfd/`)이 이 문제를 없앤 대체 형상.
- `lv_cfd_anatomical/`: t = 2.4 s까지 실행됨(시간 디렉토리는 제외, `postprocess_analysis.py`·`geometry_metadata.json` 보존). `lv_cfd_v2/`(3.3 GB 결과)는 통째로 제외 — 재실행 스크립트 `lv_cfd_anatomical_v2_configs/rerun_cfd_v2_robust.sh`.

## 3. 데이터 — 저장소 밖, 어디에 무엇을

| 데이터 | 자격 | 새 PC 위치 제안 | 쓰는 코드 |
|---|---|---|---|
| MIMIC-IV (+ waveform) 40 GB | PhysioNet credentialing + DUA | `D:\data\MIMIC IV\` | 루트 `mimic_*.py`, `*.sql`, `waveform_pinn/extract_*.py` |
| eICU | PhysioNet DUA (BigQuery 쿼리 `eicu_*.sql`) | `D:\data\eicu\` | `eicu_drug_response*.py`, `waveform_pinn/port_rollout.py` |
| INSPIRE v1.4.2 zip | PhysioNet DUA + CITI | `D:\data\INSPIRE\` | `waveform_pinn/inspire_extract.py`, `h2_downstream.py` |
| VitalDB | 등록·동의 | `D:\data\vitaldb\` | `waveform_pinn/build_cohort4.py` |
| MM-WHS CT/MR (nii.gz) 5.3 GB | 연구용 등록, 재배포 금지 | `D:\data\MM-WHS\` | `fusion_ready/ct_refine_lv.py`, `extract_rv_totalseg.py` |
| PIC (paediatric ICU) zip 383 MB | PhysioNet DUA | `D:\data\PIC\` | (탐색만, 코드 의존 없음) |
| 공개 동물·PV-loop 데이터 (`external_data/`) | 공개(Dryad 등) | `D:\data\external\` | `pig_edpvr_validation.py`, `multi_animal_*` |
| 파생 메시 `cardiac_meshes*/`, `lv_cfd_anatomical/constant/triSurface/` | MM-WHS 파생 | 재생성 또는 SSD | `fusion_ready/normalise_assembly.py` |

**절대 규칙**: 위 데이터와 그 파생 환자 단위 파일(`mimic_*.csv`, `wave_windows_*.csv`, `inspire_traj.csv`, `eicu_*.csv` 등)은
private 저장소에도 올리지 않는다. `.gitignore`가 막고 있지만 규칙은 사람이 지킨다. 커밋 전:
`git ls-files | Select-String -Pattern "\.(csv|parquet|nii|gz|zip|stl|glb|npz)$"` → 허용 목록(UCI csv, synth csv, mitral_flow_profile.csv, LaTeX zip)만 나와야 한다.

**하드코딩 경로 — 환경변수로 이전 완료** (2026-09-16). 이전 샌드박스(`/sessions/...`)·WSL(`/mnt/c/Users/alex0/OneDrive/...`)
절대경로는 코드에서 전부 없앴다. 규칙은 환경변수 3개뿐이고, **전부 기본값이 있어서 아무것도 설정하지 않아도 저장소 안에서 그대로 돌아간다.**

| 환경변수 | 기본값 | 무엇 |
|---|---|---|
| `CARDIAC_DATA` | `D:\data` (WSL 셸에서는 `/mnt/d/data`) | 저장소 밖 원자료 루트 — MM-WHS, INSPIRE zip, 공개 데이터 내려받을 곳 |
| `CARDIAC_OUT` | 그 스크립트가 있는 폴더(= 저장소 루트) | 그림·결과 CSV를 쓰고 읽는 곳 |
| `CARDIAC_REPO` | 스크립트 위치에서 유도 | 저장소 루트 (WSL 셸 스크립트가 저장소를 찾을 때) |

고친 파일 16개:

- 루트 파이썬 9개 — `calibrated_pinn.py`, `echonet_experiment.py`, `ef_matched_analysis.py`, `hfpef_analysis.py`,
  `quality_enhancement.py`, `ees_validation.py`, `noise_robustness_clinical.py`, `pinn_cardiac.py`, `PINN_cardiac_true.py`.
  전부 `OUT = os.environ.get("CARDIAC_OUT", 이 파일이 있는 폴더)`를 쓰고, 그림·CSV와 `heart_failure_clinical_records.csv`를
  `os.path.join(OUT, ...)`로 읽고 쓴다.
- `fusion_ready/ct_refine_lv.py` — MM-WHS CT (`$CARDIAC_DATA\MM-WHS\ct_train`).
- `waveform_pinn/inspire_extract.py`, `waveform_pinn/h2_downstream.py` — INSPIRE zip (`$CARDIAC_DATA\INSPIRE\...`).
- 셸 4개 — `download_all_datasets.sh`(내려받을 곳), `setup_samsung_notebook.sh`(안내 문구),
  `sync_wsl_to_onedrive.sh`·`lv_cfd_anatomical_v2_configs/rerun_simulation.sh`(저장소 루트를 스크립트 위치에서 유도).
  뒤 두 개는 이제 OneDrive가 아니라 저장소로 복사한다 — 변수 이름도 `REPO_BASE`/`REPO`로 바꿨다.

원고 빌더 7개도 같은 규칙으로 고쳤다.

- `waveform_pinn/manuscripts/build_paper{A,B}.js` — `BASE`를 스크립트 위치에서 유도, `CARDIAC_OUT`으로 덮어쓴다.
  그림 18개가 `waveform_pinn/figures/`에 있어 설정 없이 빌드된다.
- `build_v7.js`–`build_v11.js` — `OUT_DIR = process.env.CARDIAC_OUT || __dirname`(= 저장소 루트)에서 그림을 읽고
  docx를 쓴다. 참조하는 그림 PNG는 전부 저장소 루트에 있다(v7 13개, v8·v9 15개, v10·v11 6개). v10·v11에 있던
  두 번째 쓰기(`.../mnt/outputs/`, 샌드박스 전용 마운트)는 지웠다.

빌드하려면 `npm install docx` (node_modules는 저장소에서 제외).

문서 6개(`CARDIAC_DIGITAL_TWIN_STATUS.md`, `CFD_소프트웨어_설치가이드.md`, `ablation_patient_level/RUN_ME.md`,
`manuscript/pH_PINN_JBHI_GITHUB_PUSH.md`, `vitaldb_validation/FINDINGS.md`, `waveform_pinn/DESIGN.md`)에 있던
복사해 쓰는 명령줄의 옛 WSL 경로도 `/mnt/c/work/Cardiac`(MM-WHS는 `$CARDIAC_DATA`) 기준으로 고쳤다.
**결과: 코드·문서를 통틀어 옛 절대경로는 이 문단의 설명 외에 남아 있지 않다.**

## 4. 새 PC 세팅 (RTX 3060 12 GB / 32 GB RAM / RX 5700)

```powershell
git clone <bundle 또는 원격> C:\work\Cardiac      # OneDrive 밖!
cd C:\work\Cardiac
py -3.11 -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
python -c "import torch;print(torch.cuda.get_device_name(0))"       # 'NVIDIA GeForce RTX 3060' 이어야 함
```
- **RX 5700은 CUDA 불가**, Windows ROCm도 Navi10 미지원 → 디스플레이용. `CUDA_VISIBLE_DEVICES`가 3060을 가리키는지만 확인.
- **형상 파이프라인 파이썬 패키지**: `numpy scipy scikit-image nibabel trimesh networkx manifold3d pymeshfix matplotlib` (필수) + **`triangle`**(선택 — 29단계 절단면 재삼각분할용. 없으면 절단면만 예전 부채꼴 뚜껑으로 남고 나머지는 동일).
- **Unreal Engine 5.4+ (RTX 3060 PC 전용)**: 교육 앱 `fusion_ready/UNREAL/HeartTeach/`. Visual Studio 2022 C++ 워크로드 필요. 빌드 절차는 `_handover/sync_2026-09-17/UNREAL_TASK.md`, 설계는 `UNREAL/HeartTeach/SPEC.md`. 엔진이 만드는 디렉터리는 `.gitignore`에 있음.
- **Blender 5.2**(갈래 C 5단계): `fusion_ready/run_blender_pipeline.bat`.
- **OpenFOAM**: WSL2 Ubuntu + `openfoam2312`; 케이스는 WSL 파일시스템(`~/cases/`)에 복사해서 돌릴 것(OneDrive/NTFS 마운트 위에서 돌리면 느리고 락 문제).
- **Fusion 360**: `fusion_ready/CAD/`, `PHANTOM/*.stl` 임포트. 로컬 MCP(포트 7654)는 add-in의 POST 전용 API라 표준 MCP 클라이언트로는 안 붙었다(`fusion_ready/MCP_CONNECT.md`).
- 32 GB RAM에서는 이 세션의 OOM 우회(SDF 격자, 파트별 contains, EDT closing)가 필요 없지만 코드는 그대로 돌아간다.

**연기 테스트(각 갈래 5분)**
```
python fusion_ready/build_sdf_grid.py                # C: 30초, lv_sdf_grid.npz 생성 (PRINT/ 필요 → 먼저 1–2단계)
python waveform_pinn/capacity_match.py --help        # B: 임포트 확인 (데이터 없이)
python pinn_cardiac.py                               # A: UCI csv만으로 도는 부분이 있음
```

## 5. 핵심 결정과 근거 (짧게 — 상세는 링크)

| 결정 | 근거 | 기록 |
|---|---|---|
| Paper B는 "제약이 더 믿을 만하다"가 아니라 "보장의 정확한 범위"를 쓴다 | 무제약 모델도 실제 분포 이동에서 위반 0; 유계성은 매개변수화가 결정 | `waveform_pinn/PAPER_B_OUTLINE.md` §framing |
| E→E2→E3 | E의 양수성은 학습된 오프셋에서 왔고 참값 13–15%를 표현 못 함 | `RESULTS_v6_capacity_match.md` |
| Pm 대조군 도입, "제약이 유계성 해침" 철회 | R=LLᵀ의 2차 성장이 원인 | `RESULTS_v7_port_rollout.md` |
| H1/H2 기각을 그대로 보고 | 사전 등록 임계값을 사후에 옮기지 않음 | `PROTOCOL_v2_benefit.md`, `RESULTS_v9`, `v10` |
| 형상은 frame A만 신뢰 | 4 프레임·단위 혼재, STACOM 정합 RMS 28 mm | `fusion_ready/MANIFEST.json`, `README.md` |
| `cardiac_meshes/`는 거울상, frame A가 옳음 | 비대칭 랜드마크 검사 3/3 위반, 대칭 검사 2/2 통과 | `fusion_ready/FINDINGS.md` §3 |
| 판막을 방사형 칼라가 아니라 방실면 **판**으로 고정 | 판륜 옆에 근육이 없음(36방향 중 28) | `make_av_plate.py` docstring, `av_plate.json` |
| frame B 유두근 폐기, CT 재분할로 환자 유두근 회수 | 6-DOF 정합이 모든 게이트 동시 위반; CT에 17.8 mL 근육 존재 | `pm_registration.json`, `CT/ct_refine.json` |
| 팬텀은 2분할 음각이 아니라 lost-core | 유동 팬텀은 공동이 필요 | `make_flow_phantom_mold.py` docstring |

## 6. 함정 (이미 한 번씩 넘어진 것)

1. `trimesh` ray-cast `contains()`/`sample.volume_mesh()`를 큰 메시에 쓰면 메모리 폭발 → SDF 격자 보간(`build_sdf_grid.py`) 또는 작은 파트에만.
2. `VoxelGrid.marching_cubes`/`matrix_to_marching_cubes`는 **복셀 인덱스 좌표**를 돌려준다. 변환을 안 하면 불리언이 조용히 빈 결과를 내고 "없음"으로 오판한다(실제로 그랬음). 컨테인먼트 assert를 남겨뒀다.
3. `Path3D.to_planar()`는 단면마다 다른 2D 원점을 잡는다. 한 그림에 여러 메시를 그리려면 `to_2D`를 공유(`render_sections.py`).
4. `np.False_ is False`는 False다. `bool()`로 감쌀 것.
5. STL은 면마다 법선을 가지므로 `trimesh.load(..., process=False)`로 읽으면 수밀이 아니다 → `process=True` 또는 `merge_vertices(merge_norm=True)`.
6. `scipy.ndimage.binary_closing`에 큰 구조 요소(반경 16복셀)를 주면 MemoryError → 거리변환(EDT) 두 번으로 대체.
7. OneDrive 폴더 안에 `.git`을 두지 말 것. 동기화가 오브젝트를 깨뜨린다.
8. Paper B에서 임계값·게이트를 결과 보고 옮기지 말 것. 옮기고 싶으면 새 PROTOCOL 파일로 사전 등록하고 다시 돌린다.
9. `generate_valves.py`의 `lv_axis=[0,0,-1]` 하드코딩 — 원본 판막 파일은 60° 틀어져 있다. `frame_A_patient/mitral_valve.stl`(v2 승격본)만 쓸 것.
10. CT→frame A는 평행이동 (37.08, −31.48, 159.46) mm. `cardiac_meshes/`→frame A는 X 반사 포함(`BLENDER_OUT/frame_transform.json`). 둘을 섞지 말 것.

## 7. 다음 단계 (우선순위)

0. **20례 배치** — `cd fusion_ready; set CARDIAC_DATA=…\MM-WHS\ct_train; python batch_cases.py` (케이스당 ~5분) → `CT/cases/SUMMARY.md`. 그다음 ASOCA/ImageCAS로 관상동맥 분할 정확도.
1. **Paper B 집필** — 재료는 다 있다. `PAPER_B_OUTLINE.md` v2 구조대로, 그림은 `make_figures_v2.py`.
2. **실물 출력** — 우선순위: 속 빈 전심장 4방 절개 v2 `CT/whole_heart_hollow/whole_heart_hollow_v2_4ch_{A,B}_PRINT_ORIENTED.stl`(부위별 색 출력은 `parts/`) → LV 절개 v5 `hollow_v5_cutaway_{A,B}_PRINT_ORIENTED.stl` → 관상동맥 나무 단독(레진)(절단면 아래), 0.2 mm 레이어, 서포트 필요. 출력물 사진과 실측(벽 두께 캘리퍼)을 `fusion_ready/PRINT_LOG.md`로.
3. **팬텀 코어 CT판** — `make_flow_phantom_mold.py`의 LV 입력을 `CT/lv_bloodpool_CT_smooth.stl`에 1.5 mm closing 적용한 것으로; 캐스팅 가능성(언더컷·기포) 확인 후 PVA 출력.
4. **CFD를 팬텀 도메인으로** — `PHANTOM/cfd/LV_phantom_m.stl` + 스니펫으로 `lv_cfd_patient`의 topoSet 우회를 제거. 팬텀 계측(펌프·압력·도플러)과 같은 경계에서 비교 → Paper B의 "하류 소비자" 논지의 실험적 보강.
5. 하드코딩 경로 정리(§3) → `CARDIAC_DATA` 환경변수. (Claude Code가 PC1에서 진행함 — 새 스크립트 `ct_coronary_*.py`, `ct_hires_lv.py`는 이미 `CARDIAC_DATA`/`CARDIAC_REPO`/`CORO_OUT`을 읽음)
6. (선택) 루트 정리: `paperA/`, `paperB/`(=waveform_pinn), `geometry/`(=fusion_ready), `cfd/`로 이동. 이동 후 `run_all.py`와 상대 경로 재확인.

## 8. 저장소에 없는 것과 있는 곳

`_handover/sync_2026-09-17/` — 번들 이후 생긴 변경(코드·문서 50 파일 + 형상 산출물 16 파일)의 동기화 패키지. `SYNC_TASK.md`대로 `apply_sync.py`를 PC1 저장소에서 실행하면 PC1에서 바뀐 파일과 3-way 병합한다.


`_handover/` 폴더(원본 OneDrive 폴더 안, 저장소 밖)에 세 개를 만들었다:
- `cardiac-phpinn-workbench.bundle` — 이 저장소 전체(히스토리 포함, 544 파일). `git clone 파일.bundle 폴더명`.
- `cardiac-phpinn-workbench_tree.zip` — 같은 내용을 git 없이 푼 것(비상용).
- `handover_assets_geometry.zip` (102 MB, 63 파일) — 저장소에서 뺀 형상 산출물 중 **파이프라인을 6단계부터 재개하는 데 필요한 것 + 최종 프린트 파일**: `BLENDER_OUT/{LV_bloodpool,mitral_valve,aortic_valve,LV_myocardium_frameA}.stl`(Blender 없이 재개 가능), `hollow_ventricle_v4_CT.stl`, v4 절개 A/B, v2, `CT/*_smooth.stl`·유두근·SDF 격자, `frame_A_patient/` 판막·판·건삭, `PRINT/`, `CAD/`, `PHANTOM/`(코어·상자·CFD 패치). 저장소 루트에 그대로 풀면 경로가 맞는다.
- 넣지 않은 것: GLB 뷰어 모델(113 MB), 원고 v2–v11 docx(45 MB), `frameA_print.blend`, `cardiac_meshes*/` — 전부 OneDrive 원본 폴더에 그대로 있다(같은 계정이면 새 PC에서도 동기화됨). 데이터(§3)는 외장 SSD로 직접 복사한다.

## 9. git 운영

- 이 저장소: private, 단일 `main`, LFS 안 씀(큰 파일은 전부 재생성 가능하거나 아카이브). 커밋 단위는 "판정 JSON이 바뀐 실험 하나".
- `pH-PINN-cardiac`는 Paper A 재현 패키지로 별도 유지. 이 저장소에서 Paper A 코드를 바꾸면 그쪽에도 반영할지 그때 판단.
- 데이터 경로는 코드에 넣지 말고 환경변수로. 결과 JSON은 집계값만 커밋(환자 단위 행이 있으면 안 됨).
- 작성자 설정: `git config user.name "Kwanhyeong Lee"`, `git config user.email "kwanhyeong.lee54@gmail.com"` (bundle의 첫 커밋도 이 이름).
