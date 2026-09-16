# Cardiac Digital Twin — 확장 실행계획 (staged)

> 2026-07-07 세션 4. AUDIT_EXPANSION_BACKLOG.md의 E1~E5를 **의존성 순서**로 단계화.
> 원칙: 원자료 pull(WSL 크레덴셜)이 선행인 스레드는 스캐폴드만, 로컬 데이터로 되는 건 즉시 착수.

## 의존성 그래프
```
E0 (ECG/Waveform ↔ echo 링크)  ──┬──▶ E1b (전기-에너지 브리지)
                                  ├──▶ E1c (AF→LAA→혈전)  ← LAA 기하(진행중) 필요
                                  └──▶ E4 (ECG+혈역학 예후)
E2 (ABP waveform 검증)  ── 독립, A2 gap 직접 해소 ── 우선순위 높음
E3 (소아 PIC)           ── 로컬 zip 보유, 독립 ── 즉시 착수 가능(단 범위 주의)
E5 (약물 심독성)        ── ChEMBL(보유) + E0 ECG QTc 필요
```

## 권장 순서 (근거)
1. **E2 (ABP waveform)** — 감사 최대 약점(인체 침습 검증 부재, A2)을 직접 메움. 방어력 즉시 상승.
2. **E0 → E1b** — 공통 인프라 깔고 독창성 최고 서사(전기-에너지 트윈) 확보.
3. **E1c** — LAA 기하 완성(RV 이후) 시 기하+EP+유동 통합.
4. **E3 (소아)** — 병렬 가능(로컬). 단 범위 재정의(아래).
5. **E5 (심독성)** — E0(QTc) 이후 ChEMBL hERG와 결합.

---

## E0. ECG/Waveform ↔ echo 코호트 링크 [선행 인프라]
- **상태**: ECG/Waveform 원자료 미보유. echo 링크키 = `subject_id`(확인됨).
- **필요 pull(WSL, 크레덴셜)**: MIMIC-IV-ECG(12-lead, ~800k), MIMIC-IV Waveform(ABP).
- **산출 스크립트**: `link_ecg_waveform_cohort.py`(스캐폴드 제공) — subject_id로 echo 코호트에
  ECG record를 시간창(echo±Δ) 매칭, ECG 파생지표(QRS, QTc, axis, LVH voltage) 컬럼 생성.
- **결과물**: `cohort_echo_ecg.csv` (echo + ECG feature 병합).

## E1b. 전기-에너지 브리지 [독창성 ★]
- **가설**: ECG 재분극(QTc·T-wave) → 이온채널 상태(hERG/KCNQ1/SCN5A, STATUS §5) →
  약물효과 → 기존 drug-energy Hamiltonian network(ΔH). EP↔혈역학 통합.
- **설계**: (1) ECG feature → 이온채널 "활성 프록시" 매핑(문헌 계수), (2) 약물별 채널차단
  프로파일(ChEMBL hERG IC50) 결합, (3) 기존 `drug_hamiltonian_perturbation.csv`의 ΔH와
  상관/인과 연결. 산출: "electro-energetic coupling" 지표.
- **의존**: E0.

## E1c. 부정맥-혈전 트윈 [기하+EP+유동 통합]
- **가설**: ECG AF 검출 → LAA 형태(구축중) → CFD 정체(low velocity/washout) → 혈전위험.
- **설계**: (1) ECG AF 라벨, (2) LAA 메시(§19-D 이후 in-patient 확보 목표)에서 CFD 정체지표
  (TAWSS, OSI, residence time), (3) AF군 vs SR군 정체지표 비교. Watchman 임상 연결.
- **의존**: E0 + LAA 기하 완성.

## E2. 실제 ABP waveform 검증 [감사 gap 해소 ★]
- **목적**: cuff 근사(ESP≈0.9·SBP) → 실제 파형 기반 ESP(dicrotic notch)·dP/dt_max로 대체,
  그리고 **인체 준침습 검증** 확보(현재 동물만).
