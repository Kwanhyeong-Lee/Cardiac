#!/usr/bin/env python3
"""
Multi-Structure Cardiac Geometry Assembly Pipeline
====================================================
Assembles all STL files into integrated cardiac geometry.
Performs interference checks and outputs snappyHexMesh-ready configuration.

STL Inventory:
  [Original] lv_surface.stl, mitral_valve.stl, aortic_valve.stl, aortic_root.stl
  [STACOM2025] laa_stacom.stl, rv_stacom.stl, coronary_stacom.stl, 
               pv_stacom.stl, pa_stacom.stl, ra_stacom.stl
  [Split PM] anterolateral_pm.stl, posteromedial_pm.stl
  [Generated] chordae_al.stl, chordae_pm.stl, chordae_combined.stl
"""

import numpy as np
import os
import struct
import json
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


@dataclass
class STLMesh:
    """Lightweight STL representation"""
    name: str
    filepath: str
    vertices: np.ndarray  # (N, 3, 3) triangle vertices
    normals: np.ndarray   # (N, 3) face normals
    n_triangles: int = 0
    file_size_mb: float = 0.0
    bbox_min: np.ndarray = field(default_factory=lambda: np.zeros(3))
    bbox_max: np.ndarray = field(default_factory=lambda: np.zeros(3))
    centroid: np.ndarray = field(default_factory=lambda: np.zeros(3))
    source: str = ""  # data source annotation
    
    def compute_stats(self):
        if len(self.vertices) > 0:
            all_verts = self.vertices.reshape(-1, 3)
            self.bbox_min = all_verts.min(axis=0)
            self.bbox_max = all_verts.max(axis=0)
            self.centroid = all_verts.mean(axis=0)
            self.n_triangles = len(self.vertices)


def load_stl(filepath: str, name: str = "", source: str = "") -> Optional[STLMesh]:
    """Load STL file (auto-detect ASCII/binary)"""
    if not os.path.exists(filepath):
        return None
    
    file_size = os.path.getsize(filepath) / 1e6
    
    with open(filepath, 'rb') as f:
        header = f.read(80)
    
    is_ascii = header.startswith(b'solid') and b'\x00' not in header
    
    if is_ascii:
        return load_ascii_stl(filepath, name or os.path.basename(filepath), source, file_size)
    else:
        return load_binary_stl(filepath, name or os.path.basename(filepath), source, file_size)


def load_ascii_stl(filepath, name, source, file_size):
    vertices = []
    normals = []
    current_verts = []
    current_normal = None
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('facet normal'):
                parts = line.split()
                current_normal = [float(parts[2]), float(parts[3]), float(parts[4])]
            elif line.startswith('vertex'):
                parts = line.split()
                current_verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif line.startswith('endfacet'):
                if len(current_verts) == 3 and current_normal:
                    vertices.append(current_verts)
                    normals.append(current_normal)
                current_verts = []
    
    mesh = STLMesh(
        name=name, filepath=filepath,
        vertices=np.array(vertices) if vertices else np.empty((0,3,3)),
        normals=np.array(normals) if normals else np.empty((0,3)),
        file_size_mb=file_size, source=source
    )
    mesh.compute_stats()
    return mesh


def load_binary_stl(filepath, name, source, file_size):
    with open(filepath, 'rb') as f:
        f.read(80)  # header
        n_tri = struct.unpack('<I', f.read(4))[0]
        
        vertices = []
        normals = []
        for _ in range(n_tri):
            n = struct.unpack('<fff', f.read(12))
            v0 = struct.unpack('<fff', f.read(12))
            v1 = struct.unpack('<fff', f.read(12))
            v2 = struct.unpack('<fff', f.read(12))
            f.read(2)  # attribute
            normals.append(n)
            vertices.append([v0, v1, v2])
    
    mesh = STLMesh(
        name=name, filepath=filepath,
        vertices=np.array(vertices),
        normals=np.array(normals),
        file_size_mb=file_size, source=source
    )
    mesh.compute_stats()
    return mesh


def check_bbox_overlap(m1: STLMesh, m2: STLMesh) -> bool:
    """Check if bounding boxes overlap (potential interference)"""
    return not (
        np.any(m1.bbox_max < m2.bbox_min) or
        np.any(m2.bbox_max < m1.bbox_min)
    )


def compute_distance(m1: STLMesh, m2: STLMesh) -> float:
    """Approximate min distance between meshes using centroids"""
    return float(np.linalg.norm(m1.centroid - m2.centroid))


