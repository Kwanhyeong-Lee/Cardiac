# Cardiac Digital Twin — 종합 진행 현황 및 실행 가이드

> **최종 업데이트**: 2026-07-06
> **작성 목적**: OneDrive로 동기화된 **어떤 컴퓨터에서든** Claude를 통해 이어서 작업할 수 있도록, 현재까지의 모든 진행사항/파일구조/다음 단계/실행 명령어를 기록
> **환경**: OneDrive 동기화 대상 모든 컴퓨터 (원본: Samsung Notebook 7 Force, i7-8565U / GTX 1650 4GB / 40GB RAM)
> **Patient**: MM-WHS Case 1009, CT contrast-enhanced, voxel 0.488×0.488×0.625 mm

---

## 1. 프로젝트 전체 구조

이 프로젝트는 **환자별 심장 Digital Twin**을 구축하는 것이 목표이며, 크게 두 개의 Track으로 나뉜다.

### Track A: pH-PINN (Port-Hamiltonian Physics-Informed Neural Network)

혈역학 파라미터(Ees, Ea, tau, Vo 등)를 에너지 보존 기반으로 학습하는 신경망이다. 이미 v5까지 완성되었고, eICU 검증까지 마쳤다.

**핵심 파일들:**
- `pinn_hamiltonian_v5.py` — pH-PINN 모델 정의 + 학습 코드
- `phpinn_v5_trained.pt` — 학습된 모델 가중치 (PyTorch)
- `phpinn_v5_history.json` / `phpinn_v5_metrics.json` — 학습 이력
- `eicu_drug_response_v2.py` — eICU 외부 검증 (2,720 에피소드)
- `eicu_drug_response_v2_results.json` — 검증 결과 (AUC 0.837, Concordance 84.4%)

**Hamiltonian 구조:**
- H = PVA = SW + PE (Pressure-Volume Area)
- 단위 변환: 0.000133322 (mmHg·mL → J)
- Windkessel 연동: R (dissipation), C (compliance), τ=RC

### Track B: 해부학적 LV CFD (OpenFOAM pimpleFoam)

환자 CT(Case 1009)로부터 추출한 LV 내강에서 혈류역학 시뮬레이션을 수행한다. pimpleFoam으로 t=2.4s까지 시뮬레이션이 완료되었다.

**핵심 디렉토리:** `lv_cfd_anatomical/`
- `0/p`, `0/U` — 초기조건
- `system/controlDict` — pimpleFoam, endTime 2.4, deltaT 1e-5, maxCo 0.8 (v1, 발산 원인)
- `system/snappyHexMeshDict` — LV 표면 메시 설정
- `system/blockMeshDict`, `fvSchemes`, `fvSolution` — 메시/이산화/솔버
- `constant/triSurface/` — STL 파일들 (아래 상세)
- `constant/transportProperties` — rho 1060 kg/m³, nu 3.3e-6 m²/s (혈액)
- `postprocess.sh` — WSL에서 실행하는 후처리 스크립트
- `postprocess_analysis.py` — Python 후처리 (probe 파싱, 유량, Windkessel 추출, WSS)
- `run.sh` — 시뮬레이션 실행 스크립트

**시뮬레이션 상태:**
- ⚠️ **pimpleFoam 발산 (SIGFPE crash at t ≈ 2.64×10⁻⁵ s)** — 상세 분석 Section 18 참조
- 61개 시간 디렉토리는 **빈 placeholder** (uniform (0 0 0), 32줄) — 실제 시뮬레이션 결과가 아님
- ✅ WSL → OneDrive 동기화 완료 (메시 + 로그 + 설정파일)
- 🔧 **v2 수정 config 생성 완료** — `lv_cfd_anatomical_v2_configs/` 참조
- 총 733MB (대부분 polyMesh + 빈 time dirs)

**probe 위치 (4곳):**
1. LV center: (-0.0373, 0.0318, -0.1596) m
2. Near mitral: (-0.0250, 0.0080, -0.1500) m
3. Near aortic: (-0.0200, 0.0220, -0.1350) m
4. Mid-cavity: (-0.0373, 0.0200, -0.1500) m

**flowRate function objects:** mitralInlet, aorticOutlet → phi 적분 → 유량(m³/s)

### Track A+B 통합 (미완료)

CFD에서 Windkessel 파라미터(R_total, C) 추출 → pH-PINN의 Ea, tau에 매핑. `postprocess_analysis.py`가 이 통합을 수행하는 코드이나, 아직 실제 시뮬레이션 데이터에 대해 실행되지 않았다.

---

## 2. 현재 보유 STL 파일 인벤토리

### `lv_cfd_anatomical/constant/triSurface/` (CFD 프로젝트 내)

| 파일 | 크기 | 삼각형 수 | 출처 | 상태 |
|------|------|-----------|------|------|
| `lv_surface.stl` | 44 MB | 166,936 | MM-WHS label 550 (marching cubes) | **사용 중** — CFD 주 도메인 |
| `mitral_valve.stl` | 5.5 MB | 22,344 | `generate_valves.py` (parametric) | **생성 완료** — D=30mm saddle annulus |
| `aortic_valve.stl` | 12 MB | 45,284 | `generate_valves.py` (parametric) | **생성 완료** — D=23mm, Valsalva sinus |
| `aortic_root.stl` | 7.9 MB | 32,744 | CT label 820 하부 30% 추출 | **생성 완료** — 12.9 mL |
| `papillary_muscles.stl` | 79 MB | 253,920 | HU thresholding (0-150 in label 550) | **정제 필요** — 단일 덩어리, 2개 PM 분리 안 됨 |
| `laa.stl` | 170 KB | 688 | 형태학적 분리 시도 | **실패** — 139 voxels뿐, 전용 데이터 필요 |
| `valve_metadata.json` | 3 KB | — | valve 위치/재료 속성 | **완료** |

### `cardiac_meshes/` (초기 추출 — 전체 심장 STL)

| 파일 | 크기 | 출처 |
|------|------|------|
| `LV_case1009.stl` | 8.0 MB | MM-WHS label 550 |
| `LV_case1009_CFD.stl` | 8.0 MB | CFD용 후처리 버전 |
| `LV_Myocardium_case1009.stl` | 18 MB | label 205+500 |
| `LA_case1009.stl` | 4.5 MB | label 420 |
| `Aorta_case1009.stl` | 4.3 MB | label 820 |
| `PA_case1009.stl` | 7.6 MB | label 850 |
| `RA_case1009.stl` | 5.3 MB | label 600 |
| `RV_case1009.stl` | 12 MB | label 620 — **경고: 0 voxels, 빈 STL** |

### `cardiac_meshes_all/case_1009/` (Valve-open 버전 포함)

| 파일 | 크기 | 특이사항 |
|------|------|----------|
| `LV_valves_open.stl` | 7.7 MB | MV/AV 개구부가 뚫린 LV |
| `Myo.stl` | 18 MB | 심근 전체 |
| `valve_cfd_config.json` | 581 B | CFD BC 설정 |
| `valve_info.json` | 608 B | Valve 위치 정보 |

---

## 3. 해부학적 구조 현황 (5 present / 12 missing)

### 현재 보유 구조물 (Present)

1. **LV blood cavity** (label 550) — 76.5 mL, CFD 유체 도메인
   - 내부 trabeculae/papillary가 blood pool로 합쳐져 있음 (24.8% tissue-like voxels)
2. **LV wall** (label 500) — 150.4 mL, 두께 8-15mm
   - Holzapfel-Ogden anisotropic hyperelastic
   - fiber angle: epicardium -60° → endocardium +60° (transmural rotation)
   - 현재 rigid wall BC → FSI 전환 시 deformable로
3. **Myocardium** (label 205) — 125.7 mL, ρ=1050 kg/m³
4. **Left Atrium** (label 420) — 54.7 mL, inlet pressure BC로만 반영
5. **Ascending Aorta** (label 820) — 50.7 mL, outlet pressure BC로만 반영

### 누락 구조물 (Missing) — 12개, 생체역학 속성 포함

#### 3.1 Mitral Valve Leaflets (승모판 첨판)
- **해부**: Anterior (A1-A3) + Posterior (P1-P3), annulus 25-35mm
- **두께**: 0.4-1.3 mm (anterior thicker)
- **탄성**: Circumferential 2000-8000 kPa / Radial 500-2000 kPa (J-shaped)
- **밀도**: 1100 kg/m³
- **구성모델**: Fung-type exponential or May-Newman-Yin
- **Poisson ratio**: 0.49
- **CFD 전략**: Tier 1 (resistance/porosity) → Tier 2 (prescribed kinematics) → Tier 3 (FSI via preCICE)
- **현재 상태**: `mitral_valve.stl` 생성 완료 (parametric, D=30mm)
- **개선 필요**: MVAA 2026 실측 데이터로 교체

#### 3.2 Aortic Valve Cusps (대동맥판 교두)
- **해부**: 3 cusps (LCC, RCC, NCC), 23-27mm annulus
- **두께**: 0.3-0.7 mm
- **탄성**: Circumferential 2000-15000 kPa / Radial 500-3000 kPa
- **밀도**: 1100 kg/m³
- **구성모델**: Fung-type or Holzapfel fiber-reinforced
- **현재 상태**: `aortic_valve.stl` 생성 완료 (parametric, D=23mm, Valsalva sinus)

#### 3.3 Chordae Tendineae (건삭)
- **해부**: Marginal, basal, strut chordae → leaflet edge에서 papillary muscle로 연결
- **직경**: 0.3-2.5 mm (strut ~2.5mm, marginal ~0.3mm)
- **탄성**: 40,000-80,000 kPa (extensional)
- **구성모델**: 1D nonlinear elastic (exponential or polynomial)
- **해상도 문제**: CT 0.488mm → marginal chordae (0.3mm) 해상도 미달
- **데이터 필요**: 문헌 기반 parametric 생성 또는 micro-CT

