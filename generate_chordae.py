#!/usr/bin/env python3
"""
Chordae Tendineae Parametric Generator
========================================
Literature-based parametric generation of chordae tendineae connecting
papillary muscles (PM) to mitral valve (MV) leaflets.

References:
- Lam et al. (1970) Circulation — chordae anatomy classification
- Kunzelman et al. (1993) J Heart Valve Dis — chordae dimensions
- Prot et al. (2009) Ann Biomed Eng — chordae mechanics
- He et al. (2000) J Heart Valve Dis — insertion patterns

Chordae types:
  1. Marginal (primary): PM tip → leaflet free edge, d=0.4-0.7mm
  2. Strut (secondary): PM tip → leaflet body (rough zone), d=0.8-1.2mm
  3. Basal (tertiary): PM base/LV wall → leaflet base, d=0.3-0.5mm

Output: ASCII STL with tubular chordae
"""

import numpy as np
import os

# ============================================================
# PARAMETERS (Literature-based)
# ============================================================

# From Kunzelman 1993, Lam 1970
CHORDAE_CONFIG = {
    'marginal': {
        'count_per_pm': 6,         # 4-8 per PM (Lam 1970)
        'diameter_mm': 0.55,       # 0.4-0.7mm
        'n_segments': 8,           # tube resolution along length
        'n_circle': 6,             # tube cross-section resolution
        'spread_angle_deg': 40,    # fan angle at leaflet edge
        'length_factor': 1.0,      # direct PM-tip to leaflet-edge
    },
    'strut': {
        'count_per_pm': 2,         # 1-3 per PM
        'diameter_mm': 1.0,        # 0.8-1.2mm (thickest)
        'n_segments': 8,
        'n_circle': 8,
        'spread_angle_deg': 20,
        'length_factor': 0.7,      # attach to leaflet body, not edge
    },
    'basal': {
        'count_per_pm': 3,         # 2-4 per PM
        'diameter_mm': 0.4,        # 0.3-0.5mm (thinnest)
        'n_segments': 6,
        'n_circle': 5,
        'spread_angle_deg': 30,
        'length_factor': 0.4,      # attach near leaflet base
    },
}

# Coordinate system: model is in meters (from MM-WHS)
# PM centroids from K-means:
#   AL-PM centroid: (0.0706, 0.1478, 0.1164) — more posterior, higher Z
#   PM-PM centroid: (0.0743, 0.1409, 0.0802) — more anterior, lower Z

# MV parameters from generate_valves.py
MV_CENTER = np.array([0.0688, 0.1423, 0.1095])  # approximate MV annulus center
MV_RADIUS = 0.015  # ~15mm radius
MV_NORMAL = np.array([0.0, 0.2, -1.0])  # MV opens toward LV apex
MV_NORMAL = MV_NORMAL / np.linalg.norm(MV_NORMAL)

# PM tip positions (top of each PM, closest to MV)
AL_PM_TIP = np.array([0.0706, 0.1478, 0.1164])  
PM_PM_TIP = np.array([0.0743, 0.1409, 0.0802])

# Adjust tips slightly upward toward MV
# (real tips are ~5-10mm below MV plane)
TIP_OFFSET = MV_NORMAL * 0.005  # 5mm toward MV
AL_PM_TIP_ADJ = AL_PM_TIP + TIP_OFFSET
PM_PM_TIP_ADJ = PM_PM_TIP + TIP_OFFSET


def generate_leaflet_points(mv_center, mv_radius, mv_normal, n_points, 
                            start_angle, end_angle, length_factor):
    """Generate attachment points on the MV leaflet surface"""
    # Create local coordinate frame on MV plane
    up = np.array([0, 0, 1])
    if abs(np.dot(mv_normal, up)) > 0.9:
        up = np.array([1, 0, 0])
    
    e1 = np.cross(mv_normal, up)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(mv_normal, e1)
    e2 /= np.linalg.norm(e2)
    
    points = []
    angles = np.linspace(start_angle, end_angle, n_points)
    
    for angle in angles:
        # Point on leaflet at given radius fraction
        r = mv_radius * length_factor
        p = mv_center + r * (np.cos(angle) * e1 + np.sin(angle) * e2)
        # Offset slightly below MV plane (toward LV)
        p -= mv_normal * 0.003 * length_factor  # leaflet droop
        points.append(p)
    
    return np.array(points)


def create_tube(p0, p1, radius, n_segments=8, n_circle=6):
    """Create a tube (cylinder) between two points, returns vertices and faces"""
    direction = p1 - p0
    length = np.linalg.norm(direction)
    if length < 1e-10:
        return np.array([]), np.array([])
    
    d = direction / length
    
    # Find perpendicular vectors
    up = np.array([0, 0, 1])
    if abs(np.dot(d, up)) > 0.9:
        up = np.array([1, 0, 0])
    
    e1 = np.cross(d, up)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(d, e1)
    
    # Generate vertices along the tube
    vertices = []
    for i in range(n_segments + 1):
        t = i / n_segments
        center = p0 + t * direction
        
        # Add slight catenary sag (natural chordae shape)
        sag = 4 * t * (1 - t) * 0.002  # max 2mm sag at midpoint
        center -= MV_NORMAL * sag
        
        # Taper: thinner at attachment points
        taper = 1.0 - 0.3 * (2*t - 1)**2  # thinnest at ends
        r = radius * taper
        
        for j in range(n_circle):
            angle = 2 * np.pi * j / n_circle
            v = center + r * (np.cos(angle) * e1 + np.sin(angle) * e2)
            vertices.append(v)
    
    vertices = np.array(vertices)
    
    # Generate faces (quads → 2 triangles each)
    faces = []
    for i in range(n_segments):
        for j in range(n_circle):
            v0 = i * n_circle + j
            v1 = i * n_circle + (j + 1) % n_circle
            v2 = (i + 1) * n_circle + j
            v3 = (i + 1) * n_circle + (j + 1) % n_circle
            faces.append([v0, v2, v1])
            faces.append([v1, v2, v3])
    
    return vertices, np.array(faces)