def generate_snappyhexmesh_dict(meshes: List[STLMesh], 
                                  output_path: str,
                                  refinement_levels: Dict[str, int] = None):
    """
    Generate snappyHexMeshDict for OpenFOAM
    
    Default refinement levels based on structure importance:
    - Valves: level 4 (highest — thin structures)
    - Chordae: level 4 (thin)
    - LV surface: level 3
    - Papillary muscles: level 3
    - Great vessels: level 2
    - Chambers: level 2
    """
    default_levels = {
        'mitral_valve': 4, 'aortic_valve': 4,
        'chordae_al': 4, 'chordae_pm': 4, 'chordae_combined': 4,
        'lv_surface': 3,
        'anterolateral_pm': 3, 'posteromedial_pm': 3, 'papillary_muscles': 3,
        'aortic_root': 2,
        'laa_stacom': 2, 'rv_stacom': 2, 'coronary_stacom': 3,
        'pv_stacom': 2, 'pa_stacom': 2, 'ra_stacom': 2,
    }
    
    if refinement_levels:
        default_levels.update(refinement_levels)
    
    lines = [
        "FoamFile",
        "{",
        "    version     2.0;",
        "    format      ascii;",
        "    class       dictionary;",
        "    object      snappyHexMeshDict;",
        "}",
        "",
        "castellatedMesh true;",
        "snap            true;",
        "addLayers       true;",
        "",
        "geometry",
        "{",
    ]
    
    for mesh in meshes:
        stl_name = os.path.basename(mesh.filepath)
        base_name = stl_name.replace('.stl', '')
        level = default_levels.get(base_name, 2)
        lines.extend([
            f"    {stl_name}",
            "    {",
            "        type triSurfaceMesh;",
            f"        name {base_name};",
            "    }",
        ])
    
    lines.extend([
        "}",
        "",
        "castellatedMeshControls",
        "{",
        "    maxLocalCells       1000000;",
        "    maxGlobalCells      5000000;",
        "    minRefinementCells  10;",
        "    maxLoadUnbalance    0.1;",
        "    nCellsBetweenLevels 3;",
        "    resolveFeatureAngle 30;",
        "",
        "    features ();",
        "",
        "    refinementSurfaces",
        "    {",
    ])
    
    for mesh in meshes:
        base_name = os.path.basename(mesh.filepath).replace('.stl', '')
        level = default_levels.get(base_name, 2)
        lines.extend([
            f"        {base_name}",
            "        {",
            f"            level ({level} {level+1});",
            "        }",
        ])
    
    lines.extend([
        "    }",
        "",
        "    refinementRegions {}",
        "",
        '    locationInMesh (0.07 0.14 0.10);  // inside LV cavity',
        "}",
        "",
        "snapControls",
        "{",
        "    nSmoothPatch         3;",
        "    tolerance             2.0;",
        "    nSolveIter           100;",
        "    nRelaxIter            5;",
        "    nFeatureSnapIter     10;",
        "}",
        "",
        "addLayersControls",
        "{",
        "    relativeSizes        true;",
        "    expansionRatio       1.2;",
        "    finalLayerThickness  0.3;",
        "    minThickness         0.1;",
        "    nGrow                0;",
        "    featureAngle         60;",
        "    nRelaxIter           5;",
        "    nSmoothSurfaceNormals 1;",
        "    nSmoothNormals       3;",
        "    nSmoothThickness     10;",
        "    maxFaceThicknessRatio 0.5;",
        "    maxThicknessToMedialRatio 0.3;",
        "    minMedialAxisAngle   90;",
        "    nBufferCellsNoExtrude 0;",
        "    nLayerIter           50;",
        "",
        "    layers",
        "    {",
    ])
    
    # Add boundary layers to wall surfaces
    wall_surfaces = ['lv_surface', 'mitral_valve', 'aortic_valve', 
                     'anterolateral_pm', 'posteromedial_pm']
    for ws in wall_surfaces:
        lines.extend([
            f'        "{ws}"',
            "        {",
            "            nSurfaceLayers 3;",
            "        }",
        ])
    
    lines.extend([
        "    }",
        "}",
        "",
        "meshQualityControls",
        "{",
        "    maxNonOrtho         65;",
        "    maxBoundarySkewness 20;",
        "    maxInternalSkewness 4;",
        "    maxConcave          80;",
        "    minVol              1e-18;",
        "    minTetQuality       1e-15;",
        "    minArea             -1;",
        "    minTwist            0.02;",
        "    minDeterminant      0.001;",
        "    minFaceWeight       0.05;",
        "    minVolRatio         0.01;",
        "    minTriangleTwist    -1;",
        "    nSmoothScale        4;",
        "    errorReduction      0.75;",
        "}",
    ])
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
    
    return output_path


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    trisurface = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "lv_cfd_anatomical", "constant", "triSurface")
    
    # Define all STL files with source annotations
    stl_registry = {
        # Original (from MM-WHS 1009 + parametric generation)
        'lv_surface':       ('lv_surface.stl', 'MM-WHS Case 1009, CT segmentation'),
        'mitral_valve':     ('mitral_valve.stl', 'Parametric (generate_valves.py), Kunzelman 1993'),
        'aortic_valve':     ('aortic_valve.stl', 'Parametric (generate_valves.py), Thubrikar 1990'),
        'aortic_root':      ('aortic_root.stl', 'Parametric (generate_valves.py)'),
        # STACOM2025 extractions (this session)
        'laa_stacom':       ('laa_stacom.stl', 'STACOM2025 Case 1, label 8 (LAA)'),
        'rv_stacom':        ('rv_stacom.stl', 'STACOM2025 Case 1, label 3 (RV blood pool)'),
        'coronary_stacom':  ('coronary_stacom.stl', 'STACOM2025 Case 1, label 9 (Coronary)'),
        'pv_stacom':        ('pv_stacom.stl', 'STACOM2025 Case 1, label 10 (Pulmonary Veins)'),
        'pa_stacom':        ('pa_stacom.stl', 'STACOM2025 Case 1, label 7 (Pulmonary Artery)'),
        'ra_stacom':        ('ra_stacom.stl', 'STACOM2025 Case 1, label 5 (Right Atrium)'),
        # Split papillary muscles
        'anterolateral_pm': ('anterolateral_pm.stl', 'K-means split from papillary_muscles.stl'),
        'posteromedial_pm': ('posteromedial_pm.stl', 'K-means split from papillary_muscles.stl'),
        # Parametric chordae
        'chordae_combined': ('chordae_combined.stl', 'Parametric (generate_chordae.py), Lam 1970'),
    }
    
    print("=" * 70)
    print(" Cardiac Geometry Assembly Pipeline")
    print("=" * 70)
    
    # Load all meshes
    meshes = []
    print(f"\n--- Loading STL Files from {trisurface} ---\n")
    
    for name, (filename, source) in stl_registry.items():
        filepath = os.path.join(trisurface, filename)
        mesh = load_stl(filepath, name, source)
        if mesh:
            meshes.append(mesh)
            bbox_size = (mesh.bbox_max - mesh.bbox_min) * 1000  # to mm
            print(f"  OK {name:20s}: {mesh.n_triangles:>8,} tri, "
                  f"{mesh.file_size_mb:>5.1f} MB, "
                  f"bbox {bbox_size[0]:.0f}x{bbox_size[1]:.0f}x{bbox_size[2]:.0f} mm")
        else:
            print(f"  -- {name:20s}: NOT FOUND")
    
    print(f"\nTotal: {len(meshes)} meshes, {sum(m.n_triangles for m in meshes):,} triangles")
    
    # Bounding box overlap analysis
    print(f"\n--- Bounding Box Overlap Analysis ---\n")
    overlaps = []
    for i, m1 in enumerate(meshes):
        for j, m2 in enumerate(meshes):
            if j <= i:
                continue
            if check_bbox_overlap(m1, m2):
                dist = compute_distance(m1, m2) * 1000  # mm
                overlaps.append((m1.name, m2.name, dist))
                if dist < 5:  # close proximity
                    print(f"  !! {m1.name} <-> {m2.name}: {dist:.1f} mm (CLOSE)")
                else:
                    print(f"  ~  {m1.name} <-> {m2.name}: {dist:.1f} mm")
    
    if not overlaps:
        print("  No bounding box overlaps detected")
    
    # Generate snappyHexMeshDict
    print(f"\n--- Generating snappyHexMeshDict ---")
    system_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "lv_cfd_anatomical", "system")
    os.makedirs(system_dir, exist_ok=True)
    shm_path = generate_snappyhexmesh_dict(
        meshes, os.path.join(system_dir, "snappyHexMeshDict")
    )
    print(f"  Saved: {shm_path}")
    
    # Assembly summary
    summary = {
        'total_meshes': len(meshes),
        'total_triangles': sum(m.n_triangles for m in meshes),
        'total_size_mb': sum(m.file_size_mb for m in meshes),
        'meshes': [
            {
                'name': m.name,
                'file': os.path.basename(m.filepath),
                'triangles': m.n_triangles,
                'size_mb': round(m.file_size_mb, 2),
                'source': m.source,
                'bbox_mm': {
                    'min': (m.bbox_min * 1000).tolist(),
                    'max': (m.bbox_max * 1000).tolist(),
                    'size': ((m.bbox_max - m.bbox_min) * 1000).tolist(),
                },
                'centroid_mm': (m.centroid * 1000).tolist(),
            }
            for m in meshes
        ],
        'overlaps': [
            {'mesh1': o[0], 'mesh2': o[1], 'centroid_dist_mm': round(o[2], 1)}
            for o in overlaps
        ],
    }
    
    summary_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "cardiac_assembly_summary.json")
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"  Summary: {summary_path}")
    
    print(f"\nDone!")