#### 3.4 Papillary Muscles (유두근)
- **해부**: Anterolateral PM + Posteromedial PM
- **탄성**: Passive 10-30 kPa / Active 100-300 kPa
- **밀도**: 1060 kg/m³
- **구성모델**: Transversely isotropic (fiber 방향 long axis)
- **현재 상태**: `papillary_muscles.stl` 존재하나 단일 덩어리 (18.66 mL)
- **개선 필요**: 2개 PM으로 분리 (X좌표 기준 anterolateral/posteromedial)

#### 3.5 Trabeculae Carneae (심실 소주)
- **해부**: LV endocardium 위의 근육 돌기
- **탄성**: 10-50 kPa (myocardium과 동일 — 같은 조직)
- **밀도**: 1060 kg/m³
- **현재 상태**: PM과 합쳐진 상태로 HU thresholding 됨
- **개선 필요**: PM과 trabeculae 분리

#### 3.6 Coronary Arteries (관상동맥)
- **해부**: LCA (LAD, LCx) + RCA, 직경 3-5mm (proximal)
- **벽 두께**: 0.5-1.0 mm
- **탄성**: Healthy 500-2000 kPa / Calcified plaque 5,000-50,000 kPa / Lipid core 1-10 kPa
- **구성모델**: Holzapfel-Gasser-Ogden (HGO, 2-fiber family)
- **해상도 문제**: 일반 CT로는 lumen/wall 구분 어려움 → 전용 CTA 필요
- **데이터 소스**: ImageCAS (1,000 CTA + annotation)

#### 3.7 Left Atrial Appendage (좌심방이, LAA)
- **해부**: LA에서 돌출된 맹낭 구조, 혈전 호발 부위
- **탄성**: Passive 50-200 kPa (LA wall보다 얇고 부드러움)
- **밀도**: 1050 kg/m³
- **임상 중요성**: Watchman/Amulet device 삽입 시 천공 위험, AF 시 혈전
- **현재 상태**: `laa.stl` 형태학적 분리 실패 (139 voxels)
- **데이터 소스**: Public Cardiac CT Dataset (전용 LAA annotation)

#### 3.8 Right Ventricle (우심실)
- **두께**: 3-5 mm (LV의 1/3)
- **탄성**: 5-20 kPa (LV보다 얇고 유연)
- **MM-WHS 문제**: label 620이 **모든 case에서 0 voxels** — 데이터셋 수준 결함
- **해결**: TotalSegmentator `heartchambers_highres` task (Dice ~0.58)

#### 3.9 Interventricular Septum (심실중격)
- **해부**: LV/RV를 나누는 근육벽, 두께 ~10-15mm
- **탄성**: LV free wall과 유사하나 fiber 방향 다름
- **필요**: RV 확보 후 자동 분리

#### 3.10 Mitral Annulus (승모판륜)
- **해부**: MV leaflet을 지지하는 fibrous ring
- **탄성**: 200-1000 kPa (fibrous tissue, myocardium보다 stiff)
- **필요**: Valve 모델링의 경계조건으로 중요

#### 3.11 Aortic Root Complex (대동맥근부)
- **해부**: Valsalva sinus, sinotubular junction (STJ), annulus
- **벽 탄성**: 400-1500 kPa
- **현재 상태**: `aortic_root.stl` 추출 완료 (label 820 하부 30%)

#### 3.12 Pericardium (심낭)
- **해부**: 심장 외곽을 감싸는 2중막 (섬유성 + 장측)
- **탄성**: 500-5000 kPa (highly nonlinear, J-shaped)
- **역할**: 심장 과팽창 제한, 좌우 심실 상호작용 매개

---

## 4. 데이터 소스 & 확보 방안

### 4.1 TotalSegmentator (★★★ 최우선)
- **URL**: `pip install TotalSegmentator`
- **용도**: RV, 4-chamber segmentation (MM-WHS에서 누락된 RV 보완)
- **task**: `heartchambers_highres`
- **실행 명령**:
```bash
cd /mnt/c/Users/alex0/OneDrive/PINN\ heart/MM-WHS/ct_train/
TotalSegmentator -i ct_train_1009_image.nii.gz \
  -o /mnt/c/Users/alex0/OneDrive/PINN/260421\ \(심장\)\ -\ main/totalseg_output/ \
  --task heartchambers_highres --device gpu
```
- **출력**: RV, LV, RA, LA, myocardium 각각의 NIfTI mask
- **라이선스**: Apache 2.0

