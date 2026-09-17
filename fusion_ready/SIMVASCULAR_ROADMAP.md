# SimVascular 로드맵 — 강체벽 CFD → 0D 결합 → 수동 역학 → 능동 수축 → FSI (2026-09-16)

목표: case 1009 좌심실을 SimVascular 생태계(svMultiPhysics, svZeroDSolver)에서 **FSI + 능동수축**까지
끌고 간다. 단계마다 "통과 조건(게이트)"을 두고, 못 넘으면 다음 단계로 가지 않는다 — Paper B에서 했던
그 방식 그대로.

## 0. 먼저 알고 출발해야 하는 두 개의 벽

**벽 1 — 이 환자에게는 벽 운동 데이터가 없다.** MM-WHS 1009는 정지 CT 한 프레임이다. 능동수축·FSI
모델은 만들 수 있지만, 그 결과를 이 환자로 검증할 방법이 없다. 따라서 1009로 만드는 것은
"해부학은 환자 것, 생리학은 문헌값으로 채운 **그럴듯한** 모델"이다. 논문에서 이걸 환자 특이적
검증이라고 쓰면 안 된다. 해법은 둘 중 하나, 실제로는 둘 다:
- (a) 1009로 **파이프라인을 완성**한다(방법론). 목표 지표는 집단값: EDV 132 mL(CT 혈액풀) 기준
  EF 55–65 %, 최고 LV압 100–140 mmHg, Klotz EDPVR.
- (b) **벽 운동이 있는 공개 케이스를 하나 병행**해서 검증한다. 후보: ACDC(cine MRI, ED/ES 라벨,
  등록만 하면 됨). CT 형상과 MRI 운동을 한 환자로 섞어 쓰면 안 되므로, 검증은 그 케이스에서
  파이프라인을 처음부터 다시 돌려서 한다.

**벽 2 — FSI는 유체·고체 계면의 절점이 일치하는 메시가 필요하다.** svMultiPhysics(구 svFSI)의 FSI는
유체 메시와 고체 메시가 계면에서 같은 절점을 공유해야 한다(`projection`으로 묶음). 지금의 두 표면
(`SV/fluid_cavity_cm.vtp`의 endocardium 133.6 cm², `SV/solid_myocardium_cm.vtp`의 endocardium
134.3 cm²)은 같은 라벨 경계에서 나와 위치는 일치하지만 삼각분할이 다르다. 해법: **라벨 영상에서
다중영역 사면체 메시를 한 번에** 만든다(pygalmesh/CGAL `generate_from_array`: 라벨 500 = 유체,
205 = 고체, 계면 자동 정합). 32 GB PC에서 할 일이고 샌드박스에서는 못 한다.

## 1. 단계

