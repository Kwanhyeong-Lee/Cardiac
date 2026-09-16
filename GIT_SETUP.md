# 다른 컴퓨터(RTX 3060 / 32 GB / RX 5700)로 옮기기

## 원칙: git에는 코드·문서·작은 결과만, 데이터는 따로

이 폴더는 45 GB지만 그중 git에 들어갈 것은 **100 MB 미만**이다.

| 내용 | 크기 | 어디로 |
|---|---|---|
| `waveform_pinn/*.py`, `fusion_ready/*.py`, `lv_cfd_*/system,constant(dict만)`, `*.md`, `*.json`, 작은 `*.png` | ~수십 MB | **git** |
| `MIMIC IV/`(40 GB), eICU, INSPIRE zip, `external_datasets/` | 40 GB+ | **절대 git 금지**(DUA·credentialing). 외장 SSD로 복사, 새 PC에서도 같은 상대경로 유지 |
| MM-WHS `*.nii.gz` | 5.3 GB | 재배포 금지 라이선스 → 외장 SSD |
| `lv_cfd_v2/` OpenFOAM 결과, `processor*/`, 시간 디렉토리 | 3.3 GB | 재생성 대상, git 제외 |
| `fusion_ready/{PRINT,CAD,BLENDER_OUT,CT,PHANTOM}/*.stl` | ~0.5 GB | `PIPELINE.md`로 재생성. 최종 프린트 파일 3개만 Git LFS |

`.gitignore`는 이미 이 기준으로 작성돼 있다.

## 절차 (이미 끝남 — 2026-09-16, 기록용)

> 아래는 이 저장소를 처음 만들 때 쓴 명령이다. 저장소는 이미
> `https://github.com/Kwanhyeong-Lee/Cardiac` (PRIVATE)에 있으므로 **다시 실행하지 말 것** —
> 새 PC에서는 아래 "새 PC 세팅"의 clone만 하면 된다.

```powershell
# 1. OneDrive 폴더 안에서 git init 하지 말 것 — .git 오브젝트가 동기화 충돌로 깨지는 흔한 사고.
#    OneDrive 밖(예: C:\work)으로 코드만 복사해서 저장소를 만든다.
robocopy "C:\Users\alex0\OneDrive\PINN\260421 (심장) - main" C:\work\cardiac-phpinn /E /XD "MIMIC IV" external_datasets external_data lv_cfd_v2 node_modules cardiac_meshes_all /XF *.nii.gz *.stl *.glb *.npz *.npy *.blend *.csv.gz
cd C:\work\cardiac-phpinn
git init -b main
git lfs install
git lfs track "fusion_ready/BLENDER_OUT/hollow_ventricle_v4_CT.stl" "fusion_ready/PHANTOM/*_PRINT_ORIENTED.stl"
git add .gitattributes .gitignore
git add .
git status            # 여기서 MIMIC/eICU/INSPIRE/nii 가 하나도 없는지 눈으로 확인
git commit -m "cardiac pH-PINN + geometry pipeline"
# 2. GitHub에 PRIVATE 저장소 만들고 push (원격 URL은 직접):
git remote add origin <url>
git push -u origin main
```

커밋 전 마지막 확인: `git ls-files | Select-String -Pattern "mimic|eicu|inspire|nii|physionet" -CaseSensitive:$false` 가 아무것도 안 나와야 한다.

## 새 PC 세팅

```powershell
git clone https://github.com/Kwanhyeong-Lee/Cardiac.git C:\work\Cardiac   # OneDrive 밖에
# 데이터: 외장 SSD -> D:\data\{MIMIC IV, eICU, INSPIRE, MM-WHS}
# 경로는 환경변수로 (코드에 하드코딩된 경로가 있으면 이걸 읽도록 한 줄씩 고침)
setx CARDIAC_DATA D:\data
```

파이썬 환경(conda 또는 venv):
```
pip install torch --index-url https://download.pytorch.org/whl/cu121     # RTX 3060용 CUDA
pip install numpy scipy pandas scikit-learn matplotlib trimesh fast-simplification rtree pymeshfix shapely mapbox-earcut manifold3d scikit-image nibabel
```
- **RTX 3060 (12 GB)**: `waveform_pinn/` 학습(Paper B 전 실험)이 유일한 GPU 작업. 샌드박스에서 CPU로 돌리던 것들이 10배 이상 빨라짐.
- **RX 5700**: CUDA 불가, Windows ROCm도 Navi10은 사실상 미지원 → 디스플레이용. PyTorch는 `cuda:0` = 3060 확인 (`torch.cuda.get_device_name(0)`).
- **32 GB RAM**: 이 세션에서 우회했던 OOM(대형 메시 `contains()`, 큰 커널 closing)이 전부 사라짐. `fusion_ready/*.py`는 그대로 돌아간다(`PYTHONPATH=/tmp/pylibs` 불필요).
- **Blender 5.2** 설치 → `fusion_ready/run_blender_pipeline.bat`.
- **OpenFOAM**: WSL2 Ubuntu에 `openfoam2312` → `lv_cfd_patient/run_patient_cfd.sh`. 팬텀 도메인은 `fusion_ready/PHANTOM/cfd/`.
- **Fusion 360**: `fusion_ready/CAD/`, `PHANTOM/*.stl` 임포트. 로컬 MCP(7654)는 그 PC에서 다시 시도.

## 하드코딩 경로

**끝났다.** 샌드박스/WSL 절대경로는 코드와 문서에서 전부 없앴고, 환경변수 3개(`CARDIAC_DATA`, `CARDIAC_OUT`, `CARDIAC_REPO`)로 대체했다 — 전부 기본값이 있어 clone 직후 설정 없이 돌아간다. 자세한 내용은 `HANDOVER.md` §3.
