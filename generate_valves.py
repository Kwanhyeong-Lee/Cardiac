#!/usr/bin/env python3
"""
generate_valves.py
==================
Generate idealized mitral valve and aortic valve STL geometries
based on anatomical literature measurements.

Outputs:
  lv_cfd_anatomical/constant/triSurface/mitral_valve.stl
  lv_cfd_anatomical/constant/triSurface/aortic_valve.stl
  lv_cfd_anatomical/constant/triSurface/valve_metadata.json

Uses only numpy + standard library. STL in ASCII format.
"""

import numpy as np
import json
import os
import pathlib

# ---------------------------------------------------------------------------
# Helper: write ASCII STL
# ---------------------------------------------------------------------------

def write_ascii_stl(filepath, triangles, solid_name="valve"):
    """
    Write an ASCII STL file.
    triangles: list of (v0, v1, v2) where each v is (x, y, z) in metres.
    """
    with open(filepath, "w") as f:
        f.write(f"solid {solid_name}\n")
        for v0, v1, v2 in triangles:
            v0, v1, v2 = np.asarray(v0), np.asarray(v1), np.asarray(v2)
            normal = np.cross(v1 - v0, v2 - v0)
            norm = np.linalg.norm(normal)
            if norm > 1e-15:
                normal = normal / norm
            else:
                normal = np.array([0.0, 0.0, 0.0])
            f.write(f"  facet normal {normal[0]:.6e} {normal[1]:.6e} {normal[2]:.6e}\n")
            f.write("    outer loop\n")
            for vv in (v0, v1, v2):
                f.write(f"      vertex {vv[0]:.6e} {vv[1]:.6e} {vv[2]:.6e}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")
        f.write(f"endsolid {solid_name}\n")

# ---------------------------------------------------------------------------
# Quad-to-triangle helper
# ---------------------------------------------------------------------------

def quad_to_tris(v00, v10, v11, v01):
    """Split a quad into two triangles."""
    return [(v00, v10, v11), (v00, v11, v01)]

# ---------------------------------------------------------------------------
# Mitral Valve geometry
# ---------------------------------------------------------------------------

