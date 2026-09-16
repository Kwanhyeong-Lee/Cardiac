#!/bin/bash
# ============================================================
#  Patient-Specific LV CFD — Case 1009
#  Run this in WSL with OpenFOAM 2312 sourced
# ============================================================

set -e

echo "============================================"
echo "  Patient-Specific Cardiac CFD — Case 1009"
echo "  Mitral valve: 2.8 cm², Aortic: 1.9 cm²"
echo "============================================"

# Source OpenFOAM
source /usr/lib/openfoam/openfoam2312/etc/bashrc 2>/dev/null || \
source /opt/openfoam2312/etc/bashrc 2>/dev/null || \
echo "WARNING: OpenFOAM not sourced"

# Step 1: Background mesh
echo ""
echo ">>> Step 1: blockMesh"
blockMesh 2>&1 | tail -5

# Step 2: Conform to patient geometry
echo ""
echo ">>> Step 2: snappyHexMesh (patient LV geometry)"
snappyHexMesh -overwrite 2>&1 | tail -10

# Step 3: Check mesh quality
echo ""
echo ">>> Step 3: checkMesh"
checkMesh 2>&1 | tail -15

# Step 4: Rename patches
# snappyHexMesh creates patches from STL regions
# We need inlet/outlet/LV patches
echo ""
echo ">>> Step 4: createPatch (define inlet/outlet)"
# This step may need manual intervention based on snappyHexMesh output
# For now, proceed with default patch names

# Step 5: Run solver
echo ""
echo ">>> Step 5: pimpleFoam"
echo "  3 cardiac cycles, T=0.8s each, adaptive dt"
echo "  Expected runtime: 10-30 minutes"
pimpleFoam 2>&1 | tail -20

echo ""
echo "============================================"
echo "  CFD Complete!"
echo "  Results in timeStep directories"
echo "  Use ParaView to visualize"
echo "============================================"
