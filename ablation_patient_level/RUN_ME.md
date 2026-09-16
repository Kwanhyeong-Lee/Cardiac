# 환자 단위(patient-level) ablation 재실행

## 왜?
기존 ablation은 `train_test_split`(행 단위)이라 같은 환자가 train/test에 동시에 들어감.
데이터: 5,851행 / subject_id 4,241명 = **1.38행/환자** → data leakage 실재.
이 스크립트는 `GroupShuffleSplit(groups=subject_id)`로 **환자를 완전히 분리**한다.

## 실행 (WSL)
```bash
cd "/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/ablation_patient_level"
for L in A B C D; do for S in 0 1 2; do python3 run_ablation_patient.py $L $S; done; done
```
- 필요 패키지: torch, numpy, pandas, scikit-learn
- 모델 1개당 약 20~60초, 총 12회
- 결과: 같은 폴더에 `pat_<모델>_<시드>.json` 12개 생성
- 각 실행이 `patient leakage!` assert를 통과해야 정상

## 결과 확인
```bash
python3 - <<'PY'
import json,glob,statistics as st
for L in "ABCD":
    f=[json.load(open(p)) for p in sorted(glob.glob(f"pat_{L}_*.json"))]
    if not f: continue
    r=[x["mean_r2_all"] for x in f]
    print(f"{L}: R2={st.mean(r):.4f}±{(st.stdev(r) if len(r)>1 else 0):.4f} "
          f"Tneg={st.mean([x['T_neg'] for x in f]):.0f} "
          f"Vneg={st.mean([x['V_neg'] for x in f]):.0f} "
          f"PSD={st.mean([x['R_PSD_viol'] for x in f]):.0f} "
          f"(test patients={f[0]['n_test_patients']})")
PY
```
그 12개 JSON(또는 위 출력)을 나에게 주면 표 I·Fig.2·본문을 갱신한다.
