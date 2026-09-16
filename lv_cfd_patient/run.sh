#!/bin/bash
# Patient-specific LV CFD — Single-block mesh with patch splitting
# Run inside WSL with OpenFOAM 2312

set -e

CASE_DIR=$(pwd)
echo "=== Patient LV CFD Pipeline ==="
echo "Case: $CASE_DIR"
echo ""

# Step 1: blockMesh
echo "[1/5] Running blockMesh..."
blockMesh > log.blockMesh 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: blockMesh failed"
    tail -20 log.blockMesh
    exit 1
fi
echo "  blockMesh OK"

# Step 2: topoSet — create face sets for inlet/outlet
echo "[2/5] Running topoSet (inlet/outlet face sets)..."
topoSet > log.topoSet 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: topoSet failed"
    tail -20 log.topoSet
    exit 1
fi
echo "  topoSet OK"

# Step 3: createPatch — split top patch into inlet/outlet
echo "[3/5] Running createPatch (split patches)..."
createPatch -overwrite > log.createPatch 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: createPatch failed"
    tail -20 log.createPatch
    exit 1
fi
echo "  createPatch OK"

# Step 4: checkMesh
echo "[4/5] Running checkMesh..."
checkMesh > log.checkMesh 2>&1
MESH_OK=$(grep -c "Mesh OK" log.checkMesh || true)
if [ "$MESH_OK" -eq 0 ]; then
    echo "  WARNING: checkMesh reported issues"
    grep -A2 "Failed" log.checkMesh || true
else
    echo "  Mesh OK"
fi
NCELLS=$(grep "cells:" log.checkMesh | head -1)
echo "  $NCELLS"

# Step 5: pimpleFoam
echo "[5/5] Running pimpleFoam (this will take ~5-10 min)..."
echo "  Start: $(date)"
pimpleFoam > log.pimpleFoam 2>&1 &
PID=$!

# Progress monitor
while kill -0 $PID 2>/dev/null; do
    if [ -f log.pimpleFoam ]; then
        LATEST=$(grep "^Time = " log.pimpleFoam | tail -1 || echo "starting...")
        echo "  $LATEST"
    fi
    sleep 30
done

wait $PID
STATUS=$?
if [ $STATUS -ne 0 ]; then
    echo "ERROR: pimpleFoam failed (exit $STATUS)"
    tail -30 log.pimpleFoam
    exit 1
fi

echo ""
echo "=== SIMULATION COMPLETE ==="
echo "End: $(date)"
echo ""
echo "Results in: $CASE_DIR"
echo "Post-process: python3 postprocess.py"
