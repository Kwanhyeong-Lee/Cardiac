# 새 컴퓨터(RTX 3060) 셋업 — git pull 하나로 시작하기

이 폴더(`tools/setup/`)가 새 컴퓨터를 세우는 데 필요한 전부다. 새 컴퓨터에는 OneDrive가 없으므로
**git으로 오는 것은 이 폴더를 포함한 코드·문서뿐이고, git에 넣을 수 없는 세 가지는 외장 드라이브로 옮긴다.**

## 0. 기계

| 이름 | Windows 사용자 | 무엇이 있나 | 여기서 하는 일 |
|---|---|---|---|
| **WORK** | `alex0` | 저장소 `C:\work\Cardiac`, OneDrive 프로젝트, MM-WHS(OneDrive) | 지금까지의 모든 작업. 드라이브 만들기(A) |
| **GPU** | `wjsdm` | RTX 3060 12 GB + RX 5700(화면용), 32 GB. **OneDrive 없음** | 형상 파이프라인 20례, PINN GPU 학습, Unreal |

두 기계 모두 저장소는 `C:\work\Cardiac`(WSL에서 `/mnt/c/work/Cardiac`)에 둔다. Unreal이 Windows 경로로 빌드해야 하기 때문이다.
Python 가상환경만은 WSL 안쪽(`~/.venvs/cardiac`)에 둔다 — NTFS 위의 venv는 몇 배 느리고 Windows용과 섞이면 깨진다.

## 1. 무엇이 어떻게 건너가나

| 무엇 | 경로 | 이유 |
|---|---|---|
| 코드·문서·JSON·그림, 이 셋업 키트, 태스크 프롬프트 | **git pull** | |
| MM-WHS 원본 CT (`ct_train` 40파일) | **외장 드라이브** | 연구 라이선스, 재배포 금지 — 본인 기계 간 이동만 |
| 1009 형상 에셋 (`sync_assets_2026-09-17.zip`, 402 MB) | **외장 드라이브** | MM-WHS 파생 메시. 1009의 초기 단계(Blender 판막 등)는 라벨만으로 재생성되지 않아 통째로 옮긴다 |
| PINN 원자료 (MIMIC·eICU·INSPIRE 파생 CSV) | **외장 드라이브, 명시적으로 요청할 때만** | PhysioNet DUA: 자격자 본인의 보안 기계에서만. 암호화 드라이브(BitLocker To Go), 저장소·클라우드 금지 |
| Unreal 에셋 팩 (glb 213 MB) | **옮기지 않음** | GPU 컴퓨터에서 `export_unreal.py`로 1분 만에 재생성 |
| 1009 외 케이스의 형상 산출물 | **옮기지 않음** | GPU 컴퓨터에서 배치로 새로 만든다(`TASK_BATCH.md`) |

## 2. 순서

### A. WORK(alex0)에서 한 번 — 드라이브 만들기

Windows **PowerShell**에서(WSL 아님 — OneDrive의 클라우드 전용 파일은 네이티브 Windows에서 읽어야 내려받아진다):

```powershell
cd C:\work\Cardiac
powershell -ExecutionPolicy Bypass -File tools\setup\make_transfer.ps1 -Drive E:\
```

`E:\cardiac_transfer_<날짜>\`에 `geometry\`, `mmwhs\ct_train\`, `SHA256SUMS.txt`가 생긴다. PINN 원자료까지 옮길 때만
`-IncludePatientData -PatientDataPaths "경로1","경로2"`를 붙인다(경로를 직접 지정해야 하고, 추측해서 담지 않는다).

**USB 없이 하는 대안** — GPU 컴퓨터의 브라우저로 onedrive.live.com에 (같은 본인 계정으로) 로그인해서 두 개를 `Downloads`에 받는다:
`PINN heart/MM-WHS/ct_train` 폴더(OneDrive가 zip으로 묶어 준다)와 `PINN/260421 (심장) - main/_handover/sync_2026-09-17/sync_assets_2026-09-17.zip`.
본인 클라우드에서 본인 기계로 받는 것이라 재배포가 아니다. `unpack_transfer.sh`는 이름으로 찾으므로 그대로 `/mnt/c/Users/wjsdm/Downloads`를 주면 된다
(이 경로에는 체크섬 파일이 없어 검증은 건너뛴다). 환자 단위 원자료는 이 방법으로 옮기지 않는다.

### B. GPU(wjsdm) Windows에서 — 사람이 직접 (설치 프로그램·로그인은 자동화하지 않는다)

1. **NVIDIA 드라이버**를 Windows에 최신으로. WSL 안에 리눅스용 드라이버를 깔면 안 된다 — WSL의 CUDA는 Windows 드라이버를 쓴다.
2. **WSL2 + Ubuntu**, 그 안에 **Claude Code**.
3. (Unreal용) **Unreal Engine 5.4+** (Epic Games Launcher), **Visual Studio 2022** + "Desktop development with C++" + "Game development with C++".
4. (배치를 돌릴 거면) `C:\Users\wjsdm\.wslconfig`에 아래를 넣고 PowerShell에서 `wsl --shutdown`. 기본값은 RAM의 절반(16 GB)이다.
   ```
   [wsl2]
   memory=24GB
   swap=16GB
   ```
5. 저장소가 private이면 WSL에서 `gh auth login`(또는 사용하는 방식으로) GitHub 인증을 **직접** 해 둔다. 토큰을 Claude Code에 붙여 넣지 말 것.

### C. GPU(wjsdm) WSL에서 — Claude Code

```bash
mkdir -p /mnt/c/work && cd /mnt/c/work
git clone <저장소 주소> Cardiac        # 처음 한 번. 주소는 WORK에서: git -C /mnt/c/work/Cardiac remote get-url origin
cd Cardiac && claude                   # 이후로는 git pull
```

그리고 아래 프롬프트를 붙여 넣는다.

```
이 컴퓨터(RTX 3060, OneDrive 없음)를 tools/setup/SETUP.md 의 C 단계대로 세워 줘.
규칙: sudo 가 필요한 명령은 실행하지 말고 나에게 그대로 보여줘. 토큰·비밀번호는 다루지 않는다. --force 금지. 이 과정에서 커밋은 하지 않는다.

