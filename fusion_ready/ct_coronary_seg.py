# -*- coding: utf-8 -*-
"""Step 2c -- coronary tree from the 1009 CT: vesselness-gated hysteresis + skeleton-graph pruning.

growth domain  G  = epicardial band (<= BAND_MM outside any label, >= GAP_MM from any blood label)
                    & HU >= HU_LO & (vesselness >= V_LO  or  HU >= HU_HI inside a >=3-voxel-thick blob)
seeds             = components of (HU >= HU_HI, sheet-filtered) touching the root zone
                    (1-4 mm outside the aorta label, within ROOT_R_MM of the aortic-valve centre)
tree              = seeds geodesically reconstructed inside G, capped at GEO_CAP_MM from the root
skeleton -> MST -> branches; prune spurs (< SPUR_MM) and veins (branch HU < HU_VEIN, or HU < HU_VEIN_BIG
with diameter >= D_BIG -> great cardiac vein / coronary sinus) together with their subtrees.
Trunk names from chamber adjacency: RCA (RA+RV), LCx (LA+LV), LAD / PDA (LV+RV, anterior / posterior
of the LV-RV midpoint), LM (left ostium to first bifurcation). Everything else: 'branch'.
Outputs (frame A = RAS mm): coronary_tree_frameA.stl, coronary.json (branches + centrelines + radii),
coronary_mask.npz.
"""
import os, json, time
from collections import deque
import numpy as np, nibabel as nib, networkx as nx
from scipy import ndimage
from skimage import measure, morphology
import trimesh
from case_paths import paths as _paths, geometry as _geometry, MMWHS, dist_to
_P = _paths(); _G = _geometry()
REPO = os.environ.get("CARDIAC_REPO", os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = _P["coronary"]; os.makedirs(OUT, exist_ok=True)
CASE = _P["case"]; TAG = os.environ.get("TAG", ""); PRUNE_VEINS = os.environ.get("PRUNE_VEINS", "1") == "1"
BAND_MM, GAP_MM, MARGIN_MM = 14.0, 1.0, 20.0
HU_LO, HU_HI = float(os.environ.get("HU_LO", 180)), float(os.environ.get("HU_HI", 300))
V_LO = float(os.environ.get("V_LO", 0.02)); V_IN = float(os.environ.get("V_IN", 0.08)); HU_LO2, V_LO2, HU_RIGHT = 150.0, 0.05, 330.0
HU_VEIN, HU_VEIN_BIG, D_BIG, D_BLOB, R_PASS = 240.0, 330.0, 3.2, 6.0, 1.75
ROOT_R_MM, ROOT_D, GEO_CAP_MM, SPUR_MM, SEED_MIN_ML, SEED_MAX_ML, OFF_HEART_MM = 32.0, (1.0, 4.0), 170.0, 3.0, 0.03, 15.0, 16.0
BLOOD = (500, 600, 420, 550, 820, 850)

def ball(r):
    n = int(np.ceil(r)); g = np.mgrid[-n:n + 1, -n:n + 1, -n:n + 1]; return (g ** 2).sum(0) <= r ** 2
def cc(mask): return ndimage.label(mask, structure=np.ones((3, 3, 3)))

t0 = time.time()
img = nib.load(os.path.join(MMWHS, f"ct_train_{CASE}_image.nii.gz")); lab = nib.load(os.path.join(MMWHS, f"ct_train_{CASE}_label.nii.gz"))
A = img.affine; sp = np.array(img.header.get_zooms()[:3], float); vox_mL = np.prod(sp) / 1000
L = np.asanyarray(lab.dataobj); idx = np.argwhere(L > 0); m = np.ceil(MARGIN_MM / sp).astype(int)
lo = np.maximum(idx.min(0) - m, 0); hi = np.minimum(idx.max(0) + m + 1, L.shape); sl = tuple(slice(a, b) for a, b in zip(lo, hi))
Lc = np.asarray(L[sl]).astype(np.int16); del L, idx; I = np.asanyarray(img.dataobj)[sl].astype(np.float32)
vz = np.load(os.path.join(OUT, "vesselness.npz")); assert (vz["lo"] == lo).all(); V = vz["V"].astype(np.float32); del vz
T = np.array(_G["T"])
av_A = np.array(_G["av_centre"]); av_w = av_A - T[:3, 3]; av_idx = (np.linalg.inv(A) @ np.r_[av_w, 1])[:3] - lo
def to_A(pts_crop):
    P_ = np.atleast_2d(np.asarray(pts_crop, float)); out = trimesh.transform_points(P_ + lo, A) + T[:3, 3]
    return out if np.ndim(pts_crop) == 2 else out[0]

Hc = Lc > 0; blood = np.isin(Lc, BLOOD)
dom_out = (dist_to(Hc, sp) <= BAND_MM) & ~Hc                 # epicardial band, outside every label
gapok = dist_to(blood, sp) >= GAP_MM
# the RA/RV/LA labels sometimes swallow AV-groove fat and the artery in it: allow the inner 6 mm of those
# labels where the tube filter is strong (uniform chamber blood has ~zero vesselness)
soft = np.isin(Lc, (600, 420, 550)); dom_in = soft & (dist_to(~soft, sp) <= 6.0) & (V >= V_IN); del soft
dom = dom_out | dom_in
d = dist_to(Lc == 820, sp); ring = (d >= ROOT_D[0]) & (d <= ROOT_D[1]); del d
ax_ = [((np.arange(n) - c) * s_).astype(np.float32) ** 2 for n, c, s_ in zip(Lc.shape, av_idx, sp)]
r_av = np.sqrt(ax_[0][:, None, None] + ax_[1][None, :, None] + ax_[2][None, None, :])
hi_thick = ndimage.binary_opening(dom_out & gapok & (I >= HU_HI), structure=ball(1))
hi_thick = dom_out & gapok & (I >= HU_HI) & ndimage.binary_dilation(hi_thick, structure=np.ones((3, 3, 3)))
# two-tier tube criterion: moderate HU with some tubularity, or lower HU (partial-volume dropouts) with strong tubularity
grow = dom & (((I >= HU_LO) & (V >= V_LO)) | ((I >= HU_LO2) & (V >= V_LO2)) | hi_thick)
# right-heart rescue: RA/RV blood is dark (~220 HU) in this arterial phase, so lumen voxels >= HU_RIGHT next to
# (or wrongly inside the outer 3 mm of) the RA/RV labels cannot be chamber blood -> lets the RCA pass calcified,
# vesselness-poor segments hugging the RA label.  Kept tube-like by the same 1-voxel opening.
right = np.isin(Lc, (550, 600)); dR = dist_to(right, sp); dL = dist_to(np.isin(Lc, (500, 205, 420, 820, 850)), sp)
near_right = (dR < dL) & (dR <= 4.0); del dL
inside_right = right & (dist_to(~right, sp) <= 3.0); del right, dR
rh = (I >= HU_RIGHT) & near_right & (dom_out | inside_right)
rh = rh & ndimage.binary_dilation(ndimage.binary_opening(rh, structure=ball(1)), structure=np.ones((3, 3, 3)))
grow |= rh; dom |= rh; print(f"right-heart rescue voxels {rh.sum()*vox_mL:.2f} mL"); del rh, near_right, inside_right
root = ring & (r_av <= ROOT_R_MM) & (I >= HU_HI) & dom_out & gapok; del r_av, ring
print(f"domain {dom_out.sum()*vox_mL:.1f} (+{dom_in.sum()*vox_mL:.2f} inside RA/RV/LA) mL; grow {grow.sum()*vox_mL:.1f} mL (tier1 {(dom & (I >= HU_LO) & (V >= V_LO)).sum()*vox_mL:.1f}, tier2 {(dom & (I >= HU_LO2) & (V >= V_LO2)).sum()*vox_mL:.1f}); hi_thick {hi_thick.sum()*vox_mL:.1f}; root {root.sum()*vox_mL:.2f}  {time.time()-t0:.0f}s")
del dom_in, gapok

lbl, n = cc(hi_thick); hit = np.unique(lbl[root]); hit = hit[hit > 0]
sizes = ndimage.sum(lbl > 0, lbl, hit) * vox_mL
keep = [int(k) for k, s in zip(hit, sizes) if SEED_MIN_ML <= s <= SEED_MAX_ML]
print("seed components (mL):", [(int(k), round(float(s), 3)) for k, s in zip(hit, sizes)], "kept", keep)
seeds = np.isin(lbl, keep); del lbl
rec = ndimage.binary_dilation(seeds, structure=np.ones((3, 3, 3)), iterations=0, mask=grow | seeds)
bb = np.argwhere(rec); b0 = np.maximum(bb.min(0) - 2, 0); b1 = np.minimum(bb.max(0) + 3, rec.shape); bsl = tuple(slice(a, b) for a, b in zip(b0, b1)); del bb
R = rec[bsl]; S = (rec & root)[bsl]
nb = [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1) if (dx, dy, dz) != (0, 0, 0)]
nbl = [float(np.linalg.norm(np.array(v) * sp)) for v in nb]
gd = np.full(R.shape, np.inf, np.float32); q = deque()
for p in map(tuple, np.argwhere(S)): gd[p] = 0.0; q.append(p)
X, Y, Z = R.shape
while q:
    p = q.popleft(); g0 = gd[p]
    for v, dl in zip(nb, nbl):
        x, y, z = p[0] + v[0], p[1] + v[1], p[2] + v[2]
        if 0 <= x < X and 0 <= y < Y and 0 <= z < Z and R[x, y, z]:
            g = g0 + dl
            if g < gd[x, y, z] and g <= GEO_CAP_MM: gd[x, y, z] = g; q.append((x, y, z))
