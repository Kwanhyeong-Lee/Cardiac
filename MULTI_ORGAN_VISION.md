# Multi-Organ Digital-Twin Engine — 후보군 비전

> 2026-07-07 세션 4. 심장 트윈에서 확립한 **물리정보 + 구조보장 트윈 방법론**을
> 타 장기계로 확장. 핵심 관점: "10개 장기 트윈"이 아니라 **장기 간 전이되는 트윈 엔진 +
> 소-N 희귀질환에서 유독 강함(KRDF 접근)** 이라는 메타서사.

## 0. 지배 원리
전이력 ∝ **해당 계에 확립된 지배 형식(formalism)의 깨끗함**. 단, 형식은 계마다 다름 —
"모든 계에 Hamiltonian"이 아니라 **계에 맞는 수학을 물리정보 제약으로 embedding**.
- 역학계(심장·근골격) → Lagrangian/Hamiltonian.
- 유동/압력계(혈관·폐·신장) → Navier-Stokes / RC(Windkessel).
- 흥분성계(심장EP·뇌) → Hodgkin-Huxley / neural mass.
- 반응/개체군계(면역) → 반응네트워크·개체군 ODE (**비-Hamiltonian**, 별도 형식).

## 1. 후보 장기계 레지스트리

| 계 | 적합 형식 | 전이 적합도 | 기존 자산 | 희귀질환/KRDF 연결 | 경쟁 | 데이터 소스(예) |
|---|---|:---:|---|---|---|---|
| **심장·혈관** (현행 anchor) | Hamiltonian PVA + Windkessel | — | pH-PINN, CFD, cerebro | FMD, SCAD | 중(대형 컨소시엄) | MIMIC/eICU, CT |
| **근골격계** ★2순위 | Lagrangian/Hamiltonian 역학, Hill 근모델 | **최상** (역학이 native) | (신규) | 근이영양증·근병증·골형성이상 | 중(OpenSim 생태계) | 모션캡처·EMG·force plate·웨어러블 |
| **뇌** ★3순위 | 뇌혈류 CFD + neural mass/HH; neurovascular coupling | 높음 | **cerebrovascular_cfd** | 희귀 뇌혈관·신경계 질환 | 높음(The Virtual Brain 등) | EEG, MRA/CTA, fMRI |
| **호흡기/폐** (숨은 강수) | 폐 역학 = compliance·resistance(**Windkessel 동형**) + 가스교환 | 높음 (수학 이식 용이) | pH-PINN 후부하 레이어 재활용 | 희귀 폐질환(PAH, ILD) | 낮음~중 | MIMIC(ARDS/COPD 벤틸레이터), spirometry |
| **신장** (시너지) | 혈류 + 사구체 여과(물리적) | 높음 | FMD 신혈관성 트랙 | FMD, 희귀 신질환 | 낮음~중 | MIMIC-IV, renal CTA |
| **면역계** (탐색) | **비-Hamiltonian**: 반응네트워크/개체군 ODE, (형식 TBD by user) | 낮음~중 (구조보장 우위 소멸, 다른 방법 필요) | (신규) | 원발면역결핍·자가면역 희귀질환(KRDF 강연결) | 중(시스템면역학) | 면역표현형·사이토카인·유전 |
| (니치) 안구 | 방수·IOP 유동 | 중 | — | 희귀 녹내장/포도막염 | 낮음 | IOP·OCT |
| (니치) 1D 전신 동맥망 | 1D 혈류 네트워크 | 높음 | 심장+cerebro CFD 확장 | 전신 동맥병증 | 중 | CTA/MRA |

## 2. 형식별 전이 노트
- **역학계(근골격)**: 현 Hamiltonian NN이 가장 자연스러운 이식처. 순/역동역학=PINN 강점 역문제.
- **유동계(폐·신장)**: 폐/신장 혈역학이 동맥 Windkessel과 **같은 RC 수학** → 코드 재활용 최대.
- **흥분성계(뇌)**: 이온채널맵 방법론 → HH/neural mass로 동형 이식. EEG↔neural mass↔혈류는
  ECG↔혈역학의 복제판.
- **면역계**: 보존법칙 물리 아님 → **구조보장 에너지보존 셀링포인트 증발**. 사용자가 별도
  비-Hamiltonian 접근 검토 중(반응네트워크/개체군 동역학/기타). 방법론 정의 후 별도 설계.

## 3. 포트폴리오 전략 (권장)
- **엔진 우선**: 장기 독립적 "물리정보 + 구조보장 + 소-N 강건" 트윈 엔진을 코어로.
- **기둥 순서**: 1) 심장·혈관(anchor) → 2) **근골격**(형식 native + KRDF 근질환) →
  3) **뇌**(cerebro 자산) / **호흡·신장**(Windkessel 동형·FMD 시너지).
- **면역**: 다른 형식이라 **탐색 슬롯**(엔진과 별도 method 트랙). 성숙 후 편입.
- **경계**: 넓히면 얕아짐 + 대형 컨소시엄과 경쟁. 각 기둥은 KRDF 희귀질환 데이터 접근이
  차별점일 때만 착수.

## 4. 다음 확인 사항
- [ ] 근골격: KRDF 희귀 근/골 질환 코호트에 모션/EMG/영상 있는가?
- [ ] 뇌: cerebrovascular_cfd 현 상태·재활용 범위 점검.
- [ ] 폐/신장: MIMIC 내 벤틸레이터·신기능 변수로 RC 모델 MVP 가능성.
- [ ] 면역: 사용자 구상 중인 비-Hamiltonian 형식 명세 → 별도 설계 문서.

*(엔진·기둥 진행 시 본 문서를 후보군 SSOT로 갱신.)*
