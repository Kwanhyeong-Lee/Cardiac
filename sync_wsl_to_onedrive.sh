#!/bin/bash
# ============================================================
# WSL → 저장소 시뮬레이션 데이터 동기화 스크립트
# ============================================================
# 용도: WSL 내부에 생성된 CFD 시뮬레이션 시간 디렉토리와
#       postProcessing 결과를 저장소로 복사
#
# 실행 방법: WSL Ubuntu 터미널에서
#   bash "/mnt/c/work/Cardiac/sync_wsl_to_onedrive.sh"
#
# 주의: 디스크 용량 확인 필요 (시뮬레이션 데이터는 수 GB 가능)
# ============================================================
set -e

# ---- 경로 설정 ----
WSL_CFD_DIR="$HOME/cardiac_cfd/lv_cfd_anatomical"
# Repository root = the folder holding this script; override with CARDIAC_REPO
# (HANDOVER.md section 3). The repository is no longer inside OneDrive.
REPO_BASE="${CARDIAC_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
REPO_CFD="${REPO_BASE}/lv_cfd_anatomical"

echo "============================================================"
echo " WSL → 저장소 시뮬레이션 데이터 동기화"
echo "============================================================"
echo ""

# ---- WSL에서 lv_cfd_anatomical 위치 찾기 ----
if [ ! -d "$WSL_CFD_DIR" ]; then
    echo "[!] 기본 경로에 시뮬레이션 디렉토리 없음: $WSL_CFD_DIR"
    echo "    WSL 내부에서 lv_cfd_anatomical 디렉토리를 검색합니다..."
    FOUND_DIR=$(find $HOME -maxdepth 4 -type d -name "lv_cfd_anatomical" 2>/dev/null | head -1)
    if [ -z "$FOUND_DIR" ]; then
        echo "[!] 자동 검색 실패. 수동 입력:"
        read -p "    WSL 내 시뮬레이션 경로: " WSL_CFD_DIR
    else
        WSL_CFD_DIR="$FOUND_DIR"
        echo "    발견: $WSL_CFD_DIR"
    fi
fi

echo ""
echo "[1/4] 시뮬레이션 데이터 현황..."

# 시간 디렉토리
TIME_DIRS=$(find "$WSL_CFD_DIR" -maxdepth 1 -type d -regex '.*/[0-9].*' 2>/dev/null | sort -V)
N_TIME=$(echo "$TIME_DIRS" | grep -c . 2>/dev/null || echo 0)
echo "  시간 디렉토리: ${N_TIME}개"
if [ "$N_TIME" -gt 0 ]; then
    echo "  범위: t=$(echo "$TIME_DIRS" | head -1 | xargs basename)s ~ t=$(echo "$TIME_DIRS" | tail -1 | xargs basename)s"
fi

# postProcessing
if [ -d "$WSL_CFD_DIR/postProcessing" ]; then
    echo "  postProcessing: $(du -sh "$WSL_CFD_DIR/postProcessing" 2>/dev/null | cut -f1)"
else
    echo "  postProcessing: 없음"
fi

TOTAL_SIZE=$(du -sh "$WSL_CFD_DIR" 2>/dev/null | cut -f1)
echo "  전체: ${TOTAL_SIZE}"
echo ""

echo "[2/4] 동기화 대상 선택"
echo "  (a) 전체 — 모든 시간 디렉토리 + postProcessing + log + mesh"
echo "  (b) 결과만 — postProcessing + log + polyMesh (용량 절약, 권장)"
echo "  (c) 최종만 — 마지막 3 timestep + postProcessing"
echo ""
read -p "  선택 [a/b/c] (기본: b): " SYNC_MODE
SYNC_MODE=${SYNC_MODE:-b}

echo ""
echo "[3/4] 동기화 실행..."
mkdir -p "${REPO_CFD}/postProcessing"