- **필요 pull**: MIMIC-IV Waveform ABP 세그먼트(echo 근접 시간창).
- **산출 스크립트**: `abp_waveform_features.py`(스캐폴드) — WFDB 로드 → beat 분할 →
  ESP/dP/dt/증가지수 추출 → PINN 입력·검증셋 생성.

## E3. 소아(PIC) 확장 [로컬 보유 · 범위 주의]
- **보유**: `paediatric-intensive-care-database-1.1.0.zip` (PIC, 저장 ICU/수술 vitals).
  구성: CHARTEVENTS, SURGERY_VITAL_SIGNS, PATIENTS, ADMISSIONS, DIAGNOSES_ICD, LABEVENTS…
- **⚠️ 범위 재정의**: PIC에는 **echo 볼륨(EF/EDV/ESV)이 구조화돼 있지 않을 가능성** 큼 →
  "소아 echo-파라미터 재적합"은 부적합. 대신 **소아 ICU 혈역학/예후 검증**(eICU 유사 역할):
  SBP/DBP/HR·수술 vitals + 약물 + outcome으로 (iii)층 outcome 연관을 소아로 확장.
- **즉시 착수 가능**: zip 내 D_ITEMS/CHARTEVENTS에서 혈압/심박 itemid 탐색 → 가용성 확인 →
  가능하면 소아 혈역학 코호트 구성. (echo 있으면 파라미터 확장, 없으면 outcome 확장)

## E5. 약물 심독성 트윈
- **보유**: `cardiotoxicity_ai_pipeline.py`, ChEMBL MCP(hERG IC50 조회 가능).
- **설계**: ECG QTc(E0) + hERG 차단(ChEMBL) + Hamiltonian 에너지 섭동 → 심독성 지표.
- **의존**: E0.

---

## 공통 리스크
- ECG/Waveform pull은 용량 큼 + PhysioNet credentialed access 필요 → WSL에서 사용자 실행.
- 멀티모달 병합 시 시간창 정의(echo±Δ) 민감 → 민감도 분석 필요.
- 소아 PIC는 성인과 생리 다름 → forward-model 계수 재적합 없이는 직접 이식 불가.

*(각 스레드 착수 시 STATUS 문서에 세션 로그로 반영)*

---

## 타깃 저널 확정 (2026-07-07, 검색 근거)

| 역할 | 저널 | IF(2025, 출처별 변동) | 스코프 적합 근거 |
|------|------|------|------------------|
| **1순위(현실 flagship)** | IEEE J-BHI | ~6.8 (일부 8.2 보고) | AI/DL/ML×생리시스템·임상정보학. 기존 초안 타깃과 일치 |
| **도전(E2+E1 후)** | npj Digital Medicine | ~18.0, Q1 | **cardiac digital twin 활발히 게재** — 2025 HF digital-twin 논문(343명 기계론적 CV모델) 직접 선례 |
| **강적합 대안/safety** | Computers in Biology and Medicine | ~7급 | **PINN cardiac hemodynamics 다수 게재 + PINN-hemodynamics 리뷰**. 스코프 최상 |
| (하위 safety) | Physiological Measurement | ~2.7, Q2 | 비침습 측정·검증 방법론 앵글 |

**경쟁 지형(포지셔닝 필수):**
- *Med-Real2Sim: Non-Invasive Medical Digital Twins using PI Self-Supervised Learning* (arXiv 2403.00177) — 매우 근접 선행. 차별점(구조보장 Hamiltonian + 약물-에너지학 + ECG 멀티모달) 명확히 대비 필요.
- npj 2025 HF digital-twin 논문 — outcome/phenogroup 서사 선점됨 → 우리는 에너지학+식별성+멀티모달로 차별화.

**결론 타깃 3:** ① IEEE J-BHI(제출 현실선) ② npj Digital Medicine(E2+E1 보강 후 도전) ③ Computers in Biology and Medicine(강적합 fallback).
