"""Stage 1: echo 코호트 ↔ MIMIC-IV-ECG record 시간창 매칭 (robust/resumable)."""
from __future__ import annotations
import os, sys
import numpy as np, pandas as pd
from pipelib import load_config, get_logger, ensure_dir, is_done, mark_done, first_present

def main():
    cfg = load_config(); lg = get_logger("link", cfg["runtime"]["log_level"])
    out = ensure_dir(cfg["paths"]["out_dir"]); stage = "01_link"
    outfile = os.path.join(out, "matched_echo_ecg.csv")
    if is_done(out, stage, cfg["runtime"]["resume"]) and os.path.exists(outfile):
        lg.info(f"이미 완료 → {outfile} (강제 재실행: config resume=false)"); return

    ecg_root = cfg["paths"]["ecg_root"]
    if ecg_root.startswith("FILL_ME"):
        lg.error("ecg_root 미설정. PhysioNet pull 후 config.json 채우기(RUNBOOK)."); sys.exit(2)

    echo = pd.read_csv(cfg["paths"]["echo_cohort_csv"])
    rl = pd.read_csv(os.path.join(ecg_root, "record_list.csv"))
    et = first_present(echo.columns, cfg["linkage"]["echo_time_cols"])
    gt = first_present(rl.columns, cfg["linkage"]["ecg_time_cols"])
    if not et or not gt or "subject_id" not in echo or "subject_id" not in rl:
        lg.error(f"필수 컬럼 없음. echo_time={et}, ecg_time={gt}"); sys.exit(2)
    echo["_t"] = pd.to_datetime(echo[et], errors="coerce"); echo = echo.dropna(subset=["_t"])
    rl["_t"] = pd.to_datetime(rl[gt], errors="coerce"); rl = rl.dropna(subset=["_t"])
    win = pd.Timedelta(hours=cfg["linkage"]["window_hours"])
    lg.info(f"echo={len(echo)}, ecg records={len(rl)}, window={cfg['linkage']['window_hours']}h")

    by = {sid: g.sort_values("_t") for sid, g in rl.groupby("subject_id")}
    rows = []
    for _, e in echo.iterrows():
        g = by.get(e["subject_id"])
        if g is None: continue
        dt = (g["_t"] - e["_t"]).abs(); j = dt.idxmin()
        if dt.loc[j] <= win:
            r = g.loc[j]
            rows.append({"subject_id": e["subject_id"],
                         "measurement_id": e.get("measurement_id"),
                         "echo_time": e["_t"], "ecg_time": r["_t"],
                         "abs_gap_hours": round(dt.loc[j].total_seconds()/3600, 2),
                         "study_id": r.get("study_id"),
                         "ecg_path": r.get("path") or r.get("file_name")})
    m = pd.DataFrame(rows)
    m.to_csv(outfile, index=False)
    rate = len(m)/max(len(echo), 1)*100
    lg.info(f"매칭 {len(m)} ({rate:.1f}%)  gap median={m['abs_gap_hours'].median() if len(m) else float('nan'):.1f}h")
    lg.info(f"저장 → {outfile}")
    if rate < 20: lg.warning("매칭률 낮음(<20%) → window_hours 재검토 또는 시간컬럼 확인")
    mark_done(out, stage)

if __name__ == "__main__":
    main()
