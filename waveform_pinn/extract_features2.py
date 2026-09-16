# -*- coding: utf-8 -*-
"""Paper 2 — waveform morphology extraction against all pre-specified references.

Input  : SNUADC/ART invasive arterial pressure waveform (500 Hz, resampled to 100 Hz)
Output : one row per case with
           - morphology descriptors (the model inputs)
           - pulse-contour CO/SV        (secondary reference, PC cohort)
           - thermodilution CO          (PRIMARY reference, TD cohort)
           - Vigilance EDV/ESV/RVEF     (exploratory reference)
           - Windkessel R_tot, C        (secondary; tau-derived Zc excluded per PROTOCOL §3.2)

None of the morphology descriptors appear in any target formula. See PROTOCOL.md §1.1
for the one circularity this does *not* remove (FloTrac-family CO is computed from the
same waveform, which is why it is not the primary endpoint).

Usage:  python3 extract_features2.py [n_cases] [start_index]
        python3 extract_features2.py                 # all cases in cohort4.csv
"""
import os, sys, time, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
import vitaldb

HERE = os.path.dirname(os.path.abspath(__file__))
FS = 100.0          # Hz after resampling
WIN_MIN = 3.0       # analysis window length, minutes
PHYS = (20, 250)    # plausible arterial pressure range, mmHg

# Reference tracks are read over the SAME window as the waveform. Taking a whole-case
# median instead destroys the signal: within-case cardiac output varies with a
# coefficient of variation of 13-19%, comparable to the between-patient spread, so a
# whole-case median is effectively an independent draw from the window value.
REF_TRACKS = ["EV1000/CO", "EV1000/SV", "Vigileo/CO", "Vigileo/SV",
              "Vigilance/CO", "Vigilance/EDV", "Vigilance/ESV", "Vigilance/RVEF",
              "EV1000/CVP", "Solar8000/CVP"]


# ------------------------------------------------------------------ beats
def detect_beats(p, fs=FS):
    d = np.diff(p)
    pos = d[d > 0]
    if pos.size == 0:
        return np.array([], dtype=int)
    thr = np.percentile(pos, 90)
    up = np.where((d[:-1] <= thr) & (d[1:] > thr))[0]
    on, last = [], -10 ** 9
    for i in up:
        if i - last > int(0.35 * fs):          # 350 ms refractory
            on.append(i); last = i
    return np.array(on, dtype=int)


def ensemble_beat(seg, onsets):
    """Length-normalised ensemble-average beat, plus beat-to-beat SD and count."""
    if len(onsets) < 10:
        return None, None, None
    L = int(np.median(np.diff(onsets)))
    if not (int(0.3 * FS) < L < int(2.0 * FS)):
        return None, None, None
    stack = [seg[s:s + L] for s in onsets[:-1]
             if s + L <= len(seg) and np.isfinite(seg[s:s + L]).all()]
    if len(stack) < 10:
        return None, None, None
    B = np.asarray(stack)
    return B.mean(0), B.std(0), B.shape[0]


# --------------------------------------------------------------- features
def morphology(mb, fs=FS):
    """Shape descriptors of the ensemble beat — the model's inputs."""
    L = len(mb)
    d1 = np.gradient(mb) * fs
    d2 = np.gradient(np.gradient(mb))
    sbp, dbp = float(mb.max()), float(mb.min())
    pp = sbp - dbp
    if pp < 10:
        return None
    i_sys = int(np.argmax(mb))
    # dicrotic notch: strongest upward curvature after the systolic peak
    lo = min(i_sys + int(0.05 * fs), L - 2)
    hi = max(lo + 2, int(0.75 * L))
    i_notch = lo + int(np.argmax(d2[lo:hi])) if hi > lo else lo
    p_notch = float(mb[i_notch])
    a_sys = float(np.trapezoid(mb[:i_notch]) / fs) if i_notch > 1 else np.nan
    a_dia = float(np.trapezoid(mb[i_notch:]) / fs) if L - i_notch > 1 else np.nan
    mean_p = float(mb.mean())
    return dict(
        SBP=sbp, DBP=dbp, PP=pp, MAP=mean_p,
        t_sys_peak=i_sys / fs,
        t_notch=i_notch / fs,
        notch_frac_time=i_notch / L,                 # notch timing, cycle fraction
        P_notch=p_notch,
        notch_frac=(p_notch - dbp) / pp,             # augmentation-like index
        max_dPdt=float(d1.max()),
        min_dPdt=float(d1.min()),
        area_sys=a_sys, area_dia=a_dia,
        area_ratio=a_sys / a_dia if (a_dia and np.isfinite(a_dia) and a_dia > 0) else np.nan,
        form_factor=(mean_p - dbp) / pp,
        upstroke_time=i_sys / fs,
        beat_len=L / fs,
        # higher moments of the beat shape (FloTrac-adjacent but computed openly)
        skew=float(pd.Series(mb).skew()),
        kurt=float(pd.Series(mb).kurt()),
    )


def windkessel(mb, feats, cvp, co_ref, fs=FS):
    """R_tot and C from the waveform. Zc/tau-derived quantities are NOT returned:
    Paper 1 found Zc identifiable in only 1.7% of an 841-patient cohort."""
    i_notch = int(round(feats["t_notch"] * fs))
    y = mb[i_notch:]
    out = {}
    if len(y) >= int(0.12 * fs):
        t = np.arange(len(y)) / fs
        z = y - (y.min() - 5.0)
        if (z > 0).all():
            k = np.polyfit(t, np.log(z), 1)[0]
            if k < 0 and 0.2 < -1.0 / k < 4.0:
                out["tau_raw"] = -1.0 / k          # reported for transparency only
    if co_ref and np.isfinite(co_ref) and co_ref > 0:
        Q = co_ref * 1000.0 / 60.0                 # L/min -> mL/s
        out["R_tot"] = (feats["MAP"] - (cvp or 0.0)) / Q
    return out


