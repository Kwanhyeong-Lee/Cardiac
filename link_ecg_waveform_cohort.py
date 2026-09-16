"""
E0: MIMIC-IV-ECG ↔ echo 코호트 링크 스캐폴드
=============================================
목적: echo 코호트(subject_id, measurement_datetime)에 12-lead ECG record를 시간창으로
      매칭하고, ECG 파생지표(HR, QRS, QTc, axis, LVH voltage)를 컬럼으로 붙여
      멀티모달 코호트 CSV를 만든다. (E1b/E1c/E4/E5 공통 선행)

⚠️ 이 스크립트는 원자료 pull이 선행되어야 실행 가능 (PhysioNet credentialed access):
   - MIMIC-IV-ECG: record_list.csv + waveform(.hea/.dat) — subject_id, ecg_time
   - (선택) neurokit2로 파형에서 지표 계산. 없으면 machine-measurement 컬럼 사용.
현재 세션 디스크에는 ECG 원자료가 없어 end-to-end 미실행(스캐폴드/문법만 검증).

실행(WSL):
   python3 link_ecg_waveform_cohort.py \
       --echo mimic_echo_full_extraction.csv \
       --ecg_list <MIMIC-IV-ECG>/record_list.csv \
       --window_hours 168 --out cohort_echo_ecg.csv
"""
from __future__ import annotations
import argparse, os, sys
import numpy as np
import pandas as pd

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--echo", default="mimic_echo_full_extraction.csv")
    ap.add_argument("--ecg_list", required=True,
                    help="MIMIC-IV-ECG record_list.csv (subject_id, ecg_time, path)")
    ap.add_argument("--window_hours", type=float, default=168.0,
                    help="echo와 ECG 최대 시간차(시간). 기본 7일")
    ap.add_argument("--waveform_root", default=None,
                    help="파형 루트(.hea/.dat). 주면 neurokit2로 지표 계산 시도")
    ap.add_argument("--out", default="cohort_echo_ecg.csv")
    return ap.parse_args()

def load_echo(path):
    df = pd.read_csv(path)
    # 시간 컬럼 정규화
    tcol = next((c for c in ["measurement_datetime", "echo_time", "charttime", "storetime"]
                 if c in df.columns), None)
    if tcol is None or "subject_id" not in df.columns:
        sys.exit(f"[!] echo CSV에 subject_id 또는 시간 컬럼 없음: cols={list(df.columns)[:12]}")
    df["_echo_time"] = pd.to_datetime(df[tcol], errors="coerce")
    return df.dropna(subset=["_echo_time"])

def load_ecg_list(path):
    df = pd.read_csv(path)
    tcol = next((c for c in ["ecg_time", "charttime", "acquisition_time"]
                 if c in df.columns), None)
    if tcol is None or "subject_id" not in df.columns:
        sys.exit(f"[!] ECG list에 subject_id/시간 컬럼 없음: cols={list(df.columns)[:12]}")
    df["_ecg_time"] = pd.to_datetime(df[tcol], errors="coerce")
    return df.dropna(subset=["_ecg_time"])

def nearest_ecg(echo, ecg, window_hours):
    """subject_id별로 echo 시각에 가장 가까운 ECG record를 창 내에서 매칭."""
    win = pd.Timedelta(hours=window_hours)
    ecg_by = {sid: g.sort_values("_ecg_time") for sid, g in ecg.groupby("subject_id")}
    rows = []
    for _, e in echo.iterrows():
        g = ecg_by.get(e["subject_id"])
        if g is None:
            continue
        dt = (g["_ecg_time"] - e["_echo_time"]).abs()
        j = dt.idxmin()
        if dt.loc[j] <= win:
            rec = g.loc[j]
            rows.append({
                "subject_id": e["subject_id"],
                "measurement_id": e.get("measurement_id"),
                "echo_time": e["_echo_time"],
                "ecg_time": rec["_ecg_time"],
                "abs_gap_hours": dt.loc[j].total_seconds() / 3600.0,
                "ecg_path": rec.get("path") or rec.get("file_name"),
            })
    return pd.DataFrame(rows)

def ecg_features(matched, waveform_root):
    """파형에서 지표 계산(neurokit2). 미설치/미보유 시 컬럼만 NaN으로 생성."""
    cols = ["ecg_HR", "ecg_QRS_ms", "ecg_QTc_ms", "ecg_PR_ms", "ecg_axis_deg",
            "ecg_Sokolow_mV", "ecg_Cornell_mV", "ecg_AF_flag"]
    for c in cols:
        matched[c] = np.nan
    if not waveform_root:
        print("[i] waveform_root 미지정 → ECG 지표는 NaN(추후 machine-measurement 병합).")
        return matched
    try:
        import wfdb, neurokit2 as nk
    except Exception as e:
        print(f"[i] wfdb/neurokit2 미설치({e}) → 지표 스킵.")
        return matched
    for i, r in matched.iterrows():
        p = r["ecg_path"]
        if not p:
            continue
        try:
            rec = wfdb.rdrecord(os.path.join(waveform_root, os.path.splitext(str(p))[0]))
            sig = rec.p_signal[:, 0]; fs = rec.fs
            _, info = nk.ecg_process(sig, sampling_rate=fs)
            matched.at[i, "ecg_HR"] = float(np.nanmean(info.get("ECG_Rate", [np.nan])))
            # 나머지 지표는 nk.ecg_delineate 등으로 확장(placeholder)
        except Exception:
            continue
    return matched

def main():
    a = parse_args()
    echo = load_echo(a.echo)
    ecg = load_ecg_list(a.ecg_list)
    print(f"[1] echo rows={len(echo)}  ECG records={len(ecg)}")
    matched = nearest_ecg(echo, ecg, a.window_hours)
    print(f"[2] 시간창 {a.window_hours}h 내 매칭 = {len(matched)} "
          f"(echo의 {len(matched)/max(len(echo),1)*100:.1f}%)")
    matched = ecg_features(matched, a.waveform_root)
    matched.to_csv(a.out, index=False)
    print(f"[✓] 저장: {a.out}  (cols={list(matched.columns)})")

if __name__ == "__main__":
    main()
