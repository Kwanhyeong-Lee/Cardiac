# PINN v2 Redesign Roadmap
## Non-Invasive Hemodynamic Profiling Framework

**Date**: 2026-04-22
**Author**: Kwanhyeong Lee
**Goal**: IF 7–15 journal (J-BHI / AIM / npj Digital Medicine)

---

## 1. Research Question (Redesigned)

**Old**: "Can a PINN estimate Ees from non-invasive data?"
**New**: "Can physics-informed hemodynamic profiling identify cardiac dysfunction invisible to EF alone?"

Key shift: Ees accuracy → clinically actionable hemodynamic state vector

---

## 2. Model Architecture: Physics-Embedded PINN

### 2.1. Core Concept

Replace "MLP + physics loss" with "physiological model embedded in network architecture."

```
Non-invasive inputs → Encoder (MLP) → Latent hemodynamic parameters
                                           ↓
                                    Physics Decoder (known equations)
                                           ↓
                                    Hemodynamic state vector
```

### 2.2. Physiological Model Components

**A. Time-Varying Elastance Model (Suga-Sagawa)**
- P(t) = E(t) × (V(t) - V₀)
- E(t) = Emin + (Ees - Emin) × eₙ(tₙ)
- eₙ(tₙ): normalized elastance curve (double-Hill function)
- Peak E(t) = Ees at end-systole

**B. Arterial Windkessel (2-element)**
- Ea = ESP / SV  (arterial elastance)
- ESP ≈ 0.9 × SBP (Shishido approximation)
- Optional: 3-element with characteristic impedance Zc

**C. Frank-Starling Relationship**
- SV = f(EDV, Ees): monotonically increasing with EDV up to plateau
- Starling reserve index = dSV/dEDV at operating point
- Embedded as architectural constraint (monotonic network branch)

**D. Energy Balance**
- PVA = SW + PE (pressure-volume area = stroke work + potential energy)
- SW = SV × MAP
- PE = 0.5 × Ees × (ESV - V₀)²
- Mechanical efficiency η = SW / PVA

### 2.3. Network Architecture

```
Input layer (7 features):
  EF, EDV, ESV, SBP, DBP, HR, CO

Encoder (MLP, 3 hidden layers × 128 neurons, SiLU activation):
  → Latent parameters: [Ees, V₀, Emin, τ_sys, Ea_raw]

Physics Decoder (deterministic, differentiable):
  ESP = 0.9 × SBP
  SV  = EDV - ESV
  MAP = (SBP + 2×DBP) / 3

  # ESPVR consistency
  Ees_check = ESP / (ESV - V₀)

  # Arterial elastance
  Ea = ESP / SV

  # Coupling ratio
  coupling = Ea / Ees

  # Cardiac power
  CPO = CO × MAP / 451

  # Stroke work & PVA
  SW  = SV × MAP × 0.0133  (mmHg·mL → Joules)
  PE  = 0.5 × Ees × (ESV - V₀)²  × 0.0133
  PVA = SW + PE
  efficiency = SW / PVA

  # Frank-Starling index
  FS_index = SV / EDV  (simplified; full version uses dSV/dEDV)

Output: [Ees, Ea, Ea/Ees, V₀, CPO, SW, PVA, efficiency, FS_index]
```

### 2.4. Loss Function (Multi-Task)

```
L_total = λ₁·L_data + λ₂·L_ESPVR + λ₃·L_coupling + λ₄·L_starling + λ₅·L_bounds

L_data:     MSE between predicted and reference Ees (Chen/Shishido average)
L_ESPVR:    |ESP - Ees×(ESV - V₀)|² (ESPVR consistency)
L_coupling: penalty if Ea/Ees outside [0.3, 3.0] (physiological range)
L_starling: penalty if ∂SV/∂EDV < 0 (Frank-Starling monotonicity)
L_bounds:   soft penalties for physiological plausibility
            Ees ∈ [0.5, 8.0], Ea ∈ [0.5, 5.0], V₀ ∈ [-20, 30]
            efficiency ∈ [0.3, 0.95], CPO ∈ [0.1, 3.0]
```

### 2.5. Key Differences from v1

| Aspect | v1 (current) | v2 (redesign) |
|--------|-------------|---------------|
| Physics role | Loss regularization only | Embedded in architecture |
| Output | Ees only | 9-element hemodynamic state vector |
| Frank-Starling | Loss penalty | Architectural monotonicity constraint |
| Windkessel | Not used | Ea derived from arterial model |
| Clinical focus | Ees accuracy | Coupling ratio, efficiency, FS reserve |
| Calibration | Post-hoc isotonic | Physics decoder ensures consistency |

---

## 3. Data Strategy

### 3.1. Training Data

**Simulation (Phase 1 pre-training)**
- Lumped-parameter ODE model generates synthetic PV loops
- Vary: Ees (0.5–8.0), Ea (0.5–5.0), HR (40–150), EDV (50–300)
- Add realistic noise profiles (Gaussian + systematic)
- N = 50,000 synthetic patients

### 3.2. Validation Cohorts (3-cohort strategy)

| Cohort | N | What it provides | Status |
|--------|---|------------------|--------|
| EchoNet-Dynamic | ~10,000 | Real echo EDV/ESV/EF, cross-method agreement, noise robustness | DUA 신청 필요 |
| MIMIC-IV-ECHO | ~2,000–5,000 | Real echo + vital signs + ICU mortality, outcome prediction | CITI 교육 → credentialed access |
| UK Biobank cardiac MRI | ~50,000 | Population-level, cardiac MRI volumes, long-term outcomes | 기관 IRB + 신청서 |

