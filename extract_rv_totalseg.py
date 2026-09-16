"""
환자 내(in-patient) RV 추출: TotalSegmentator mask -> STL -> CFD 좌표계
======================================================================
목적: MM-WHS Case 1009는 RV(label 620)가 비어 있음. 이를 교차환자 STACOM RV로
      빌려온 v2 정합은 해부학적으로 부적합(RV-LV 35mm gap)이었다(STATUS §19-D).
      → 동일 환자 CT에 TotalSegmentator를 돌려 RV를 직접 분할하면 교차환자
        오차가 원천 제거된다.

이 스크립트가 하는 일:
  1. TotalSegmentator 출력(heartchambers_highres)에서 RV mask NIfTI 로드
  2. NIfTI affine을 적용한 marching cubes로 world(mm) STL 생성
  3. 스무딩 + 최대 연결성분 + decimation
  4. mm_to_cfd_transform.npy 적용 → CFD(m) 좌표계로 배치 (registration 불필요)
  5. [자체검증] TotalSeg가 함께 낸 LV(heart_ventricle_left)도 같은 변환으로 옮겨
     기존 lv_surface.stl과 표면 RMS 비교 → 프레임 일치 확인
  6. [해부검증] 새 RV와 lv_surface의 표면 최소거리 계산(septum 공유 → ≈0 기대)

전제:
  - TotalSegmentator 출력이 입력 CT와 동일 affine(world mm)을 가짐 (표준 동작)
  - 그 world mm 프레임 = cardiac_meshes 추출 프레임 = mm_to_cfd_transform의 정의역
    (LV_case1009 extent가 lv_surface ×1000, ICP RMS 3.1mm로 검증됨)

실행:
  python3 extract_rv_totalseg.py [--seg_dir DIR] [--project DIR]
  기본 seg_dir = <project>/totalseg_output
"""
from __future__ import annotations
import argparse, glob, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

def find_mask(seg_dir, *names):
    for n in names:
        p = os.path.join(seg_dir, n)
        if os.path.exists(p):
            return p
    # glob fallback
    for n in names:
        hits = glob.glob(os.path.join(seg_dir, "**", n), recursive=True)
        if hits:
            return hits[0]
    return None

def mask_to_mesh(mask_path, sigma=0.8, level=0.5, step=1):
    """NIfTI binary mask -> trimesh (world mm coords via affine)."""
    import nibabel as nib
    from skimage import measure
    from scipy.ndimage import gaussian_filter
    import trimesh
    img = nib.load(mask_path)
    vol = (img.get_fdata() > 0.5).astype(np.float32)
    if vol.sum() == 0:
        raise ValueError(f"빈 mask: {mask_path}")
    vol = gaussian_filter(vol, sigma=sigma)
    verts, faces, normals, _ = measure.marching_cubes(vol, level=level, step_size=step)
    # voxel(i,j,k) -> world(mm) via affine
    A = img.affine
    world = (A[:3, :3] @ verts.T).T + A[:3, 3]
    m = trimesh.Trimesh(vertices=world, faces=faces, process=True)
    # 최대 연결성분만
    comps = m.split(only_watertight=False)
    if len(comps) > 1:
        m = max(comps, key=lambda c: len(c.faces))
    # 가벼운 laplacian 스무딩
    trimesh.smoothing.filter_taubin(m, iterations=10)
    return m

def surf_rms(A, B, n=6000):
    from scipy.spatial import cKDTree
    import trimesh
    a = A.sample(n); b = B.sample(n)
    da, _ = cKDTree(b).query(a); db, _ = cKDTree(a).query(b)
    d = np.concatenate([da, db]) * 1000.0
    return float(np.sqrt((d**2).mean())), float(d.max())

def min_gap(A, B, n=6000):
    from scipy.spatial import cKDTree
    a = A.sample(n); b = B.sample(n)
    da, _ = cKDTree(b).query(a)
    return float(da.min() * 1000), float(np.median(da) * 1000)

