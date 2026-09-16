"""
STACOM STL 정합의 해부학적/학술적 타당성 검증
================================================
채택된 RA기반 변환으로 정합한 *_registered_v2.stl 이 해부학적으로
말이 되는지 정량 평가한다.

검증 항목:
  1. 반사(좌우반전) 여부 — 변환 선형부의 det 부호
  2. 앵커 정합 정확도 — registered stacom_RA/PA vs MM-WHS ground-truth (표면 RMS/Hausdorff)
  3. 해부학적 방향관계 — MM-WHS GT(LV/LA/Aorta/RA)로 (Right,Anterior,Superior)
     좌표계를 세우고 각 구조 centroid를 표현, 교과서 기대 부호와 비교
  4. RV-LV 중격 인접성 — 표면 최소거리(≈0이어야 septum 공유)
  5. 관상동맥 epicardial 밀착 — LV 표면에 대한 근접도
  6. 챔버 상호침투 — registered RV 표본점이 LV 혈액풀 내부에 들어간 비율

출력: stacom_registration_v2_validation.json, stacom_registration_v2_validation.png
"""
import json
import numpy as np
import trimesh
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TRI = "lv_cfd_anatomical/constant/triSurface"
CM = "cardiac_meshes"
T_mm2cfd = np.load("mm_to_cfd_transform.npy")
T_stacom = np.load("stacom_to_cfd_transform_v2.npy")
rng = np.random.default_rng(0)


def load(p):
    return trimesh.load(p, process=False)


def spts(m, n=6000):
    return np.asarray(m.sample(n)) if len(m.faces) > 0 else np.asarray(m.vertices)


def gt_cfd(name):
    """MM-WHS ground-truth (mm) -> CFD(m) frame."""
    m = load(f"{CM}/{name}_case1009.stl")
    m.apply_transform(T_mm2cfd)
    return m


def surf_rms_hausdorff(A, B, n=6000):
    """A,B trimesh in same frame. symmetric nearest-surface distances (mm)."""
    a, b = spts(A, n), spts(B, n)
    da, _ = cKDTree(b).query(a)
    db, _ = cKDTree(a).query(b)
    d = np.concatenate([da, db]) * 1000.0
    return float(np.sqrt((d**2).mean())), float(d.max())


out = {}

# ---- 1. 반사 여부 ----
L = T_stacom[:3, :3]
det = float(np.linalg.det(L))
scale = float(np.cbrt(abs(det)))
out["reflection_check"] = {
    "det_linear": det,
    "implied_uniform_scale": scale,
    "reflection": det < 0,
    "verdict": "PASS (반사 없음, 우수계 보존)" if det > 0 else "FAIL (좌우반전 발생!)",
}

# ---- ground-truth & registered in CFD frame ----
LV = gt_cfd("LV")
LA = gt_cfd("LA")
AO = gt_cfd("Aorta")
RA_gt = gt_cfd("RA")
PA_gt = gt_cfd("PA")
lv_c = LV.centroid

reg = {s: load(f"{TRI}/{s}_registered_v2.stl") for s in
       ["laa", "rv", "coronary", "pv", "pa", "ra"]}

# ---- 2. 앵커 정합 정확도 ----
rms_ra, hd_ra = surf_rms_hausdorff(reg["ra"], RA_gt)
rms_pa, hd_pa = surf_rms_hausdorff(reg["pa"], PA_gt)
out["anchor_accuracy_mm"] = {
    "RA_fit_anchor":  {"surface_rms": round(rms_ra, 2), "hausdorff": round(hd_ra, 2)},
    "PA_independent": {"surface_rms": round(rms_pa, 2), "hausdorff": round(hd_pa, 2)},
    "note": "RA는 적합 앵커(하한), PA는 독립 검증(일반화 성능의 실제 지표)",
}

