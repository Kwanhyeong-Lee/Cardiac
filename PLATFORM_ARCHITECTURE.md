# Cardiac Digital Twin — Platform Architecture

> 2026-07-07 세션 4. 목적: PINN/생리모델(0D) + 3D 해부 CFD + EP/ECG를 **하나의
> multiscale digital-twin 플랫폼**으로 통합. 흩어진 스크립트 → 모듈이 **계약(공유 파라미터
> 스키마)으로 맞물리는 시스템**. 이 문서 = 플랫폼 명세(single source of truth).

## 1. 비전
환자/집단의 심장을 **0D(집단 통계 파라미터) ↔ 3D(환자별 해부·유동) ↔ EP(전기·이온채널)**
세 스케일로 표현하고, 스케일 간 파라미터를 **양방향으로 교환**하는 트윈 플랫폼.

## 2. 레이어 아키텍처
```
┌───────────────────────────────────────────────────────────────────┐
│ L5 APPLICATION   위험예측 · 약물반응 · LAA 혈전위험 · 심독성 스크리닝  │
├───────────────────────────────────────────────────────────────────┤
│ L4 INTEGRATION BUS   ▶ 공유 파라미터 스키마(twin_parameters.json)     │
│   0D⇄3D: Windkessel(R,C) ⇄ Ea/tau  |  3D⇄EP: activation ⇄ wall motion │
│   EP⇄0D: QTc/이온채널 ⇄ 에너지섭동(ΔH)                                 │
├──────────────┬───────────────────────┬────────────────────────────┤
│ L3a 0D PINN  │ L3b 3D ANATOMY/CFD     │ L3c EP / ECG               │
│ (Track A)    │ (Track B)              │                            │
│ pH-PINN v5   │ MM-WHS+TotalSeg+STACOM │ 이온채널맵 + ECG feature   │
│ Ees,Eed,Ea,  │ → mesh assembly        │ QRS,QTc,LVH,PTFV1,AF       │
│ tau,V0,PVA,  │ → OpenFOAM CFD         │ → electro-energetic 브리지 │
│ 약물-에너지  │ → Windkessel 추출      │                            │
├──────────────┴───────────────────────┴────────────────────────────┤
│ L2 VALIDATION REGISTRY  각 파라미터에 검증 tier 태그(i 합성/ii 침습/iii outcome) │
├───────────────────────────────────────────────────────────────────┤
│ L1 DATA  MIMIC-IV(echo/ECG/waveform)·eICU·MM-WHS/STACOM CT·동물PV·ChEMBL·PIC │
└───────────────────────────────────────────────────────────────────┘
```

## 3. 모듈 레지스트리
| 모듈 | 레이어 | 입력 | 출력 | 상태 | 핵심 파일 |
|---|---|---|---|---|---|
| pH-PINN | L3a | echo/vitals | Ees,Eed,Ea,tau,V0,PVA | **게재임박** | `pinn_hamiltonian_v5.py` |
| 약물-에너지 | L3a | PINN params+약물 | ΔH network | 완료 | `drug_hamiltonian_perturbation.csv` |
| 분할·조립 | L3b | CT | STL 13종 | 부분(RV in-patient 진행) | `assemble_cardiac_geometry.py` |
| CFD | L3b | mesh+BC | 유동·Windkessel | **미수렴(v2 재실행중)** | `lv_cfd_anatomical/`, `rerun_cfd_v2_robust.sh` |
| Windkessel 브리지 | L4 | CFD | R,C→Ea,tau | 코드有·데이터대기 | `windkessel_phpinn_bridge.py` |
| 이온채널맵 | L3c | — | 12ch×8region | 완료 | `ion_channel_cardiac_map.py` |
| ECG 보강 | L3c | ECG | 파라미터 prior | 설계완료 | `ECG_AUGMENTATION_DESIGN.md` |

