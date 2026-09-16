# -*- coding: utf-8 -*-
"""v5 — distance-based abstention (PROTOCOL.md §6).

The transplant degradation is scatter, not bias: slope 1.05, offset -0.32 L/min, but
residual SD twice that of the training speciality. An optimal affine recalibration buys
0.028 of R², so no correction factor helps. What does help is knowing which readings not
to trust — and the model's distance from its training distribution predicts its own error
(Spearman 0.23, p = 1.7e-74; median absolute error rises 0.41 -> 0.77 L/min from the
nearest to the furthest quartile).

Selective prediction: abstain on the fraction of inputs furthest from training, report
performance on what remains, and report both together as a risk-coverage curve. Never a
single accuracy figure at an unstated coverage.

Two scores are computed and compared, because the cheaper one may be enough:

    mahalanobis   full covariance of the training features
    zmean         mean absolute standardised deviation, no covariance

A third, `random`, abstains at random. It is the control: any real score must beat it,
otherwise the curve is only showing that discarding data raises accuracy on easy leftovers.
"""
import numpy as np
import pandas as pd
from scipy import stats


def fit_scores(X_train):
    """Return scoring functions calibrated on the training features."""
    mu = X_train.mean(0)
    sd = X_train.std(0) + 1e-9
    cov = np.cov(X_train, rowvar=False) + 1e-6 * np.eye(X_train.shape[1])
    inv = np.linalg.pinv(cov)

    def mahalanobis(X):
        dx = X - mu
        return np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", dx, inv, dx), 0))

    def zmean(X):
        return np.abs((X - mu) / sd).mean(1)

    return {"mahalanobis": mahalanobis, "zmean": zmean}


def risk_coverage(score, err, coverages=(1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3)):
    """Error among the retained fraction, as coverage falls.

    `score` is higher = more suspect. At each coverage the highest-scoring inputs are
    abstained on. Reported: median and 90th-percentile absolute error of what remains,
    since the tail is what matters clinically.
    """
    order = np.argsort(score)                 # most trusted first
    e = np.asarray(err)[order]
    rows = []
    for c in coverages:
        k = max(int(round(c * len(e))), 10)
        kept = e[:k]
        rows.append({"coverage": c, "n_kept": k,
                     "mae_median": float(np.median(kept)),
                     "mae_mean": float(kept.mean()),
                     "p90": float(np.percentile(kept, 90)),
                     "frac_over_1Lmin": float((kept > 1.0).mean())})
    return pd.DataFrame(rows)


def compare(scores, err, rng_seed=0):
    """Risk-coverage for each score plus a random-abstention control."""
    rng = np.random.default_rng(rng_seed)
    out = {}
    for name, s in scores.items():
        out[name] = risk_coverage(s, err)
    out["random"] = risk_coverage(rng.standard_normal(len(err)), err)
    return out


def selective_summary(scores, err):
    """One line per score: rank correlation with error, and error reduction at 70%
    coverage relative to abstaining at random."""
    rnd = risk_coverage(np.random.default_rng(0).standard_normal(len(err)), err)
    base = float(rnd.loc[rnd.coverage == 0.7, "mae_median"].iloc[0])
    rows = []
    for name, s in scores.items():
        rc = risk_coverage(s, err)
        at70 = float(rc.loc[rc.coverage == 0.7, "mae_median"].iloc[0])
        rho = stats.spearmanr(s, err)
        rows.append({"score": name,
                     "spearman_rho": round(float(rho.statistic), 3),
                     "p": float(rho.pvalue),
                     "mae_median_full": round(float(rc.loc[rc.coverage == 1.0,
                                                           "mae_median"].iloc[0]), 3),
                     "mae_median_at70": round(at70, 3),
                     "vs_random_at70": round(at70 - base, 3)})
    return pd.DataFrame(rows)
