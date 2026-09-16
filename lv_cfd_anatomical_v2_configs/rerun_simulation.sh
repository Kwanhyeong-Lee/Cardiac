#!/bin/bash
# ============================================================
# Cardiac LV CFD v2 — Re-run Script
# ============================================================
# 이전 시뮬레이션이 SIGFPE로 발산한 원인:
#   1. 메시에 음수 부피 셀 3개 (aspect ratio 10^92)
#   2. backward ddt 스키마가 초기 과도현상에 너무 공격적
#   3. maxCo=0.8이 불안정 셀에서 제어 불가
#   4. 메시 품질 기준(minTetQuality, minArea)이 비활성화 상태
#
# 수정 사항 (v2):
#   - snappyHexMeshDict: 메시 품질 기준 강화, 레이어 설정 완화
#   - fvSchemes: backward → Euler, linearUpwind → upwind
#   - fvSolution: corrector 증가, 잔차 제어 추가
#   - controlDict: maxCo 0.3, deltaT 1e-6, 잔차 모니터링 추가
#
# 실행 방법: WSL Ubuntu에서
#   cd ~/lv_cfd_anatomical
#   bash "/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/lv_cfd_anatomical_v2_configs/rerun_simulation.sh"
# ============================================================
set -e

# ── 경로 ──
WSL_CASE="$HOME/lv_cfd_anatomical"
ONEDRIVE="/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main"
V2_CONFIGS="${ONEDRIVE}/lv_cfd_anatomical_v2_configs"

cd "$WSL_CASE"

echo "============================================================"
echo " Cardiac LV CFD v2 Re-run"
echo "============================================================"
echo ""

# ── Step 0: 기존 결과 백업 ──
echo "[0/6] 기존 결과 백업..."
BACKUP_DIR="${WSL_CASE}_backup_$(date +%Y%m%d_%H%M)"
mkdir -p "$BACKUP_DIR"
cp -r system "$BACKUP_DIR/"
cp -r 0 "$BACKUP_DIR/"
cp log.* "$BACKUP_DIR/" 2>/dev/null || true
echo "  백업 위치: $BACKUP_DIR"

# ── Step 1: v2 설정 파일 복사 ──
echo ""
echo "[1/6] v2 설정 파일 적용..."
cp "${V2_CONFIGS}/system/controlDict"       system/controlDict
cp "${V2_CONFIGS}/system/fvSchemes"          system/fvSchemes
cp "${V2_CONFIGS}/system/fvSolution"         system/fvSolution
cp "${V2_CONFIGS}/system/snappyHexMeshDict"  system/snappyHexMeshDict
echo "  controlDict, fvSchemes, fvSolution, snappyHexMeshDict 복사 완료"

# ── Step 2: 기존 시뮬레이션 데이터 삭제 ──
echo ""
echo "[2/6] 기존 시간 디렉토리 및 결과 삭제..."
# Remove time directories (keep 0/)
find . -maxdepth 1 -type d -regex '.*/[0-9].*' ! -name '0' -exec rm -rf {} +
rm -rf postProcessing processor* log.pimpleFoam
echo "  삭제 완료"

# ── Step 3: 메시 재생성 ──
echo ""
echo "[3/6] 메시 재생성 (snappyHexMesh)..."
echo "  blockMesh..."
blockMesh > log.blockMesh_v2 2>&1
echo "  snappyHexMesh..."
snappyHexMesh -overwrite > log.snappyHexMesh_v2 2>&1
echo "  완료"

# ── Step 4: 메시 품질 확인 ──
echo ""
echo "[4/6] 메시 품질 확인..."
checkMesh > log.checkMesh_v2 2>&1

# Check for critical failures
if grep -q "negative volume" log.checkMesh_v2; then
    echo "  ⚠ 경고: 음수 부피 셀 여전히 존재!"
    echo "  수동 확인 필요: cat log.checkMesh_v2"
    read -p "  계속하시겠습니까? [y/N]: " CONT
    [ "$CONT" != "y" ] && [ "$CONT" != "Y" ] && exit 1
fi

# Print mesh stats
grep -A2 "^Mesh stats" log.checkMesh_v2
echo ""
grep "Max aspect ratio" log.checkMesh_v2 || true
grep "non-orthogonality" log.checkMesh_v2 || true
grep "negative volume" log.checkMesh_v2 || echo "  ✓ 음수 부피 셀 없음"
grep "Failed" log.checkMesh_v2 || echo "  ✓ 모든 메시 품질 체크 통과"

# ── Step 5: Patch 재설정 ──
echo ""
echo "[5/6] createPatch + topoSet..."
if [ -f system/createPatchDict ]; then
    createPatch -overwrite > log.createPatch_v2 2>&1
fi
if [ -f system/topoSetDict ]; then
    topoSet > log.topoSet_v2 2>&1
fi
echo "  완료"

# ── Step 6: potentialFoam 초기화 + pimpleFoam 실행 ──
echo ""
echo "[6/6] 시뮬레이션 실행..."

# Optional: potentialFoam for better initial condition
if command -v potentialFoam &> /dev/null; then
    echo "  potentialFoam 초기화..."
    potentialFoam -initialiseUBCs > log.potentialFoam_v2 2>&1 || true
fi

echo "  pimpleFoam 시작 (endTime=2.4s, 3 cardiac cycles)..."
echo "  (Ctrl+C로 중단 가능)"
echo ""
pimpleFoam > log.pimpleFoam_v2 2>&1 &
PID=$!

echo "  PID: $PID"
echo "  로그 모니터링: tail -f log.pimpleFoam_v2"
echo ""
echo "  시뮬레이션 후 OneDrive 동기화:"
echo "    bash \"${ONEDRIVE}/sync_wsl_to_onedrive.sh\""
echo ""
echo "============================================================"