## 4. 통합 계약 (플랫폼의 핵심)
### 4.1 공유 파라미터 스키마 `twin_parameters.json` (제안)
모든 모듈이 읽고 쓰는 canonical 레코드:
```json
{
  "id": "<patient|cohort id>",
  "provenance": {"modality": "echo|ecg|cfd|animal", "source": "MIMIC-IV|Case1009|..."},
  "hemodynamic": {"Ees":, "Eed":, "Ea":, "tau":, "V0":, "coupling":, "EDP":, "efficiency":},
  "energetics": {"H_PVA":, "SW":, "PE":, "eff":},
  "windkessel": {"R1":, "R2":, "C":},
  "geometry": {"mesh_ids":[], "LV_mL":, "RV_mL":},
  "ep": {"QRS_ms":, "QTc_ms":, "LVH_mV":, "PTFV1":, "AF":},
  "validation_tier": {"Ees":"ii", "Eed":"i", ...}
}
```
→ 0D·3D·EP가 같은 스키마를 통해 파라미터를 교환(느슨한 결합). 각 값에 **검증 tier 태그**로
감사(A2)와 플랫폼을 일체화.

### 4.2 스케일 브리지 (양방향)
- **0D→3D**: 집단 PINN이 학습한 Ea/R/C 분포 → CFD outlet Windkessel BC. (지금 실증가능)
- **3D→0D**: CFD Windkessel(R,C) → pH-PINN Ea/tau 캘리브레이션. (`windkessel_phpinn_bridge.py`)
- **EP→0D**: ECG/이온채널 → 에너지섭동 ΔH (E1b).
- **3D→EP**: activation map → wall-motion timing (Phase 4, openCARP).

## 4.3 L5 Application 레지스트리 (플랫폼의 목적)
| 응용 | 사용 레이어 | 데이터/자산 | 성숙도 | 검증 요건 |
|---|---|---|---|---|
| **약물 심독성 스크리닝** | 0D+EP | ChEMBL hERG IC50 + 이온채널맵 + ΔH network + `cardiotoxicity_ai_pipeline.py` | **near-term(자산 보유)** | QTc/TdP 임상 상관, in-silico→관측 대조 |
| **약물반응 최적화(GDMT 적정)** | 0D | PINN params + PSM/IPTW + digital-twin counterfactual | **near-term** | 인과추론 엄밀화(E-value), 전향 검증 |
| **위험층화/예후** | 0D+EP | ECG+혈역학 → 사망/HF입원 (E4) | mid | incremental value vs EF+NT-proBNP |
| **LAA 폐색술(Watchman) 계획** | 3D+EP | LAA 기하 + CFD 정체(E1c) + AF | mid(기하 구축중) | 디바이스 사이징·잔여누출·혈전 대조 |
| **판막 중재(TAVR/mitral) 계획** | 3D | aortic_root/valve STL + CFD | long(CFD 수렴·밸브동역학 선행) | 중재 전후 혈역학 예측 검증 |
| **CRT(재동기화) 계획** | EP+0D | QRS/dyssynchrony + activation map(Phase4) | long | responder 예측 정확도 |
| **가상수술(septal myectomy 등)** | 3D+FSI | mesh + FSI(Phase3) | long(FSI 선행) | in-silico 수술 결과 타당성 |

**성숙도 원칙(정직)**: 약물 심독성·약물반응은 **자산이 있어 near-term 실증 가능**. 수술/중재
계획(LAA·판막·CRT·가상수술)은 **3D CFD 수렴 + 밸브동역학/FSI + 환자별 기하**가 선행이라
현재는 "in-silico 데모" 수준으로 포지셔닝(임상배치 아님). 규제·전향검증은 별도 장기 트랙.

## 5. 지금 실증 가능 vs 데이터 공백
- **가능(now)**: 0D→3D BC 이식 worked example(Case 1009 CFD의 Windkessel BC를 집단 PINN
  분포에서 세팅), 스키마 기반 파라미터 교환, ECG prior 설계.
- **공백**: 동일 환자가 (영상+종단 혈역학)을 함께 보유한 코호트 부재 → 완전한 end-to-end
  단일환자 트윈은 미실증. 필요: CMR+혈역학 동시 코호트(UK Biobank류) 또는 CT+cath.

