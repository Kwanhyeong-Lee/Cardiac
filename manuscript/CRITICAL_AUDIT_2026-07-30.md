# 코드 대조 감사 결과 — 제출 보류 권고
검증 방법: 원고 서술 ↔ 실제 실행 코드/결과 JSON 1:1 대조 (추측 아님)

## ✅ 먼저: 이 연구는 실재합니다 (날조 아님)
- `pinn_hamiltonian_v5.py`, `ablation_models.py`, `windkessel_phpinn_bridge.py`, `eicu_validation.py` 등 실제 코드 존재
- 논문의 모든 수치가 결과 JSON에서 재현됨 (예: E_diss 137.1 = 코드 계산 137.14)
- ablation R²는 seed별 원시 float 존재(0.9737059428141668 등) → 타이핑된 숫자 아님
→ "AI가 지어낸 가짜 논문" 혐의는 **사실이 아님**. 단, 아래 과학적 결함은 진짜.

---
## 🔴 반드시 고쳐야 할 결함 3건

### 1. E_diss (식 8) 차원 불일치 — 헤드라인 수치에 영향
코드(windkessel_phpinn_bridge.py:164-165):
    mean_P_sys = (Pes + 0.5*Ea*SV)/2      # = 76.25 mmHg
    E_diss = r_diss * SV * mean_P_sys      # = 137.14
차원: [mmHg·s/mL]×[mL]×[mmHg] = **mmHg²·s** → 에너지(mmHg·mL) 아님.
물리적으로 옳은 형태: E = r_diss·Q̄·SV, Q̄=SV/T_sys → r_diss·SV²/T_sys = **441.7 mmHg·mL**
영향: E_diss=137.1, "2.4% of PVA", net efficiency 62.3%, SW_net=3538 — **전부 재계산 필요**.
(코드와 논문은 일치 → 위조 아님. 그러나 공식 자체가 틀림.)

### 2. Bland–Altman이 검증하는 대상이 pH-PINN이 아님 — 가장 심각
코드(eicu_validation.py:23-35):
    svr_m = eicu['measured_SVR'];  svr_c = eicu['computed_SVR']
    diff = svr_c - svr_m           # 그림 제목도 "SVR Formula Validation"
→ 이건 **대리 공식(computed SVR) vs 카테터 측정치**의 일치도이지, **모델 예측 vs 측정치가 아님**.
그런데 원고는 이를 "the strongest validation evidence"(모델 검증)로 제시.
조치: (a) 서술을 "surrogate formula validation"으로 정정하거나, (b) pH-PINN 예측 SVR로 실제 재분석.
→ 리뷰어가 코드를 요구하면 즉시 드러남. **최우선 수정.**

### 3. Ablation split이 환자 단위가 아님 (leakage 가능)
코드(ablation_one.py:33): train_test_split(X, Y, test_size=0.2, random_state=42)  # 단순 행 단위
→ 한 환자에 여러 행이 있으면 data leakage. R²=0.97의 원인일 수 있음.
조치: 환자 ID 기준 GroupShuffleSplit으로 재실행하거나, 1환자=1행임을 증빙.

### 4. (보조) 표 I의 H=T+V MSE는 A와 C를 구분하지 못함
ablation_models.py: 모델 C도 `H = T + V`를 문자 그대로 계산(line 70) → C도 float32 반올림 수준.
A/C의 실제 차이는 softplus(T,V≥0)와 Cholesky(R⪰0)이지 H=T+V가 아님.
조치: 해당 열은 "구성상 동일" 각주 추가, 판별 지표는 T<0/V<0/non-PSD임을 명시.

---
## ⚪ 리뷰어 주장 중 사실이 아닌 것
- "STACOM2025는 AI가 지어낸 데이터셋" → **틀림.** 실제 보유·추출 이력 있음(2025는 과거). 단 인용/URL은 추가 필요.
- "식 (4)가 그 페이지에 없다 / 상호참조 엉망" → **틀림.** LaTeX 자동번호(\eqref) 사용, undefined 참조 0건 확인.
- "모든 R²가 소수 셋째 자리까지 같은 건 AI가 타이핑한 것" → **틀림.** seed별 원시값 존재, 실제 학습 산출.
- "이메일이 AI가 지어낸 것" → 근거 없는 추측.
- "식 (3) dH/dt는 미분 불가라 구현 불가" → 이미 오늘 수정 완료(구현되지 않은 L_H 서술을 제거하고 구조적 보장으로 대체).

---
## 권고
1. **프리프린트/투고 보류.** #1·#2는 헤드라인 수치와 핵심 주장에 직결.
2. #2 먼저: pH-PINN 예측값 기반으로 재분석하거나 주장 격하.
3. #1: E_diss 공식 유도 정정 후 에너지 파티션 재계산 → 그림/표/본문 동기화.
4. #3: 환자 단위 split 재실행(가장 신뢰 회복 효과 큼).
5. 그 후 재감사 → 그때 제출.

---
# 추가 검증 (3차 리뷰) — 코드로 확인된 2건 더

