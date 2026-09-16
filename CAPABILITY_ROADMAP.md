# Capability Roadmap — 트윈 엔진을 떠받치는 가로지르는 역량

> 2026-07-07 세션 4. 개별 장기/질환 모델과 **별개로**, 프로그램 전체의 천장을 올리는
> cross-cutting 역량. 관점: 각 역량은 multi-organ 트윈 엔진 × 희귀질환 미션(KRDF)에
> **곱셈기**로 작동. 다 하지 말고 2~3개를 깊게(아래 우선순위).

## 역량 레지스트리

| # | 역량 | 왜 곱셈기인가 | 기존 자산 연결 | 희귀질환(KRDF) 레버 | 우선순위/시점 |
|---|---|---|---|---|---|
| C1 | **UQ / Bayesian SciML** | 임상신뢰=점추정 아닌 예측구간. 물리정보+베이지안은 소-N에 특히 강함 | 현 모델 대부분 점추정(B2 gap) → 즉시 곱해짐 | 소-N 희귀코호트에서 신뢰구간 필수 | **1순위(즉시)** |
| C2 | **인과추론** | 최약 감사지점(치료효과 PSM/IPTW) 정면 수정. durable 스킬 | `master_treatment_summary.csv`, PSM/IPTW | 소-N 관찰연구 인과주장 방어 | **1순위(즉시)** |
| C3 | **신뢰성·규제 과학** (ASME V&V40, SaMD, GMLP) | 응용(수술계획·독성·in-silico trial)을 "데모→신뢰가능"으로. 학계에 희소=차별 | PLATFORM L5 응용층, 합성 코호트 | 규제급 rare-disease in-silico 근거 | **2순위(응용 성숙기)** |
| C4 | **연합학습 + 프라이버시(DP)** | 다기관 소코호트를 데이터 이동 없이 풀링 | twin_parameters 스키마(교환 계약) | **KRDF 다기관 연계의 핵심 enabler** | **2~3순위(규모확장기)** |
| C5 | **SciML 프론티어** (Neural ODE/UDE, DeepONet/FNO, SINDy) | PINN의 다음 세대. SINDy=지배식 발견, operator learning=일반화 | pH-PINN, CFD 서로게이트 | 데이터 희소계에서 식 발견 유용 | **3순위(방법확장기)** |
| C6 | **QSP / PK-PD** | 면역·약물 동역학의 **표준 형식(비-Hamiltonian)** = 면역 트랙의 답 | 약물-에너지 network, ChEMBL | 면역/대사 희귀질환·약물 | **면역 트랙 착수 시** |
| M | **그랜트십 + 오픈소스 커뮤니티** (비기술) | 영향력 천장(레퍼런스 아키텍처화)은 채택·자금이 좌우 | 플랫폼 오픈소스화 계획 | 희귀질환 그랜트·컨소시엄 | 상시 |

## 핵심 수렴점: in-silico trial
`pinn_v4_physiology.py`가 이미 **합성 코호트(virtual patients)** 를 생성 → in-silico
trial 역량의 절반 보유. 여기에 **C1(UQ) + C3(신뢰성)** 을 얹으면 규제기관이 밀어주는
"규제급 in-silico 트라이얼 / 가상 대조군"으로 자연 확장(고가치·fundable).

## 우선순위 시퀀스
1. **C1 UQ + C2 인과추론** — 현 자산에 즉시 곱해지고 감사 방어력↑. 먼저.
2. **C3 신뢰성과학** — 응용층(독성·수술계획) 성숙과 병행.
3. **C6 QSP** — 면역 트랙 시작 시 (그 트랙의 형식 자체).
4. **C4 연합/프라이버시, C5 SciML 프론티어** — 다기관·방법 확장 국면.
5. **M 그랜트십/OSS** — 상시(영향력 레버).

## 다음 확인/행동
- [ ] C1: 현 모델에 부트스트랩→deep ensemble/BNN로 예측구간 붙이는 최소 실험.
- [ ] C2: 치료효과 재분석에 E-value·negative control·target trial emulation 적용.
- [ ] C3: ASME V&V40 신뢰성 프레임을 CFD/PINN 검증에 매핑(체크리스트화).
- [ ] C6: 면역 QSP 형식 명세(사용자 구상) → MULTI_ORGAN_VISION 면역 슬롯과 연결.

*(역량 착수 시 본 문서를 SSOT로 갱신. 관련: PLATFORM_ARCHITECTURE, MULTI_ORGAN_VISION, AUDIT_EXPANSION_BACKLOG.)*
