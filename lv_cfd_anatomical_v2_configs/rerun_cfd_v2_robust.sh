#!/bin/bash
# ============================================================
# Cardiac LV CFD — v2 Robust Re-run (mesh-quality gated)
# ============================================================
# v1 발산 근본 원인 = 메시 결함:
#   - 음수 부피 셀 3개, aspect ratio 1.74e92, 잘못 배향된 면 28개
#   → 압력 Poisson 발산 → Courant 3e14 → SIGFPE
#
# 이 스크립트가 기존 rerun_simulation.sh와 다른 점:
#   1. 경로 자동 감지 (BASH_SOURCE 기준) — 사용자명(alex0/USER 등) 무관
#   2. checkMesh 하드 게이트 — 음수 부피/잘못 배향 면이 있으면 pimpleFoam을
#      절대 실행하지 않고, 메시 설정을 완화하며 자동 재시도
#   3. 3단 fallback: (A) 풀 v2 → (B) addLayers off → (C) refinement 축소
#   4. 소프트 결함(비직교성/skewness)은 nNonOrthCorrectors로 흡수하므로 통과
#
# 사용법 (WSL Ubuntu, OpenFOAM 소싱된 상태):
#   bash ".../lv_cfd_anatomical_v2_configs/rerun_cfd_v2_robust.sh" [케이스경로]
#   케이스경로 생략 시 기본값 $HOME/lv_cfd_anatomical
# ============================================================
set -uo pipefail

# ── 경로 자동 감지 ─────────────────────────────────────────
V2_CONFIGS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ONEDRIVE="$(dirname "$V2_CONFIGS")"
WSL_CASE="${1:-$HOME/lv_cfd_anatomical}"

echo "============================================================"
echo " Cardiac LV CFD v2 Robust Re-run"
echo "============================================================"
echo " V2 configs : $V2_CONFIGS"
echo " OneDrive   : $ONEDRIVE"
echo " Case dir   : $WSL_CASE"
echo ""

# ── 환경 확인 ─────────────────────────────────────────────
command -v pimpleFoam >/dev/null || { echo "✗ OpenFOAM 미소싱. 'source .../etc/bashrc' 후 재실행"; exit 1; }

if [ ! -d "$WSL_CASE" ]; then
    echo "케이스 디렉토리가 없습니다. OneDrive에서 복사합니다..."
    cp -r "$ONEDRIVE/lv_cfd_anatomical" "$WSL_CASE" || { echo "✗ 복사 실패"; exit 1; }
fi
cd "$WSL_CASE"

# ── Step 0: 백업 ──────────────────────────────────────────
BACKUP="${WSL_CASE}_backup_$(date +%Y%m%d_%H%M)"
mkdir -p "$BACKUP"
cp -r system "$BACKUP/" 2>/dev/null || true
cp -r 0 "$BACKUP/" 2>/dev/null || true
cp log.* "$BACKUP/" 2>/dev/null || true
echo "[0] 백업: $BACKUP"

# ── Step 1: v2 설정 적용 ──────────────────────────────────
cp "$V2_CONFIGS/system/controlDict"       system/controlDict
cp "$V2_CONFIGS/system/fvSchemes"          system/fvSchemes
cp "$V2_CONFIGS/system/fvSolution"         system/fvSolution
cp "$V2_CONFIGS/system/snappyHexMeshDict"  system/snappyHexMeshDict
echo "[1] v2 config 적용 완료 (controlDict/fvSchemes/fvSolution/snappyHexMeshDict)"

# ── Step 2: 기존 결과 삭제 ────────────────────────────────
find . -maxdepth 1 -type d -regex '.*/[0-9].*' ! -name '0' -exec rm -rf {} + 2>/dev/null || true
rm -rf postProcessing processor* log.pimpleFoam* 2>/dev/null || true
echo "[2] 기존 시간 디렉토리/결과 삭제"