tree = np.isfinite(gd)
print(f"seeds {seeds.sum()*vox_mL:.2f} -> reconstructed {rec.sum()*vox_mL:.2f} -> capped tree {tree.sum()*vox_mL:.2f} mL (max geodesic {gd[tree].max():.0f} mm)  {time.time()-t0:.0f}s")
Ib, Lb, Vb = I[bsl], Lc[bsl], V[bsl]
del rec, grow, hi_thick, dom, dom_out, V

# ---- skeleton -> voxel graph -> MST -> branches ----
skel = morphology.skeletonize(tree)
rad = ndimage.distance_transform_edt(tree, sampling=sp)
pts = np.argwhere(skel); key = {tuple(p): i for i, p in enumerate(map(tuple, pts))}
G = nx.Graph()
for i, p in enumerate(pts):
    G.add_node(i, p=tuple(p), r=float(rad[tuple(p)]), hu=float(Ib[tuple(p)]), gd=float(gd[tuple(p)]))
    for v, dl in zip(nb, nbl):
        j = key.get((p[0] + v[0], p[1] + v[1], p[2] + v[2]))
        if j is not None and j > i: G.add_edge(i, j, w=dl)
G = nx.minimum_spanning_tree(G, weight="w")
rootnodes = [n_ for n_ in G.nodes if G.nodes[n_]["gd"] <= 2.0]
keep_nodes = set()
for rn in rootnodes: keep_nodes |= nx.node_connected_component(G, rn)
G = G.subgraph(keep_nodes).copy()
td = nx.multi_source_dijkstra_path_length(G, set(rootnodes), weight="w")
nx.set_node_attributes(G, td, "td")
print(f"skeleton {len(pts)} voxels -> MST, root-connected {G.number_of_nodes()} voxels, max tree distance {max(td.values()):.0f} mm  {time.time()-t0:.0f}s")

