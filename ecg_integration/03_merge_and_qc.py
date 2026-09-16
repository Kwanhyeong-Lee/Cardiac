"""Stage 3: ECG feature를 PINN/echo 코호트에 병합 + QC 리포트."""
from __future__ import annotations
import json, os
import numpy as np, pandas as pd
from pipelib import load_config, get_logger, ensure_dir, is_done, mark_done

def main():
    cfg = load_config(); lg = get_logger("merge", cfg["runtime"]["log_level"])
    out = ensure_dir(cfg["paths"]["out_dir"]); stage = "03_merge"
    outfile = os.path.join(out, "cohort_echo_ecg.csv")
    if is_done(out, stage, cfg["runtime"]["resume"]) and os.path.exists(outfile):
        lg.info(f"이미 완료 → {outfile}"); return

    feats = pd.read_csv(os.path.join(out, "ecg_features.csv"))
    pinn = pd.read_csv(cfg["paths"]["pinn_cohort_csv"])
    key = "measurement_id" if "measurement_id" in feats and "measurement_id" in pinn else "subject_id"
    merged = pinn.merge(feats, on=key, how="left", suffixes=("", "_ecg"))
    merged.to_csv(outfile, index=False)

    # QC 리포트
    ecg_cols = [c for c in ["qrs_duration","qtc","sokolow_lyon_mV","cornell_mV","ptfv1","af_flag"]
                if c in merged.columns]
    qc = {"n_rows": len(merged),
          "n_with_any_ecg": int(merged[ecg_cols].notna().any(axis=1).sum()) if ecg_cols else 0,
          "coverage_pct": round(float(merged[ecg_cols].notna().any(axis=1).mean()*100), 1) if ecg_cols else 0,
          "missing_by_col": {c: round(float(merged[c].isna().mean()*100), 1) for c in ecg_cols}}
    with open(os.path.join(out, "merge_qc.json"), "w", encoding="utf-8") as f:
        json.dump(qc, f, ensure_ascii=False, indent=2)
    lg.info(f"병합 {len(merged)}행, ECG 커버리지 {qc['coverage_pct']}% → {outfile}")
    lg.info(f"QC → {os.path.join(out, 'merge_qc.json')}")
    if qc["coverage_pct"] < 30:
        lg.warning("ECG 커버리지 낮음 → window/키 매칭 재검토")
    mark_done(out, stage)

if __name__ == "__main__":
    main()
