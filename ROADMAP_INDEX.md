# Roadmap Index — 전체 비전 한눈에

> 2026-07-07 세션 4 정리. 이 프로젝트의 전략 문서 지도(navigation hub). 각 문서가
> single source of truth이며, 본 인덱스는 상호관계만 요약.

## 계층 구조 (좁은→넓은)
```
CAPABILITY_ROADMAP        ← 가로지르는 역량(UQ·인과·규제·연합·SciML·QSP)  [엔진을 떠받침]
        ▲
MULTI_ORGAN_VISION        ← 심장→근골격·뇌·폐·신장·면역 전이 엔진        [엔진의 확장면]
        ▲
PLATFORM_ARCHITECTURE     ← 0D↔3D↔EP 통합 플랫폼 + L5 응용 + §8 FMD      [심장 플랫폼 본체]
        ▲
EXPANSION_PLAN (E0~E5) + ECG_AUGMENTATION_DESIGN   ← 심장 트윈 보강/확장  [근거리 실행]
        ▲
AUDIT_EXPANSION_BACKLOG   ← 감사(T1~T3) + 문헌근거                        [현 논문 방어]
        ▲
CARDIAC_DIGITAL_TWIN_STATUS  ← 현 구현 상태(§1~20, RV·CFD·정합)          [지금 코드]
```

## 문서 색인
| 문서 | 역할 | 상태 |
|---|---|---|
| `CARDIAC_DIGITAL_TWIN_STATUS.md` | 구현 현황(마스터 인수인계) | 활성(§20까지) |
| `AUDIT_EXPANSION_BACKLOG.md` | 감사·확장 항목(문헌근거) | 활성 |
| `EXPANSION_PLAN.md` | E0~E5 단계화 + 타깃저널 | 활성 |
| `ECG_AUGMENTATION_DESIGN.md` | ECG 물리정보 prior 설계 | 설계완료 |
| `PLATFORM_ARCHITECTURE.md` | 0D↔3D↔EP 플랫폼 + FMD(§8) | 활성 |
| `MULTI_ORGAN_VISION.md` | 다장기 전이 엔진 후보군 | 활성 |
| `CAPABILITY_ROADMAP.md` | 가로지르는 역량 로드맵 | 활성 |
| `ecg_integration/ECG_INTEGRATION_RUNBOOK.md` | ECG 통합 실행 런북(PowerShell) + 파이프라인 | 준비완료(데이터 pull 대기) |
| `CARDIAC_DIGITAL_TWIN_STATUS.md §21` | Session 4 산출물 전체 인덱스 | 활성 |

## 3-지평선 요약
- **H1 (지금)**: 심장 flagship 방어(AUDIT) + 근거리 보강(E2 인체침습, E0/E1 ECG) + 플랫폼 backbone(twin_parameters 스키마). 역량 C1(UQ)·C2(인과) 병행.
- **H2 (중기)**: 플랫폼 통합(3D↔0D 브리지 실증), FMD 트랙(KRDF), 근골격 2번째 기둥, 신뢰성과학 C3.
- **H3 (장기)**: 다장기 엔진 + 면역 QSP(C6) + 연합학습 C4 다기관 + 규제급 in-silico trial.

## 핵심 관통 논지
**물리정보 + 구조보장 + 소-N 강건 트윈 엔진**을, **희귀질환(KRDF 데이터 접근)** 이라는
데이터 굶주린 영역에 적용 — 대형 컨소시엄과 정면 경쟁 대신 **방법론 엔진 × 희귀질환 니치**로
차별화. 영향력 천장: 오픈소스 + 결정적 검증 시 npj급 레퍼런스 아키텍처.

## 다음 실행 후보 (택1)
1. 플랫폼 backbone `twin_parameters.json` 스키마 + 모듈 어댑터 코드.
2. near-term 응용: 약물 심독성(ChEMBL hERG) 착수.
3. 역량 C1(UQ) 최소실험: 현 PINN에 예측구간 부착.
4. 면역 QSP 형식 명세(사용자 구상 반영) → 별도 설계.

*(문서 추가/변경 시 본 인덱스 갱신.)*
