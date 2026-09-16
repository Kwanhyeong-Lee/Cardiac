# Cardiac Digital Twin — Audit & Expansion Backlog

> 시작: 2026-07-07 (세션 4, 리뷰 병렬 진행 중)
> 목적: Papers 1–3 + geometry/CFD 파이프라인에 대해 **리뷰어 공격 지점(audit)**과
>       **확장 기회(expansion)**를 문헌 근거와 함께 지속 축적.
> 우선순위: T1(치명적) > T2(방법론 엄밀성) > T3(확장). 각 항목은 근거파일/문헌 명시.

---

## T1 — 치명적 (리뷰어 리젝 사유가 될 수 있음)

### A1. [정정됨 2026-07-07] "라벨 순환논리"는 반증됨 → 검증 위계 표기 문제로 격하
- **초기 오판(철회)**: `calibrated_pinn.py`의 Chen/Shishido 닫힌형 라벨을 보고 "R²=0.98은
  항등식"이라 판단했으나, 그 파일은 **v1 잔재**였음. v4/v5는 `pinn_v4_physiology.py
  generate_training_data(N=15000)`로 6개 표현형 범위에서 **합성 파라미터 샘플링 → forward
  physics → 역문제 복원**으로 학습. 즉 헤드라인 R²는 **합성 recovery**이지 닫힌형 되학습 아님.
- **반증 근거(실측)**: `invasive_validation_results.csv`(n=339)에서 PINN vs 침습 다중박동
  ESPVR: **r=0.977, MAE=0.108 mmHg/mL, bias +0.003**. 같은 데이터에서 닫힌형은
  Ees_Chen MAE=8.59, Ees_Shishido MAE=3.92 → PINN이 공식을 단순재현했다면 불가능한 우위.
  ⇒ 순환논리 주장 폐기.
- **남는(정제된) 감사 포인트**:
  1) **헤드라인 R² 표기**: Paper 3의 "Clinical R² 0.98"은 합성 recovery 수치. 원고에서
     이를 침습 정확도(r=0.977, n=339 + 동물 LOPO)와 **명확히 분리·전면배치**. 합성 R²가
     앞서면 리뷰어 오해 유발.
  2) **`invasive_validation_results.csv`(n=339) 출처 = 확정: 돼지(porcine) PV-loop.**
     `run_all.py` STEP 14 "Invasive Validation (Porcine PV Loops)", n_animals=6.
     값도 EDV~49mL/ESV~14mL/HR~101로 인체 성인 아님. 원리상 침습 ESPVR Ees는 다박동
     부하변화 PV-loop 필요 → ICU 데이터엔 없음. ⇒ 침습 gold-standard는 **동물**.
     인체 코호트·outcome은 실데이터지만, Ees 침습검증은 동물이라는 점 원고에 명시 필요.
     **E2(인체 ABP waveform 준침습)**가 이 gap의 직접 해소책.
  3) **동물 기준자 품질**: `multi_animal_validation`은 6마리, 침습 ESPVR_R2 평균 0.56
     (min 0.15)로 노이즈 큼. Leave-one-pig-out(LOPO) 한 점은 좋으나 n 작음 → 한계 명시.
- **문헌(맥락)**: single-beat Ees 자체가 CoV ~20%, 구조적 underdetermined
  (Chen 2001 JACC; Lulić 2026 BPEX) → PINN이 닫힌형을 능가하는 것 자체가 강점 서사가 됨.

### A2. 검증 위계 3층 명시 (과대주장 방지)
- **감사 조치**: 검증을 3층으로 분리 표기 — (i) **합성 recovery**(현재 헤드라인 R²=0.98,
  식별성 증명), (ii) **침습/동물 정확도**(invasive n=339 r=0.977; animal LOPO), (iii)
  **임상 outcome 연관**(eICU 실측, AUC 0.837, 2,720 episodes). 각 층 주장 강도 분리.
- **비고**: eICU(`eicu_hemodynamic.csv`)는 measured_CO/CI/SVR/PAOP·troponin·BNP 등
  실측 침습성 지표 포함 → (iii)는 독립적 실데이터. 강한 근거.

### A3. Geometry 교차환자 차용 부적합 (진행 중)
- **상태**: STATUS §19-D에서 확정 — 교차환자 STACOM RV는 RV-LV 35mm gap로 부적합.
  in-patient RV 추출(`run_rv_extraction.sh`) 진행 중. **완료 시 T1에서 제거.**

---

## T2 — 방법론 엄밀성

### B1. PVA–MVO₂ 에너지 주장의 "일정 수축능" 가정 위반
- **문제**: 약물/HF 표현형 간 Hamiltonian 에너지(H=PVA) 비교(drug interaction network 등).
  그러나 PVA–MVO₂ 선형성은 **"stable inotropic background"에서만** 성립.
- **문헌**: PVA↔MVO₂ r=0.92지만 given a **stable inotropic background** 조건부
  (Khalafbeigui 1979; Suga 1981, Am J Physiol). 약물은 수축능을 바꿔 slope(경사)를 이동시킴.
- **감사 조치**: 약물 간 ΔH 비교 시 inotropy 변화에 따른 PVA–MVO₂ 절편/기울기 이동을
  민감도 분석으로 다루거나, 주장을 "PVA 자체(부하)" 수준으로 한정.
- **확장**: 수축능 변화를 반영하는 e_a(contractility-dependent) 항 도입.

### B2. 관찰데이터 인과주장(PSM/IPTW)의 잔여 교란
- **문제**: MIMIC 관찰코호트에서 치료효과 ATE 주장. indication bias, immortal-time,
  잔여 교란 위험.
- **감사 조치**: negative-control outcome, E-value(잔여교란 정량), 다중 추정치(PSM vs IPTW)
  일치성, 처방 시점 정의(immortal-time) 점검. `master_treatment_summary.csv` 재감사.

### B3. 잠재 파라미터 식별성 (V0, tau, A)
- **문제**: latent V0/A/tau가 데이터로 식별 가능한지 미검증. V0는 특히 악명 높게 비식별.
- **문헌**: 혈류 PINN은 파라미터 추정 가능하나 정확도가 측정품질에 의존하며 파라미터 수가
  많을수록 취약 (Garay 2024, Comput Biol Med).
- **감사 조치**: synthetic recovery(참값 주입→복원 RMSE), profile-likelihood 또는
  posterior 폭으로 식별성 정량. 비식별 파라미터는 prior로 고정 명시.

### B4. 시간외적 검증의 한계
- **문제**: temporal split이 MIMIC 내부 pre/post-median 날짜뿐 → 진짜 외부검증 아님.
- **감사 조치**: 병원/장비 이질성 split, eICU를 hemodynamic 파라미터 검증에도 확장
  (현재 eICU는 drug-response에만 사용).

---

## T3 — 확장 기회

### C1. CFD Track B 물리 충실도
- **관찰(직접 점검)**: 현재 `lv_cfd_anatomical`은 rigid wall(noSlip)+aortic pressure outlet.
  이완기엔 승모판 유입이 강체 강을 채우는데 대동맥판이 열려 있어 유출 → **이완기 유출이
  비생리적**(밸브 동역학 없음).
- **확장**: (1) prescribed wall motion 또는 FSI(preCICE+CalculiX/FEBio),
  (2) 밸브 저항/kinematics(Tier 1→2, STATUS §3.1), (3) 3-element Windkessel outlet.

### C2. 해부학적 완전성
- in-patient RV(진행) → 4-chamber → IVS 분리 → coronary(ImageCAS) → LAA(전용 데이터).
  각 단계 fidelity 목표는 STATUS §6 로드맵.

### C3. 외부 기하/유동 검증
- 4D-flow MRI 챌린지 데이터로 CFD velocity field 검증(STATUS §4.7). 현재 검증 부재.

### C4. 불확실성 정량화(UQ)
- 일부 bootstrap CI 존재. 확장: 파라미터 posterior(Bayesian/deep ensemble)로
  예측구간 제시 → 임상 의사결정 신뢰도 표기.

---

## 다음 문헌 조사 큐 (계속 채울 것)
- [ ] EDPVR Klotz 곡선 vs 본 프로젝트 EDP = A·exp(B·(EDV−V0)) 파라미터(A_ed=0.337,B_ed=0.028) 타당성
- [ ] Ea = ESP/SV(Sunagawa) 및 ESP≈0.9·SBP(Shishido) 근사의 HF에서의 오차
- [ ] Hamiltonian NN(Greydanus 2019) 심장 적용의 물리적 해석 한계
- [ ] MIMIC echo 측정치의 관측자간 변동이 라벨/입력에 주는 영향

*(이 문서는 리뷰 진행에 따라 계속 append.)*

---

## 확장 로드맵 (2026-07-07, ECG/멀티모달/PhysioNet)

> 데이터 현실: 디스크에는 MIMIC/eICU 추출 CSV + PICU zip만 존재. ECG/ABP waveform
> 원자료는 미보유(별도 pull 필요, MIMIC 크레덴셜). 침습 기준자는 실동물(Davidson/Stonko).

### E1. ECG-멀티모달 PINN ★사용자 관심
- **데이터**: MIMIC-IV-ECG(약 80만 12-lead) → subject_id로 echo 코호트 링크(별도 pull).
- **E1a 입력 확장(식별성 보강, B3 대응)**: ECG 파생지표를 PINN 보조입력으로.
  QRS폭↔dyssynchrony, Sokolow/Cornell LVH↔벽응력/Ees, QTc↔재분극/약물효과.
  독립 모달리티라 파라미터 식별성 개선 + 과적합 완화.
- **E1b 전기-에너지 브리지(신규 서사)**: ECG 재분극(QTc, T-wave) → 이온채널맵(§5:
  hERG/KCNQ1/SCN5A) → 약물효과 → 기존 drug-energy Hamiltonian network 연결.
  Track EP(Phase 4)와 혈역학 Hamiltonian을 하나로 → "electro-energetic digital twin".
- **E1c 부정맥-혈전 트윈**: ECG로 AF 검출 → LAA 기하(구축 중) → CFD 정체(stasis) →
  혈전위험. 기하+EP+유동 통합. Watchman/LAA 임상 연결.

### E2. 실제 ABP waveform으로 라벨/검증 강화 (A2 gap 해소)
- **데이터**: MIMIC-IV Waveform DB의 동맥압 파형(별도 pull).
- **효과**: 실제 ESP(dicrotic notch), dP/dt_max(수축능), beat-to-beat → cuff 근사
  (ESP≈0.9·SBP) 대체. **인체 준침습 검증** 확보 → "동물만 있음" 한계 보완.

### E3. 소아 확장 (PICU zip 실보유)
- paediatric-intensive-care-database로 소아 생리 범위 재적합 → 교차도메인 일반화 시험.
  성인 forward-model이 소아에 실패하는지 = 모델 물리 타당성의 강한 시험. 2nd 코호트 논문.

### E4. Outcome/예후 확장
- ECG + 혈역학 파라미터 → 사망/HF입원 예측(EF+NT-proBNP 대비 incremental).
  기존 `PINN_incremental_prognostic`에 ECG 추가.

### E5. 약물 심독성 트윈 (cardiotoxicity 파이프라인 + ChEMBL 보유)
- ECG QTc + 이온채널(hERG IC50, ChEMBL) + Hamiltonian 에너지 섭동 → 약물 심독성 트윈.
  기존 `cardiotoxicity_ai_pipeline.py` 확장.

### 보완(모델 자체)
- **B1 semi-supervised**: 합성 학습을 실동물 ESPVR + 실 ABP waveform으로 앵커 →
  synthetic-to-real gap 축소.
- **B2 UQ**: 파라미터 posterior(deep ensemble/BNN)로 예측구간.
- **B3 식별성**: synthetic recovery + profile likelihood로 V0/tau 식별성 증명·명시.