# ---- 3. 해부학 좌표계 (Right, Anterior, Superior) ----
S = (0.5 * (LA.centroid + AO.centroid)) - lv_c          # base(superior) 방향
S = S / np.linalg.norm(S)
Rraw = RA_gt.centroid - lv_c                              # rightward(우심방)
R = Rraw - (Rraw @ S) * S
R = R / np.linalg.norm(R)
A = np.cross(S, R)                                        # 우수계
A = A / np.linalg.norm(A)
ant_sign = np.sign((PA_gt.centroid - lv_c) @ A)          # PA가 전방 → +A 부호 고정
A = A * ant_sign

def ras(m):
    o = m.centroid - lv_c
    return np.array([o @ R, o @ A, o @ S]) * 1000.0       # mm (right, anterior, superior)

# 기대 부호 (dominant): (right, anterior, superior)  None=중립
expect = {
    "ra":       (+1,  0, +1),   # GT 앵커
    "pa":       ( 0, +1, +1),   # 전방-상방 (독립검증)
    "rv":       (+1, +1,  0),   # 전방, 우측으로 랩핑, LV와 중격 공유
    "pv":       ( 0, -1, +1),   # 후방-상방 (LA로 유입)
    "laa":      ( 0, +1, +1),   # LA 전방 부속기
    "coronary": ( 0,  0,  0),   # 표면 밀착 (방향 중립)
}
label_gt = {"ra": RA_gt, "pa": PA_gt}
dir_tbl = {}
for s, m in reg.items():
    v = ras(m)
    exp = expect[s]
    signs = np.sign(v)
    # 방향 일치: 기대부호가 0이 아닌 축에서 부호가 맞는지
    checks = [(signs[i] == exp[i]) for i in range(3) if exp[i] != 0]
    consistent = bool(np.all(checks)) if checks else None
    entry = {"RAS_mm": [round(x, 1) for x in v],
             "expected_sign": exp,
             "anatomically_consistent": consistent}
    if s in label_gt:      # GT 있는 구조는 방향 코사인도
        og = label_gt[s].centroid - lv_c
        om = m.centroid - lv_c
        cos = float((og @ om) / (np.linalg.norm(og) * np.linalg.norm(om) + 1e-12))
        entry["direction_cosine_vs_GT"] = round(cos, 3)
    dir_tbl[s] = entry
out["anatomical_directions"] = dir_tbl

# ---- 4. RV-LV 중격 인접성 & 5. 관상동맥 밀착 ----
def min_surface_gap(A, B, n=6000):
    a, b = spts(A, n), spts(B, n)
    da, _ = cKDTree(b).query(a)
    return float(da.min() * 1000), float(np.median(da) * 1000)  # mm

rv_min, rv_med = min_surface_gap(reg["rv"], LV)
co_min, co_med = min_surface_gap(reg["coronary"], LV)
out["adjacency_mm"] = {
    "RV_to_LV":       {"min_gap": round(rv_min, 2), "median_gap": round(rv_med, 2),
                       "expect": "septum 공유 → min≈0"},
    "coronary_to_LV": {"min_gap": round(co_min, 2), "median_gap": round(co_med, 2),
                       "expect": "epicardial 밀착 → median 작음"},
}

# ---- 6. 상호침투 (registered RV 점이 LV 혈액풀 내부?) ----
try:
    rv_pts = spts(reg["rv"], 4000)
    inside = LV.contains(rv_pts)
    frac = float(inside.mean())
except Exception as e:
    frac = None
out["interpenetration"] = {
    "RV_pts_inside_LV_fraction": None if frac is None else round(frac, 3),
    "expect": "낮아야 함 (중격/벽으로 분리). 큰 값이면 오정합",
    "note": None if frac is not None else f"LV not watertight: {e}",
}

