# ECG 통합 — 실행 런북 (Windows PowerShell)

> 2026-07-07. 목적: 심장 트윈을 **ECG 물리정보 prior로 보강**하는 파이프라인을 별도
> PowerShell 터미널에서 실행. 설계 근거: `ECG_AUGMENTATION_DESIGN.md`.
> 원칙: config 기반 · 단계별 QC 게이트 · resumable · **데이터 pull을 명확한 gate로 분리**.

## 0. 전체 흐름
```
[준비: 환경] → [★ 당신이 직접: PhysioNet에서 MIMIC-IV-ECG pull] → [config 채움]
   → Stage1 링크 → Stage2 지표추출 → Stage3 병합/QC → Stage4 식별성 ablation
```
Stage 0(환경점검)·스크립트 준비는 **데이터 없이도 지금 가능**. 실제 산출은 pull 이후.

## 1. 환경 준비 (지금 가능)
```powershell
# 프로젝트/ecg_integration 폴더에서
python --version                     # 3.10+ 확인
python -m pip install pandas numpy scipy scikit-learn
python -m pip install wfdb neurokit2 matplotlib   # 파형지표(선택, 대용량 파형 계산 시)
# 환경·경로 점검 (ecg_root 미설정 경고는 정상)
powershell -ExecutionPolicy Bypass -File .\run_ecg_pipeline.ps1 -Stage 0
```

## 2. ★ 데이터 pull (당신이 직접 — credentialed access 필요)
MIMIC-IV-ECG (12-lead, ~90GB). PhysioNet 계정 + 데이터 사용 동의 필요.
- 페이지: https://physionet.org/content/mimic-iv-ecg/
- **핵심 파일**: `record_list.csv`, `machine_measurements.csv`(QRS·QT·QTc·축 이미 계산됨!), `files/`(파형 .hea/.dat).

**옵션 A — wget (Windows용 wget 또는 WSL/Git-Bash에서):**
```bash
wget -r -N -c -np --user <PhysioNet_ID> --ask-password \
  https://physionet.org/files/mimic-iv-ecg/1.0/
```
**옵션 B — wfdb 파이썬(부분 다운로드 가능):**
```python
import wfdb; wfdb.dl_database('mimic-iv-ecg', dl_dir=r'D:\data\mimic-iv-ecg')
```
> 팁: 초기엔 `machine_measurements.csv` + `record_list.csv`만으로도 Stage 1~4의
> 대부분(QRS/QTc/AF)이 돌아감. 파형(files/)은 LVH voltage·PTFV1 계산 때만 필요 →
> 용량·시간 아끼려면 나중에.

다운로드 후 **`config.json`의 `paths.ecg_root`** 를 그 폴더로 채우기.

## 3. 파이프라인 실행 (pull 이후)
```powershell
# 전체
powershell -ExecutionPolicy Bypass -File .\run_ecg_pipeline.ps1 -Stage all
# 또는 단계별
... -Stage 1   # 코호트 링크 → out/matched_echo_ecg.csv
... -Stage 2   # ECG 지표    → out/ecg_features.csv (결측률 로그)
... -Stage 3   # 병합/QC     → out/cohort_echo_ecg.csv + out/merge_qc.json
... -Stage 4   # 식별성 ablation → out/ablation_identifiability.json
```
`resume=true`(config)라 완료 단계는 자동 스킵. 재실행하려면 `out/.NN_*.done` 삭제 또는 resume=false.

## 4. 각 단계 QC 게이트 (통과 기준)
| 단계 | 산출 | 통과 기준 | 실패 시 |
|---|---|---|---|
| 1 링크 | matched_echo_ecg.csv | 매칭률 ≥20%, gap median 합리 | window_hours↑ / 시간컬럼 확인 |
| 2 지표 | ecg_features.csv | QRS/QTc 결측 <50% | machine_measurements 키(study_id) 확인 |
| 3 병합 | merge_qc.json | ECG 커버리지 ≥30% | 병합키(measurement_id/subject_id) 점검 |
| 4 ablation | ablation_identifiability.json | echo+ECG의 pred_std↓ (식별성↑) | feature set·타깃 컬럼명 확인 |

## 5. 지표 → 파라미터 매핑 (설계 근거 요약)
- QRS duration → efficiency/Ees (dyssynchrony), QTc → 재분극/약물,
  Sokolow/Cornell LVH → Eed(확장기 강성), PTFV1 → LA압/E-e′, AF → LAA(E1c).
- 상세·문헌: `ECG_AUGMENTATION_DESIGN.md`.

## 6. 다음(논문용, 데이터 확보 후)
- Stage 4 proxy 대신 **`pinn_hamiltonian_v5` 학습에 두 feature set(echo_only vs echo+ecg) 적용**
  → Eed·efficiency·V0 recovery RMSE·CI폭 비교(B3 식별성 정면돌파).
- 헤드라인: "ECG 물리정보 prior가 echo-underdetermined 파라미터 식별성 개선".

## 7. 파일 구성
```
ecg_integration/
├── config.json                     ← 경로/파라미터 (먼저 채움)
├── pipelib.py                      ← 공유 유틸
├── 00_env_check.py                 ← 환경/경로 점검
├── 01_link_cohort.py               ← echo↔ECG 시간창 링크
├── 02_extract_ecg_features.py      ← machine_meas + 파형 + AF
├── 03_merge_and_qc.py              ← PINN 코호트 병합 + QC
├── 04_ablation_identifiability.py  ← echo-only vs echo+ECG (proxy)
├── run_ecg_pipeline.ps1            ← PowerShell 오케스트레이터
└── out/                            ← 산출물(자동 생성)
```