def main():
    import trimesh
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=HERE)
    ap.add_argument("--seg_dir", default=None)
    ap.add_argument("--out_stl", default=None)
    args = ap.parse_args()

    proj = args.project
    seg_dir = args.seg_dir or os.path.join(proj, "totalseg_output")
    tri_dir = os.path.join(proj, "lv_cfd_anatomical", "constant", "triSurface")
    out_stl = args.out_stl or os.path.join(tri_dir, "rv_insegment_registered.stl")

    T = np.load(os.path.join(proj, "mm_to_cfd_transform.npy"))
    print(f"[i] seg_dir  = {seg_dir}")
    print(f"[i] out_stl  = {out_stl}")

    # RV mask (TotalSegmentator heartchambers_highres 파일명)
    rv_mask = find_mask(seg_dir, "heart_ventricle_right.nii.gz", "ventricle_right.nii.gz",
                        "rv.nii.gz")
    if rv_mask is None:
        sys.exit(f"[!] RV mask를 못 찾음. TotalSegmentator를 먼저 실행하라:\n"
                 f"    TotalSegmentator -i <CT>.nii.gz -o {seg_dir} "
                 f"--task heartchambers_highres --device gpu")
    print(f"[1] RV mask: {rv_mask}")

    rv = mask_to_mesh(rv_mask)
    rv_cfd = rv.copy(); rv_cfd.apply_transform(T)
    os.makedirs(tri_dir, exist_ok=True)
    rv_cfd.export(out_stl)
    print(f"[2] RV STL 저장: {out_stl}  (tri={len(rv_cfd.faces)}, "
          f"vol≈{rv_cfd.volume*1e6:.1f} mL)")

    report = {"rv_stl": out_stl, "rv_triangles": int(len(rv_cfd.faces)),
              "rv_volume_mL": round(float(abs(rv_cfd.volume))*1e6, 2)}

    # 자체검증: TotalSeg LV로 프레임 일치 확인
    lv_ref_path = os.path.join(tri_dir, "lv_surface.stl")
    lv_mask = find_mask(seg_dir, "heart_ventricle_left.nii.gz", "ventricle_left.nii.gz")
    if lv_mask and os.path.exists(lv_ref_path):
        lv_seg = mask_to_mesh(lv_mask); lv_seg.apply_transform(T)
        lv_ref = trimesh.load(lv_ref_path, process=False)
        rms, hd = surf_rms(lv_seg, lv_ref)
        report["frame_check_LV_rms_mm"] = round(rms, 2)
        report["frame_check_LV_hausdorff_mm"] = round(hd, 2)
        ok = rms < 12
        print(f"[3] 프레임 검증: TotalSeg-LV vs lv_surface  RMS={rms:.1f}mm  "
              f"{'OK(프레임 일치)' if ok else 'WARN(프레임 불일치 의심 → affine 확인)'}")
        report["frame_consistent"] = bool(ok)
    else:
        print("[3] 프레임 검증 스킵 (LV mask 또는 lv_surface 없음)")

    # 해부검증: RV-LV 인접(septum) — v2의 34.9mm에서 개선됐는지
    if os.path.exists(lv_ref_path):
        lv_ref = trimesh.load(lv_ref_path, process=False)
        g_min, g_med = min_gap(rv_cfd, lv_ref)
        report["RV_to_LV_min_gap_mm"] = round(g_min, 2)
        report["RV_to_LV_median_gap_mm"] = round(g_med, 2)
        verdict = "PASS(septum 인접)" if g_min < 5 else "CHECK(여전히 떨어짐)"
        print(f"[4] RV-LV 최소거리 = {g_min:.1f}mm (v2 교차환자=34.9mm) → {verdict}")

    with open(os.path.join(proj, "rv_insegment_report.json"), "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[✓] 리포트: {os.path.join(proj, 'rv_insegment_report.json')}")

if __name__ == "__main__":
    main()
