#!/bin/bash
# =====================================================
# Post-processing: Patient-specific LV CFD (Case 1009)
# pimpleFoam 완료 후 실행
# =====================================================
set -e
echo "=== Post-Processing Pipeline ==="

# 1) Wall Shear Stress
echo "[1/4] Computing Wall Shear Stress..."
pimpleFoam -postProcess -func wallShearStress -latestTime 2>&1 | tail -5
echo "  → wallShearStress field written"

# 2) Vorticity
echo "[2/4] Computing vorticity..."
pimpleFoam -postProcess -func vorticity -latestTime 2>&1 | tail -5
echo "  → vorticity field written"

# 3) Q-criterion (vortex identification)
echo "[3/4] Computing Q-criterion..."
pimpleFoam -postProcess -func Q -latestTime 2>&1 | tail -5
echo "  → Q field written"

# 4) Pressure/velocity magnitude for last cardiac cycle
echo "[4/4] Computing field magnitudes..."
pimpleFoam -postProcess -func "mag(U)" -latestTime 2>&1 | tail -5 || true
echo "  → Done"

echo ""
echo "=== Extracting probe & flow rate data ==="

# Probe data
if [ -d postProcessing/probes ]; then
    echo "Probe data found:"
    ls postProcessing/probes/0/
fi

# Flow rates
if [ -d postProcessing/flowRateMitral ]; then
    echo "Mitral flow rate data found:"
    wc -l postProcessing/flowRateMitral/0/surfaceFieldValue.dat
fi
if [ -d postProcessing/flowRateAortic ]; then
    echo "Aortic flow rate data found:"
    wc -l postProcessing/flowRateAortic/0/surfaceFieldValue.dat
fi

echo ""
echo "=== Time directories ==="
ls -d [0-9]* 2>/dev/null | wc -l
echo "time directories found"
echo "Last 5 time steps:"
ls -d [0-9]* 2>/dev/null | sort -g | tail -5

echo ""
echo "=== Post-processing complete ==="
echo "Next steps:"
echo "  1) Run: python3 postprocess_analysis.py"
echo "  2) Open ParaView for 3D visualization"
echo "  3) Copy results back to the repository for analysis"
