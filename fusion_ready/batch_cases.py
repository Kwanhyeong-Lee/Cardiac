# -*- coding: utf-8 -*-
"""Step 23 -- run the CT pipeline on many MM-WHS cases and tabulate what came out.

Per case (env CASE=<id>, per-case layout CT/cases/<id>/):
  geometry -> vesselness (resumable, looped until ASSEMBLED) -> seg -> finalize -> cpr -> xsec -> hires -> territories -> great_vessels -> whole -> hollow -> checklist -> right_valves -> anatomy
Each step is a subprocess; stdout/stderr go to CT/cases/<id>/logs/<step>.log; a failing step stops that case and the
batch moves on.  Re-running skips steps whose key output exists (--force to redo).  At the end (or with --summary-only)
the per-case JSONs are collected into CT/cases/SUMMARY.md / SUMMARY.csv / summary.png.

Usage (PC1, from fusion_ready/):
  set CARDIAC_DATA=D:\\data\\MM-WHS\\ct_train
  python batch_cases.py                      # all ct_train_*_image.nii.gz found in CARDIAC_DATA
  python batch_cases.py --cases 1001 1002    # subset
  python batch_cases.py --summary-only
1009 is run in the per-case layout too (CASE_LAYOUT=cases) so all cases are comparable; its frame-A outputs under
CT/ are untouched.
"""
import os, sys, json, time, glob, subprocess, argparse, csv
HERE = os.path.dirname(os.path.abspath(__file__)); CASES_DIR = os.path.join(HERE, "CT", "cases")
MMWHS = os.environ.get("CARDIAC_DATA", "/sessions/vibrant-youthful-hopper/mnt/MM-WHS/ct_train")
PY = sys.executable
STEPS = [  # (name, script, key output relative to the case dir, extra env)
    ("geometry", "ct_case_geometry.py", "case_geometry.json", {}),
    ("vesselness", "ct_coronary_vesselness.py", "coronary/vesselness.npz", {"BUDGET_S": "100000"}),
    ("seg", "ct_coronary_seg.py", "coronary/coronary.json", {}),
    ("finalize", "ct_coronary_finalize.py", "coronary/coronary_tree_print_frameA.stl", {}),
    ("cpr", "ct_coronary_cpr.py", "coronary/coronary_cpr.png", {}),
    ("xsec", "ct_coronary_xsec.py", "coronary/coronary_xsec.png", {}),
    ("hires", "ct_hires_lv.py", "hires/hires_report.json", {}),
    ("territories", "ct_perfusion_territories.py", "territories/territory_report.json", {}),
    ("great_vessels", "ct_great_vessels.py", "labels_extended.npz", {}),
    ("whole", "build_whole_heart.py", "whole_heart_ext/whole_heart_with_coronaries.stl", {}),
    ("hollow", "build_whole_heart_hollow.py", "whole_heart_hollow/whole_heart_hollow_4ch_B.stl", {}),
    ("checklist", "ct_coronary_checklist.py", "coronary/coronary_checklist.json", {}),
    ("right_valves", "generate_right_valves.py", "valves/right_valves.json", {}),
    ("anatomy", "build_whole_heart_anatomy.py", "whole_heart_hollow/parts_manifest.json", {}),
]


def run_step(case, name, script, key, extra, force, log_dir):
    case_dir = os.path.join(CASES_DIR, case)
    if key.startswith("whole_heart_ext/") and not os.path.exists(os.path.join(case_dir, "labels_extended.npz")): key = key.replace("whole_heart_ext/", "whole_heart/")
    out = os.path.join(case_dir, key)
    if os.path.exists(out) and not force: return "skip", 0.0
    env = dict(os.environ, CASE=case, CASE_LAYOUT="cases", MPLCONFIGDIR=os.environ.get("MPLCONFIGDIR", "/tmp/mpl"), **extra)
    t = time.time(); log = open(os.path.join(log_dir, f"{name}.log"), "a", encoding="utf-8")
    for attempt in range(40):                                        # vesselness / whole are resumable and may ask to be rerun
        r = subprocess.run([PY, os.path.join(HERE, script)] + (["--stage", "all"] if name in ("whole", "hollow", "anatomy") else []), cwd=HERE, env=env, stdout=log, stderr=subprocess.STDOUT)
        if r.returncode != 0: log.close(); return f"FAIL({r.returncode})", time.time() - t
        if os.path.exists(out) and (name not in ("whole", "hollow", "anatomy") or "DONE" in open(os.path.join(log_dir, f"{name}.log"), encoding="utf-8", errors="replace").read()): break
        if name not in ("vesselness", "whole", "hollow", "anatomy"): break
    log.close()
    return ("ok" if os.path.exists(out) else "no-output"), time.time() - t