def generate_chordae_for_pm(pm_tip, mv_center, mv_radius, mv_normal, 
                            pm_name, start_angle, end_angle):
    """Generate all chordae types for one papillary muscle"""
    all_vertices = []
    all_faces = []
    total_tris = 0
    chordae_count = 0
    
    for chordae_type, config in CHORDAE_CONFIG.items():
        n = config['count_per_pm']
        radius = config['diameter_mm'] / 2000.0  # mm to meters
        n_seg = config['n_segments']
        n_circ = config['n_circle']
        lf = config['length_factor']
        spread = np.radians(config['spread_angle_deg'])
        
        # Generate leaflet attachment points
        a_start = (start_angle + end_angle) / 2 - spread / 2
        a_end = (start_angle + end_angle) / 2 + spread / 2
        leaflet_pts = generate_leaflet_points(
            mv_center, mv_radius, mv_normal, n, a_start, a_end, lf
        )
        
        for i, lp in enumerate(leaflet_pts):
            # Slight random variation in PM tip origin
            rng = np.random.RandomState(hash(f"{pm_name}_{chordae_type}_{i}") % 2**31)
            tip_var = pm_tip + rng.uniform(-0.002, 0.002, 3)
            
            verts, faces = create_tube(tip_var, lp, radius, n_seg, n_circ)
            if len(verts) == 0:
                continue
            
            # Offset face indices
            faces_offset = faces + len(all_vertices)
            all_vertices.extend(verts)
            all_faces.extend(faces_offset)
            chordae_count += 1
            total_tris += len(faces)
    
    return np.array(all_vertices), np.array(all_faces), chordae_count, total_tris


def write_stl(filepath, name, vertices, faces):
    """Write ASCII STL"""
    with open(filepath, 'w') as f:
        f.write(f"solid {name}\n")
        for face in faces:
            v0, v1, v2 = vertices[face]
            e1 = v1 - v0
            e2 = v2 - v0
            n = np.cross(e1, e2)
            nl = np.linalg.norm(n)
            if nl > 0:
                n /= nl
            f.write(f"  facet normal {n[0]} {n[1]} {n[2]}\n")
            f.write(f"    outer loop\n")
            f.write(f"      vertex {v0[0]} {v0[1]} {v0[2]}\n")
            f.write(f"      vertex {v1[0]} {v1[1]} {v1[2]}\n")
            f.write(f"      vertex {v2[0]} {v2[1]} {v2[2]}\n")
            f.write(f"    endloop\n")
            f.write(f"  endfacet\n")
        f.write(f"endsolid {name}\n")
    sz = os.path.getsize(filepath) / 1e6
    print(f"  Saved: {filepath.split('/')[-1]} — {len(faces):,} tri, {sz:.1f} MB")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    output_dir = os.path.dirname(os.path.abspath(__file__))
    trisurface_dir = os.path.join(output_dir, "lv_cfd_anatomical", "constant", "triSurface")
    
    # If run from project root, use triSurface path
    if not os.path.exists(trisurface_dir):
        trisurface_dir = output_dir
    
    print("=" * 60)
    print(" Chordae Tendineae Parametric Generator")
    print("=" * 60)
    print(f"\nMV center: {MV_CENTER}")
    print(f"MV radius: {MV_RADIUS*1000:.1f} mm")
    print(f"AL-PM tip: {AL_PM_TIP_ADJ}")
    print(f"PM-PM tip: {PM_PM_TIP_ADJ}")
    
    # AL-PM chordae: anterior leaflet (roughly 0 to pi)
    print("\n--- Anterolateral PM chordae ---")
    al_v, al_f, al_n, al_t = generate_chordae_for_pm(
        AL_PM_TIP_ADJ, MV_CENTER, MV_RADIUS, MV_NORMAL,
        "AL", start_angle=0, end_angle=np.pi*0.7
    )
    write_stl(os.path.join(trisurface_dir, "chordae_al.stl"), "chordae_al", al_v, al_f)
    print(f"  {al_n} chordae, {al_t:,} triangles")
    
    # PM-PM chordae: posterior leaflet (roughly pi to 2*pi)
    print("\n--- Posteromedial PM chordae ---")
    pm_v, pm_f, pm_n, pm_t = generate_chordae_for_pm(
        PM_PM_TIP_ADJ, MV_CENTER, MV_RADIUS, MV_NORMAL,
        "PM", start_angle=np.pi*0.7, end_angle=np.pi*1.7
    )
    write_stl(os.path.join(trisurface_dir, "chordae_pm.stl"), "chordae_pm", pm_v, pm_f)
    print(f"  {pm_n} chordae, {pm_t:,} triangles")
    
    # Combined
    print("\n--- Combined chordae ---")
    all_v = np.concatenate([al_v, pm_v])
    all_f = np.concatenate([al_f, pm_f + len(al_v)])
    write_stl(os.path.join(trisurface_dir, "chordae_combined.stl"), "chordae_combined", all_v, all_f)
    
    print(f"\nTotal: {al_n + pm_n} chordae, {al_t + pm_t:,} triangles")
    print(f"\nChordae type breakdown:")
    for ct, cfg in CHORDAE_CONFIG.items():
        total = cfg['count_per_pm'] * 2
        print(f"  {ct:10s}: {total} chordae, d={cfg['diameter_mm']}mm")
    
    print("\nDone!")
