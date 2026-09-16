# Cardiac CFD 파이프라인 — 소프트웨어 설치 가이드 (Windows)

## 전체 파이프라인 흐름

```
CT/MRI 데이터 (NIfTI)
    ↓
[3D Slicer] 시각화 + segmentation 확인/수정
    ↓
[Python] marching cubes → STL (이미 완료)
    ↓
[OpenFOAM on WSL] blockMesh → snappyHexMesh → pimpleFoam
    ↓
[ParaView] CFD 결과 시각화 (WSS, pressure, streamlines)
    ↓
[Python] lumped parameter 추출 → pH-PINN 비교
```


## 1. WSL (Windows Subsystem for Linux) — 필수

OpenFOAM은 Linux 전용이므로 WSL이 필수입니다.

### 설치
```powershell
# PowerShell (관리자 권한)
wsl --install
```
- 재부팅 후 Ubuntu 자동 설치
- 사용자명/비밀번호 설정

### 확인
```powershell
wsl --list --verbose
```


## 2. OpenFOAM v2312 — CFD 솔버

### WSL Ubuntu 안에서 설치
```bash
# OpenFOAM 저장소 추가
curl -s https://dl.openfoam.com/add-debian-repo.sh | sudo bash

# 설치
sudo apt update
sudo apt install openfoam2312

# 환경 설정 (.bashrc에 추가)
echo "source /usr/lib/openfoam/openfoam2312/etc/bashrc" >> ~/.bashrc
source ~/.bashrc

# 확인
simpleFoam -help
```

### Windows 파일 접근
WSL에서 Windows 파일은 `/mnt/c/` 경로로 접근:
```bash
# 예: OneDrive의 OpenFOAM 케이스
cd "/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/lv_cfd/openfoam_case"
```

### CFD 실행 순서
```bash
cd openfoam_case
blockMesh                    # 배경 hex 메시 생성 (~5초)
snappyHexMesh -overwrite     # 표면 적합 메시 + BL (~1-5분)
checkMesh                    # 메시 품질 확인
pimpleFoam                   # Navier-Stokes 풀기 (~수시간)
```


## 3. ParaView — CFD 결과 시각화

### Windows 버전 설치 (추천)
- 다운로드: https://www.paraview.org/download/
- 최신 버전 (5.12+) Windows installer
- 설치 후 바로 사용 가능

### 사용법
```bash
# WSL에서 OpenFOAM 결과를 ParaView 형식으로 변환
paraFoam -touchAll
# → .foam 파일 생성

# Windows ParaView에서 열기:
# File → Open → openfoam_case.foam
```

### 주요 시각화
- Surface → wallShearStress (WSS 분포)
- Slice → p (pressure 단면)
- StreamTracer → U (유선 시각화)
- Plot Over Line → velocity profile


## 4. 3D Slicer — 의료영상 시각화 & segmentation

### 설치
- 다운로드: https://download.slicer.org/
- Windows 64-bit installer
- 설치 후 바로 NIfTI 파일 열기 가능

### 사용법
1. File → Add Data → ct_train_1009_image.nii.gz
2. 같은 방법으로 ct_train_1009_label.nii.gz 로드
3. Volume Rendering 모듈 → 3D volume rendering
4. Segment Editor → segmentation 수정/보정

### MM-WHS 데이터 보기
- Preset: CT-Cardiac 선택하면 이 사진처럼 심장 volume rendering 바로 가능
- Label map overlay로 7개 구조 색상 확인


## 5. GMSH (선택) — 추가 메시 도구

snappyHexMesh 대신 더 정교한 volume mesh가 필요할 때.

### 설치
- 다운로드: https://gmsh.info/#Download
- Windows 64-bit 버전
- 또는 WSL: `sudo apt install gmsh`

### 사용법
```bash
gmsh lv_endocardium.stl -3 -o lv_volume.msh -format msh2
```


## 6. Python 패키지 (이미 설치됨 / 로컬에도 설치 권장)

```bash
pip install nibabel          # NIfTI 읽기
pip install trimesh          # STL 메시 처리
pip install scikit-image     # marching cubes
pip install numpy scipy matplotlib
pip install pyvista          # 3D 시각화 (VTK 기반, 선택)
```


## 설치 우선순위

| 순서 | 소프트웨어 | 용도 | 시간 |
|------|-----------|------|------|
| 1 | WSL + Ubuntu | OpenFOAM 기반 | 10분 |
| 2 | OpenFOAM 2312 | CFD 솔버 | 15분 |
| 3 | ParaView | 결과 시각화 | 5분 |
| 4 | 3D Slicer | 의료영상 보기 | 5분 |
| 5 | GMSH (선택) | 고급 메시 | 3분 |

**총 소요 시간: ~35분** (다운로드 속도에 따라 다름)


## 설치 후 테스트 — 바로 실행 가능

```bash
# WSL에서
source /usr/lib/openfoam/openfoam2312/etc/bashrc
cd "/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/lv_cfd/openfoam_case"

# 1단계: 메시 생성
blockMesh
snappyHexMesh -overwrite
checkMesh

# 2단계: 시뮬레이션 (시간 소요)
pimpleFoam | tee log.pimpleFoam

# 3단계: 후처리
paraFoam -touchAll
# → Windows ParaView에서 열기
```


## 트러블슈팅

### WSL에서 OpenFOAM 못 찾을 때
```bash
source /usr/lib/openfoam/openfoam2312/etc/bashrc
which blockMesh  # 경로 확인
```

### snappyHexMesh 실패할 때
- `checkMesh` 로 메시 품질 확인
- `system/snappyHexMeshDict`에서 `maxGlobalCells` 늘리기
- `locationInMesh` 좌표가 실제 LV 내부인지 확인

### pimpleFoam 발산할 때
- `system/controlDict`에서 `deltaT` 줄이기
- `maxCo 0.5`로 낮추기
- `system/fvSchemes`에서 `div(phi,U)` → `Gauss upwind`로 변경 (1st order, 안정적)