### 5. 🔴 관성(L)=0 인데 운동량 상태 p 를 정의함
windkessel_phpinn_results.json → "L": 0.0
원고는 상태 p=(p_mv,p_ao)를 "inertance-scaled valve-flow momenta"로 정의하고
T(q,p)=½pᵀM⁻¹(q)p 를 운동에너지로 계산하지만, 보정된 Windkessel 회로에 관성 소자가 없음(L=0).
→ 운동량 상태가 물리적으로 뒷받침되지 않음. **리뷰어 지적 타당.**
조치: (a) 4-element Windkessel(L 포함)로 보정하거나, (b) p를 "물리적 관성이 아닌
잠재 상태(latent state)"로 정직하게 재정의하고 T의 해석을 낮출 것.

### 6. 🔴 Ees 예측의 순환성 — 헤드라인 R²의 의미 약화
ablation_one.py:20  INPUT_COLS = ['pre_EF','pre_EDV','pre_ESV','pre_SBP','pre_DBP','pre_HR','pre_CO', ...]
Chen 단일박동 공식의 인자(SBP, DBP, SV=EDV−ESV, EF)가 **전부 입력에 포함**됨.
→ Ees(R²=0.951~0.984)는 "결정론적 대수공식을 그 인자들로부터 재현"한 것에 가까움.
원고가 emulator/internal consistency로 일부 인정하고는 있으나, R²를 성과처럼 제시하는 톤은 과함.
조치: R²를 "surrogate formula reproduction(sanity check)"로 격하하고, 핵심 기여를 ablation으로 이동.

---
# 종합 판단
- **살아남는 핵심 기여:** ablation. 동일 capacity에서 hard 제약이 물리적 유효성을 보장(위반 0)하고,
  무제약 모델은 수백~전 케이스에서 위반. 이건 순환성 문제와 무관하게 유효하고 발표 가치 있음.
- **재작업 필요:** 에너지 회계(E_diss 차원), SVR 검증 주장, split 방식, 운동량/관성 정합성, R² 톤.
- **결론: 현 상태로 프리프린트/투고 보류.** 위 5건 처리 후 재감사 권장.

---
# 추가 검증 (4차 리뷰)

### 7. 🔴 식 (1)의 g(x)u 항이 코드에 없음
pinn_hamiltonian_v5.py:422  dx_dt = torch.bmm(J - R, dH_dx)   ← g(x)u 없음
원고 식 (1)·(2)는 외부 입력 u와 공급전력 yᵀu를 포함하지만, 구현은 u=0(자율계).
또한 u, y가 eICU/MIMIC의 어떤 변수인지 원고에 정의 없음. **리뷰어 지적 타당.**
조치: u,y를 명시적으로 정의하고 구현하거나, 자율계(u=0) 가정임을 본문에 명시.

### 8. 🔴 정준 정합성(canonical consistency) 미보장
q_head와 p_head가 각각 독립 출력 → ∂H/∂p = q̇ 가 강제되지 않음.
"해밀토니안 구조"라는 명칭에 비해 정준 관계가 성립하지 않음. **타당한 이론적 지적.**
조치: p를 latent state로 재정의(정직) 또는 ∂H/∂p 정합성 손실 추가.

### ⚪ 사실이 아닌 것 (4차)
- "L_PSD가 Hessian 볼록성을 강제 → 박동 불가" : 원고 표현 오류였고 **오늘 이미 수정**함
  (실제 코드는 R의 음수 고윳값 페널티. 현재 원고도 그렇게 서술).
- "temporal R²는 random R²를 복사한 것" : **틀림.** 서로 다른 완전정밀도 실수값 존재.
  다만 두 split 차이가 작은 것은 타깃이 입력의 결정론적 함수(순환성, 항목 6)라는 정황과 부합.

---
# 추가 검증 (5차 리뷰)

### 9. 🟠 SW = ½·Ea·SV² 의 ½ 계수 — 문헌 대조 필요 (영향 큼)
Ea=Pes/SV 이므로 Ea·SV² = Pes·SV. 논문식은 그 절반(= Ea선 아래 '삼각형' 면적).
  논문 SW = 3675,  통상 PV-loop 면적 근사 Pes·SV = 7000  → 약 52%
  효율도 64.8% ↔ (Pes·SV 사용 시) 77.8% 로 크게 달라짐.
원고 문장("area under the arterial elastance line")과는 일치하나,
그 삼각형이 곧 stroke work인지 Suga–Sagawa 원문으로 확인 필요. **미해결 → 확인 필수.**

### ⚪ 사실이 아닌 것 (5차)
- "batch 512 × 95만 메시 → OOM이라 구현 불가" : 전제가 틀림. 메시는 학습 그래프에 아예 없음
  (입력은 11개 tabular feature). 다만 "메시가 추론에 기여하지 않는다"는 **결론 자체는 이미 항목 3에서 인정**.
- "Bland–Altman LoA가 대칭이라 조작" : **틀림.** LoA는 정의상 bias±1.96·SD → 대칭이 당연.
  코드도 ba_mean±1.96*ba_std. 통계 개념 오해에서 나온 주장.
- "r_diss가 상수라 inductive bias가 작동 불가" : 부분적으로만 맞음. r_diss는 사후 에너지 회계에만 쓰이고
  학습 손실에 없음. 구조적 bias(softplus T,V / Cholesky R / H=T+V)는 그래프 안에서 실제 작동함.