def branches_of(G):
    deg = dict(G.degree()); special = {n_ for n_, d_ in deg.items() if d_ != 2}
    seen, out = set(), []
    for s in special:
        for nbr in G.neighbors(s):
            if frozenset((s, nbr)) in seen: continue
            path = [s, nbr]; seen.add(frozenset((s, nbr))); prev, cur = s, nbr
            while cur not in special:
                nxt = [x for x in G.neighbors(cur) if x != prev]
                if not nxt: break
                prev, cur = cur, nxt[0]; seen.add(frozenset((prev, cur))); path.append(cur)
            out.append(path)
    return out

def summ(path):
    L_ = sum(G[a][b]["w"] for a, b in zip(path[:-1], path[1:]))
    rr = np.array([G.nodes[n_]["r"] for n_ in path]); hu = np.array([G.nodes[n_]["hu"] for n_ in path]); g = np.array([G.nodes[n_]["td"] for n_ in path])
    return dict(len_mm=L_, r_med=float(np.median(rr)), r_max=float(rr.max()), hu=float(np.median(hu)), gd_min=float(g.min()), gd_max=float(g.max()))

def prune_spurs():
    for _ in range(20):
        deg = dict(G.degree()); removed = 0
        for path in branches_of(G):
            e0, e1 = path[0], path[-1]
            if (deg.get(e0) == 1) != (deg.get(e1) == 1) and summ(path)["len_mm"] < SPUR_MM:
                tip = e0 if deg[e0] == 1 else e1
                G.remove_nodes_from([n_ for n_ in path if n_ != (e1 if tip == e0 else e0)]); removed += 1
        if not removed: break