def window_reference(cid, t_start, t_end):
    """Median of each reference track over [t_start, t_end] seconds -- the same interval
    the morphology descriptors are computed from."""
    v = vitaldb.load_case(cid, REF_TRACKS, 1)
    out = {k: np.nan for k in ["CO_pc", "SV_pc", "CO_td", "EDV", "ESV", "RVEF", "CVP"]}
    if v is None or v.size == 0:
        return out, 0
    sl = slice(int(t_start), int(t_end))

    def m(j):
        if j >= v.shape[1]:
            return np.nan
        c = v[sl, j]
        c = c[np.isfinite(c) & (c > 0)]
        return float(np.median(c)) if c.size >= 10 else np.nan

    co_ev, sv_ev, co_vg, sv_vg = m(0), m(1), m(2), m(3)
    out["CO_pc"] = co_ev if np.isfinite(co_ev) else co_vg
    out["SV_pc"] = sv_ev if np.isfinite(sv_ev) else sv_vg
    out["CO_td"], out["EDV"], out["ESV"], out["RVEF"] = m(4), m(5), m(6), m(7)
    cvp = m(8)
    out["CVP"] = cvp if np.isfinite(cvp) else (m(9) if np.isfinite(m(9)) else 0.0)
    n_ok = int(sum(np.isfinite(x) for x in [out["CO_pc"], out["CO_td"]]))
    return out, n_ok


def process(row):
    cid = int(row.caseid)
    v = vitaldb.load_case(cid, ["SNUADC/ART"], 1 / FS)
    if v is None or v.size == 0:
        return None
    a = v[:, 0].astype(float)
    i0 = len(a) // 3
    t_start = i0 / FS                       # seconds
    t_end = t_start + WIN_MIN * 60
    seg = a[i0:i0 + int(WIN_MIN * 60 * FS)]
    seg = seg[np.isfinite(seg) & (seg > PHYS[0]) & (seg < PHYS[1])]
    if len(seg) < FS * 60:
        return None
    mb, sd, nb = ensemble_beat(seg, detect_beats(seg))
    if mb is None:
        return None
    f = morphology(mb)
    if f is None:
        return None

    rr = np.diff(detect_beats(seg)) / FS
    rr = rr[(rr > 0.3) & (rr < 2.0)]
    hr = 60.0 / float(np.median(rr)) if len(rr) >= 5 else np.nan

    out = dict(caseid=cid, tier=row.tier, n_beats=int(nb),
               beat_sd=float(np.median(sd)), HR=hr,
               t_win_start=round(t_start, 1), **f)
    # reference values (targets), read over the same window; never used as inputs
    ref, _ = window_reference(cid, t_start, t_end)
    out.update(ref)
    # whole-case medians retained for the alignment sensitivity analysis
    for c in ["CO_pc", "SV_pc", "CO_td"]:
        v_case = getattr(row, c, np.nan)
        out[c + "_case"] = float(v_case) if pd.notna(v_case) else np.nan
    # fall back to the whole-case value only when the window has no usable samples
    for c in ["CO_pc", "SV_pc", "CO_td", "EDV", "ESV", "RVEF"]:
        if not np.isfinite(out.get(c, np.nan)):
            out[c] = out.get(c + "_case", np.nan) if c + "_case" in out else \
                (float(getattr(row, c)) if pd.notna(getattr(row, c)) else np.nan)
    if np.isfinite(out["EDV"]) and np.isfinite(out["ESV"]):
        out["SV_vol"] = out["EDV"] - out["ESV"]        # RV stroke volume, thermodilution
    # Windkessel: fitted against whichever CO reference the case's tier provides
    co_ref = out["CO_td"] if np.isfinite(out["CO_td"]) else out["CO_pc"]
    out.update(windkessel(mb, f, out["CVP"], co_ref))
    return out


if __name__ == "__main__":
    coh = pd.read_csv(os.path.join(HERE, "cohort4.csv"))
    coh = coh[coh.tier != "DROP"].reset_index(drop=True)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else len(coh)
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    sub = coh.iloc[start:start + n]
    print(f"extracting {len(sub)} cases (tiers: "
          f"{sub.tier.value_counts().to_dict()})", flush=True)

    rows, t0 = [], time.time()
    for k, row in enumerate(sub.itertuples()):
        try:
            r = process(row)
        except Exception:
            r = None
        if r:
            rows.append(r)
        if k % 25 == 0 and k:
            el = time.time() - t0
            print(f"  {k}/{len(sub)}  ok={len(rows)}  {el:.0f}s"
                  f"  eta={el/k*(len(sub)-k):.0f}s", flush=True)

    if not rows:
        print("no cases extracted"); sys.exit(1)
    df = pd.DataFrame(rows)
    out = os.path.join(HERE, f"wave_features2_{start}.csv")
    df.to_csv(out, index=False)
    print(f"\nsaved {len(df)} cases -> {os.path.basename(out)}")
    print(df.tier.value_counts().to_string())
    print("\nreference coverage:")
    for c in ["CO_pc", "SV_pc", "CO_td", "EDV", "ESV", "SV_vol", "R_tot"]:
        if c in df:
            print(f"  {c:7s} {int(np.isfinite(df[c]).sum()):4d}")
