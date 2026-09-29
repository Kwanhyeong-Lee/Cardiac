# TASK_UNREAL — HeartTeach M1 (GPU 컴퓨터)

전제: `check_setup.py`에서 **unreal READY** — UE 5.4+, Visual Studio C++, 1009 형상 에셋, 에셋 팩(`fusion_ready/UNREAL/1009`, glb 20개).
에셋 팩은 `unpack_transfer.sh --unreal`이 이 컴퓨터에서 만들었으므로 **스크립트 기본 경로(`C:\work\Cardiac\fusion_ready\UNREAL\1009`)에 이미 있다.
`HEART_PACK`을 따로 잡을 필요가 없다.** 설계 근거는 `fusion_ready/UNREAL/HeartTeach/SPEC.md`.

## WSL의 Claude Code로 Windows용 UE를 다루는 법

UE와 Visual Studio는 Windows 프로그램이지만 WSL에서 그대로 부를 수 있다(Windows interop). 경로만 Windows 형식으로 넘기면 된다.

```bash
UE="/mnt/c/Program Files/Epic Games/UE_5.4"          # 설치된 버전으로
PROJ='C:\work\Cardiac\fusion_ready\UNREAL\HeartTeach\HeartTeach.uproject'
cd /mnt/c/work/Cardiac                                 # cmd.exe 는 WSL 경로를 작업 폴더로 못 쓴다 -> /mnt/c 아래에서 실행
cmd.exe /c "\"C:\Program Files\Epic Games\UE_5.4\Engine\Build\BatchFiles\Build.bat\" HeartTeachEditor Win64 Development -Project=\"$PROJ\" -WaitMutex -NoHotReload"
"$UE/Engine/Binaries/Win64/UnrealEditor.exe" "$PROJ" -ExecutePythonScript='C:\work\Cardiac\fusion_ready\UNREAL\HeartTeach\Python\01_import_assets.py'
```

`-ExecutePythonScript`는 에디터를 띄운 채로 스크립트를 실행한다(창이 열린다). 01 → 02 → 03을 차례로.
플레이 화면을 보고 판단하는 4가지 확인은 **사람이 한다** — Claude Code는 결과를 받아 적는다.

## Claude Code 프롬프트

```
fusion_ready/UNREAL/HeartTeach 를 이 컴퓨터에서 빌드하고 레벨까지 만들어 줘. TASK_UNREAL.md 의 방법(WSL에서 cmd.exe / UnrealEditor.exe 호출)을 써.
규칙: --force 금지, 토큰 취급 금지. .glb, Saved/, Intermediate/, Binaries/, DerivedDataCache/, Content/ 는 커밋하지 않는다.

0. SPEC.md 를 먼저 읽어. 2절(좌표계), 4절(머티리얼), 5절(관류 색 = 데이터)은 임의로 바꾸지 마.
1. python tools/setup/check_setup.py 에서 unreal 이 READY 인지 확인. 아니면 NEXT STEPS 를 보여주고 멈춰.
2. HeartTeach.uproject 의 EngineAssociation 을 설치된 UE 버전에 맞추고 Build.bat 으로 HeartTeachEditor Win64 Development 빌드.
   C++ 은 UE 헤더 없이 쓴 초안이라 에러가 날 수 있다 — 고치되 공개 API(함수 이름·시그니처)와 주석의 의도는 유지하고, 무엇을 왜 바꿨는지 요약해 줘.
3. UnrealEditor.exe ... -ExecutePythonScript 로 Python/01_import_assets.py, 02_build_materials.py, 03_build_level.py 를 차례로.
   API 이름이 바뀐 것뿐이면(SPEC.md 7절 목록) 그 줄만 고치고 스크립트에 주석으로 남겨. 각 단계의 [HeartTeach] 로그를 보여줘.
4. 여기서 멈추고 나에게 L_Heart 를 Play 해서 확인할 4가지를 안내해 줘:
   (a) 기본 시점에서 두꺼운 짙은 붉은 벽(좌심실)이 화면 오른쪽에 있는가 — 아니면 좌표계가 뒤집힌 것. 음수 스케일로 때우지 말고 보고.
   (b) SetClipEnabled(true) 후 SetClipOffset -3~+3 cm 에서 잘린 면이 평평한 단면으로 보이는가
   (c) 부위 클릭 시 OnPartClicked 가 이름을 주는가   (d) Stat FPS
5. 내가 알려준 결과로 fusion_ready/UNREAL/HeartTeach/BUILD_NOTES.md 를 써: UE 버전, 고친 컴파일 에러, 고친 Python API, 4가지 결과, 남은 문제.
6. git status 로 엔진 산출물이 안 잡히는지 확인하고 소스·스크립트·문서만 커밋·푸시.
   메시지: "Unreal: HeartTeach M1 building and running on the 3060 box"
```

## 완료 기준과 다음

M1 = 궤도 카메라로 돌려 보고, 아무 위치나 잘라 단면을 보고, 부위를 클릭하면 이름이 나오는 것. UI 모양은 M4에서.
다음: M2 부위 토글·격리·분해 + 출처 배지 → M3 관류(혈관 클릭 → 영역 회색 + 위험 심근량, 실측/가정 구분) → M4 UMG → M5 퀴즈.
M3 데이터는 이미 DataTable에 다 있다.

라이선스: 형상은 MM-WHS 파생이라 **지오메트리가 들어간 패키지 빌드는 공개 배포 불가**. 교내 설치·시연·스크린샷은 가능.