case $SYNC_MODE in
    a)
        echo "  전체 동기화 (${TOTAL_SIZE})..."
        read -p "  계속? [y/N]: " CONFIRM
        [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ] && echo "취소" && exit 0
        rsync -av --progress \
            --exclude='processor*' --exclude='dynamicCode' --exclude='*.foam' \
            "$WSL_CFD_DIR/" "${REPO_CFD}/"
        ;;
    b)
        echo "  결과만 동기화..."
        [ -d "$WSL_CFD_DIR/postProcessing" ] && cp -rv "$WSL_CFD_DIR/postProcessing/"* "${REPO_CFD}/postProcessing/" 2>/dev/null
        cp -v "$WSL_CFD_DIR"/log.* "${REPO_CFD}/" 2>/dev/null || true
        if [ -d "$WSL_CFD_DIR/constant/polyMesh" ]; then
            mkdir -p "${REPO_CFD}/constant/polyMesh"
            cp -rv "$WSL_CFD_DIR/constant/polyMesh/"* "${REPO_CFD}/constant/polyMesh/" 2>/dev/null
        fi
        ;;
    c)
        echo "  최종 timestep 동기화..."
        LAST_3=$(echo "$TIME_DIRS" | tail -3)
        for TD in $LAST_3; do
            TNAME=$(basename "$TD")
            mkdir -p "${REPO_CFD}/${TNAME}"
            cp -rv "$TD/"* "${REPO_CFD}/${TNAME}/" 2>/dev/null
        done
        [ -d "$WSL_CFD_DIR/postProcessing" ] && cp -rv "$WSL_CFD_DIR/postProcessing/"* "${REPO_CFD}/postProcessing/" 2>/dev/null
        cp -v "$WSL_CFD_DIR"/log.* "${REPO_CFD}/" 2>/dev/null || true
        ;;
esac

echo ""
echo "[4/4] 검증"
echo "  동기화된 파일: $(find "${REPO_CFD}" -type f 2>/dev/null | wc -l)개"
echo "  동기화된 크기: $(du -sh "${REPO_CFD}" 2>/dev/null | cut -f1)"
echo ""
echo "============================================================"
echo "  완료. 다음 단계:"
echo "  cd \"${REPO_CFD}\" && python3 postprocess_analysis.py"
echo "============================================================"

# ============================================================
# [추가] 저장소 쪽 파일 무결성 체크
# ============================================================
echo ""
echo "============================================================"
echo " 저장소 파일 무결성 체크"
echo "============================================================"

# 이번 세션에서 생성된 핵심 파일 확인
echo ""
echo "[A] STL 파일 (triSurface/) 확인:"
TRISURFACE="${REPO_CFD}/constant/triSurface"
for stl in lv_surface mitral_valve aortic_valve aortic_root \
           laa_stacom rv_stacom coronary_stacom pv_stacom pa_stacom ra_stacom \
           anterolateral_pm posteromedial_pm \
           chordae_al chordae_pm chordae_combined; do
    f="${TRISURFACE}/${stl}.stl"
    if [ -f "$f" ]; then
        sz=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null)
        sz_mb=$(echo "scale=1; $sz/1000000" | bc 2>/dev/null || echo "${sz}B")
        echo "  OK ${sz_mb}MB  ${stl}.stl"
    else
        echo "  !! MISSING   ${stl}.stl"
    fi
done

echo ""
echo "[B] 스크립트 & 데이터 파일 확인:"
for f in generate_chordae.py windkessel_phpinn_bridge.py \
         assemble_cardiac_geometry.py postprocess_analysis.py \
         windkessel_phpinn_results.json cardiac_assembly_summary.json \
         CARDIAC_DIGITAL_TWIN_STATUS.md; do
    fp="${REPO_BASE}/${f}"
    if [ -f "$fp" ]; then
        sz=$(stat -c%s "$fp" 2>/dev/null || stat -f%z "$fp" 2>/dev/null)
        echo "  OK ${sz}B  ${f}"
    else
        echo "  !! MISSING   ${f}"
    fi
done

echo ""
echo "[C] snappyHexMeshDict 확인:"
SHM="${REPO_CFD}/system/snappyHexMeshDict"
if [ -f "$SHM" ]; then
    echo "  OK  system/snappyHexMeshDict"
else
    echo "  !! MISSING  system/snappyHexMeshDict"
fi

echo ""
echo "============================================================"
echo " WSL 쪽 남은 핵심 데이터:"
echo "   - 시간 디렉토리 (0/, 0.2/, 0.4/ ... 2.4/)"
echo "   - postProcessing/ (flowRate, probes)"
echo "   - log.pimpleFoam"
echo ""
echo " 위 스크립트의 모드 (b)를 실행하면 이 데이터가 저장소로 복사됩니다."
echo "============================================================"