def load(p):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return None


def summarise(cases):
    rows = []
    for c in cases:
        d = os.path.join(CASES_DIR, c); g = load(os.path.join(d, "case_geometry.json")); co = load(os.path.join(d, "coronary", "coronary.json"))
        h = load(os.path.join(d, "hires", "hires_report.json")); te = load(os.path.join(d, "territories", "territory_report.json")); w = load(os.path.join(d, "whole_heart_ext", "whole_heart_report.json")) or load(os.path.join(d, "whole_heart", "whole_heart_report.json"))
        st = load(os.path.join(d, "logs", "status.json")) or {}
        L = (co or {}).get("length_by_name_mm", {}); tr = (co or {}).get("trunks", {})
        row = dict(case=c, voxel_mm="x".join(f"{v:.2f}" for v in g["voxel_mm"]) if g else "", aorta_HU=(g or {}).get("hu_by_label", {}).get("aorta", {}).get("mean", ""), contrast=(g or {}).get("contrast_note", "")[:14] if g else "",
                   LV_label_mL=(g or {}).get("volume_mL_by_label", {}).get("LV", ""),
                   LM=L.get("LM", ""), LAD=L.get("LAD", ""), D=L.get("D", ""), LCx=L.get("LCx", ""), OM=L.get("OM", ""), RCA=L.get("RCA", ""), PDA=L.get("PDA", ""), PLV=L.get("PLV", ""),
                   LAD_tip_mm=tr.get("LAD", {}).get("gd", [""])[-1] if "LAD" in tr else "", LCx_tip_mm=tr.get("LCx", {}).get("gd", [""])[-1] if "LCx" in tr else "", RCA_tip_mm=tr.get("RCA", {}).get("gd", [""])[-1] if "RCA" in tr else "",
                   tree_mL=(co or {}).get("tree_mL", ""), print_watertight=(co or {}).get("deliverables", {}).get("print_watertight", ""),
                   myo_mL=(h or {}).get("parts", {}).get("myocardium", {}).get("new", {}).get("volume_mL", ""), blood_mL=(h or {}).get("parts", {}).get("blood", {}).get("new", {}).get("volume_mL", ""),
                   LV_mass_g=(te or {}).get("lv_mass_g", ""), terr_LAD=(te or {}).get("territory_mass_g", {}).get("priors_RD", {}).get("LAD", ""), terr_LCx=(te or {}).get("territory_mass_g", {}).get("priors_RD", {}).get("LCx", ""),
                   terr_RCA=(te or {}).get("territory_mass_g", {}).get("priors_RD", {}).get("RCA", ""), far_from_visible_pct=(te or {}).get("far_from_visible_percent", ""),
                   AHA_agree=(f"{sum(r['agree'] for r in te['segments'])}/17" if te else ""), AHA_measured=(f"{sum(r['agree'] for r in te['segments'] if r['measured'])}/{sum(r['measured'] for r in te['segments'])}" if te else ""),
                   whole_watertight=(w or {}).get("union", {}).get("watertight", "") if w else "", coronary_outside_shell=(w or {}).get("union", {}).get("coronary_volume_outside_shell_frac", "") if w else "",
                   status=" ".join(f"{k}:{v}" for k, v in st.items() if v not in ("ok", "skip")) or "ok")
        rows.append(row)
    keys = list(rows[0].keys()) if rows else []
    with open(os.path.join(CASES_DIR, "SUMMARY.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=keys); wr.writeheader(); wr.writerows(rows)
    with open(os.path.join(CASES_DIR, "SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write(f"# MM-WHS CT batch — {len(rows)} cases ({time.strftime('%Y-%m-%d')})\n\nCentreline lengths in mm (topology names: LM, LAD, D = diagonals, LCx, OM = marginals, RCA, PDA, PLV); territory masses g (right-dominant map); AHA agreement overall / on measured segments.\n\n")
        f.write("| case | voxel | aorta HU | LM | LAD | D | LCx | OM | RCA | PDA | PLV | LAD tip | LCx tip | RCA tip | LV mass g | LAD/LCx/RCA g | far from tree % | AHA | whole heart | status |\n|" + "---|" * 20 + "\n")
        for r in rows:
            f.write(f"| {r['case']} | {r['voxel_mm']} | {r['aorta_HU']} | {r['LM']} | {r['LAD']} | {r['D']} | {r['LCx']} | {r['OM']} | {r['RCA']} | {r['PDA']} | {r['PLV']} | {r['LAD_tip_mm']} | {r['LCx_tip_mm']} | {r['RCA_tip_mm']} | {r['LV_mass_g']} | {r['terr_LAD']}/{r['terr_LCx']}/{r['terr_RCA']} | {r['far_from_visible_pct']} | {r['AHA_agree']} ({r['AHA_measured']}) | {r['whole_watertight']} ({r['coronary_outside_shell']}) | {r['status']} |\n")
        ok = [r for r in rows if r["status"] == "ok"]
        f.write(f"\n{len(ok)}/{len(rows)} cases ran to the end. Failures are listed per step in the status column; logs in CT/cases/<case>/logs/.\n")
    # figure
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt, numpy as np
        cs = [r["case"] for r in rows]; x = np.arange(len(cs)); fig, ax = plt.subplots(2, 1, figsize=(max(8, 0.6 * len(cs) + 3), 8))
        for i, (k, col) in enumerate([("LAD", "#d62728"), ("LCx", "#ff9f1c"), ("RCA", "#1f4fd6"), ("PDA", "#17a2b8")]):
            ax[0].bar(x + (i - 1.5) * 0.2, [float(r[k] or 0) for r in rows], 0.2, label=k, color=col)
        ax[0].set_xticks(x); ax[0].set_xticklabels(cs, rotation=45); ax[0].set_ylabel("centreline mm"); ax[0].legend(); ax[0].set_title("visible coronary tree per case")
        for i, (k, col) in enumerate([("terr_LAD", "#d62728"), ("terr_LCx", "#ff9f1c"), ("terr_RCA", "#1f4fd6")]):
            ax[1].bar(x + (i - 1) * 0.25, [float(r[k] or 0) for r in rows], 0.25, label=k[5:], color=col)
        ax[1].set_xticks(x); ax[1].set_xticklabels(cs, rotation=45); ax[1].set_ylabel("territory mass g (RD map)"); ax[1].legend(); ax[1].set_title("LV territory mass per case")
        plt.tight_layout(); plt.savefig(os.path.join(CASES_DIR, "summary.png"), dpi=90)
    except Exception as e: print("summary figure skipped:", e)
    print(f"summary -> {os.path.join(CASES_DIR, 'SUMMARY.md')}  ({len(rows)} cases)")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--cases", nargs="*"); ap.add_argument("--force", action="store_true"); ap.add_argument("--summary-only", action="store_true"); ap.add_argument("--steps", nargs="*")
    a = ap.parse_args()
    cases = a.cases or sorted(os.path.basename(p)[9:13] for p in glob.glob(os.path.join(MMWHS, "ct_train_*_image.nii.gz")))
    steps = [s for s in STEPS if not a.steps or s[0] in a.steps]
    os.makedirs(CASES_DIR, exist_ok=True)
    if not a.summary_only:
        for c in cases:
            log_dir = os.path.join(CASES_DIR, c, "logs"); os.makedirs(log_dir, exist_ok=True)
            status = load(os.path.join(log_dir, "status.json")) or {}
            print(f"== case {c}", flush=True)
            for name, script, key, extra in steps:
                st, dt = run_step(c, name, script, key, extra, a.force, log_dir); status[name] = st
                print(f"   {name:12s} {st:10s} {dt:6.0f}s", flush=True)
                json.dump(status, open(os.path.join(log_dir, "status.json"), "w"), indent=1)
                if st.startswith("FAIL") or st == "no-output": break
    summarise([c for c in cases if os.path.isdir(os.path.join(CASES_DIR, c))])


if __name__ == "__main__":
    main()
