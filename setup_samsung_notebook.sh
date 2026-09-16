#!/bin/bash
# ============================================================
# Cardiac Digital Twin — Samsung Notebook 7 Force 설치 스크립트
# i7-8565U / GTX 1650 4GB / 40GB RAM
# ============================================================
set -e

# Repository root (the folder holding this script) and the data root outside it.
# Override with CARDIAC_REPO / CARDIAC_DATA (HANDOVER.md section 3).
REPO="${CARDIAC_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
DATA="${CARDIAC_DATA:-/mnt/d/data}"

echo "============================================================"
echo " Samsung Notebook 7 Force — Cardiac Digital Twin Setup"
echo "============================================================"

# 1. WSL2 확인 (OpenFOAM용)
echo -e "\n[1/7] WSL2 상태 확인..."
if command -v wsl.exe &>/dev/null; then
    echo "  ✓ WSL 설치됨"
else
    echo "  ✗ WSL 필요: 관리자 PowerShell에서 'wsl --install -d Ubuntu-22.04'"
    echo "  설치 후 재시작 필요"
fi

# 2. Python + CUDA 환경
echo -e "\n[2/7] Python 환경 설정..."
pip install --upgrade pip
pip install numpy scipy nibabel scikit-image matplotlib

# 3. TotalSegmentator (RV 추출 핵심)
echo -e "\n[3/7] TotalSegmentator 설치 (GPU 활용)..."
pip install TotalSegmentator
echo "  테스트: TotalSegmentator -i test.nii.gz -o output/ --task heartchambers_highres --device gpu"

# 4. PyTorch + CUDA (pH-PINN용)
echo -e "\n[4/7] PyTorch + CUDA 설치..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
python3 -c "import torch; print(f'PyTorch {torch.__version__}, CUDA: {torch.cuda.is_available()}, GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"

# 5. SimVascular
echo -e "\n[5/7] SimVascular 다운로드 안내..."
echo "  URL: https://simtk.org/frs/?group_id=188"
echo "  Windows installer 다운로드 → 설치"
echo "  또는 WSL에서: conda install -c simvascular simvascular"

# 6. vmtk (coronary centerline)
echo -e "\n[6/7] vmtk 설치..."
pip install vmtk 2>/dev/null || echo "  vmtk pip 실패 → conda install -c vmtk vmtk"

# 7. OpenFOAM (WSL 내부)
echo -e "\n[7/7] OpenFOAM 10 (WSL Ubuntu)..."
echo "  WSL Ubuntu에서 실행:"
echo "    curl -s https://dl.openfoam.com/add-debian-repo.sh | sudo bash"
echo "    sudo apt install openfoam2406"
echo "    echo 'source /usr/lib/openfoam/openfoam2406/etc/bashrc' >> ~/.bashrc"

echo -e "\n============================================================"
echo " 데이터 다운로드 안내"
echo "============================================================"

echo -e "\n--- [A] TotalSegmentator 실행 (RV 추출) ---"
echo "  cd $DATA/MM-WHS/ct_train"
echo "  TotalSegmentator -i ct_train_1009_image.nii.gz -o \"$REPO/totalseg_output/\" --task heartchambers_highres --device gpu"

echo -e "\n--- [B] ImageCAS + Public Cardiac CT Dataset ---"
echo "  1. Kaggle 계정 로그인: https://www.kaggle.com/"
echo "  2. ImageCAS: https://www.kaggle.com/datasets/xiaoweixumedicalai/imagecas"
echo "     → 'Download' 클릭 (약 200GB)"
echo "  3. Public Cardiac CT (LAA+Coronary+PV):"
echo "     git clone https://github.com/Bjonze/Public-Cardiac-CT-Dataset"

echo -e "\n--- [C] MVAA 2026 Challenge (Mitral Valve) ---"
echo "  1. https://www.codabench.org/competitions/15662/"
echo "  2. 계정 생성 → 'Participate' → training data 다운로드"

echo -e "\n--- [D] SimVascular Vascular Model Repository ---"
echo "  https://www.vascularmodel.com/"
echo "  → Coronary 모델 다운로드 (CFD-ready)"

echo -e "\n--- [E] 4D Flow MRI (CFD validation) ---"
echo "  https://www.cardiacatlas.org/challenges/"
echo "  → STACOM challenge datasets"

echo -e "\n--- [F] PhysioNet (이미 활용 중) ---"
echo "  https://physionet.org/content/eicu-crd/2.0/"
echo "  https://physionet.org/content/mimiciv/3.1/"

echo -e "\n============================================================"
echo "  설치 완료 후 Phase 0 실행:"
echo "  1. python3 generate_valves.py"
echo "  2. TotalSegmentator (위 명령어)"
echo "  3. python3 cardiac_structure_inventory.py"
echo "============================================================"
