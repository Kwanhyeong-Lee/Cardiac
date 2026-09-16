# ECG 보강 설계 — 물리정보적 멀티모달 PINN (E1a 상세)

> 2026-07-07 세션 4. 목적: ECG를 "블랙박스 특징"이 아니라 **각 지표가 특정 혈역학
> 파라미터에 독립 제약을 거는 구조화 prior**로 넣어, echo-only에서 비식별인 파라미터
> (Eed, efficiency, V0, tau)의 **식별성(B3)을 개선**하고 티어를 올린다.

## 1. 왜 티어가 올라가나
- echo-only 역문제는 underdetermined(§B3). ECG는 **독립 모달리티**라 같은 파라미터에
  다른 물리 경로로 제약을 걸어 식별성·강건성을 높인다.
- 기존 AI-ECG는 대부분 EF 분류/회귀(블랙박스). 우리는 **기전적 파라미터 prior**로 써서
  해석가능·물리일관 → 차별화(포지셔닝).

## 2. 기전 매핑 (ECG feature → 혈역학 파라미터, 문헌 근거)

| ECG feature | → 파라미터 | 방향/근거 |
|---|---|---|
| **QRS duration (≥120ms, LBBB)** | efficiency↓, coupling, Ees | 전기 dyssynchrony → 수축효율 저하, QRS는 심실기능 저하와 선형관계 (Ngeno 2021; Ghio 2004 EHJ) |
| **AI-ECG 추정 LVEF** | EF/Ees 일관성 앵커 | 12-lead로 LVEF 정확 추정(AUC 0.91, MIMIC-IV 외부검증 MAE~5.3%) (Attia 2019; Sangha 2022 Circulation; Hou 2024) |
| **LVH voltage (Sokolow-Lyon, Cornell)** | Eed↑(확장기 강성), Ees(구심성 재형성) | ECG-LVH ↔ 확장기능 저하(e′↓)·동맥강성 독립연관 (Hsu 2012 PLoS ONE) |
| **PTFV1 (P-wave terminal force V1)** | LA압/E-e′, Eed | PTFV1 ↔ E/e′·LA 확대 (Jiang 2018) |
| **QTc / T-wave** | (E1b 이온채널·약물 브리지) | 재분극 → hERG/KCNQ1 → 약물 에너지섭동 |
| **AF flag** | (E1c LAA 정체·혈전) | 심방세동 → LAA washout↓ |

## 3. 아키텍처 (3안, B+C 하이브리드 권장)
- **A. 보조입력 concat**: ECG feature를 encoder 입력에 추가(가장 단순, 그러나 물리성 약).
- **B. ECG-유도 soft prior(권장)**: ECG feature로 파라미터 prior 평균·분산을 만들어
  손실에 페널티. 예: `L_ecg = Σ w_k (θ_k − μ_k(ECG))² / σ_k²`.
  - efficiency: μ = f(QRS)  (QRS↑ → efficiency↓)
  - Eed: μ = g(LVH voltage, PTFV1)
  - Ees: EF 일관성 — AI-ECG EF와 모델 유도 EF의 차이 페널티(C와 결합).
- **C. EF 일관성 앵커(권장)**: AI-ECG LVEF를 독립 관측으로 두고 모델 EF와 정합.
  → echo EF 결측/노이즈 보정 + Ees 식별 보강.
- 권장: **B(prior 페널티) + C(EF 앵커)**. A는 ablation 비교군.

## 4. 검증 실험 (식별성 증명 = B3 정면돌파)
1. **Ablation**: echo-only vs echo+ECG(B+C). 대상: Eed·efficiency·V0·tau.
2. **식별성 지표**: synthetic recovery(참값 주입) RMSE 감소, posterior/부트스트랩 폭 감소,
   profile-likelihood 곡률 증가.
3. **기대결과**: ECG 추가 시 확장기·효율 파라미터의 recovery RMSE·CI폭 유의 감소.
4. **임상 검증**: 침습(동물) + 인체 outcome(eICU)에서 정확도 유지/향상.
5. **민감도**: echo–ECG 시간창(Δ) 스윕(E0), 결측 ECG 강건성.

## 5. 포지셔닝 (리뷰어 방어)
- vs Attia/Sangha(AI-ECG EF 분류): 우리는 EF 하나가 아니라 **기전적 다-파라미터 prior +
  에너지학**. "또 다른 EF 분류기"가 아님을 intro에서 명시.
- vs Med-Real2Sim: 구조보장 Hamiltonian + ECG 물리 prior + 약물-에너지학으로 차별.

## 6. 데이터 의존
- 선행: E0(`link_ecg_waveform_cohort.py`)로 MIMIC-IV-ECG를 subject_id 시간창 매칭 →
  QRS/QTc/LVH voltage/PTFV1/AF/AI-ECG-EF 컬럼 생성(원자료 pull, WSL 크레덴셜).
- AI-ECG-EF는 공개 모델(예: 재현된 Attia류) 또는 자체 학습으로 산출.

*(구현 착수 시 STATUS + BACKLOG에 반영. B3 항목에 "ECG-augmented 식별성" 링크.)*
