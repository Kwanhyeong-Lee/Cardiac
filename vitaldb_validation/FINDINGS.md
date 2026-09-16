# VitalDB 파일럿 결과 (2026-07-30)

## 코호트 (VitalDB open API, CC BY-NC-SA)
- 전체 6,388 케이스 중
  - **SNUADC/ART (침습 동맥압 파형, 500Hz): 3,645**
  - ART + CO(EV1000/Vigileo) + SV: **964**
  - + CVP까지: **531**  (SVR 계산 가능)
  - Vigilance(열희석 PAC) CO: 65 / ESV: 49  ← 진짜 독립 gold standard, 소수
- ART+CO+SV 코호트: 나이 57.9±15.4, **성인 98.3%**, 수술과 general/thoracic
- **비-ICU 수술환자** → 원고의 "ICU population bias" 한계를 직접 해소

## ✅ 신뢰성 있게 얻을 수 있는 것 (환자별)
| 항목 | 방법 | 파일럿 값(n=8) |
|---|---|---|
| R_tot | (MAP−CVP)/CO | 0.64–1.72 mmHg·s/mL |
| C | pulse-pressure법 SV/PP | **0.78–1.52 mL/mmHg** |
| MAP / PP | 파형 | 66–103 / 45–71 mmHg |
| HR | 파형 beat detection | 52–86 bpm |
| Ea, SW | Pes=0.9·SBP, SW=Pes·SV | 환자별 산출 가능 |

**중요:** 실측 C는 **0.78–1.52**로, 원고의 대표값 **1.75(건강 성인)** 가 수술/중증 환자에
비현실적이라는 지적이 **데이터로 확인**됨. → 대표 1케이스를 실제 코호트 분포로 교체해야 함.

## ❌ 신뢰성 있게 얻을 수 없는 것 — Zc(R1) 분리
3-element WK 분해에는 확산기 감쇠 시상수 τ=R2·C가 필요한데:
- 관측된 확산기 길이 ≈ **0.48 s**
- R2≈0.9·R_tot 가정 시 필요한 τ ≈ **1.03 s**
- **비율 0.40** → 시상수보다 짧은 창에서 지수 감쇠를 적합 → τ가 구조적으로 과소추정
- 결과: R1이 R_tot의 40~57%로 비생리학적(정상 5~10%)
- 2-param/3-param(P∞ 자유) 둘 다 동일 → **코드 문제가 아니라 방법의 한계**

**함의:** r_diss는 이 데이터로 *측정*할 수 없고, Zc 기반 **보정(calibration) 가정**으로
남는다. 이는 원고에 **정직한 한계**로 기술해야 하며, 동시에 "왜 r_diss를 자유롭게
적합하지 않고 고정했는가"에 대한 근거가 된다.

## 권고 사용법
1. 대표 1케이스 → **VitalDB 코호트 분포**(R_tot, C, MAP, PP, SV, Ea, SW)로 교체
2. "비-ICU 일반화" 근거로 사용 (ICU 편향 한계 해소)
3. Zc/r_diss는 **가정임을 명시**하고, 파형만으로 분리 불가함을 한계로 기술
4. 진짜 독립 검증이 필요하면 **Vigilance(열희석) 65케이스** 서브셋 사용

## 전체 실행 (로컬/WSL 권장)
```bash
pip install vitaldb
cd "/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/vitaldb_validation"
python3 build_cohort.py        # 964 케이스 CO/SV/CVP 수집
python3 vitaldb_wk.py 964 0    # 파형 분석 (케이스당 ~5초)
```