prune_spurs()

def drop_subtree(path):
    """remove the branch and everything downstream of its far end (never the root side)."""
    far, near = (path[-1], path[0]) if G.nodes[path[-1]]["td"] > G.nodes[path[0]]["td"] else (path[0], path[-1])
    H = G.copy(); H.remove_node(near); drop = set(path) - {near}
    if far in H:
        comp = nx.node_connected_component(H, far)
        if not any(H.nodes[c]["td"] <= 2.0 for c in comp): drop |= comp
    G.remove_nodes_from(drop)
def dist_to(vals): return ndimage.distance_transform_edt(~np.isin(Lb, vals), sampling=sp).astype(np.float32)
dHeart = dist_to((500, 205, 600, 420, 550, 820, 850)); dLA_ = dist_to((420,))
veins, offheart, blobs, passthru = [], [], [], []
def downstream(path):
    far, near = (path[-1], path[0]) if G.nodes[path[-1]]["td"] > G.nodes[path[0]]["td"] else (path[0], path[-1])
    H = G.copy(); H.remove_node(near)
    return (nx.node_connected_component(H, far) - set(path)) if far in H else set()
def arterial_beyond(path):
    """does an artery continue past this branch? -> >= 20 skeleton voxels downstream with arterial HU and vessel calibre"""
    ds = downstream(path); return sum(1 for n_ in ds if G.nodes[n_]["hu"] >= HU_VEIN_BIG and G.nodes[n_]["r"] <= 2.0) >= 30
def make_passthru(path, why):
    """a merged region (LA appendage contact, artery+vein confluence) that an artery passes THROUGH: keep the centreline
    so the distal artery stays connected, but thin it to R_PASS (the surface mask drops the fat surroundings)"""
    for n_ in path: G.nodes[n_]["passthru"] = True; G.nodes[n_]["r"] = min(G.nodes[n_]["r"], R_PASS)
    passthru.append(dict(len_mm=round(summ(path)["len_mm"], 1), hu=round(summ(path)["hu"]), diam=round(2 * summ(path)["r_med"], 1), why=why))
for path in sorted(branches_of(G), key=lambda p: -len(p)):
    if not all(n_ in G for n_ in path): continue
    s = summ(path)
    if s["len_mm"] < 4.0: continue
    P = np.array([G.nodes[n_]["p"] for n_ in path]); dh = float(np.median(dHeart[tuple(P.T)]))
    if dh > OFF_HEART_MM:
        offheart.append(dict(len_mm=round(s["len_mm"], 1), hu=round(s["hu"]), diam=round(2 * s["r_med"], 1), d_heart=round(dh, 1))); drop_subtree(path); continue
    fat_near_LA = 2 * s["r_med"] >= 4.0 and s["gd_min"] > 12.0 and float(np.median(dLA_[tuple(P.T)])) < 6.0    # LA appendage / atrial wall contact
    if (2 * s["r_med"] >= D_BLOB and s["gd_min"] > 12.0) or fat_near_LA:      # coronary arteries are < 5 mm; a fat blob beyond the LM is the LA appendage / a vein confluence
        if arterial_beyond(path): make_passthru(path, "blob with an artery beyond it"); continue
        blobs.append(dict(len_mm=round(s["len_mm"], 1), hu=round(s["hu"]), diam=round(2 * s["r_med"], 1), td=round(s["gd_min"], 1))); drop_subtree(path); continue
    if PRUNE_VEINS and (s["hu"] < HU_VEIN or (s["hu"] < HU_VEIN_BIG and 2 * s["r_med"] >= D_BIG)):
        if arterial_beyond(path): make_passthru(path, "vein-like segment with an artery beyond it (artery + vein merged)"); continue
        veins.append(dict(len_mm=round(s["len_mm"], 1), hu=round(s["hu"]), diam=round(2 * s["r_med"], 1))); drop_subtree(path)