### 4.2 ImageCAS (★★★)
- **URL**: https://www.kaggle.com/datasets/xiaoweixumedicalai/imagecas
- **용도**: Coronary artery segmentation (1,000 CTA with 3D annotation)
- **크기**: ~200 GB
- **Fills**: Coronary arteries (#3.6)
- **라이선스**: CC BY-NC-SA 4.0

### 4.3 Public Cardiac CT Dataset (★★★)
- **URL**: https://github.com/Bjonze/Public-Cardiac-CT-Dataset
- **용도**: LAA, pulmonary vein, coronary ostia annotation
- **특이점**: LAA 전용 annotation 있음 (MM-WHS에는 없는 것)
- **Fills**: LAA (#3.7), coronary (#3.6) — 3개 gap 동시 해결

### 4.4 MVAA 2026 Challenge (★★)
- **URL**: https://www.codabench.org/competitions/15662/
- **용도**: Mitral valve 전용 데이터 (CT + 3D TEE + surgical video)
- **Fills**: MV leaflets (#3.1), chordae (#3.3), annulus (#3.10)
- **접근**: 계정 생성 → Participate → training data 다운로드

### 4.5 SimVascular Vascular Model Repository (★★)
- **URL**: https://www.vascularmodel.com/
- **용도**: CFD-ready coronary artery 모델 (mesh + BC)
- **Fills**: Coronary (#3.6) — SimVascular format → OpenFOAM 변환 필요

### 4.6 openCARP + CARPentry (★ — Phase 4 이후)
- **URL**: https://opencarp.org/
- **용도**: 심장 전기생리학 시뮬레이션 (activation → wall motion → CFD coupling)
- **Fills**: Ion channel distribution → electromechanical coupling

### 4.7 4D Flow MRI Challenges (★)
- **URL**: https://www.cardiacatlas.org/challenges/
- **용도**: CFD 검증용 in-vivo flow data
- **Fills**: Validation (velocity field, flow pattern 비교)

### 4.8 PhysioNet (이미 활용 중)
- eICU-CRD 2.0: pH-PINN 외부 검증에 사용
- MIMIC-IV 3.1: 연동 대기 중 (renal PINN 확장 시)

---

## 5. 이온 채널 분포 지도 (Phase 4 — 외골격 완료 후)

`ion_channel_cardiac_map.py` / `.json`에 다음이 정리되어 있다.

### 12개 주요 이온 채널

| 채널 | 유전자 | 전류 | 역할 |
|------|--------|------|------|
| Nav1.5 | SCN5A | I_Na | 탈분극 upstroke |
| Cav1.2 | CACNA1C | I_CaL | plateau, EC coupling trigger |
| Cav3.1/3.2 | CACNA1G/H | I_CaT | SA/AV pacemaking |
| hERG | KCNH2 | I_Kr | 빠른 재분극 |
| KCNQ1 | KCNQ1 | I_Ks | 느린 재분극 |
| Kir2.1 | KCNJ2 | I_K1 | 휴지전위 유지 |
| Kv4.3 | KCND3 | I_to | early repolarization notch |
| HCN4 | HCN4 | I_f | 동방결절 pacemaker current |
| RyR2 | RYR2 | SR Ca release | EC coupling |
| SERCA2a | ATP2A2 | SR Ca reuptake | 이완 속도 결정 |
| NCX1 | SLC8A1 | I_NCX | Ca extrusion |
| Connexin43 | GJA1 | Gap junction | 세포간 전도 |

### 8개 심장 영역별 AP 특성

SA node, Atrium, AV node, Purkinje fiber, LV endocardium, LV midmyocardium, LV epicardium, RV

### Cell Model 매핑
- 심실: O'Hara-Rudy 2011 (ORd)
- 심방: Courtemanche 1998 / Koivumäki 2011
- SA/AV node: Fabbri 2017

### openCARP 통합 워크플로우 (7 단계)
1. 해부학적 메시 (현재 STL) → openCARP 볼륨 메시 변환
2. 영역별 fiber orientation 할당 (Rule-Based: Bayer et al. 2012)
3. 채널 conductance 매핑 (위 테이블 기반)
4. openCARP 시뮬레이션 → activation time map
5. Activation → wall motion timing (Active tension: Land et al. 2017)
6. Wall motion → CFD prescribed displacement BC
7. CFD 결과 → pH-PINN 파라미터 업데이트

### Heart Failure Remodeling 패턴
- SERCA2a: ↓40-60% → 이완 장애 (HFpEF key mechanism)
- NCX1: ↑50-100% → diastolic Ca leak
- I_to: ↓50-70% → APD prolongation
- Cx43: Lateralization → 전도 이질성 → arrhythmia substrate

---

## 6. 구현 로드맵 (5 Phase)

### Phase 0: 즉시 실행 가능 (1주) ← 현재 여기

| 작업 | 상태 | 파일 |
|------|------|------|
| 구조물 인벤토리 + 생체역학 | **완료** | `cardiac_structure_inventory.py/.json` |
| 데이터 소스 로드맵 | **완료** | `cardiac_digital_twin_roadmap.py/.json` |
| Parametric MV/AV STL 생성 | **완료** | `generate_valves.py`, triSurface/내 STL |
| Aortic root 추출 | **완료** | `aortic_root.stl` (label 820 하부 30%) |
| PM HU thresholding | **부분 완료** | `papillary_muscles.stl` (정제 필요) |
| LAA 형태학적 분리 | **실패** | `laa.stl` (139 voxels, 전용 데이터 필요) |
| 이온 채널 분포 지도 | **완료** | `ion_channel_cardiac_map.py/.json` |
| Samsung Notebook 설치 스크립트 | **완료** | `setup_samsung_notebook.sh` |
| WSL 동기화 스크립트 | **완료** | `sync_wsl_to_onedrive.sh` |

**남은 Phase 0 작업 (Samsung Notebook에서 실행):**

```bash
# 1. TotalSegmentator 설치 + RV 세그멘테이션
pip install TotalSegmentator
TotalSegmentator -i /mnt/c/Users/alex0/OneDrive/PINN\ heart/MM-WHS/ct_train/ct_train_1009_image.nii.gz \
  -o /mnt/c/Users/alex0/OneDrive/PINN/260421\ \(심장\)\ -\ main/totalseg_output/ \
  --task heartchambers_highres --device gpu

# 2. WSL 시뮬레이션 데이터 OneDrive 동기화
bash "/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/sync_wsl_to_onedrive.sh"

# 3. CFD 후처리 (WSL에서, 시뮬레이션 데이터가 있는 디렉토리에서)
cd <WSL 내 lv_cfd_anatomical 경로>
bash postprocess.sh
python3 postprocess_analysis.py

# 4. PM STL 정제 (2개 PM 분리)
# → Claude에서 Python 스크립트로 X좌표 기준 anterolateral/posteromedial 분리
```

### Phase 1: 데이터 확보 + RV 통합 (2-3주)

1. TotalSegmentator로 RV 세그멘테이션 → NIfTI → STL 변환
2. Public Cardiac CT Dataset 다운로드 → LAA annotation 추출
3. ImageCAS에서 coronary CTA 다운로드 (용량 주의: ~200GB)
4. MVAA 2026 등록 → MV training data 확보
5. RV STL을 기존 geometry에 합체

**목표 Fidelity: 15% → 35%**

### Phase 2: Valve 고도화 + Coronary 통합 (3-4주)

1. MVAA 데이터로 실측 MV geometry 교체
2. Valve resistance model (Tier 1) → prescribed kinematics (Tier 2) 전환
3. Coronary centerline 추출 (vmtk) → 1D-3D coupling
4. PM 2개 분리 + chordae parametric 생성
5. Trabeculae 분리 (PM과 구분)

**목표 Fidelity: 35% → 60%**

### Phase 3: 4-Chamber + FSI (6-8주)

1. 4-chamber 조립 (LV + RV + LA + RA + valves)
2. IVS 분리 (LV+RV wall intersection)
3. FSI 연동 (preCICE: OpenFOAM ↔ CalculiX 또는 FEBio)
4. Pericardium 경계조건 추가
5. CFD Windkessel → pH-PINN 캘리브레이션 (Track A+B 통합)

**목표 Fidelity: 60% → 80%**

### Phase 4: Electrophysiology (8-12주) ← 외골격 완료 후

1. openCARP 설치 + mesh 변환
2. Fiber orientation 할당 (Bayer 2012)
3. 이온 채널 conductance 매핑 (위 테이블)
4. Activation → wall motion coupling
5. Electromechanical → CFD prescribed displacement

**목표 Fidelity: 80% → 90%**

### Phase 5: 지속적 검증 + 임상 응용 (ongoing)

1. 4D Flow MRI 데이터로 CFD velocity field 검증
2. eICU / MIMIC-IV 약물 반응 예측
3. 환자별 파라미터 calibration pipeline
4. 독성 평가 (심장 약물 → 이온 채널 → hemodynamics)

---

## 7. WSL 파일 동기화 가이드

### 문제
시뮬레이션 데이터(시간 디렉토리 0/, 0.04/, ..., 2.4/ 와 postProcessing/)는 WSL 내부 파일시스템에만 존재한다. OneDrive에는 설정파일과 STL만 동기화되어 있다.

### 해결
```bash
# WSL Ubuntu 터미널에서 실행
bash "/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/sync_wsl_to_onedrive.sh"
```
이 스크립트는 3가지 동기화 모드를 제공한다:
- **(a) 전체**: 모든 시간 디렉토리 + postProcessing + log + mesh (수 GB)
- **(b) 결과만** (권장): postProcessing + log + polyMesh만 (용량 절약)
- **(c) 최종만**: 마지막 3 timestep + postProcessing

### 동기화 후 후처리
```bash
cd "/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/lv_cfd_anatomical"
python3 postprocess_analysis.py
# → cfd_postprocess_results.json 생성
```

---

## 8. Samsung Notebook 환경 설정

### 설치 스크립트
```bash
bash "/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/setup_samsung_notebook.sh"
```

### 수동 설치 순서 (스크립트가 실패할 경우)

**Step 1: WSL2 확인/설치**
```powershell
# PowerShell (관리자)
wsl --install -d Ubuntu-22.04
# 재시작 후
wsl --set-default-version 2
```

**Step 2: Python 환경**
```bash
# WSL Ubuntu 또는 Windows Python
pip install numpy scipy nibabel scikit-image matplotlib trimesh
```

**Step 3: TotalSegmentator**
```bash
pip install TotalSegmentator
# 테스트
TotalSegmentator --help
```

**Step 4: PyTorch + CUDA**
```bash
# GTX 1650용 — CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
python3 -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# 기대 출력: True NVIDIA GeForce GTX 1650
```

**Step 5: OpenFOAM (WSL 내부)**
```bash
curl -s https://dl.openfoam.com/add-debian-repo.sh | sudo bash
sudo apt install openfoam2406
echo 'source /usr/lib/openfoam/openfoam2406/etc/bashrc' >> ~/.bashrc
source ~/.bashrc
```

**Step 6: vmtk (coronary centerline 추출용)**
```bash
pip install vmtk
# 실패 시
conda install -c vmtk vmtk
```

**Step 7: SimVascular (선택)**
- URL: https://simtk.org/frs/?group_id=188
- Windows installer 또는 `conda install -c simvascular simvascular`

### GPU 메모리 제약 (GTX 1650 = 4GB VRAM)
- TotalSegmentator: `--device gpu` 가능 (모델 크기 ~2GB)
- pH-PINN 학습: batch size 줄이기 (--batch-size 32)
- OpenFOAM: CPU only (GPU 불필요)
- 대규모 메시 작업 시: `--device cpu` fallback

---

## 9. 핵심 코드 파일 요약

### generate_valves.py
- Parametric MV (2-leaflet, D=30mm saddle) + AV (3-cusp, D=23mm, Valsalva) 생성
- 환자별 좌표에 맞게 위치 지정:
  - MV center: (-0.0222, 0.0044, -0.1489) m
  - AV center: (-0.0153, 0.0192, -0.1311) m
- `valve_metadata.json` 동시 출력 (재료 속성 포함)
- 의존성: numpy, trimesh

### cardiac_structure_inventory.py
- MM-WHS label 데이터 분석 → 5 present + 12 missing 구조물 분류
- 각 구조물에 biomechanical properties 매핑
- JSON 출력 → cardiac_structure_inventory.json

### cardiac_digital_twin_roadmap.py
- 9개 데이터 소스 카탈로그 (URL, 접근법, 구조물 커버리지, 라이선스)
- 5-phase 구현 로드맵
- JSON 출력 → cardiac_digital_twin_roadmap.json

### ion_channel_cardiac_map.py
- 12 이온 채널 × 8 심장 영역 매핑
- 정규화된 conductance 분포 (각 영역별 0.0-1.5)
- openCARP 통합 7단계 워크플로우
- HF remodeling 패턴 (SERCA2a↓, NCX1↑, I_to↓, Cx43 lateralization)

### postprocess_analysis.py
- CFD probe 데이터 파싱 (4 위치 × U,p)
- 유량 계산 (mitralInlet, aorticOutlet)
- Windkessel 추출: R_total = mean(P)/mean(Q), C = SV/(P_sys - P_dia)
- WSS 분석
- pH-PINN 파라미터 매핑 (kinematic → mmHg: ρ=1060, 1 Pa = 0.00750062 mmHg)

### pinn_hamiltonian_v5.py
- Port-Hamiltonian PINN (pH-PINN) 모델
- Hamiltonian H = PVA = SW + PE
- Ees (end-systolic elastance), Ea (arterial elastance), tau (time constant), Vo (volume intercept)
- 에너지 보존 + dissipation inequality 제약

---

## 10. MM-WHS 데이터셋 참고 사항

### 디렉토리 구조
```
C:\Users\alex0\OneDrive\PINN heart\MM-WHS\
├── ct_train\           ← Case 1001-1020 (image + label)
│   ├── ct_train_1009_image.nii.gz    ← 현재 사용 중
│   └── ct_train_1009_label.nii.gz
├── ct_test\            ← Case 1021-1040 (image only, no label)
├── mr_train\           ← MRI cases
└── mr_test\
```

### Label 번호 매핑
| Label | 구조 | Case 1009 존재 여부 |
|-------|------|-------------------|
| 205 | Myocardium | ✅ 존재 |
| 420 | Left Atrium | ✅ 존재 |
| 500 | LV Wall | ✅ 존재 |
| 550 | LV Cavity | ✅ 존재 |
| 600 | Right Atrium | ✅ 존재 |
| **620** | **Right Ventricle** | **❌ 모든 case에서 0 voxels** |
| 820 | Ascending Aorta | ✅ 존재 |
| 850 | Pulmonary Artery | ✅ 존재 |

### CT 해상도 한계
- Voxel: 0.488 × 0.488 × 0.625 mm
- Valve leaflets (<1mm): 해상도 미달 → parametric 또는 전용 데이터 필요
- Chordae (0.3-2.5mm): marginal chordae는 해상도 미달
- Coronary arteries (3-5mm): lumen은 보이나 wall/plaque 구분은 전용 CTA 필요
- LAA: thin-walled structure → 일반 CT에서 분리 어려움

---

## 11. eICU 외부 검증 결과 요약

pH-PINN이 예측하는 hemodynamic state가 실제 약물 반응과 정합하는지 eICU-CRD 2.0으로 검증했다.

- **Phase 1** (약물 클래스 간 에너지 차이): Cohen's d 0.59-0.83 (medium-large effect)
- **Phase 2** (에너지 기반 약물 반응 예측): AUC 0.760
- **Phase 3 v2** (concordance 평가): Concordance 84.4%, AUC 0.837
- **데이터**: 2,720 episodes, 34 columns (`eicu_drug_response.csv`)

---

## 12. Claude에서 이어받기 위한 지침

Samsung Notebook의 Claude에게 이 파일을 보여준 뒤, 다음과 같이 요청할 수 있다:

### 즉시 실행 가능한 요청 예시

```
"setup_samsung_notebook.sh 실행해서 환경 설정해줘"

"TotalSegmentator로 Case 1009에서 RV 세그멘테이션 해줘"

"sync_wsl_to_onedrive.sh로 WSL 시뮬레이션 데이터 동기화해줘"

"papillary_muscles.stl에서 anterolateral/posteromedial PM 2개로 분리해줘"

"postprocess_analysis.py 실행해서 CFD 결과에서 Windkessel 파라미터 추출해줘"

"Public Cardiac CT Dataset에서 LAA annotation 가져와서 laa.stl 재생성해줘"

"generate_valves.py의 MV를 MVAA 데이터로 교체해줘"

"ImageCAS에서 coronary artery 다운로드하고 vmtk으로 centerline 추출해줘"
```

### Phase 진행 요청 예시

```
"Phase 1 시작: TotalSegmentator RV → STL 변환 → 기존 LV geometry에 합체"

"Phase 2: Valve Tier 1(resistance) → Tier 2(prescribed kinematics) 전환"

"Phase 3: 4-chamber 조립 시작 (LV+RV+LA+RA+valves)"

"Phase 4: openCARP 설치하고 ion_channel_cardiac_map.json 기반으로 전기생리학 시뮬레이션 세팅"
```

### 주의사항
1. WSL 시뮬레이션 데이터는 OneDrive에 **자동 동기화되지 않음** → `sync_wsl_to_onedrive.sh` 필수
2. GTX 1650 VRAM 4GB 제약 → TotalSegmentator는 `--device gpu` 가능하나, 대형 모델은 `--device cpu`
3. ImageCAS는 ~200GB → 디스크 여유 공간 확인 필요
4. OpenFOAM은 WSL 내부에서만 실행 (Windows native 아님)
5. `laa.stl`은 현재 **사용 불가** → Public Cardiac CT Dataset 확보 후 재생성 필요
6. `papillary_muscles.stl`은 **79MB로 과대** — decimation + 2-PM 분리 필요

---

## 13. 파일 디렉토리 트리 (핵심만)

```
C:\Users\alex0\OneDrive\PINN\260421 (심장) - main\
├── CARDIAC_DIGITAL_TWIN_STATUS.md      ← 이 문서
├── setup_samsung_notebook.sh           ← 환경 설치 스크립트
├── sync_wsl_to_onedrive.sh             ← WSL→OneDrive 동기화
│
├── # ===== Track A: pH-PINN =====
├── pinn_hamiltonian_v5.py              ← pH-PINN 모델 코드
├── phpinn_v5_trained.pt                ← 학습된 가중치
├── phpinn_v5_history.json              ← 학습 이력
├── eicu_drug_response_v2.py            ← eICU 외부 검증
├── eicu_drug_response_v2_results.json  ← 검증 결과 (AUC 0.837)
├── eicu_drug_response.csv              ← 원본 데이터 (2,720 episodes)
│
├── # ===== Track B: Anatomical CFD =====
├── lv_cfd_anatomical/
│   ├── 0/p, 0/U                        ← 초기조건
│   ├── system/
│   │   ├── controlDict                 ← pimpleFoam, endTime 2.4
│   │   ├── snappyHexMeshDict           ← 메시 설정
│   │   ├── blockMeshDict, fvSchemes, fvSolution
│   │   ├── createPatchDict, topoSetDict
│   │   └── fvConstraints
│   ├── constant/
│   │   ├── transportProperties         ← ρ=1060, ν=3.3e-6
│   │   ├── turbulenceProperties
│   │   └── triSurface/
│   │       ├── lv_surface.stl          ← LV 주 도메인 (44MB)
│   │       ├── mitral_valve.stl        ← parametric MV (5.5MB)
│   │       ├── aortic_valve.stl        ← parametric AV (12MB)
│   │       ├── aortic_root.stl         ← CT 추출 (7.9MB)
│   │       ├── papillary_muscles.stl   ← HU threshold (79MB, 정제 필요)
│   │       ├── laa.stl                 ← 실패 (170KB)
│   │       └── valve_metadata.json
│   ├── postprocess.sh                  ← WSL 후처리 스크립트
│   ├── postprocess_analysis.py         ← Python 후처리
│   ├── run.sh                          ← 시뮬레이션 실행
│   ├── geometry_metadata.json
│   └── lv_anatomy_preview.png
│
├── # ===== 구조물 분석 =====
├── cardiac_structure_inventory.py/.json ← 5 present + 12 missing
├── cardiac_digital_twin_roadmap.py/.json ← 데이터 소스 + 5 phase
├── generate_valves.py                   ← MV/AV parametric 생성
├── ion_channel_cardiac_map.py/.json     ← 12 채널 × 8 영역
│
├── # ===== 기존 메시 =====
├── cardiac_meshes/                      ← 초기 추출 STL 모음
├── cardiac_meshes_all/case_1009/        ← Valve-open 포함
│
├── # ===== 기타 =====
├── lv_cfd/                              ← 초기 단순 CFD (deprecated)
├── lv_cfd_patient/                      ← 환자별 CFD v1
├── lv_cfd_v2/                           ← CFD v2
└── ...
```

---

## 14. 핵심 숫자 & 상수 참조

| 파라미터 | 값 | 비고 |
|----------|----|----|
| Blood density (ρ) | 1060 kg/m³ | OpenFOAM transportProperties |
| Blood kinematic viscosity (ν) | 3.3e-6 m²/s | Newtonian approximation |
| Blood dynamic viscosity (μ) | 3.5e-3 Pa·s | μ = ρν |
| Pressure conversion | 1 Pa = 0.00750062 mmHg | 또는 133.322 Pa/mmHg |
| Energy conversion | 0.000133322 J/(mmHg·mL) | PVA → Joules |
| Heart rate | 75 bpm (T=0.8s) | 기본값 |
| Simulation endTime | 2.4 s | 3 cardiac cycles |
| Voxel size | 0.488 × 0.488 × 0.625 mm | MM-WHS Case 1009 |
| LV cavity volume | 76.5 mL | label 550 |
| LV wall volume | 150.4 mL | label 500 |
| MV annulus diameter | 30 mm | parametric |
| AV annulus diameter | 23 mm | parametric |
| MV center | (-0.0222, 0.0044, -0.1489) m | Case 1009 specific |
| AV center | (-0.0153, 0.0192, -0.1311) m | Case 1009 specific |

---

*이 문서는 Cardiac Digital Twin 프로젝트의 모든 진행 사항을 담고 있으며, Samsung Notebook의 Claude에서 이 파일을 참조하여 바로 이어서 작업할 수 있도록 작성되었다.*

## 15. 외부 데이터셋 다운로드 현황

| 데이터셋 | 상태 | 크기 | 출처 국가/인종 | 경로 |
|----------|------|------|---------------|------|
| STACOM2025 labels | **info 확보** | 576 MB | 덴마크/Northern European | `external_datasets/01_STACOM2025_PublicCardiacCT/` |
| MM-WHS | **보유 중** | ~2 GB | 중국/East Asian | `../PINN heart/MM-WHS/` |
| ACDC | 미다운로드 | ~2 GB | 프랑스/Western European | `external_datasets/03_ACDC/` |
| M&Ms | 미다운로드 | ~12 GB | 스페인+독일+캐나다/Multi | `external_datasets/04_MandMs/` |
| ImageCAS CTA | 미다운로드 | ~200 GB | 중국/East Asian | `external_datasets/05_ImageCAS/` |
| MVAA 2026 | 미등록 | TBD | 유럽+미국/Multi | `external_datasets/06_MVAA2026/` |
| Cardiac Atlas | 미다운로드 | 가변 | 미국 4인종/Multi-ethnic | `external_datasets/07_CardiacAtlas/` |
| PhysioNet | **접근 가능** | ~57 GB | 미국 전역/Multi-ethnic | `external_datasets/08_PhysioNet/` |

각 디렉토리의 `SOURCE_INFO.txt`에 출처, 저자, 인종/지역, 라이선스 정보가 상세 기록되어 있다.
상세 레지스트리: `external_datasets/DATASET_REGISTRY.md`
다운로드 실행: `bash download_all_datasets.sh`

---

## 16. Session 2 작업 내역 (2026-07-04, 2차 세션)

### 16-A. STACOM2025 → STL 구조 추출 (6개)

STACOM2025 Case 1 segmentation (label 0-10)에서 marching cubes로 6개 해부학적 구조를 STL로 추출했다.

| 파일명 | Label | 구조 | 삼각형 수 | 크기 | 볼륨(mL) |
|--------|-------|------|-----------|------|----------|
| `laa_stacom.stl` | 8 | Left Atrial Appendage | 69,706 | 3.4 MB | 8.31 |
| `rv_stacom.stl` | 3 | Right Ventricle (blood pool) | 58,304 | 2.8 MB | 112.60 |
| `coronary_stacom.stl` | 9 | Coronary arteries | 117,932 | 5.7 MB | 5.54 |
| `pv_stacom.stl` | 10 | Pulmonary veins | 49,554 | 2.4 MB | 23.85 |
| `pa_stacom.stl` | 7 | Pulmonary artery | 58,372 | 2.8 MB | 70.25 |
| `ra_stacom.stl` | 5 | Right atrium | 80,488 | 3.9 MB | 146.49 |

**중요 — 좌표계 불일치 문제:**
- MM-WHS 기반 STL (lv_surface, valves 등): 좌표가 0.05-0.17m 범위 (normalized)
- STACOM2025 기반 STL: 좌표가 수십~수백 mm 범위 (world coordinates, affine 적용됨)
- **Samsung Notebook에서 해야 할 일**: STACOM2025 STL들을 MM-WHS 좌표계로 rigid registration (ICP 또는 manual affine)
- 방법: `trimesh`의 `registration.icp()` 또는 `scipy.spatial.transform`으로 alignment

**기존 laa.stl (170KB, 139 voxels, FAILED) → laa_stacom.stl (3.4MB, 69,706 tri)로 교체 필요**

추출 코드: 인라인 Python (nibabel + skimage.measure.marching_cubes)
- `gaussian_filter(sigma=0.8)` 적용 후 `level=0.5`로 iso-surface 추출
- 큰 구조(RV 등)는 `step_size=2`로 triangle 수 제한
- crop-and-extract 방식으로 메모리 효율적 처리

### 16-B. Papillary Muscles 분리 (AL + PM)

기존 `papillary_muscles.stl` (79MB, ASCII, 253,920 triangles)은 AL-PM과 PM-PM이 하나의 blob으로 합쳐져 있었다.

**분리 방법:** K-means clustering (k=2) on triangle centroids
- Connected component 분석 시 단일 component (gap 없음) → K-means 사용
- Inter-cluster distance: 37.0mm (해부학적으로 합당)

| 파일명 | 삼각형 수 | 크기 | Cluster centroid |
|--------|-----------|------|------------------|
| `anterolateral_pm.stl` | 122,314 | 39.5 MB | (0.0706, 0.1478, 0.1164) |
| `posteromedial_pm.stl` | 131,606 | 42.6 MB | (0.0743, 0.1409, 0.0802) |

**주의:** K-means 기반이므로 정확한 해부학적 경계가 아닐 수 있음. Samsung Notebook에서 ParaView로 시각화하여 확인 권장.

### 16-C. Chordae Tendineae 파라메트릭 생성

문헌 기반 파라미터로 22개 chordae를 생성했다.

| Type | 개수 (×2 PM) | 직경 (mm) | 부착 위치 |
|------|-------------|-----------|-----------|
| Marginal (primary) | 12 | 0.55 | Leaflet free edge |
| Strut (secondary) | 4 | 1.0 | Leaflet body (rough zone) |
| Basal (tertiary) | 6 | 0.4 | Leaflet base |

- 코드: `generate_chordae.py`
- 출력: `chordae_al.stl`, `chordae_pm.stl`, `chordae_combined.stl`
- 각 chorda는 catenary sag (최대 2mm) + taper 형상의 tube로 모델링
- 참고문헌: Lam 1970 (분류), Kunzelman 1993 (치수), Prot 2009 (역학)

### 16-D. Windkessel → pH-PINN 통합 (Track A+B Bridge)

CFD 결과에서 Windkessel 파라미터를 추출하고, pH-PINN의 에너지 파라미터로 매핑하는 코드를 작성했다.

**파이프라인:**
```
CFD (flowRate + probe pressure)
  → 3-element Windkessel (R1, R2, C)
  → pH-PINN parameters (Ea, tau, Emax)
  → PV loop metrics (H = PVA = SW + PE)
```

**코드:** `windkessel_phpinn_bridge.py`
**사용법:**
- Synthetic 테스트: `python3 windkessel_phpinn_bridge.py`
- 실제 CFD 데이터: `python3 windkessel_phpinn_bridge.py /path/to/lv_cfd_anatomical/`

**Synthetic data 검증 결과 (정상 범위 확인):**
- HR=75, SV=70mL, CO=5.25L/min, EF=58.3%
- AoP: 120/80 mmHg
- Ea=1.50, Emax=2.50, **Ea/Emax=0.60 (최적 범위)**
- H = PVA = SW + PE = 2105 mmHg·mL

**핵심 수식:**
- `Ea = R_total / T_cycle` (Sunagawa 1985)
- `tau_dia = R2 × C` (diastolic time constant)
- `SW = Ea × SV` (stroke work)
- `PE = ½ Emax (Ves - Vd)²` (potential energy)
- `Coupling ratio = Ea/Emax` (최적: 0.5-1.0)

### 16-E. Multi-Structure Assembly Pipeline

모든 STL을 통합 geometry로 조립하는 파이프라인을 작성했다.

**코드:** `assemble_cardiac_geometry.py`
**출력:**
- `cardiac_assembly_summary.json` — 13개 mesh의 bbox, centroid, overlap 정보
- `lv_cfd_anatomical/system/snappyHexMeshDict` — OpenFOAM 메쉬 생성 설정

**현재 STL 인벤토리 (13개):**

| # | 파일 | 출처 | 삼각형 | 좌표계 |
|---|------|------|--------|--------|
| 1 | lv_surface.stl | MM-WHS 1009 | 166,936 | MM-WHS |
| 2 | mitral_valve.stl | Parametric | 22,344 | MM-WHS |
| 3 | aortic_valve.stl | Parametric | 45,284 | MM-WHS |
| 4 | aortic_root.stl | Parametric | 32,744 | MM-WHS |
| 5 | laa_stacom.stl | STACOM2025 | 69,706 | **STACOM (변환 필요!)** |
| 6 | rv_stacom.stl | STACOM2025 | 58,304 | **STACOM (변환 필요!)** |
| 7 | coronary_stacom.stl | STACOM2025 | 117,932 | **STACOM (변환 필요!)** |
| 8 | pv_stacom.stl | STACOM2025 | 49,554 | **STACOM (변환 필요!)** |
| 9 | pa_stacom.stl | STACOM2025 | 58,372 | **STACOM (변환 필요!)** |
| 10 | ra_stacom.stl | STACOM2025 | 80,488 | **STACOM (변환 필요!)** |
| 11 | anterolateral_pm.stl | K-means split | 122,314 | MM-WHS |
| 12 | posteromedial_pm.stl | K-means split | 131,606 | MM-WHS |
| 13 | chordae_combined.stl | Parametric | 2,024 | MM-WHS |

**총: 957,608 triangles**

### 16-F. 다음 작업 우선순위 (2026-07-06 업데이트)

> ⚠️ **이전 우선순위 목록은 시뮬레이션이 성공한 것으로 가정하고 작성되었으나, 시뮬레이션이 발산한 것으로 확인됨 (Section 18 참조). 아래는 수정된 우선순위.**

1. **[최우선/WSL 필수] CFD 재실행 (v2 config)** — Section 18-C 참조
2. **[WSL 필수] checkMesh 품질 확인** — 음수 부피 셀 0개 필수
3. **시뮬레이션 안정화 확인** — t > 0.01s 도달 시 fvSchemes 전환 (Euler→backward, upwind→linearUpwind)
4. **시뮬레이션 완료 후 OneDrive 동기화** — `sync_wsl_to_onedrive.sh`
5. **실제 CFD 후처리** — probe/flowRate 파싱 → Windkessel → pH-PINN 연동
6. **STACOM STL 좌표 등록** — ParaView에서 시각적 검증, 필요 시 수동 보정
7. **TotalSegmentator** — RV 직접 추출 (GPU 필요)
8. **ACDC/M&Ms 데이터 다운로드** — 수동 등록 필요


---

## 17. WSL 데이터 동기화 완료 및 Cross-Computer 준비 (2026-07-06)

### 17-A. WSL → OneDrive 동기화 결과

`sync_wsl_to_onedrive.sh` 모드 (a) 전체 동기화를 실행하여 WSL 내부의 모든 CFD 시뮬레이션 데이터를 OneDrive로 복사 완료했다.

**동기화된 데이터 (총 733MB):**

| 항목 | 상세 |
|------|------|
| 시간 디렉토리 | 61개 (t=0 ~ t=2.4, dt=0.04) — ⚠️ **빈 placeholder** (uniform (0 0 0), 32줄씩, 실제 결과 아님) |
| postProcessing | flowRateAortic/, flowRateMitral/, probes/ (p, U) |
| Log 파일 | 8개: blockMesh, checkMesh, checkMesh2, createPatch, pimpleFoam (73KB), snappyHexMesh (108KB), surfaceFeatureExtract, topoSet |
| polyMesh | 540MB — faces (273MB), owner (62MB), neighbour (62MB), points, boundary, cellZones, faceZones, pointZones 등 17 파일 |
| STL 파일 | 13개 (957,608 triangles) — Section 16-E 참조 |
| 스크립트 | generate_chordae.py, windkessel_phpinn_bridge.py, assemble_cardiac_geometry.py, postprocess_analysis.py 등 |

**검증 방법:** `stat -c%s` 명령으로 파일 크기 확인 (OneDrive cloud-only 파일은 `du -h`가 0을 보고하므로 `stat` 사용)

### 17-B. Cross-Computer 작업 이어가기

이 프로젝트는 OneDrive를 통해 어떤 컴퓨터에서든 이어서 작업할 수 있다.

**전제 조건:**
- OneDrive가 동기화되어 있고, `C:\Users\alex0\OneDrive\PINN\260421 (심장) - main` 경로가 동일할 것
- Python 3.10+ (numpy, scipy, trimesh, torch 설치)
- 선택: OpenFOAM (WSL/Docker), ParaView (시각화), GPU (TotalSegmentator)

**핵심 디렉토리 구조:**
```
C:\Users\alex0\OneDrive\PINN\260421 (심장) - main/
├── CARDIAC_DIGITAL_TWIN_STATUS.md      ← 이 파일 (마스터 인수인계 문서)
├── pinn_hamiltonian_v5.py              ← Track A: pH-PINN 모델
├── phpinn_v5_trained.pt                ← Track A: 학습된 가중치
├── eicu_drug_response_v2.py            ← Track A: eICU 검증
├── windkessel_phpinn_bridge.py         ← Track A+B 통합
├── generate_valves.py                  ← 밸브 생성
├── generate_chordae.py                 ← Chordae 생성
├── assemble_cardiac_geometry.py        ← 전체 geometry 조립
├── postprocess_analysis.py             ← CFD 후처리
├── cardiac_structure_inventory.py      ← 구조물 인벤토리
├── ion_channel_cardiac_map.py          ← 이온채널 맵핑
├── windkessel_phpinn_results.json      ← Windkessel-pH-PINN 결과
├── cardiac_assembly_summary.json       ← Assembly 요약
├── sync_wsl_to_onedrive.sh             ← WSL 동기화 스크립트
├── setup_samsung_notebook.sh           ← 환경 설정
├── download_all_datasets.sh            ← 데이터셋 다운로드
├── lv_cfd_anatomical/                  ← Track B: CFD 프로젝트 전체
│   ├── 0/ ~ 2.4/                       ← 61개 시간 디렉토리 (빈 placeholder — 실제 결과는 재시뮬레이션 후 생성)
│   ├── constant/
│   │   ├── polyMesh/                   ← 540MB 메시 데이터
│   │   ├── triSurface/                 ← 13개 STL 파일
│   │   └── transportProperties
│   ├── system/
│   │   ├── controlDict, blockMeshDict, fvSchemes, fvSolution
│   │   └── snappyHexMeshDict           ← 13-structure 메시 설정
│   ├── postProcessing/                 ← flowRate + probe 데이터
│   └── log.*                           ← 8개 실행 로그
├── lv_cfd_anatomical_v2_configs/        ← v2 수정 config (이번 세션 생성)
│   ├── system/controlDict              ← maxCo 0.3, Euler, deltaT 1e-6
│   ├── system/fvSchemes                ← Euler + upwind (안정성 우선)
│   ├── system/fvSolution               ← correctors 증가, 잔차 제어
│   ├── system/snappyHexMeshDict        ← 메시 품질 기준 강화
│   └── rerun_simulation.sh             ← 원클릭 재실행 스크립트
├── cfd_simulation_analysis.json        ← CFD 발산 진단 결과
├── cfd_diagnostic_dashboard.png        ← Courant/deltaT/잔차/연속성 차트
├── cardiac_stl_geometry.png            ← STL 3-view 산점도
├── mesh_quality_assessment.png         ← 메시 품질 차트
├── mitral_flow_profile.png             ← E/A파 유량 프로파일
└── external_datasets/
    └── DATASET_REGISTRY.md             ← 8개 데이터소스 정보
```

**새 컴퓨터에서 Claude에게 전달할 첫 메시지 예시:**
```
CARDIAC_DIGITAL_TWIN_STATUS.md를 읽고 cardiac digital twin 작업을 이어가자.
경로: C:\Users\alex0\OneDrive\PINN\260421 (심장) - main

현재 상태 요약:
- CFD 시뮬레이션이 발산함 (Section 18 참조)
- v2 수정 config 생성 완료 (lv_cfd_anatomical_v2_configs/)
- Section 16-F의 수정된 우선순위를 따라 진행해줘
- WSL OpenFOAM 환경이 있으면 Section 18-G의 단계별 가이드 실행
```

**즉시 실행 가능한 작업 (GPU/OpenFOAM 불필요):**
1. STACOM2025 STL 좌표 변환 재시도 — ParaView에서 시각적 검증 후 수동 affine 보정
2. 진단 차트 확인 — `cfd_diagnostic_dashboard.png`, `mesh_quality_assessment.png` 참조
3. pH-PINN 모델 자체 테스트 — `python3 pinn_hamiltonian_v5.py` (학습된 가중치 로드)
4. ParaView 시각화 — GUI 앱 필요

**⚠️ 시뮬레이션 발산으로 실행 불가:**
- ~~실제 CFD 후처리~~ → 시뮬레이션 성공 후에만 (Section 18-D 참조)
- ~~Windkessel-PINN 연동~~ → 유효한 probe/flowRate 데이터 필요

**GPU/OpenFOAM 필요 작업:**
1. TotalSegmentator — RV 직접 추출
2. CFD 재실행 — snappyHexMesh + pimpleFoam

### 17-C. 좌표계 불일치 상세 (Cross-Computer 작업 시 주의)

현재 STL 파일들은 두 가지 좌표계가 섞여 있다:

| 좌표계 | STL 파일 | Bounding Box 범위 |
|--------|----------|-------------------|
| **MM-WHS** (정규화) | lv_surface, mitral_valve, aortic_valve, aortic_root, anterolateral_pm, posteromedial_pm, chordae_* | 0.05 ~ 0.17 m |
| **STACOM2025** (world) | laa_stacom, rv_stacom, coronary_stacom, pv_stacom, pa_stacom, ra_stacom | 수천~수만 mm |

**해결 방법:** trimesh를 이용한 ICP (Iterative Closest Point) 또는 manual affine registration
```python
import trimesh
# 1. MM-WHS LV를 reference로 로드
ref = trimesh.load('lv_cfd_anatomical/constant/triSurface/lv_surface.stl')
# 2. STACOM STL 로드
src = trimesh.load('lv_cfd_anatomical/constant/triSurface/laa_stacom.stl')
# 3. ICP registration
matrix, transformed, cost = trimesh.registration.icp(src.vertices, ref.vertices)
# 4. 변환 적용 후 저장
src.apply_transform(matrix)
src.export('lv_cfd_anatomical/constant/triSurface/laa_registered.stl')
```


---

## 18. CFD 시뮬레이션 분석 결과 (2026-07-06 세션 2)

### 18-A. 시뮬레이션 발산 분석

pimpleFoam 시뮬레이션이 t ≈ 2.64×10⁻⁵ s에서 SIGFPE (부동소수점 예외)로 발산했다.

**타임라인:**
- 18 timestep 시도, 물리적 시간 0.0011% 진행 (2.64e-5 / 2.4 s)
- deltaT 붕괴: 1.44e-05 → 9.70e-83 (10⁷⁷배 축소)
- max Courant: 0 → 3.04×10¹⁴ (목표: 0.8)
- 압력 솔버: 420회 중 61%가 초기 잔차 > 0.1 (수렴 실패)
- 연속성 누적 오류: -120,743
- 실행 시간: 77분 (CPU), 물리적 시간 거의 0

**근본 원인 — checkMesh 결과:**
```
Failed 5 mesh checks:
- 음수 부피 셀 3개 (volume < 0)
- 극단적 aspect ratio 셀 3개 (최대 1.74×10⁹²)
- 비직교성 오류 13개 (>90°), 심각 2개 (>70°)
- 잘못된 방향 면 28개
- 높은 skewness 면 2개 (최대 8.85)
```

이 메시 결함들이 압력 Poisson 방정식의 수렴을 불가능하게 만들었고, Courant 수 폭발 → SIGFPE로 이어졌다.

**추가 요인:**
1. backward ddt 스킴이 초기 과도현상에 너무 공격적
2. maxCo=0.8이 불안정 셀에서 제어 불가
3. meshQualityControls에서 minTetQuality = -1e30 (사실상 비활성화)

### 18-B. v2 수정 사항 (`lv_cfd_anatomical_v2_configs/`)

| 파일 | 주요 변경 |
|------|-----------|
| `system/controlDict` | deltaT: 1e-5→1e-6, maxCo: 0.8→0.3, maxDeltaT: 2e-3→5e-4, 잔차 모니터링 추가, WSS 계산 추가 |
| `system/fvSchemes` | ddt: backward→Euler, div(phi,U): linearUpwind→upwind, limited corrected 0.5→0.333, 구배 제한 추가 |
| `system/fvSolution` | nOuterCorrectors: 2→3, nCorrectors: 3→4, nNonOrthCorrectors: 3→4, U relaxation: 0.7→0.5, 잔차 제어 추가 |
| `system/snappyHexMeshDict` | 품질 기준 강화 (minTetQuality 활성화, minVol 강화), 레이어 2개로 축소, 스냅 반복 증가 |

### 18-C. 재실행 방법

```bash
# WSL Ubuntu에서:
cd ~/lv_cfd_anatomical
bash "/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/lv_cfd_anatomical_v2_configs/rerun_simulation.sh"
```

이 스크립트가 수행하는 작업:
1. 기존 설정 백업
2. v2 config 파일 복사
3. 메시 재생성 (blockMesh + snappyHexMesh)
4. checkMesh 실행 (음수 부피 셀 있으면 경고)
5. potentialFoam 초기화 (가능한 경우)
6. pimpleFoam 백그라운드 실행

### 18-D. postProcessing 데이터 상태

시뮬레이션이 발산했으므로 모든 후처리 데이터는 비물리적:
- `probes/0/p`: 압력 ~10⁶² Pa (무효)
- `probes/0/U`: 속도 ~10²⁸ m/s (무효)
- `flowRateAortic`: -3.34×10²¹ (무효)
- `flowRateMitral`: -7.66×10⁻⁸ (초기값, 유효하지 않음)

**→ Windkessel-PINN 연동은 시뮬레이션 성공 후에만 가능**

### 18-E. 생성된 파일 목록 (이번 세션)

| 파일 | 위치 | 설명 |
|------|------|------|
| `cfd_simulation_analysis.json` | 프로젝트 루트 | 시뮬레이션 진단 JSON (설정, 수렴, Courant, 진단, 수정 권장사항) |
| `cfd_diagnostic_dashboard.png` | 프로젝트 루트 | 4-패널 진단 차트 (Courant/deltaT/잔차/연속성) |
| `cardiac_stl_geometry.png` | 프로젝트 루트 | STL 해부학 3-view 산점도 |
| `mesh_quality_assessment.png` | 프로젝트 루트 | 셀 타입 분포 + 품질 이슈 바 차트 |
| `mitral_flow_profile.png` | 프로젝트 루트 | 승모판 E/A파 유량 + 속도 프로파일 |
| `lv_cfd_anatomical_v2_configs/` | 프로젝트 루트 | 수정된 OpenFOAM 설정 파일 4개 + rerun 스크립트 |

### 18-F. 다음 작업 우선순위

→ Section 16-F로 통합 (2026-07-06 업데이트됨)

### 18-G. CFD v2 재실행 — 단계별 실행 가이드 (새 컴퓨터 인수인계용)

이 가이드는 WSL Ubuntu + OpenFOAM 2312이 설치된 컴퓨터에서 Claude가 직접 실행할 수 있도록 작성되었다.

#### Step 0: 환경 확인

```bash
# OpenFOAM 확인
which pimpleFoam && echo "OK" || echo "OpenFOAM 미설치 — apt install openfoam2312"

# WSL에 시뮬레이션 디렉토리 존재 확인
ls ~/lv_cfd_anatomical/system/controlDict && echo "OK" || echo "디렉토리 없음 — OneDrive에서 복사 필요"

# OneDrive v2 configs 접근 확인
ls "/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/lv_cfd_anatomical_v2_configs/system/controlDict" && echo "OK"
```

**환경이 없는 경우:**
```bash
# OpenFOAM 설치 (Ubuntu 22.04)
curl -s https://dl.openfoam.com/add-debian-repo.sh | sudo bash
sudo apt install openfoam2312
echo "source /usr/lib/openfoam/openfoam2312/etc/bashrc" >> ~/.bashrc
source ~/.bashrc

# 시뮬레이션 디렉토리가 WSL에 없으면 OneDrive에서 복사
cp -r "/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/lv_cfd_anatomical" ~/lv_cfd_anatomical
```

#### Step 1: 기존 설정 백업 + v2 config 적용

```bash
cd ~/lv_cfd_anatomical
BACKUP="$(pwd)_backup_$(date +%Y%m%d_%H%M)"
mkdir -p "$BACKUP" && cp -r system 0 "$BACKUP/"
cp log.* "$BACKUP/" 2>/dev/null

# v2 configs 복사
V2="/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/lv_cfd_anatomical_v2_configs"
cp "$V2/system/controlDict"       system/controlDict
cp "$V2/system/fvSchemes"          system/fvSchemes
cp "$V2/system/fvSolution"         system/fvSolution
cp "$V2/system/snappyHexMeshDict"  system/snappyHexMeshDict
```

#### Step 2: 기존 결과 삭제 + 메시 재생성

```bash
# 기존 시간 디렉토리와 발산 로그 삭제
find . -maxdepth 1 -type d -regex '.*/[0-9].*' ! -name '0' -exec rm -rf {} +
rm -rf postProcessing processor* log.pimpleFoam

# 메시 재생성
blockMesh > log.blockMesh_v2 2>&1
snappyHexMesh -overwrite > log.snappyHexMesh_v2 2>&1
```

#### Step 3: 메시 품질 확인 (★ 핵심 체크포인트)

```bash
checkMesh > log.checkMesh_v2 2>&1
cat log.checkMesh_v2 | tail -20
```

**예상 출력 및 판단 기준:**

| 항목 | 통과 기준 | v1 실패값 | 조치 |
|------|-----------|-----------|------|
| 음수 부피 셀 | 0개 | 3개 | ✗ → Step 3a로 |
| Max aspect ratio | < 100 | 1.74×10⁹² | ✗ → Step 3a로 |
| 비직교성 오류 (>90°) | 0개 | 13개 | △ → 0이면 이상적, 5개 이하면 진행 가능 |
| 잘못된 방향 면 | 0개 | 28개 | ✗ → Step 3a로 |
| Max skewness | < 4 | 8.85 | △ → 5 이하면 진행 가능 |

**✓ 통과 시:** Step 4로 진행
**✗ 실패 시:** Step 3a 실행

#### Step 3a: 메시 품질 실패 시 대응

```bash
# 레이어 추가 비활성화 시도 (가장 흔한 원인)
# snappyHexMeshDict에서 addLayers를 false로 변경
sed -i 's/addLayers       true;/addLayers       false;/' system/snappyHexMeshDict
snappyHexMesh -overwrite > log.snappyHexMesh_v2b 2>&1
checkMesh > log.checkMesh_v2b 2>&1

# 그래도 실패하면 → refinement level 낮추기
# castellatedMeshControls.refinementSurfaces.lvWall.level (2 3) → (1 2)
# 또는 maxGlobalCells 줄이기: 3000000 → 1500000
```

#### Step 4: 초기 조건 설정 + 실행

```bash
# potentialFoam (가능하면 — 더 좋은 초기 유동장)
potentialFoam -initialiseUBCs > log.potentialFoam_v2 2>&1 || echo "potentialFoam 건너뜀"

# pimpleFoam 실행 (백그라운드)
nohup pimpleFoam > log.pimpleFoam_v2 2>&1 &
echo "PID: $!"
```

#### Step 5: 실시간 모니터링

```bash
# Courant 수 확인 (max Co < 1이면 안정)
tail -f log.pimpleFoam_v2 | grep "Courant Number"

# 시간 진행 확인
grep "^Time = " log.pimpleFoam_v2 | tail -5

# 연속성 오류 확인 (cumulative < 1이면 양호)
grep "cumulative" log.pimpleFoam_v2 | tail -5
```

**판단 기준:**

| 지표 | 양호 | 주의 | 발산 징후 |
|------|------|------|-----------|
| max Co | < 0.5 | 0.5~1.0 | > 1.0 연속 |
| deltaT | 증가/안정 | 감소 중 | 10⁻¹⁰ 이하로 축소 |
| 압력 잔차 | < 0.01 | 0.01~0.1 | > 0.1 반복 |
| 누적 연속성 | |값| < 1 | 1~100 | > 1000 |

**t > 0.01s 도달 시 (안정화 확인):**
```bash
# fvSchemes를 더 정확한 스킴으로 전환
# system/fvSchemes 수정:
#   ddtSchemes { default backward; }
#   div(phi,U) Gauss linearUpwind grad(U);
# 그 후 pimpleFoam이 자동으로 읽어감 (runTimeModifiable true)
```

#### Step 6: 완료 후 OneDrive 동기화

```bash
# 시뮬레이션 완료 확인
grep "^End$" log.pimpleFoam_v2 && echo "완료" || echo "아직 실행 중"

# 동기화 실행
bash "/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/sync_wsl_to_onedrive.sh"
# 모드 (b) 선택 권장 (결과만 — postProcessing + log + polyMesh)
```

#### Step 7: 후처리 파이프라인

시뮬레이션 성공 + OneDrive 동기화 후:

```bash
cd "/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main"

# 1. CFD 후처리 (probe 파싱, flowRate, WSS)
python3 postprocess_analysis.py

# 2. Windkessel → pH-PINN 연동
python3 windkessel_phpinn_bridge.py ./lv_cfd_anatomical/

# 3. 결과 확인
cat windkessel_phpinn_results.json
```

**예상 결과 (정상 시뮬레이션 기준):**
- `probes/0/p`: LV 중심부 압력 0~16 kPa (0~120 mmHg)
- `probes/0/U`: 속도 0~1.5 m/s
- `flowRateMitral`: E파 피크 ~2.3×10⁻⁴ m³/s, A파 ~1.4×10⁻⁴ m³/s
- `flowRateAortic`: 수축기 유출 ~3×10⁻⁴ m³/s

### 18-H. 이번 세션에서 확인된 사실 (인수인계 필수 정보)

1. **61개 시간 디렉토리는 빈 placeholder**: `internalField uniform (0 0 0)`, 32줄, `allBoundary` — 실제 시뮬레이션 출력이 아님
2. **0/U의 aortic BC는 정상**: `pressureInletOutletVelocity` 이미 설정됨 (기존 진단에서 누락 지적했으나 실제로는 맞음)
3. **메시 품질이 근본 원인**: checkMesh Failed 5 — 음수 부피, 1.74e92 aspect ratio, 28 잘못된 면
4. **v2 snappyHexMeshDict의 핵심 변경**: `minTetQuality 1e-15` (v1은 `-1e30`=비활성), `minArea 1e-15` (v1은 `-1`=비활성)
5. **진단 차트 4종 + JSON 저장 완료**: 프로젝트 루트에 `.png` + `.json`
6. **STACOM 좌표 등록은 preliminary 상태**: *_registered.stl 파일 존재하나 거리 0.35-0.58 (정상 기대값 0.1-0.15)

---

## 19. STACOM STL 좌표 등록 재작업 (2026-07-06 세션 3)

### 19-A. 문제 진단
기존 `*_registered.stl`(§17-C, §18-H #6)은 정합 실패 상태였음. 실측 결과 등록된 구조들의 centroid가 LV에서 **350~580mm 떨어져** 있어 조립 불가.

**근본 원인 = 방법론 오류.** 문서 §17-C가 제안한 "각 STACOM STL을 lv_surface에 ICP"는 잘못된 접근이다. STACOM 구조(RV·RA·PA·PV·LAA·관상동맥)는 (1) LV가 아닌 다른 장기이고 (2) 다른 환자(STACOM2025 Case 1) 데이터라, LV 표면에 최근접 정합하면 전부 LV 위로 뭉개진다.

### 19-B. 올바른 방법 — 공통구조 기반 단일 변환
두 데이터셋에 **공통 존재하는 구조**로 변환을 1회 산출해 6개 STL에 일괄 적용(상호 위치관계 보존).

- 좌표계 사실: `cardiac_meshes/*_case1009.stl`은 **mm** 좌표, CFD `lv_surface.stl`은 **m** 좌표. LV extent가 정확히 ×1000 관계.
- **Step A**: LV(동일 구조)로 mm→CFD(m) 변환 산출 → ICP RMS **3.1mm**, scale 0.00098. (`mm_to_cfd_transform.npy`)
- **Step B**: 공통구조 RA·PA 각각으로 stacom→mm 변환 산출 (RA RMS 4.8mm, PA RMS 3.9mm).
- **교차검증**: RA기반 변환을 held-out PA에 평가 = **14.7mm**, PA기반을 held-out RA = 55.0mm → **RA기반 채택**. (`stacom_to_cfd_transform_v2.npy`)

### 19-C. 결과
채택 변환을 6개 STL에 적용 → `*_registered_v2.stl` 저장. 전 구조가 LV 중심 68~108mm 이내(심장 영역)에 안착. **350~580mm → ~15mm 개선.**

| 파일 | 심장영역 내 | LV중심 거리 |
|------|:---:|---:|
| ra_registered_v2.stl | ✓ | 67.8mm |
| coronary_registered_v2.stl | ✓ | 82.8mm |
| rv_registered_v2.stl | ✓ | 95.4mm |
| pa_registered_v2.stl | ✓ | 106.2mm |
| laa_registered_v2.stl | ✓ | 107.9mm |
| pv_registered_v2.stl | ✓ | 108.4mm |

- 검증 그림: `stacom_registration_v2_comparison.png` (기존 vs v2, 3-view)
- **주의**: 교차환자 정합이라 해부학적 위치는 근사. 4-chamber 조립 시 구조별 미세 보정(ParaView) 권장. 완벽 정합이 필요하면 STACOM Case의 LV/LA를 확보해 동일환자급 랜드마크로 재산출.
- **다음**: `assemble_cardiac_geometry.py`가 참조하는 STL을 `*_registered_v2.stl`로 교체 필요(§16-E 인벤토리 갱신).

### 19-D. 해부학적 타당성 학술 검증 (2026-07-06 세션 3, 이어서)

`validate_stacom_registration.py` 로 v2 정합의 해부학적 정합성을 정량 평가.

**통과:** 반사 없음(det>0, 좌우반전 X) / RA 앵커 표면 RMS 5.4mm / PV 후방-상방 방향 일치 / RV-LV 상호침투 0%.

**실패·미흡(중요):**
- RV-LV 표면 최소거리 **34.9mm** (septum 공유해야 하므로 ≈0 기대) → RV가 LV에 안 붙음.
- PA 독립검증 표면 RMS **28mm**, Hausdorff **69mm**, 약간 후방 편위.
- 전방(anterior) 축 관계 대부분 불일치(RV·LAA·PA).

**근본 원인:** 다른 환자의 단일 구조(RA)로 구한 rigid+등방스케일 변환은 다구조 해부 제약을 동시 만족 불가(원리적 한계).

**판정:** v2 = 시각화 placeholder로만 유효. **CFD/FSI 지오메트리·정량 주장에는 부적합.**

**옳은 경로:**
1. RV는 **환자 내 분할**로 해결 — Case 1009 CT에 TotalSegmentator `heartchambers_highres` (roadmap Phase 1, GPU). 교차환자 오차 원천 제거.
2. 미세구조 부득이 차용 시 공유 경계면 국소정합/SSM/변형정합 사용, 단일 전역 rigid 금지.
3. 차용 교차환자 챔버를 CFD 도메인으로 직접 사용 금지.

**산출물:** `validate_stacom_registration.py`, `stacom_registration_v2_validation.json`, `stacom_registration_v2_validation.png`

---

## 20. 환자 내 RV 추출 파이프라인 (2026-07-07 세션 4)

§19-D 결론(교차환자 STACOM RV 부적합, RV-LV 35mm gap)에 따라, 동일 환자(Case 1009)
CT에서 in-patient RV를 직접 분할하는 파이프라인을 준비했다. in-patient이므로 교차환자
registration이 불필요하고, 이미 검증된 `mm_to_cfd_transform.npy`(LV 기반, ICP RMS 3.1mm)로
CFD 좌표계에 바로 배치한다.

### 산출 스크립트
- `run_rv_extraction.sh` — WSL 래퍼. 경로 자동감지 → TotalSegmentator(heartchambers_highres,
  GPU 없으면 자동 CPU) → 추출 스크립트 호출. CT는 `<OneDrive>/PINN heart/MM-WHS/ct_train/
  ct_train_1009_image.nii.gz` 자동 탐색.
- `extract_rv_totalseg.py` — RV mask(NIfTI) → affine 적용 marching cubes → 스무딩/최대성분/
  decimation → `mm_to_cfd_transform.npy` 적용 → `rv_insegment_registered.stl`.

### 내장 검증
1. 프레임 일치: TotalSeg-LV(heart_ventricle_left)를 같은 변환으로 옮겨 `lv_surface.stl`과
   표면 RMS 비교(<12mm면 프레임 일치 확정).
2. 해부 검증: 새 RV–LV 표면 최소거리 → v2 교차환자 34.9mm 대비 ≈0(septum 인접) 확인.
   → `rv_insegment_report.json`.

### 실행
```bash
bash "<PROJECT>/run_rv_extraction.sh"
```
요구: TotalSegmentator, python(nibabel scikit-image scipy trimesh), GPU 권장(VRAM 부족 시 CPU).

### 성공 후
- `assemble_cardiac_geometry.py`의 RV 참조를 `rv_stacom` → `rv_insegment_registered`로 교체.
- §16-E STL 인벤토리(13개) 갱신: rv 항목을 in-patient 버전으로.
- 주의: 이 스크립트는 GPU 환경에서 end-to-end 미검증(문법만 확인). TotalSeg 출력 파일명이
  다르면 extract 스크립트의 find_mask fallback이 탐색하나, 로그 확인 권장.

---

## 21. Session 4 산출물 인덱스 (2026-07-07)

이 세션은 (A) 기하 정합 실작업 + (B) 전략/확장 설계 문서화 + (C) ECG 통합 파이프라인
구축으로 구성. 아래는 생성/갱신 파일 전체 인덱스.

### A. 코드·실작업 (검증 완료)
- STACOM 좌표 정합 v2: `stacom_to_cfd_transform_v2.npy`, `mm_to_cfd_transform.npy`,
  `*_registered_v2.stl`(6종), `stacom_registration_v2_comparison.png`.
  → 350~580mm → ~15mm 개선. §19 참조.
- 정합 해부검증: `validate_stacom_registration.py`, `..._validation.json/.png`.
  → 판정: 시각화 placeholder OK, CFD 지오메트리엔 부적합(RV-LV 35mm). §19-D.
- 환자 내 RV 추출(WSL/GPU용, 문법검증): `run_rv_extraction.sh`, `extract_rv_totalseg.py`. §20.
- CFD v2 재실행(WSL용): `lv_cfd_anatomical_v2_configs/rerun_cfd_v2_robust.sh`, `monitor_cfd.sh`.

### B. 전략·확장 설계 문서
- `AUDIT_EXPANSION_BACKLOG.md` — 감사(T1~T3)+문헌. A1 정정(라벨 순환논리 반증→검증위계 표기),
  침습 Ees 정답=**porcine** 확정.
- `EXPANSION_PLAN.md` — E0~E5 단계화 + 타깃저널 3(J-BHI/npj/CBM).
- `ECG_AUGMENTATION_DESIGN.md` — ECG 물리정보 prior(문헌 기전매핑).
- `PLATFORM_ARCHITECTURE.md` — 0D↔3D↔EP 플랫폼 + L5 응용(독성·수술계획) + §8 FMD(KRDF).
- `MULTI_ORGAN_VISION.md` — 다장기 전이 엔진(근골격 최상, 뇌/폐/신장, 면역=비-Hamiltonian).
- `CAPABILITY_ROADMAP.md` — 역량(UQ·인과·규제·연합·SciML·QSP).
- `ROADMAP_INDEX.md` — 전체 비전 인덱스(3-지평선).

### C. ECG 통합 파이프라인 (`ecg_integration/`, PowerShell용, 문법·Stage0 검증)
- `ECG_INTEGRATION_RUNBOOK.md`(런북), `config.json`, `pipelib.py`,
  `00_env_check~04_ablation_identifiability.py`, `run_ecg_pipeline.ps1`.
- 흐름: 환경점검 → **[사용자: PhysioNet MIMIC-IV-ECG pull]** → 링크→지표→병합/QC→식별성 ablation.
- 로버스트: config기반·QC게이트·resumable·machine_measurements.csv 우선활용.

### 현재 스레드 상태(요약)
- CFD v2: WSL에서 재실행 대기(사용자). RV in-patient: 스크립트 준비, GPU 실행 대기.
- ECG(E1): 파이프라인 준비완료, 사용자 데이터 pull 대기.
- E2(ABP)/E3(소아)/E5(심독성): 계획 확정, 미착수.
- 플랫폼 backbone(`twin_parameters.json`): 미구현(다음 후보).