with open("stacom_registration_v2_validation.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

# ================= FIGURE =================
fig = plt.figure(figsize=(17, 5.2))

# (1) anatomical RAS scatter (Right vs Superior)
ax1 = fig.add_subplot(1, 3, 1)
cols = dict(zip(reg, plt.cm.tab10(np.linspace(0, 1, len(reg)))))
ax1.scatter(0, 0, c="k", s=120, marker="*", label="LV (origin)")
for s, m in reg.items():
    v = ras(m)
    ok = dir_tbl[s]["anatomically_consistent"]
    edge = "green" if ok else ("red" if ok is False else "gray")
    ax1.scatter(v[0], v[2], s=160, c=[cols[s]], edgecolors=edge, linewidths=2.2)
    ax1.annotate(s, (v[0], v[2]), fontsize=9, xytext=(4, 4), textcoords="offset points")
for g, mk in [("ra", RA_gt), ("pa", PA_gt)]:
    o = ras(mk)   # project GT into anatomical RAS frame (consistent with circles)
    ax1.scatter(o[0], o[2], s=200, facecolors="none", edgecolors="black",
                linewidths=1.5, marker="s")
    ax1.annotate(f"{g}_GT", (o[0], o[2]), fontsize=8, color="black")
ax1.axhline(0, c="gray", lw=.5); ax1.axvline(0, c="gray", lw=.5)
ax1.set_xlabel("Right (mm) →"); ax1.set_ylabel("Superior (mm) →")
ax1.set_title("Anatomical frame (Right–Superior)\n□=GT, green ring=consistent, red=inconsistent")
ax1.legend(fontsize=8, loc="lower left"); ax1.set_aspect("equal")

# (2) anatomical RAS scatter (Anterior vs Superior)
ax2 = fig.add_subplot(1, 3, 2)
ax2.scatter(0, 0, c="k", s=120, marker="*")
for s, m in reg.items():
    v = ras(m)
    ok = dir_tbl[s]["anatomically_consistent"]
    edge = "green" if ok else ("red" if ok is False else "gray")
    ax2.scatter(v[1], v[2], s=160, c=[cols[s]], edgecolors=edge, linewidths=2.2)
    ax2.annotate(s, (v[1], v[2]), fontsize=9, xytext=(4, 4), textcoords="offset points")
for g, mk in [("ra", RA_gt), ("pa", PA_gt)]:
    o = ras(mk)
    ax2.scatter(o[1], o[2], s=200, facecolors="none", edgecolors="black",
                linewidths=1.5, marker="s")
    ax2.annotate(f"{g}_GT", (o[1], o[2]), fontsize=8, color="black")
ax2.axhline(0, c="gray", lw=.5); ax2.axvline(0, c="gray", lw=.5)
ax2.set_xlabel("Anterior (mm) →"); ax2.set_ylabel("Superior (mm) →")
ax2.set_title("Anatomical frame (Anterior–Superior)")
ax2.set_aspect("equal")

# (3) quantitative bars
ax3 = fig.add_subplot(1, 3, 3)
names = ["RA anchor\nRMS", "PA indep\nRMS", "PA indep\nHausd.", "RV→LV\nmin gap", "coron→LV\nmedian"]
vals = [rms_ra, rms_pa, hd_pa, rv_min, co_med]
colors = ["#3b82f6", "#3b82f6", "#93c5fd", "#10b981", "#10b981"]
bars = ax3.bar(names, vals, color=colors)
for b, v in zip(bars, vals):
    ax3.text(b.get_x() + b.get_width() / 2, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
ax3.set_ylabel("mm")
refl = out["reflection_check"]["verdict"]
ax3.set_title(f"Quantitative metrics (mm)\nReflection: {refl}")
ax3.grid(axis="y", alpha=0.3)

fig.suptitle("STACOM registration v2 - anatomical validity check (RA-based transform)", fontsize=13)
fig.tight_layout()
fig.savefig("stacom_registration_v2_validation.png", dpi=130, bbox_inches="tight")
print("saved stacom_registration_v2_validation.png + .json")
print(json.dumps(out, ensure_ascii=False, indent=2))
