#!/bin/bash
# Patient-specific anatomical LV CFD — snappyHexMesh pipeline
# Case 1009 (MM-WHS CT)

set -e

echo "=== Step 1: Background mesh ==="
blockMesh | tee log.blockMesh

echo "=== Step 2: Surface feature extraction ==="
surfaceFeatureExtract | tee log.surfaceFeatureExtract 2>/dev/null || echo "skipping feature extract"

echo "=== Step 3: snappyHexMesh ==="
snappyHexMesh -overwrite | tee log.snappyHexMesh

echo "=== Step 4: Check mesh quality ==="
checkMesh | tee log.checkMesh

echo "=== Step 5: Run CFD ==="
pimpleFoam > log.pimpleFoam 2>&1 &
PID=$!
echo "pimpleFoam started (PID=$PID)"
echo "Monitor: tail -f log.pimpleFoam"
echo "Progress: grep '^Time = ' log.pimpleFoam | tail -1"