1. bash tools/setup/setup_wsl.sh
   - torch 설치가 오래 걸린다(수 GB). 타임아웃이 나면 그냥 다시 실행 — 모든 단계가 이어서 진행된다.
   - apt 패키지가 없다고 멈추면, 출력된 sudo 명령을 나에게 보여주고 기다려.
2. 새 셸 환경을 반영: source ~/.bashrc && source ~/.venvs/cardiac/bin/activate
3. 전송 파일을 찾아서 풀어 줘: 외장 드라이브의 /mnt/<문자>/cardiac_transfer_* 를 먼저, 없으면 /mnt/c/Users/wjsdm/Downloads 에서
   sync_assets_*.zip 과 ct_train 파일(또는 그걸 담은 zip)을 찾아:
   bash tools/setup/unpack_transfer.sh <찾은 폴더> --unreal
   둘 다 없으면 어디 있는지 나에게 물어봐. 파이프라인을 다시 돌려서 대신하려 하지 말 것.
4. python tools/setup/gpu_smoke.py
   - "SETUP OK on cuda" 가 나와야 한다. [KNOWN] 항목은 기존 코드 문제라 셋업 실패가 아니다(TASK_PINN_GPU.md).
5. python tools/setup/check_setup.py --fetch
   - 마지막의 geometry / pinn / unreal 세 줄과 NEXT STEPS 를 그대로 보여주고, NOT READY 가 있으면 각각 무엇을 하면 되는지 정리해 줘.
```

### D. 그다음 — 서로 독립, 순서 상관없음

| 파일 | 무엇 | 필요한 것 |
|---|---|---|
| `TASK_BATCH.md` | MM-WHS 20례 형상 파이프라인 | check_setup: geometry READY |
| `TASK_PINN_GPU.md` | GPU 학습 확인 → 실제 실험 | pinn READY, gpu_smoke 통과 |
| `TASK_UNREAL.md` | HeartTeach M1 빌드 | unreal READY |

## 3. 넘어지는 곳

- **CUDA가 안 잡힘** — `torch.version.cuda`가 None이면 CPU판 torch가 깔린 것(`pip uninstall -y torch && pip install torch`).
  CUDA는 있는데 장치가 없으면 Windows 드라이버 문제이고, 설치 후 `wsl --shutdown`을 안 한 경우가 많다.
- **모든 파일이 수정됨으로 보임** — NTFS 위 클론에서 `core.filemode`. setup_wsl.sh가 `false`로 맞춘다.
  같은 클론을 Windows용 git으로도 만지면 줄바꿈 설정이 섞이니 WSL git 하나만 쓰는 게 안전하다.
- **`CARDIAC_DATA`** — 데이터 **루트**다(`/mnt/d/data` 또는 `~/data`). MM-WHS는 그 아래 `MM-WHS/ct_train`.
  형상 스크립트는 예전 방식(ct_train 폴더를 직접 지정)도 받아 준다(`fusion_ready/case_paths.py: resolve_mmwhs`).
- **배치 도중 죽음** — WSL 메모리(위 B-4). 배치는 끊겨도 이어서 돈다(완료된 단계는 건너뜀).
- **형상 메시·원자료가 git에 들어갈 뻔함** — `unpack_transfer.sh`가 풀기 전에 모든 경로가 ignore되는지 먼저 확인하고,
  하나라도 아니면 거부한다. 커밋 전에는 항상 `git status`.