| 단계 | 하는 일 | 도구 | 입력(있음/없음) | 게이트 | 기간 |
|---|---|---|---|---|---|
| **0** ✔ | SV가 읽는 모델 3개, 면 ID, cm 단위 | `export_simvascular.py` → `SV/` | 있음 | 면적 일치(유체 endo 133.6 ≈ 고체 endo 134.3 cm²; 승모판 7.5, 대동맥 3.9 cm²) | 끝 |
| **1** | 강체벽 비정상 Navier–Stokes, 팬텀 도메인 | SV GUI: Import Model(`fluid_phantom_cm.vtp`) → 면 지정 → TetGen(엣지 0.10–0.15 cm, 경계층 3층) → svMultiPhysics 유체; inlet 유량 파형 = `lv_cfd/mitral_flow_profile.csv`, outlet RCR | 있음 | OpenFOAM `lv_cfd_patient`와 **같은 형상·같은 BC**에서 최고 유속·압력강하 10 % 이내 | 2–3주 |
| **2** | 0D 폐회로 + 3D–0D 결합 | svZeroDSolver(`pip install pysvzerod`): LV 시변 탄성(Ees, Eed/EDPVR, V0, τ) + 대동맥 RCR + 폐정맥 압력원. pH-PINN 8개 지표 → 0D 블록 매핑표 작성 → 0D 단독 PV loop → 1단계 유출구를 0D 회로에 결합 | 있음(Paper A 지표) | 0D PV loop의 EDV/ESV/EF/최고압이 Paper A 코호트 범위 안; 결합 후 유출 유량 = 0D 유량 | 2주 |
| **3** | 고체 수동 역학(이완기 충만) | 다중영역 메시(pygalmesh) → 심근 사면체 ~300k(벽 두께 방향 3–4층) → 섬유 방향 LDRB(Bayer 2012 규칙: endo +60°, epi −60°; SV에 없음 → 자체 `ldrb.py`, Laplace 3개를 scipy sparse로) → Holzapfel–Ogden 수동 재료(문헌 시작값) → 내막 압력 0→10 mmHg 팽창 | 메시·섬유 없음(만들어야 함) | 압력–부피 곡선이 Klotz EDPVR(EDV 132 mL 기준) ±15 %; 기저면 경계조건(용수철/고정)에 따른 민감도 기록 | 3–4주 |
| **4** | 능동 수축(전기생리 없이 먼저) | svMultiPhysics 심근 능동응력: 시간에 따른 활성 장력 함수 부과 → 등척 수축 → 후부하(2단계 0D 회로)로 박출 → PV loop | 활성 장력 파형 없음(문헌) | EF 55–65 %, 최고압 100–140 mmHg, 종축 단축·벽 비후·**심첨 비틀림 방향이 생리적**(frame A 손대칭 검증과 직결) | 4–6주 |
| **5** | FSI 한 주기 | 유체(공동) + 고체(3단계 메시) 정합 메시 → svMultiPhysics FSI(ALE); 판막은 면 BC(시간 개폐 압력 또는 저항 판막), 접촉 없음; 충만+박출 1주기 | 있음(3·4 결과) | 수렴·질량 보존; 승모판 E파 0.6–1.0 m/s, 대동맥 최고 1.0–1.5 m/s(정상 성인 범위) | 6–8주+ |
| **6** | 검증·집필 | 1단계 ↔ 팬텀 계측; 4단계 ↔ ACDC 케이스; **0D pH-PINN 추정치 ↔ 3D EM 모델의 emergent PV 거동 일치성** | (b) 케이스 필요 | — | — |

6단계의 마지막 항목이 이 전체의 논문 주제다: "0D 디지털 트윈(pH-PINN)이 추정한 파라미터가 같은 해부에서
돌린 3D 전기역학 트윈의 거동과 일치하는가". Paper A/B와 이 로드맵을 하나로 묶는 질문이다.

## 2. 환경 (새 PC, WSL2 Ubuntu 22.04)

- SimVascular GUI(Windows 설치판) — 모델·메시 단계. Python API(`sv` 패키지)는 GUI 내장 파이썬.
- svMultiPhysics — 소스 빌드(CMake, OpenMPI, 선택 PETSc/Trilinos). 예제 디렉토리의 `LV_*` 테스트
  (수동 팽창·능동 수축 케이스)가 3·4단계의 교재다 — 먼저 그걸 그대로 돌려본다.
- `pip install pysvzerod pygalmesh gmsh meshio pyvista` (pygalmesh는 `apt install libcgal-dev libeigen3-dev` 선행).
- 계산량: 1단계 50만 사면체·3주기 → 8코어 수 시간; 5단계 FSI 1주기 → 하루 단위. GPU는 안 쓴다(RTX 3060은 PINN 전용).
- OneDrive 밖(WSL 파일시스템)에서 돌릴 것. 케이스 폴더는 `C:\work\Cardiac\sv\stage<k>/`에 설정만 두고 결과는 git 제외.

## 3. 파라미터 출처 표 (무엇이 환자 것이고 무엇이 문헌인지 — 논문에 그대로)

