"""Stage 2: ECG 파생지표 추출.
전략(robust): (a) machine_measurements.csv에서 QRS/QT/QTc/축을 구조화로 바로 사용,
(b) LVH voltage(Sokolow/Cornell)·PTFV1은 파형에서 계산(wfdb+neurokit2, 있을 때),
(c) AF flag은 판독 statement에서 규칙 추출. 파형/패키지 없으면 해당 컬럼 NaN으로 진행."""
from __future__ import annotations
import os, re, sys
import numpy as np, pandas as pd
from pipelib import load_config, get_logger, ensure_dir, is_done, mark_done

AF_PAT = re.compile(r"atrial fibrillation|a\.?fib|\bAF\b", re.I)

def load_machine(ecg_root):
    fp = os.path.join(ecg_root, "machine_measurements.csv")
    return pd.read_csv(fp) if os.path.exists(fp) else None

def af_from_statements(row):
    txt = " ".join(str(row.get(c, "")) for c in row.index if str(c).startswith("report"))
    return int(bool(AF_PAT.search(txt)))

def waveform_voltages(ecg_root, rel_path):
    """Sokolow-Lyon, Cornell, PTFV1 (mV). 실패 시 (nan,nan,nan)."""
    try:
        import wfdb
    except Exception:
        return (np.nan, np.nan, np.nan)
    try:
        rec = wfdb.rdrecord(os.path.join(ecg_root, os.path.splitext(str(rel_path))[0]))
        sig = rec.p_signal; leads = [s.upper() for s in rec.sig_name]
        def amp(lead):  # peak-to-peak proxy(mV)
            if lead in leads:
                x = sig[:, leads.index(lead)]; x = x[~np.isnan(x)]
                return (np.nanmax(x) - np.nanmin(x)) if len(x) else np.nan
            return np.nan
        # Sokolow-Lyon: S(V1)+max(R(V5),R(V6)); Cornell: R(aVL)+S(V3) (근사: p2p amplitude)
        sl = amp("V1") + max(amp("V5"), amp("V6"))
        cor = amp("AVL") + amp("V3")
        ptfv1 = amp("V1")  # PTFV1 근사 placeholder(정밀계산은 P파 델리니에이션 필요)
        return (float(sl), float(cor), float(ptfv1))
    except Exception:
        return (np.nan, np.nan, np.nan)

def main():
    cfg = load_config(); lg = get_logger("feat", cfg["runtime"]["log_level"])
    out = ensure_dir(cfg["paths"]["out_dir"]); stage = "02_feat"
    outfile = os.path.join(out, "ecg_features.csv")
    if is_done(out, stage, cfg["runtime"]["resume"]) and os.path.exists(outfile):
        lg.info(f"이미 완료 → {outfile}"); return

    ecg_root = cfg["paths"]["ecg_root"]
    matched = pd.read_csv(os.path.join(out, "matched_echo_ecg.csv"))
    mm = load_machine(ecg_root)
    feats = cfg["features"]

    df = matched.copy()
    # (a) machine measurements 병합
    if feats["use_machine_measurements"] and mm is not None:
        key = "study_id" if "study_id" in mm and "study_id" in df else None
        cols = [c for c in feats["from_machine"] if c in mm.columns]
        if key and cols:
            df = df.merge(mm[[key] + cols + [c for c in mm.columns if str(c).startswith("report")]],
                          on=key, how="left")
            lg.info(f"machine_measurements 병합: {cols}")
        else:
            lg.warning("machine_measurements 키/컬럼 불일치 → 파형 계산에 의존")
    else:
        lg.warning("machine_measurements 미사용/없음")

    # qrs_duration 파생(onset/end 있으면)
    if "qrs_duration" not in df and {"qrs_onset", "qrs_end"} <= set(df.columns):
        df["qrs_duration"] = df["qrs_end"] - df["qrs_onset"]

    # (c) AF flag
    if feats["af_from_report"]:
        rep_cols = [c for c in df.columns if str(c).startswith("report")]
        df["af_flag"] = df.apply(af_from_statements, axis=1) if rep_cols else np.nan

    # (b) 파형 전압지표 (있을 때만; 대용량이면 시간 소요 → 로그로 진행률)
    if feats["compute_from_waveform"] and "ecg_path" in df:
        n = len(df); sl = np.full(n, np.nan); cor = np.full(n, np.nan); pt = np.full(n, np.nan)
        for i, (_, r) in enumerate(df.iterrows()):
            sl[i], cor[i], pt[i] = waveform_voltages(ecg_root, r["ecg_path"])
            if i % 500 == 0: lg.info(f"파형 {i}/{n}")
        df["sokolow_lyon_mV"], df["cornell_mV"], df["ptfv1"] = sl, cor, pt

    keep = ["subject_id", "measurement_id", "study_id", "abs_gap_hours",
            "qrs_duration", "qtc", "qt_interval", "p_axis", "qrs_axis", "t_axis",
            "sokolow_lyon_mV", "cornell_mV", "ptfv1", "af_flag"]
    df[[c for c in keep if c in df.columns]].to_csv(outfile, index=False)
    # QC: 컬럼별 결측률
    lg.info("결측률: " + ", ".join(
        f"{c}={df[c].isna().mean()*100:.0f}%" for c in keep if c in df.columns))
    lg.info(f"저장 → {outfile}")
    mark_done(out, stage)

if __name__ == "__main__":
    main()