### 3.3. Ground Truth (Animal)

- Stonko (1 pig, hemorrhage) + Davidson (5 pigs, sepsis) = 6 pigs, 1,020 windows
- LOPO cross-validation
- Already completed — reuse results

---

## 4. Experiment Plan

### Phase 1: Model Development (데이터 승인 대기 중, ~2–4주)

- [ ] 4.1. Lumped-parameter ODE simulator 구현
  - Time-varying elastance + 2-element Windkessel
  - Frank-Starling curve generator
  - 50,000 synthetic patients 생성

- [ ] 4.2. PINN v2 architecture 구현
  - Encoder MLP + Physics decoder
  - Multi-task loss with physiological constraints
  - Monotonic network branch for Frank-Starling

- [ ] 4.3. Simulation validation
  - Ees, Ea, coupling ratio recovery accuracy
  - Noise robustness test (v1 대비 비교)
  - Physics ablation (full physics vs partial vs none)

- [ ] 4.4. Animal PV loop validation
  - 6-pig LOPO with v2 model
  - Compare v1 vs v2 performance
  - Derived metrics (Ea, coupling, efficiency) on porcine data

### Phase 2: Real Data Validation (데이터 도착 순서대로)

- [ ] 4.5. EchoNet-Dynamic validation (1순위, 가장 빠름)
  - Real echo volumes → PINN v2 hemodynamic profile
  - Cross-method agreement (PINN vs Chen vs Shishido)
  - Distribution plausibility by HF subtype
  - Noise robustness with real measurement variability

- [ ] 4.6. MIMIC-IV-ECHO validation (2순위, 핵심)
  - Real echo + vitals → hemodynamic profile
  - Primary endpoint: ICU mortality prediction
  - Head-to-head: PINN hemodynamic profile vs EF alone vs Chen Ees
  - Subgroup: HFpEF, HFrEF, sepsis, post-surgical
  - Incremental value: base model (SOFA + age + EF) + PINN metrics

- [ ] 4.7. UK Biobank validation (3순위, scale)
  - Cardiac MRI volumes → population-level profiling
  - Subclinical dysfunction detection (normal EF, abnormal coupling)
  - Long-term outcome prediction (MI, HF hospitalization, death)
  - Phenotyping: unsupervised clustering by hemodynamic profile

### Phase 3: Paper Writing

- [ ] 4.8. Figure design (6 main + supplementary)
  - Fig 1: Model architecture schematic
  - Fig 2: Simulation validation + noise robustness + physics ablation
  - Fig 3: Animal invasive LOPO validation (6 pigs)
  - Fig 4: EchoNet cross-method agreement + distributions
  - Fig 5: MIMIC outcome prediction (ROC, Kaplan-Meier, subgroups)
  - Fig 6: UK Biobank population profiling + subclinical detection

- [ ] 4.9. Manuscript drafting (MIMIC-centered structure)
- [ ] 4.10. Internal review + revision
- [ ] 4.11. Submission

---

## 5. Target Journal Strategy

| Priority | Journal | IF | Fit | Threshold |
|----------|---------|-----|-----|-----------|
| 1차 | IEEE J-BHI | ~7 | ML + clinical + validation | MIMIC + 1 cohort |
| 1차 | Artif. Intell. Med. | ~7.5 | AI methodology + clinical | MIMIC + EchoNet |
| Stretch | npj Digital Medicine | ~15 | Digital health, Nature계열 | 3 cohort + strong ΔAUC |
| Stretch | EBioMedicine | ~11 | Clinical + translational | 3 cohort + HFpEF story |
| Backup | CMPB | ~4.9 | Computational methods | MIMIC alone |

---

## 6. Timeline

| Week | Task |
|------|------|
| Week 1 (now) | 데이터 신청 3건 동시 + PINN v2 architecture 구현 |
| Week 2–3 | ODE simulator + simulation training + animal validation |
| Week 3–4 | EchoNet DUA 승인 예상 → real echo validation |
| Week 4–6 | MIMIC CITI 완료 → credentialed access → outcome analysis |
| Week 6–10 | UK Biobank (if approved) + manuscript drafting |
| Week 10–12 | Final figures + submission |

---

## 7. Reusable Assets from v1

- pinn_cardiac.py: MLP backbone, training loop → encoder 재활용
- calibrated_pinn.py: isotonic regression pipeline → calibration 재활용
- multi_animal_validation: 6-pig LOPO code → 그대로 사용
- noise_robustness_clinical.py: noise injection + MC trials → 재활용
- run_all.py: pipeline orchestration → 확장
- build_v11.js: manuscript builder → 구조 변경 후 재활용
- All figure generation code → 수정 후 재활용

---

## 8. Risk Factors

| Risk | Impact | Mitigation |
|------|--------|------------|
| MIMIC 승인 지연 | 핵심 validation 불가 | EchoNet + animal로 1차 제출, MIMIC은 revision에 추가 |
| UK Biobank 승인 거절 | 3rd cohort 부재 | MIMIC + EchoNet 2-cohort로 진행 (IF 7급 타겟) |
| PINN v2가 v1보다 성능 저하 | 모델 실패 | v1 결과를 baseline으로 유지, v2는 추가 contribution |
| MIMIC에서 ΔAUC 미미 | Clinical impact 부족 | Subgroup 분석 (HFpEF), coupling ratio focus |
| Reviewer가 ground truth 부족 지적 | Major revision | 돼지 6마리 LOPO + population ranges로 방어 |