| 항목 | 출처 |
|---|---|
| 심근·공동 형상, 벽 두께, 유두근·육주 | 환자 CT (1009) |
| 판막 위치·크기(판륜) | 환자 CT에서 측정, 첨판 형상은 파라메트릭 |
| 섬유 방향 | 규칙 기반(LDRB) — 문헌 |
| 수동 재료(HO), 능동 장력 파형 | 문헌 시작값 → 3·4단계 게이트에 맞춰 조정 |
| 후부하(RCR), 전부하 | Paper A pH-PINN 코호트 추정치 범위 → 0D 매핑 |
| 벽 운동·PV 검증 | **없음(1009)** → ACDC 케이스 |

## 4. 지금 바로 할 수 있는 것 / 새 PC에서 할 것

- 지금(샌드박스): 0단계 완료. `SV/sv_models.json`에 면 ID·면적.
- 새 PC 첫 주: SimVascular 설치 → Demo 프로젝트(원통→대동맥) 한 번 → `fluid_phantom_cm.vtp` 임포트 → TetGen → svMultiPhysics 유체 정상 실행까지. 이게 되면 1단계는 BC 맞추기만 남는다.
- 그다음: svMultiPhysics `LV_*` 예제 재현(3·4단계 교재) → pygalmesh로 1009 다중영역 메시.

## 5. 리스크와 중단 기준

- svMultiPhysics 빌드·수렴 문제는 흔하다. 2주 이상 막히면 커뮤니티(SimTK 포럼)에 케이스 파일과 함께 질문.
- 3단계에서 Klotz 곡선을 ±15 % 안에 못 넣으면 4단계로 가지 않는다(수동 역학이 틀린 채로 능동을 얹으면 전부 의미 없음).
- 5단계는 3·4 통과 후에만. 시간이 없으면 4단계(EM + 0D 후부하)에서 멈춰도 논문 하나가 된다 — FSI 없는 EM 모델이 표준 관행이다.

## 6. 운동 데이터 확보 계획 (2026-09-16 조사)

| 트랙 | 데이터 | 접근 | 쓰임 |
|---|---|---|---|
| 운동학 검증 (주) | **cMAC** — Cardiac Atlas Project, STACOM 2011 Motion Tracking Challenge: 자원자 15명 + 팬텀, cine SSFP + 3D 태깅 MRI + 3D US, 전 주기 수동 추적 랜드마크 12개 | 신청 없이 공개 (cardiacatlas.org) | 4단계 능동수축의 비틀림·단축·변형률을 랜드마크 궤적과 직접 비교 |
| 운동학 검증 (부) | **ACDC** — cine SAX 150명, 5군(정상/DCM/HCM/MI/RV), ED/ES 라벨 | 등록 (creatis.insa-lyon.fr) | 질환별 부피 곡선·형상; 슬라이스 5–10 mm |
| 보강 | M&Ms-2 (동의서), MITEA 3D echo (기관 이메일 신청, ED/ES만) | 신청 | 다벤더·3D echo |
| **혈역학 보정** | **MIMIC-IV-ECHO** (PhysioNet, credentialing 있음): TTE DICOM 4,579명/7,243 스터디 + A4C LV 부피 주석 서브셋; MIMIC-IV 파형과 환자 단위 연결 | 이미 자격 있음 | 2·4단계의 0D/EM 목표값(EF·부피·E/A·LVOT VTI + 동맥압) — pH-PINN 코호트와 동일 환자 |
| 불가/보류 | 공개 4D CT 사실상 없음(루이진 18명 세트는 공개 여부 확인 필요); UK Biobank는 PI 명의 신청 | — | — |

원칙: CT 1009 형상에 다른 피험자의 운동을 얹지 않는다. 운동학 검증은 그 피험자(cMAC/ACDC)의 cine에서
형상을 다시 만들어 파이프라인 전체를 돌린다(슬라이스 스택 → 표면 재구성 단계 추가; SimVascular
세그멘테이션-로프팅 활용). 압력은 어디에도 없으므로 비침습 추정(ESP ≈ 0.9 × SBP)을 명시.