## 6. 플랫폼 → 산출 매핑
- **소프트웨어 산출**: 공유 스키마 + 오케스트레이터(기존 `run_all.py`/CFD 스크립트 통합 CLI)
  → 재사용가능 플랫폼(오픈소스화 가능, 논문 impact↑).
- **논문 산출(조율 시리즈)**: Flagship(플랫폼 프레임워크→npj) / Paper A(0D PINN→J-BHI) /
  Paper B(3D CFD+BC 캘리브레이션→MedIA·CBM) / Paper C(ECG 멀티모달→J-BHI/npj).

## 7. 빌드 로드맵 (기존 STATUS Phase·E-thread와 정렬)
1. **스키마 확정** `twin_parameters.json` + 각 모듈 read/write 어댑터. (플랫폼 backbone)
2. CFD 수렴(v2) → Windkessel 추출 → 3D⇄0D 브리지 실증(worked example).
3. E0(ECG 링크) → E1 ECG prior → L3c 통합.
4. Validation registry 자동화(각 산출 파라미터에 tier 태그).
5. 오케스트레이터 CLI로 L1→L5 파이프라인 일원화.

*(플랫폼 변경 시 이 문서를 single source of truth로 갱신.)*

---

## 8. 질환특이 확장 트랙: FMD (Fibromuscular Dysplasia)

> 2026-07-07 추가. 데이터 접근 enabler: 저자가 **한국희귀질환재단** 직위 보유 →
> FMD 코호트 접근이 현실적. FMD를 플랫폼의 disease-specific 응용 + 신규 vascular-bed
> 모듈로 정식 트랙화.

### 8.1 핵심 논지 (방법론↔미션 정합)
희귀질환은 소표본 → 데이터굶주린 ML 실패. **physics-informed 트윈은 기계론이 데이터를
대체**하므로 소-N에서 강함 → "**희귀질환 = 물리정보 트윈 최적 적용처**". PINN 방법론과
재단 미션을 하나로 묶는 서사(논문·그랜트 공용).

### 8.2 플랫폼 접속점
- FMD = 전신 동맥병증 → **Ea / Windkessel R·C(후부하 레이어)** 직접 교란(네이티브 파라미터).
- 신장동맥 협착 → 신혈관성 HTN → 심장 후부하·LVH → **심장 트윈** 되먹임.
- 경동맥/두개내 → **cerebrovascular_cfd**(기존 자산) 재활용 → 협착 혈역학·박리·WSS.
- 관상(SCAD) → 관상 CFD·WSS.
- 공유 스키마 `twin_parameters.json`의 windkessel/hemodynamic 필드가 **심장↔혈관 교차 통화**.

### 8.3 빌드 분기 (레지스트리 내용에 의존 — 확인 필요)
| 레지스트리 보유 데이터 | 빌드 가능 MVP | 활용 자산 |
|---|---|---|
| 영상(CTA/MRA renal·carotid) | 환자별 혈관 CFD → 협착 심각도·박리위험·WSS | cerebrovascular_cfd 파이프라인 |
| 임상+혈압 | 0D 동맥 모델(Ea/R/C, 신혈관성 HTN→심장 후부하) | pH-PINN 후부하 레이어 |
| 유전자 중심 | 기전 링크(혈관 유전자), 트윈 간접 | 이온채널/유전 매핑 |

### 8.4 거버넌스(초기 필수)
- IRB·동의·비식별, **소표본 재식별 위험** 관리, 재단 데이터 사용정책 준수.

### 8.5 산출 포지셔닝
- 신규성: 한국 FMD 코호트 + 다영역 혈관 트윈 + 소-N 물리정보 방법론 → 미충족수요.
- 타깃: npj Digital Medicine(rare-disease digital twin 선호) / Orphanet J Rare Dis 등.
- **오픈 질문(다음 확인)**: 재단 레지스트리에 영상/유전/임상 중 무엇이 있는가? → 8.3 분기 결정.