prune_spurs()
print("pass-through segments kept (thinned):", passthru[:6])
keep_nodes = set()
for rn in [n_ for n_ in G.nodes if G.nodes[n_]["td"] <= 2.0]: keep_nodes |= nx.node_connected_component(G, rn)
G = G.subgraph(keep_nodes).copy()
print("off-heart branches dropped:", offheart[:6]); print("blob branches dropped:", blobs[:6])
br = branches_of(G)
print(f"after pruning: {len(br)} branches ({sum(1 for p in br if summ(p)['len_mm'] >= 4)} >= 4 mm), {G.number_of_nodes()} skeleton voxels; vein branches dropped {len(veins)}: {veins[:8]}  {time.time()-t0:.0f}s")

# ---- anatomy: topology-based naming ----
# Each root-connected component is one coronary system; the side comes from the ostium position relative to the
# aortic-valve centre (RAS: the right ostium is to the patient's right, +x).  Left system: LM = root -> first node
# where >= 2 children carry >= MIN_DAUGHTER mm of subtree; daughters are LAD (anterior interventricular groove:
# near LV and RV), LCx (left AV groove: near LA) or RI (ramus, the rest); inside each, the trunk is the path to the
# farthest node and everything else is a side branch (D / OM).  Right system: trunk to the farthest node, named PDA
# where it lies in the posterior interventricular groove, RCA elsewhere; side branches PLV (near LV) / RV-br.
# Aortic-rim pieces (root-adjacent subtrees that never leave the aorta by > RIM_MM) are dropped first.
dLV, dRV, dLA, dRA, dAo = dist_to((500, 205)), dist_to((600,)), dist_to((420,)), dist_to((550,)), dist_to((820,))
cLV = to_A(np.argwhere(Lc == 500)[::37]).mean(0); cRV = to_A(np.argwhere(Lc == 600)[::37]).mean(0); mid = (cLV + cRV) / 2
MIN_DAUGHTER, RIM_MM = 15.0, 8.0
unit = lambda v: v / (np.linalg.norm(v) + 1e-12)
def node_desc(n_):
    p_ = G.nodes[n_]["p"]; return dict(LV=float(dLV[p_]), RV=float(dRV[p_]), LA=float(dLA[p_]), RA=float(dRA[p_]), Ao=float(dAo[p_]), ant=float(to_A(np.array(p_) + b0)[1] - mid[1]))
for n_ in G.nodes: G.nodes[n_].update(node_desc(n_))
# rim pruning
for path in sorted(branches_of(G), key=lambda p: -len(p)):
    if not all(n_ in G for n_ in path): continue
    s_ = summ(path)
    if s_["gd_min"] > 15: continue
    far = path[-1] if G.nodes[path[-1]]["td"] > G.nodes[path[0]]["td"] else path[0]; near = path[0] if far == path[-1] else path[-1]
    H = G.copy(); H.remove_node(near); sub = nx.node_connected_component(H, far) if far in H else {far}
    if any(H.nodes[c]["td"] <= 2.0 for c in sub): continue
    if max(G.nodes[c]["Ao"] for c in sub) < RIM_MM: G.remove_nodes_from(sub)
keep_nodes = set()
for rn in [n_ for n_ in G.nodes if G.nodes[n_]["td"] <= 2.0]: keep_nodes |= nx.node_connected_component(G, rn)
G = G.subgraph(keep_nodes).copy(); br = branches_of(G)
node_name, node_sys = {}, {}
def subtree_len(Tdir, n_):
    return sum(Tdir[u][v]["w"] for u, v in nx.dfs_edges(Tdir, n_))
def path_to(Tdir, src, dst):
    return nx.shortest_path(Tdir, src, dst)
def farthest(Tdir, nodes):
    return max(nodes, key=lambda n_: G.nodes[n_]["td"])