def generate_mitral_valve():
    """
    Generate mitral valve with 2 leaflets (anterior + posterior with 3 scallops).
    Thin shell (inner + outer surface offset by thickness).
    D-shaped saddle annulus.
    """
    # Case-specific positioning (metres)
    center = np.array([-0.0222, 0.0044, -0.1489])
    annulus_radius = 0.0225  # m

    # Anatomical dimensions (mm -> m)
    annulus_diam = 0.030
    annulus_r = annulus_diam / 2.0
    anterior_height = 0.020
    anterior_thickness = 0.001
    posterior_height = 0.015
    posterior_thickness = 0.0008
    saddle_height = 0.007

    # Scale factor to match the case geometry radius
    scale = annulus_radius / annulus_r

    # LV long axis direction (approximate: pointing from base toward apex, roughly -z)
    lv_axis = np.array([0.0, 0.0, -1.0])
    lv_axis = lv_axis / np.linalg.norm(lv_axis)

    # Annulus plane normal = LV axis
    normal = lv_axis
    # Two orthogonal directions in the annulus plane
    if abs(np.dot(normal, np.array([1, 0, 0]))) < 0.9:
        u = np.cross(normal, np.array([1, 0, 0]))
    else:
        u = np.cross(normal, np.array([0, 1, 0]))
    u = u / np.linalg.norm(u)
    v = np.cross(normal, u)
    v = v / np.linalg.norm(v)

    # Resolution
    n_circ = 80
    n_rad = 60

    triangles = []

    def annulus_point(theta):
        """
        Compute annulus point with saddle shape.
        Saddle: z-offset = saddle_height * cos(2*theta)
        D-shape: slightly flatten one side.
        """
        d_factor = 1.0 - 0.15 * np.exp(-((theta - np.pi / 2) ** 2) / (0.5 ** 2))
        r = annulus_r * scale * d_factor
        z_saddle = saddle_height * scale * np.cos(2.0 * theta)
        x = r * np.cos(theta)
        y = r * np.sin(theta)
        return center + x * u + y * v + z_saddle * normal

    def leaflet_surface(theta_start, theta_end, height, thickness, n_theta, n_h, offset_sign=1.0):
        """
        Generate a leaflet surface as a thin shell.
        offset_sign: +1 for outer surface, -1 for inner surface.
        """
        tris = []
        thetas = np.linspace(theta_start, theta_end, n_theta)
        fracs = np.linspace(0, 1, n_h)

        pts = np.zeros((n_theta, n_h, 3))

        for i, th in enumerate(thetas):
            p_ann = annulus_point(th)
            radial = center - p_ann
            radial_plane = radial - np.dot(radial, normal) * normal
            radial_norm = np.linalg.norm(radial_plane)
            if radial_norm > 1e-10:
                radial_dir = radial_plane / radial_norm
            else:
                radial_dir = u

            for j, frac in enumerate(fracs):
                droop = height * scale * frac ** 1.3
                belly = 0.3 * height * scale * np.sin(np.pi * frac)
                p = p_ann + belly * radial_dir + droop * normal

                shell_normal_dir = np.cross(
                    radial_dir,
                    np.array([-np.sin(th), np.cos(th), 0.0])
                )
                sn_norm = np.linalg.norm(shell_normal_dir)
                if sn_norm > 1e-10:
                    shell_normal_dir = shell_normal_dir / sn_norm
                else:
                    shell_normal_dir = normal

                p += offset_sign * (thickness / 2.0) * shell_normal_dir
                pts[i, j] = p

        for i in range(n_theta - 1):
            for j in range(n_h - 1):
                tris.extend(quad_to_tris(
                    pts[i, j], pts[i+1, j], pts[i+1, j+1], pts[i, j+1]
                ))

        return tris

    # Anterior leaflet: spans ~120 degrees
    ant_start = np.radians(30)
    ant_end = np.radians(150)
    n_ant_theta = n_circ // 2

    triangles.extend(leaflet_surface(ant_start, ant_end, anterior_height, anterior_thickness,
                                      n_ant_theta, n_rad, offset_sign=1.0))
    triangles.extend(leaflet_surface(ant_start, ant_end, anterior_height, anterior_thickness,
                                      n_ant_theta, n_rad, offset_sign=-1.0))

    # Posterior leaflet: 3 scallops P1, P2, P3
    scallop_ranges = [
        (np.radians(155), np.radians(210)),   # P1
        (np.radians(215), np.radians(310)),   # P2 (largest)
        (np.radians(315), np.radians(385)),   # P3
    ]
    n_post_theta_per_scallop = [n_circ // 5, n_circ // 3, n_circ // 5]

    for (ps, pe), n_th in zip(scallop_ranges, n_post_theta_per_scallop):
        triangles.extend(leaflet_surface(ps, pe, posterior_height, posterior_thickness,
                                          n_th, n_rad, offset_sign=1.0))
        triangles.extend(leaflet_surface(ps, pe, posterior_height, posterior_thickness,
                                          n_th, n_rad, offset_sign=-1.0))

    # Annulus ring
    n_ann = n_circ
    ann_width = 0.002 * scale
    ann_thetas = np.linspace(0, 2 * np.pi, n_ann, endpoint=False)

    for i in range(n_ann):
        th0 = ann_thetas[i]
        th1 = ann_thetas[(i + 1) % n_ann]
        p0_outer = annulus_point(th0) + ann_width * normal
        p1_outer = annulus_point(th1) + ann_width * normal
        p0_inner = annulus_point(th0)
        p1_inner = annulus_point(th1)
        triangles.extend(quad_to_tris(p0_inner, p1_inner, p1_outer, p0_outer))

    return triangles


# ---------------------------------------------------------------------------
# Aortic Valve geometry
# ---------------------------------------------------------------------------

def generate_aortic_valve():
    """
    Generate aortic valve with 3 cusps, sinus of Valsalva, and coronary ostia markers.
    """
    center = np.array([-0.0153, 0.0192, -0.1311])
    case_radius = 0.0169

    annulus_diam = 0.023
    annulus_r = annulus_diam / 2.0
    cusp_height = 0.014
    cusp_thickness = 0.0005
    sinus_diam = 0.032
    sinus_r = sinus_diam / 2.0
    sinus_height = 0.020
    coronary_height = 0.012

    scale = case_radius / annulus_r

    # Valve axis direction
    mv_center = np.array([-0.0222, 0.0044, -0.1489])
    valve_axis = center - mv_center
    valve_axis = valve_axis / np.linalg.norm(valve_axis)

    if abs(np.dot(valve_axis, np.array([1, 0, 0]))) < 0.9:
        u = np.cross(valve_axis, np.array([1, 0, 0]))
    else:
        u = np.cross(valve_axis, np.array([0, 1, 0]))
    u = u / np.linalg.norm(u)
    v = np.cross(valve_axis, u)
    v = v / np.linalg.norm(v)

    n_circ = 60
    n_rad = 55
    n_sinus_circ = 90
    n_sinus_h = 40

    triangles = []

    # --- 3 cusps at 120-degree intervals ---
    for cusp_idx in range(3):
        cusp_angle_center = cusp_idx * (2 * np.pi / 3)
        cusp_span = 2 * np.pi / 3
        theta_start = cusp_angle_center - cusp_span / 2
        theta_end = cusp_angle_center + cusp_span / 2

        thetas = np.linspace(theta_start, theta_end, n_circ)
        fracs = np.linspace(0, 1, n_rad)

        for offset_sign in [1.0, -1.0]:
            pts = np.zeros((n_circ, n_rad, 3))

            for i, th in enumerate(thetas):
                r = annulus_r * scale
                x = r * np.cos(th)
                y = r * np.sin(th)
                p_ann = center + x * u + y * v

                radial_dir = center - p_ann
                radial_plane = radial_dir - np.dot(radial_dir, valve_axis) * valve_axis
                rn = np.linalg.norm(radial_plane)
                if rn > 1e-10:
                    radial_dir = radial_plane / rn
                else:
                    radial_dir = u

                angular_pos = (th - theta_start) / cusp_span
                scallop_factor = np.sin(np.pi * angular_pos)

                for j, frac in enumerate(fracs):
                    h = cusp_height * scale * frac * scallop_factor
                    belly = 0.4 * cusp_height * scale * np.sin(np.pi * frac) * scallop_factor
                    sag = -0.1 * cusp_height * scale * (frac ** 3) * scallop_factor
                    p = p_ann + h * valve_axis + belly * radial_dir + sag * valve_axis

                    tangent_circ = np.array([-np.sin(th), np.cos(th), 0.0])
                    tangent_circ_3d = tangent_circ[0] * u + tangent_circ[1] * v
                    shell_n = np.cross(radial_dir, tangent_circ_3d)
                    sn = np.linalg.norm(shell_n)
                    if sn > 1e-10:
                        shell_n = shell_n / sn
                    else:
                        shell_n = valve_axis

                    p += offset_sign * (cusp_thickness / 2.0) * shell_n
                    pts[i, j] = p

            for i in range(n_circ - 1):
                for j in range(n_rad - 1):
                    triangles.extend(quad_to_tris(
                        pts[i, j], pts[i+1, j], pts[i+1, j+1], pts[i, j+1]
                    ))

    # --- Sinus of Valsalva ---
    sinus_thetas = np.linspace(0, 2 * np.pi, n_sinus_circ, endpoint=False)
    sinus_heights = np.linspace(0, sinus_height * scale, n_sinus_h)

    sinus_pts = np.zeros((n_sinus_circ, n_sinus_h, 3))

    for i, th in enumerate(sinus_thetas):
        for j, h in enumerate(sinus_heights):
            frac_h = h / (sinus_height * scale) if sinus_height * scale > 0 else 0
            bulge = 0.0
            for cusp_idx in range(3):
                cusp_center = cusp_idx * (2 * np.pi / 3)
                angular_dist = abs(((th - cusp_center + np.pi) % (2 * np.pi)) - np.pi)
                if angular_dist < np.pi / 3:
                    circ_factor = np.cos(angular_dist * 3 / 2)
                    height_factor = np.sin(np.pi * frac_h)
                    bulge = (sinus_r - annulus_r) * scale * circ_factor * height_factor

            r = annulus_r * scale + bulge
            x = r * np.cos(th)
            y = r * np.sin(th)
            sinus_pts[i, j] = center + x * u + y * v + h * valve_axis

    for i in range(n_sinus_circ):
        i_next = (i + 1) % n_sinus_circ
        for j in range(n_sinus_h - 1):
            triangles.extend(quad_to_tris(
                sinus_pts[i, j], sinus_pts[i_next, j],
                sinus_pts[i_next, j+1], sinus_pts[i, j+1]
            ))

    # --- Coronary ostia markers ---
    ostium_radius = 0.002 * scale
    n_ostium = 16

    left_angle = np.radians(300)
    left_pos = (center
                + (sinus_r * scale * 0.95) * (np.cos(left_angle) * u + np.sin(left_angle) * v)
                + coronary_height * scale * valve_axis)

    right_angle = np.radians(120)
    right_pos = (center
                 + (sinus_r * scale * 0.95) * (np.cos(right_angle) * u + np.sin(right_angle) * v)
                 + coronary_height * scale * valve_axis)

    for ostium_center in [left_pos, right_pos]:
        ring_pts = []
        for k in range(n_ostium):
            angle = 2 * np.pi * k / n_ostium
            offset = ostium_radius * (np.cos(angle) * valve_axis +
                                       np.sin(angle) * v)
            ring_pts.append(ostium_center + offset)

        for k in range(n_ostium):
            k_next = (k + 1) % n_ostium
            triangles.append((ostium_center, ring_pts[k], ring_pts[k_next]))

    return triangles


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def generate_metadata():
    """Generate valve_metadata.json with dimensions and material properties."""
    metadata = {
        "mitral_valve": {
            "geometry": {
                "annulus_diameter_mm": 30.0,
                "annulus_shape": "D-shaped saddle",
                "saddle_height_mm": 7.0,
                "anterior_leaflet": {
                    "height_mm": 20.0,
                    "thickness_mm": 1.0,
                    "angular_span_deg": 120.0
                },
                "posterior_leaflet": {
                    "height_mm": 15.0,
                    "thickness_mm": 0.8,
                    "angular_span_deg": 240.0,
                    "scallops": ["P1", "P2", "P3"]
                }
            },
            "positioning": {
                "center_m": [-0.0222, 0.0044, -0.1489],
                "annulus_radius_m": 0.0225,
                "annulus_plane_normal": [0.0, 0.0, -1.0],
                "coordinate_system": "case geometry (metres)"
            },
            "material_properties": {
                "elastic_modulus_circumferential_kPa": 5000.0,
                "elastic_modulus_radial_kPa": 1200.0,
                "thickness_range_mm": [0.4, 1.3],
                "density_kg_m3": 1100.0,
                "tissue_type": "anisotropic_hyperelastic"
            }
        },
        "aortic_valve": {
            "geometry": {
                "annulus_diameter_mm": 23.0,
                "cusp_height_mm": 14.0,
                "cusp_thickness_mm": 0.5,
                "num_cusps": 3,
                "cusp_angular_spacing_deg": 120.0,
                "sinus_of_valsalva": {
                    "diameter_mm": 32.0,
                    "height_mm": 20.0
                },
                "coronary_ostia": {
                    "left_position": "10 o'clock",
                    "right_position": "2 o'clock",
                    "height_above_annulus_mm": 12.0
                }
            },
            "positioning": {
                "center_m": [-0.0153, 0.0192, -0.1311],
                "annulus_radius_m": 0.0169,
                "valve_axis_direction": "LV outflow (base to aorta)",
                "coordinate_system": "case geometry (metres)"
            },
            "material_properties": {
                "elastic_modulus_circumferential_kPa": 8000.0,
                "elastic_modulus_radial_kPa": 2000.0,
                "thickness_range_mm": [0.3, 0.7],
                "density_kg_m3": 1100.0,
                "tissue_type": "anisotropic_hyperelastic"
            }
        },
        "chordae_tendineae": {
            "note": "Reference properties only (geometry not generated)",
            "elastic_modulus_MPa": [40.0, 80.0],
            "diameter_range_mm": [0.3, 2.5],
            "count_range": [25, 120],
            "density_kg_m3": 1100.0
        },
        "references": [
            "Prot V et al. (2009) Finite element analysis of the mitral apparatus",
            "Kunzelman KS et al. (1993) Annular dilatation and papillary muscle repositioning",
            "Thubrikar M (1990) The Aortic Valve, CRC Press",
            "Grande-Allen KJ et al. (2001) Glycosaminoglycans and proteoglycans in normal mitral valve leaflets"
        ],
        "stl_format": "ASCII",
        "units": "metres"
    }
    return metadata


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    script_dir = pathlib.Path(__file__).resolve().parent
    output_dir = script_dir / "lv_cfd_anatomical" / "constant" / "triSurface"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating mitral valve geometry...")
    mv_tris = generate_mitral_valve()
    mv_path = output_dir / "mitral_valve.stl"
    write_ascii_stl(str(mv_path), mv_tris, solid_name="mitral_valve")
    mv_size = os.path.getsize(mv_path)
    print(f"  Mitral valve: {len(mv_tris)} triangles, {mv_size:,} bytes ({mv_size/1024:.1f} KB)")

    print("Generating aortic valve geometry...")
    av_tris = generate_aortic_valve()
    av_path = output_dir / "aortic_valve.stl"
    write_ascii_stl(str(av_path), av_tris, solid_name="aortic_valve")
    av_size = os.path.getsize(av_path)
    print(f"  Aortic valve: {len(av_tris)} triangles, {av_size:,} bytes ({av_size/1024:.1f} KB)")

    print("Writing valve metadata...")
    metadata = generate_metadata()
    metadata["generated_files"] = {
        "mitral_valve_stl": {
            "path": "lv_cfd_anatomical/constant/triSurface/mitral_valve.stl",
            "num_triangles": len(mv_tris),
            "file_size_bytes": mv_size
        },
        "aortic_valve_stl": {
            "path": "lv_cfd_anatomical/constant/triSurface/aortic_valve.stl",
            "num_triangles": len(av_tris),
            "file_size_bytes": av_size
        }
    }

    meta_path = output_dir / "valve_metadata.json"
    with open(str(meta_path), "w") as f:
        json.dump(metadata, f, indent=2)
    meta_size = os.path.getsize(meta_path)
    print(f"  Metadata: {meta_size:,} bytes")

    print(f"\nDone. Files written to: {output_dir}")
    print(f"  - mitral_valve.stl  ({len(mv_tris)} triangles)")
    print(f"  - aortic_valve.stl  ({len(av_tris)} triangles)")
    print(f"  - valve_metadata.json")


if __name__ == "__main__":
    main()