# ── checkMesh 하드 게이트 함수 ────────────────────────────
# 반환: 0 = 통과(치명 결함 없음), 1 = 치명 결함(음수부피/잘못배향 면)
mesh_ok () {
    local log="$1"
    checkMesh > "$log" 2>&1
    local neg orient
    neg=$(grep -icE "negative volume|zero or negative cell volume" "$log" || true)
    orient=$(grep -icE "faces are incorrectly oriented|incorrectly oriented faces" "$log" || true)
    echo "    --- checkMesh 요약 ---"
    grep -iE "cells:|Max aspect ratio|Max cell openness|non-orthogonality|Max skewness|Mesh OK|Failed .* mesh checks" "$log" | sed 's/^/    /'
    if [ "$neg" -gt 0 ] || [ "$orient" -gt 0 ]; then
        echo "    ✗ 치명 결함: 음수부피/잘못배향 면 존재 → pimpleFoam 실행 불가"
        return 1
    fi
    echo "    ✓ 치명 결함 없음 (비직교성/skewness는 corrector로 흡수)"
    return 0
}

build_mesh () {
    echo "    blockMesh...";       blockMesh > log.blockMesh_v2 2>&1
    echo "    snappyHexMesh...";   snappyHexMesh -overwrite > log.snappyHexMesh_v2 2>&1
}

# ── Step 3: 메시 생성 + 3단 fallback ──────────────────────
echo "[3] 메시 생성 (Attempt A: 풀 v2 — castellate+snap+layers)"
build_mesh
if mesh_ok log.checkMesh_v2A; then
    PASS=1
else
    echo "[3] Attempt B: addLayers false (레이어가 퇴화 셀의 흔한 원인)"
    sed -i 's/^addLayers .*true;/addLayers       false;/' system/snappyHexMeshDict
    build_mesh
    if mesh_ok log.checkMesh_v2B; then
        PASS=1
    else
        echo "[3] Attempt C: refinement (2 3)→(1 2), maxGlobalCells 3M→1.5M"
        sed -i 's/level (2 3);/level (1 2);/' system/snappyHexMeshDict
        sed -i 's/maxGlobalCells      3000000;/maxGlobalCells      1500000;/' system/snappyHexMeshDict
        build_mesh
        if mesh_ok log.checkMesh_v2C; then PASS=1; else PASS=0; fi
    fi
fi

if [ "${PASS:-0}" -ne 1 ]; then
    echo ""
    echo "✗ 3단 fallback 모두 치명 결함 잔존. pimpleFoam 실행 중단."
    echo "  다음 수동 조치를 검토하세요:"
    echo "   1) STL 자체 결함: surfaceCheck constant/triSurface/lv_surface.stl"
    echo "      → 자기교차/구멍이 있으면 surfaceClean / meshlab 정리 필요"
    echo "   2) locationInMesh (-0.0373 0.0318 -0.1596) 가 내강 안쪽인지 재확인"
    echo "   3) 최근 checkMesh 로그: tail -40 log.checkMesh_v2C"
    exit 2
fi

# ── Step 4: patch/topoSet (있으면) ────────────────────────
[ -f system/createPatchDict ] && createPatch -overwrite > log.createPatch_v2 2>&1 || true
[ -f system/topoSetDict ]     && topoSet > log.topoSet_v2 2>&1 || true
echo "[4] createPatch/topoSet 완료"

# ── Step 5: 초기화 + 실행 ─────────────────────────────────
if command -v potentialFoam >/dev/null; then
    echo "[5] potentialFoam 초기화..."
    potentialFoam -initialiseUBCs > log.potentialFoam_v2 2>&1 || echo "    (potentialFoam 건너뜀)"
fi
echo "[5] pimpleFoam 백그라운드 실행 (endTime=2.4s)"
nohup pimpleFoam > log.pimpleFoam_v2 2>&1 &
PID=$!
echo "    PID=$PID   로그: $WSL_CASE/log.pimpleFoam_v2"
echo ""
echo "  모니터링:  bash \"$V2_CONFIGS/monitor_cfd.sh\" \"$WSL_CASE\""
echo "  동기화:    bash \"$ONEDRIVE/sync_wsl_to_onedrive.sh\"   # 완료 후, 모드(b) 권장"
echo "============================================================"