def groove_scores(nodes):
    d = np.array([[G.nodes[n_][k] for k in ("LV", "RV", "LA", "ant")] for n_ in nodes])
    lad = float(np.mean((d[:, 0] < 8) & (d[:, 1] < 10))); lcx = float(np.mean((d[:, 2] < 12) & (d[:, 0] < 14) & (d[:, 3] < 0))); return lad, lcx
systems = []
# side of each system: projection of its ostium on the patient's own left->right axis (LA centroid -> RA centroid),
# relative to the aortic-valve centre; with several systems the split point is the midpoint of the extremes
# (the label-derived valve centre can sit a few mm off, which would otherwise put both ostia on one side)
cLA = to_A(np.argwhere(Lc == 420)[::37]).mean(0); cRA = to_A(np.argwhere(Lc == 550)[::37]).mean(0); LR = unit(cRA - cLA)
comps_all = list(nx.connected_components(G)); roots = {i: min(c, key=lambda n_: G.nodes[n_]["td"]) for i, c in enumerate(comps_all)}
sc_lr = {i: float((to_A(np.array(G.nodes[r]["p"]) + b0) - av_A) @ LR) for i, r in roots.items()}
if len(sc_lr) >= 2 and not (min(sc_lr.values()) < 0 < max(sc_lr.values())): thr_lr = (max(sc_lr.values()) + min(sc_lr.values())) / 2
else: thr_lr = 0.0
for ci, comp in enumerate(comps_all):
    root = roots[ci]; Tdir = nx.bfs_tree(G, root)
    for u, v in Tdir.edges: Tdir[u][v]["w"] = G[u][v]["w"]
    side = "R" if sc_lr[ci] > thr_lr else "L"
    nodes = list(comp); systems.append((side, root, len(nodes)))
    if side == "R":
        far = farthest(Tdir, nodes); trunk = path_to(Tdir, root, far); on = set(trunk)
        for n_ in nodes:
            node_sys[n_] = "R"
            is_pda = (G.nodes[n_]["LV"] < 8 and G.nodes[n_]["RV"] < 10 and G.nodes[n_]["ant"] < -5 and G.nodes[n_]["td"] > 60)
            if n_ in on: node_name[n_] = "PDA" if is_pda else "RCA"
            else: node_name[n_] = "PDA" if is_pda else ("PLV" if G.nodes[n_]["LV"] < 10 else "RV-br")
        continue
    # left system: find the LM bifurcation
    cur = root; lm = [root]
    while True:
        kids = [k for k in Tdir.successors(cur) if subtree_len(Tdir, k) + Tdir[cur][k]["w"] >= MIN_DAUGHTER]
        if len(kids) >= 2 or len(kids) == 0: break
        cur = kids[0]; lm.append(cur)
    for n_ in lm: node_name[n_] = "LM"; node_sys[n_] = "L"
    kids = [k for k in Tdir.successors(cur) if subtree_len(Tdir, k) + Tdir[cur][k]["w"] >= MIN_DAUGHTER] or list(Tdir.successors(cur))
    subs = {k: [k] + list(nx.descendants(Tdir, k)) for k in kids}
    sc = {k: groove_scores(v_) for k, v_ in subs.items()}
    lad_k = max(kids, key=lambda k: (sc[k][0], np.mean([G.nodes[n_]["ant"] for n_ in subs[k]]))) if kids else None
    rest = [k for k in kids if k != lad_k]
    lcx_k = max(rest, key=lambda k: (sc[k][1], -np.mean([G.nodes[n_]["ant"] for n_ in subs[k]]))) if rest else None
    if lad_k is not None and sc[lad_k][0] < 0.15 and lcx_k is not None and sc[lcx_k][1] > sc[lad_k][1]:   # no groove runner: the 'LAD' pick is really LCx-like
        pass
    for k in kids:
        sub_nodes = subs[k]
        groove = [n_ for n_ in sub_nodes if G.nodes[n_]["LV"] < 8 and G.nodes[n_]["RV"] < 10] if k == lad_k else []
        far = farthest(Tdir, groove) if groove else farthest(Tdir, sub_nodes); trunk = set(path_to(Tdir, k, far))
        if k == lad_k: main_nm, side_nm = "LAD", "D"
        elif k == lcx_k: main_nm, side_nm = "LCx", "OM"
        else: main_nm, side_nm = "RI", "RI"
        for n_ in sub_nodes: node_name[n_] = main_nm if n_ in trunk else side_nm; node_sys[n_] = "L"
    # small spurs off the LM itself (< MIN_DAUGHTER) -> LM side twigs, keep the LM name
    for n_ in comp:
        if n_ not in node_name: node_name[n_] = "LM"; node_sys[n_] = "L"
