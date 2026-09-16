# -*- coding: utf-8 -*-
"""Paper 2 — agreement statistics with confidence intervals (PROTOCOL.md §3.1).

At n = 41 a point estimate is not reportable on its own, so every function here
returns a bootstrap interval alongside the estimate.
"""
import numpy as np
from scipy import stats

RNG = np.random.default_rng(0)
N_BOOT = 10000


# ------------------------------------------------------------- point estimates
def ccc(y, x):
    """Lin's concordance correlation coefficient."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    my, mx = y.mean(), x.mean()
    vy, vx = y.var(), x.var()
    cov = ((y - my) * (x - mx)).mean()
    return 2 * cov / (vy + vx + (my - mx) ** 2)


def bland_altman(test, ref):
    """Bias and 95% limits of agreement (test - ref)."""
    d = np.asarray(test, float) - np.asarray(ref, float)
    bias, sd = d.mean(), d.std(ddof=1)
    return dict(bias=bias, sd=sd, loa_lo=bias - 1.96 * sd, loa_hi=bias + 1.96 * sd)


def percentage_error(test, ref):
    """Critchley-Critchley percentage error: 2*SD(diff) / mean of the two methods.
    The conventional interchangeability threshold is 30%."""
    test, ref = np.asarray(test, float), np.asarray(ref, float)
    d = test - ref
    m = 0.5 * (test + ref)
    return 100.0 * 2.0 * d.std(ddof=1) / m.mean()


# ------------------------------------------------------------------ bootstrap
def _bca(stat_fn, test, ref, n_boot=N_BOOT, alpha=0.05, rng=RNG):
    """Bias-corrected and accelerated bootstrap interval."""
    n = len(test)
    theta = stat_fn(test, ref)
    idx = rng.integers(0, n, size=(n_boot, n))
    boots = np.array([stat_fn(test[i], ref[i]) for i in idx])
    boots = boots[np.isfinite(boots)]
    if boots.size < 100:
        return theta, np.nan, np.nan
    # bias correction
    z0 = stats.norm.ppf(np.clip((boots < theta).mean(), 1e-6, 1 - 1e-6))
    # acceleration from jackknife
    jk = np.array([stat_fn(np.delete(test, i), np.delete(ref, i)) for i in range(n)])
    jm = jk.mean()
    denom = 6.0 * ((jm - jk) ** 2).sum() ** 1.5
    a = ((jm - jk) ** 3).sum() / denom if denom > 0 else 0.0
    zl, zu = stats.norm.ppf(alpha / 2), stats.norm.ppf(1 - alpha / 2)
    lo_p = stats.norm.cdf(z0 + (z0 + zl) / (1 - a * (z0 + zl)))
    hi_p = stats.norm.cdf(z0 + (z0 + zu) / (1 - a * (z0 + zu)))
    return theta, float(np.quantile(boots, lo_p)), float(np.quantile(boots, hi_p))


def full_report(test, ref, label="", ci=True, n_boot=None):
    """Every pre-specified agreement statistic.

    `ci=False` returns point estimates only — used for internal (secondary) reporting,
    where the protocol does not require intervals. The primary endpoint always uses
    `ci=True`, since at n ~ 31 a point estimate carries almost no information."""
    test, ref = np.asarray(test, float), np.asarray(ref, float)
    ok = np.isfinite(test) & np.isfinite(ref)
    test, ref = test[ok], ref[ok]
    n = len(test)
    if n < 8:
        return dict(label=label, n=n, note="too few paired observations")

    stats_ = {
        "pearson_r": lambda t, r: stats.pearsonr(t, r)[0],
        "ccc": ccc,
        "bias": lambda t, r: (t - r).mean(),
        "sd_diff": lambda t, r: (t - r).std(ddof=1),
        "pct_error": percentage_error,
        "mae": lambda t, r: np.abs(t - r).mean(),
    }
    out = dict(label=label, n=n)
    for k, fn in stats_.items():
        if ci:
            est, lo, hi = _bca(fn, test, ref, n_boot=n_boot or N_BOOT)
            out[k] = round(float(est), 4)
            out[k + "_ci"] = [round(lo, 4), round(hi, 4)]
        else:
            out[k] = round(float(fn(test, ref)), 4)
    ba = bland_altman(test, ref)
    out["loa"] = [round(ba["loa_lo"], 3), round(ba["loa_hi"], 3)]

    pe = out["pct_error"]
    out["interpretation"] = (
        "interchangeable (PE < 30%)" if pe < 30 else
        "trend agreement only (30% <= PE < 45%)" if pe < 45 else
        "not transferable (PE >= 45%) — consistent with having learned the "
        "pulse-contour algorithm rather than a representation of flow")
    return out


def delong_auc(y, p1, p2):
    """DeLong test for two correlated ROC curves — used for the IOH control
    comparison (PROTOCOL.md §3.3.2), where the reported quantity is the increment
    of the waveform model over the MAP-only control."""
    y = np.asarray(y, int)
    pos, neg = np.where(y == 1)[0], np.where(y == 0)[0]
    if len(pos) < 5 or len(neg) < 5:
        return dict(note="too few events for DeLong")

    def structural(p):
        X, Y = p[pos], p[neg]
        # placement values
        v10 = np.array([(np.sum(Y < x) + 0.5 * np.sum(Y == x)) / len(Y) for x in X])
        v01 = np.array([(np.sum(X > y_) + 0.5 * np.sum(X == y_)) / len(X) for y_ in Y])
        return v10, v01, v10.mean()

    a10, a01, A = structural(np.asarray(p1, float))
    b10, b01, B = structural(np.asarray(p2, float))
    m, n = len(pos), len(neg)
    S10 = np.cov(np.vstack([a10, b10]))
    S01 = np.cov(np.vstack([a01, b01]))
    S = S10 / m + S01 / n
    var = S[0, 0] + S[1, 1] - 2 * S[0, 1]
    if var <= 0:
        return dict(auc1=A, auc2=B, delta=A - B, p=np.nan)
    z = (A - B) / np.sqrt(var)
    return dict(auc1=round(A, 4), auc2=round(B, 4), delta=round(A - B, 4),
                z=round(float(z), 3), p=float(2 * stats.norm.sf(abs(z))))
