# -*- coding: utf-8 -*-
"""VitalDB: per-patient 3-element Windkessel from INVASIVE arterial waveform.

Replaces the manuscript's single nominal case with a real cohort distribution,
and breaks the surrogate circularity: R1/R2/C come from waveform morphology
(diastolic decay + pulse pressure) plus device-measured CO/SV, not from a
closed-form formula whose own arguments were fed to the network.

Method (all standard):
  C      = SV / PP                      (pulse-pressure method)
  tau    = fit P(t)=A*exp(-t/tau)+B on diastolic decay
  R2     = tau / C
  R_tot  = (MAP - CVP) / Q_mean         (Q_mean = CO in mL/s)
  R1(Zc) = R_tot - R2                   (must be > 0)
  r_diss = R1 * (T_sys / T_cycle)
  E_diss = r_diss * SV^2 / T_sys        (dimensionally correct: mmHg*mL)
  SW     = Pes * SV,  Pes ~ 0.9*SBP     (rectangular work-loop approximation)
"""
import sys, json, warnings, os
HERE = os.path.dirname(os.path.abspath(__file__))
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
import vitaldb

FS = 100.0  # Hz (downsampled from 500)

def beats(p, fs=FS):
    """Detect beats from arterial waveform; return list of (onset, sbp_idx) indices."""
    d = np.diff(p)
    thr = np.percentile(d[d > 0], 90) if (d > 0).any() else 0
    up = np.where((d[:-1] <= thr) & (d[1:] > thr))[0]
    on = []
    last = -10**9
    for i in up:
        if i - last > int(0.35 * fs):     # refractory ~350 ms
            on.append(i); last = i
    return np.array(on)

def fit_tau(seg, fs=FS):
    """Exponential fit on diastolic decay: P = A*exp(-t/tau) + B."""
    if len(seg) < int(0.15 * fs): return np.nan
    t = np.arange(len(seg)) / fs
    B = seg.min() - 5.0
    y = seg - B
    if (y <= 0).any(): return np.nan
    k, _ = np.polyfit(t, np.log(y), 1)
    return -1.0 / k if k < 0 else np.nan

def analyze_case(cid, co, sv, cvp=0.0, minutes=3.0):
    v = vitaldb.load_case(cid, ['SNUADC/ART'], 1 / FS)
    if v is None or v.size == 0: return None
    a = v[:, 0].astype(float)
    ok = np.isfinite(a) & (a > 20) & (a < 250)
    if ok.sum() < FS * 60: return None
    # take the most stable window of `minutes` from the middle third
    i0 = len(a) // 3; n = int(minutes * 60 * FS)
    seg = a[i0:i0 + n]
    seg = seg[np.isfinite(seg) & (seg > 20) & (seg < 250)]
    if len(seg) < FS * 60: return None
    on = beats(seg)
    if len(on) < 20: return None
    rr = np.diff(on) / FS
    rr = rr[(rr > 0.3) & (rr < 2.0)]
    if len(rr) < 10: return None
    Tcyc = float(np.median(rr)); HR = 60.0 / Tcyc
    SBP = float(np.percentile(seg, 98)); DBP = float(np.percentile(seg, 2))
    MAP = float(np.mean(seg)); PP = SBP - DBP
    if PP < 10: return None
    # diastolic decay: last 60% of each beat
    taus = []
    for s, e in zip(on[:-1], on[1:]):
        L = e - s
        d0 = s + int(0.45 * L)
        t = fit_tau(seg[d0:e])
        if np.isfinite(t) and 0.3 < t < 5.0: taus.append(t)
    if len(taus) < 5: return None
    tau = float(np.median(taus))
    Q = co * 1000.0 / 60.0                      # L/min -> mL/s
    if Q <= 0 or sv <= 0: return None
    C = sv / PP                                  # mL/mmHg
    R2 = tau / C
    Rtot = (MAP - cvp) / Q
    R1 = Rtot - R2
    if not (0 < R1 < Rtot): return None          # physiologic admissibility
    Tsys = min(0.35 * Tcyc, 0.30 + 0.0
               )  # ~ejection duration; use Weissler-like fraction
    Tsys = 0.35 * Tcyc
    r_diss = R1 * (Tsys / Tcyc)
    E_diss = r_diss * sv ** 2 / Tsys             # mmHg*mL  (dimensionally correct)
    Pes = 0.9 * SBP
    SW = Pes * sv                                # mmHg*mL (rectangular loop)
    Ea = Pes / sv
    # --- Zc 분리 신뢰도 진단 ---
    Tdia = 0.55 * Tcyc                      # 관측 가능한 확산기 길이
    tau_needed = 0.9 * Rtot * C             # R2~0.9*Rtot 가정 시 필요한 시상수
    tau_ratio = Tdia / tau_needed if tau_needed > 0 else np.nan
    zc_reliable = bool(tau_ratio > 1.0)     # 창이 시상수보다 길어야 신뢰 가능
    return dict(caseid=int(cid), HR=HR, SBP=SBP, DBP=DBP, MAP=MAP, PP=PP,
                CO=co, SV=sv, CVP=cvp, tau=tau, C=C, R1=R1, R2=R2, Rtot=Rtot,
                r_diss=r_diss, E_diss=E_diss, SW=SW, Ea=Ea,
                E_diss_pct_SW=100 * E_diss / SW, n_beats=int(len(on)),
                Tdia=Tdia, tau_needed=tau_needed, tau_ratio=tau_ratio,
                R1_frac_Rtot=R1 / Rtot, zc_reliable=zc_reliable)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    coh = pd.read_csv(os.path.join(HERE, "cohort.csv"))
    out = []
    for _, r in coh.iloc[start:start + n].iterrows():
        try:
            res = analyze_case(int(r.caseid), r.CO, r.SV, r.get("CVP", 0.0) or 0.0)
        except Exception as e:
            res = None
        if res: out.append(res); print("  ok", res["caseid"], f"R1={res['R1']:.4f} R2={res['R2']:.3f} C={res['C']:.2f} r_diss={res['r_diss']:.4f}")
        else: print("  skip", int(r.caseid))
        if len(out) and len(out) % 50 == 0: print(f"  ... {len(out)} done")
    if out:
        pd.DataFrame(out).to_csv(os.path.join(HERE, f"wk_results_{start}.csv"), index=False)
        print("saved", len(out), "cases")
