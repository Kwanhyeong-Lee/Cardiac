# -*- coding: utf-8 -*-
"""Paper 2 — Step 1: waveform morphology feature extraction (VitalDB).

WHY THIS BREAKS THE CIRCULARITY OF PAPER 1
------------------------------------------
Paper 1 fed the *arguments* of a closed-form surrogate formula (EF, SBP, DBP,
SV ...) into the network and asked it to reproduce that formula's output.
The mapping was therefore deterministic and the high R^2 carried little
information.

Here the input is the *shape* of the invasive arterial pressure waveform
(dicrotic notch timing, augmentation index, max dP/dt, systolic/diastolic
area ratio, ...). None of these appear in any of the target formulas.
The targets are:
  (a) Windkessel parameters fitted independently from the same waveform
      (R_tot, C, tau)  -- physics identification, and
  (b) device-measured CO / SV from EV1000 / Vigileo / Vigilance
      -- an independent instrument, not a formula of the inputs.

Usage
-----
    python3 extract_features.py <n_cases> <start_index>
Outputs `wave_features_<start>.csv` next to this script.
"""
import os, sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
import vitaldb

HERE = os.path.dirname(os.path.abspath(__file__))
FS = 100.0                      # Hz (VitalDB SNUADC/ART native 500 Hz)
WIN_MIN = 3.0                   # analysis window (minutes)


# ----------------------------------------------------------------- beats
def detect_beats(p, fs=FS):
    d = np.diff(p)
    pos = d[d > 0]
    if pos.size == 0:
        return np.array([], dtype=int)
    thr = np.percentile(pos, 90)
    up = np.where((d[:-1] <= thr) & (d[1:] > thr))[0]
    on, last = [], -10 ** 9
    for i in up:
        if i - last > int(0.35 * fs):        # 350 ms refractory
            on.append(i); last = i
    return np.array(on, dtype=int)


def ensemble_beat(seg, onsets):
    """Length-normalised ensemble-average beat + beat-to-beat variability."""
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


# -------------------------------------------------------------- features
def morphology(mb, fs=FS):
    """Shape descriptors of the ensemble beat. None of these enter the
    surrogate formulas used as targets in Paper 1."""
    L = len(mb)
    t = np.arange(L) / fs
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
    return dict(
        SBP=sbp, DBP=dbp, PP=pp, MAP=float(mb.mean()),
        t_sys_peak=i_sys / fs,
        t_notch=i_notch / fs,
        P_notch=p_notch,
        notch_frac=(p_notch - dbp) / pp,          # augmentation-like index
        max_dPdt=float(d1.max()),
        min_dPdt=float(d1.min()),
        area_sys=float(np.trapezoid(mb[:i_notch]) / fs),
        area_dia=float(np.trapezoid(mb[i_notch:]) / fs),
        area_ratio=float(np.trapezoid(mb[:i_notch]).sum() /
                         max(np.trapezoid(mb[i_notch:]).sum(), 1e-6)),
        form_factor=(float(mb.mean()) - dbp) / pp,
        upstroke_time=i_sys / fs,
        beat_len=L / fs,
    )


def windkessel_from_wave(mb, feats, co, sv, cvp, fs=FS):
    """2-element Windkessel identified from the SAME waveform (target set a).

    tau is fitted on the post-notch decay; R_tot uses device CO.
    NOTE: separating Zc (3-element) is NOT attempted here -- the observable
    diastolic window is shorter than tau in surgical patients (see Paper 1
    limitation), so only R_tot / C / tau are reported as identifiable.
    """
    i_notch = int(round(feats["t_notch"] * fs))
    y = mb[i_notch:]
    if len(y) < int(0.12 * fs):
        return None
    t = np.arange(len(y)) / fs
    base = y.min() - 5.0
    z = y - base
    if (z <= 0).any():
        return None
    k = np.polyfit(t, np.log(z), 1)[0]
    if k >= 0:
        return None
    tau = -1.0 / k
    if not (0.2 < tau < 4.0):
        return None
    Q = co * 1000.0 / 60.0                 # L/min -> mL/s
    if Q <= 0:
        return None
    R_tot = (feats["MAP"] - cvp) / Q
    C_tau = tau / R_tot                    # compliance implied by decay
    C_pp = sv / feats["PP"]                # pulse-pressure method
    return dict(tau=tau, R_tot=R_tot, C_tau=C_tau, C_pp=C_pp)


def process(cid, co, sv, cvp):
    v = vitaldb.load_case(int(cid), ["SNUADC/ART"], 1 / FS)
    if v is None or v.size == 0:
        return None
    a = v[:, 0].astype(float)
    i0 = len(a) // 3
    seg = a[i0:i0 + int(WIN_MIN * 60 * FS)]
    seg = seg[np.isfinite(seg) & (seg > 20) & (seg < 250)]
    if len(seg) < FS * 60:
        return None
    on = detect_beats(seg)
    mb, sd, nb = ensemble_beat(seg, on)
    if mb is None:
        return None
    f = morphology(mb)
    if f is None:
        return None
    row = dict(caseid=int(cid), n_beats=int(nb),
               beat_sd=float(np.median(sd)), **f)
    wk = windkessel_from_wave(mb, f, co, sv, cvp)
    if wk:
        row.update(wk)
    row.update(dev_CO=float(co), dev_SV=float(sv), dev_CVP=float(cvp))
    return row


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    coh = pd.read_csv(os.path.join(HERE, os.pardir,
                                   "vitaldb_validation", "cohort.csv"))
    out = []
    for _, r in coh.iloc[start:start + n].iterrows():
        try:
            res = process(r.caseid, r.CO, r.SV, r.get("CVP", 0.0) or 0.0)
        except Exception:
            res = None
        if res:
            out.append(res)
        if len(out) and len(out) % 25 == 0:
            print(f"  {len(out)} ok")
    if out:
        p = os.path.join(HERE, f"wave_features_{start}.csv")
        pd.DataFrame(out).to_csv(p, index=False)
        print(f"saved {len(out)} cases -> {os.path.basename(p)}")
    else:
        print("no cases extracted")