print("systems (side, root skeleton voxels):", [(sd, n) for sd, _, n in systems], " LR scores", {k: round(v_, 1) for k, v_ in sc_lr.items()})
rows = []
for bi, path in enumerate(br):
    if not all(n_ in G for n_ in path): continue
    s = summ(path); P = np.array([G.nodes[n_]["p"] for n_ in path]); PA = to_A(P + b0)
    dd = {k: float(np.median(v[tuple(P.T)])) for k, v in [("LV", dLV), ("RV", dRV), ("LA", dLA), ("RA", dRA), ("Ao", dAo)]}
    ant = float(np.median(PA[:, 1] - mid[1])); vmed = float(np.median(Vb[tuple(P.T)]))
    names_ = [node_name.get(n_, "?") for n_ in path]; name = max(set(names_), key=names_.count)
    rows.append(dict(id=bi, name=name, system=node_sys.get(path[0], "?"), len_mm=round(s["len_mm"], 1), diam_mm=round(2 * s["r_med"], 2), diam_max_mm=round(2 * s["r_max"], 2), median_HU=round(s["hu"]), vesselness=round(vmed, 3),
                     geo_from_root_mm=[round(s["gd_min"]), round(s["gd_max"])], d_chambers={k: round(v_, 1) for k, v_ in dd.items()}, ant_mm=round(ant, 1),
                     start_A=PA[0].round(1).tolist(), end_A=PA[-1].round(1).tolist(), n=len(path)))
rows.sort(key=lambda r: -r["len_mm"])
for r in rows:
    if r["len_mm"] >= 4: print(f"  {r['name']:6s} len {r['len_mm']:6.1f}  d {r['diam_mm']:.1f}/{r['diam_max_mm']:.1f}  HU {r['median_HU']:4.0f} V {r['vesselness']:.2f} gd {r['geo_from_root_mm']}  LV {r['d_chambers']['LV']:5.1f} RV {r['d_chambers']['RV']:5.1f} LA {r['d_chambers']['LA']:5.1f} RA {r['d_chambers']['RA']:5.1f} Ao {r['d_chambers']['Ao']:5.1f} ant {r['ant_mm']:6.1f}")
NAMES = ("LM", "LAD", "D", "LCx", "OM", "RI", "RCA", "PDA", "PLV", "RV-br")
tot = {nm: round(sum(r["len_mm"] for r in rows if r["name"] == nm), 1) for nm in NAMES}
print("length by name (mm):", tot)

# ---- final mask (tree voxels whose nearest skeleton voxel survived) + mesh + centrelines ----
skel_all = np.zeros(tree.shape, bool); skel_all[tuple(pts.T)] = True
keep_sk = np.zeros(tree.shape, bool)
for n_ in G.nodes: keep_sk[G.nodes[n_]["p"]] = True
dsk, inds = ndimage.distance_transform_edt(~skel_all, sampling=sp, return_indices=True)
pass_sk = np.zeros(tree.shape, bool)
for n_ in G.nodes:
    if G.nodes[n_].get("passthru"): pass_sk[G.nodes[n_]["p"]] = True
final = tree & keep_sk[tuple(inds)] & ~(pass_sk[tuple(inds)] & (dsk > 2.0))
lf, nf = cc(final); sz = ndimage.sum(final, lf, range(1, nf + 1)) * vox_mL; final = np.isin(lf, 1 + np.where(sz >= 0.02)[0])
def mc_A(mask, offset, sigma=0.7, step=1):
    f = ndimage.gaussian_filter(np.pad(mask, 2).astype(np.float32), sigma)
    v, fc, _, _ = measure.marching_cubes(f, level=0.5, spacing=(1, 1, 1), step_size=step)
    mm = trimesh.Trimesh(to_A(v - 2 + offset), fc, process=True); trimesh.repair.fix_normals(mm); return mm
coro = mc_A(final, b0); coro.export(os.path.join(OUT, f"coronary_tree_frameA{TAG}.stl"))
if not os.path.exists(os.path.join(OUT, "heart_labels_context_frameA.stl")):        # all-label surface for renders (chambers + great vessels)
    ctx = mc_A(Hc, np.zeros(3, int), sigma=1.0, step=3); ctx = ctx.simplify_quadric_decimation(face_count=40000); ctx.export(os.path.join(OUT, "heart_labels_context_frameA.stl"))
# trunk paths: root -> farthest skeleton node of each named vessel (for CPR / naming QA)
trunks = {}
comps = list(nx.connected_components(G))
print("graph components after pruning:", [(len(c), round(min(G.nodes[n_]["td"] for n_ in c), 1), sorted({node_name.get(n_, '?') for n_ in c})) for c in comps])
root0 = min(G.nodes, key=lambda n_: G.nodes[n_]["gd"])
for nm in ("LAD", "LCx", "RCA"):
    cand = [n_ for n_, v_ in node_name.items() if (v_ == nm or (nm == "RCA" and v_ == "PDA")) and n_ in G]
    if not cand: continue
    far = max(cand, key=lambda n_: G.nodes[n_]["td"])
    src = min((n_ for n_ in G.nodes if G.nodes[n_]["td"] <= 2.0 and nx.has_path(G, n_, far)), key=lambda n_: nx.shortest_path_length(G, n_, far, weight="w"), default=None)
    if src is None: continue
    path = nx.shortest_path(G, src, far, weight="w")
    trunks[nm] = dict(pts=to_A(np.array([G.nodes[n_]["p"] for n_ in path]) + b0).round(2).tolist(), r_mm=[round(G.nodes[n_]["r"], 2) for n_ in path],
                      hu=[round(G.nodes[n_]["hu"]) for n_ in path], gd=[round(G.nodes[n_]["td"], 1) for n_ in path], names=[node_name.get(n_, "?") for n_ in path])
    print(f"trunk {nm}: {len(path)} nodes, root->tip {trunks[nm]['gd'][-1]} mm, segments {sorted(set(trunks[nm]['names']))}")
cl = {r["id"]: dict(name=r["name"], pts=to_A(np.array([G.nodes[n_]["p"] for n_ in br[r["id"]]]) + b0).round(2).tolist(), r_mm=[round(G.nodes[n_]["r"], 2) for n_ in br[r["id"]]]) for r in rows}
json.dump(dict(case=CASE, frame=("A (RAS, mm)" if _G["frame"] == "A" else "world (RAS, mm)"), frame_translation=T[:3, 3].round(4).tolist(), params=dict(BAND_MM=BAND_MM, GAP_MM=GAP_MM, HU_LO=HU_LO, HU_HI=HU_HI, V_LO=V_LO, V_IN=V_IN, HU_LO2=HU_LO2, V_LO2=V_LO2, HU_RIGHT=HU_RIGHT, HU_VEIN=HU_VEIN, HU_VEIN_BIG=HU_VEIN_BIG, D_BIG=D_BIG, D_BLOB=D_BLOB, ROOT_R_MM=ROOT_R_MM, GEO_CAP_MM=GEO_CAP_MM, SPUR_MM=SPUR_MM),
               tree_mL=round(float(final.sum() * vox_mL), 2), skeleton_len_mm=round(sum(r["len_mm"] for r in rows), 1), length_by_name_mm=tot, veins_dropped=veins, offheart_dropped=offheart, blobs_dropped=blobs, passthrough_kept=passthru,
               mesh=dict(faces=int(len(coro.faces)), watertight=bool(coro.is_watertight), volume_mL=round(abs(coro.volume) / 1000, 2)), branches=rows, centrelines=cl, trunks=trunks),
          open(os.path.join(OUT, f"coronary{TAG}.json"), "w"), indent=1)
np.savez_compressed(os.path.join(OUT, f"coronary_mask{TAG}.npz"), final=final, tree=tree, gd=gd, b0=b0, lo=lo, sp=sp, A=A, T=T)
print(f"final {final.sum()*vox_mL:.2f} mL; mesh faces {len(coro.faces)} watertight {coro.is_watertight} volume {abs(coro.volume)/1000:.2f} mL  {time.time()-t0:.0f}s")
