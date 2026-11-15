"""
Statistical significance for monthly climate series and fields.
Pure numpy/scipy (no xarray) so it can be tested on its own.

Workflow: remove the monthly climatology (seasonal cycle) -> anomalies ->
trend tests that account for autocorrelation -> field significance via FDR.
"""

import numpy as np
from scipy import stats as st


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def decimal_years(times):
    """times: array of datetime64 (monthly). Returns decimal years."""
    t = np.asarray(times).astype("datetime64[M]")
    months = t.astype(int)               # months since 1970-01
    return 1970 + (months + 0.5) / 12.0


def month_of_year(times):
    t = np.asarray(times).astype("datetime64[M]").astype(int)
    return (t % 12).astype(int)          # 0..11


def anomalies(values, times):
    """Subtract the monthly climatology. values: (T, ...)."""
    values = np.asarray(values, dtype=float)
    moy = month_of_year(times)
    out = np.empty_like(values)
    for m in range(12):
        sel = moy == m
        if sel.any():
            out[sel] = values[sel] - np.nanmean(values[sel], axis=0)
    return out


def lag1(x):
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    d = np.sum(x * x)
    return 0.0 if d == 0 else float(np.sum(x[1:] * x[:-1]) / d)


def effective_n(n, r1):
    """Bretherton et al. (1999) effective sample size; r1 clipped to [0, .99]."""
    r = min(max(r1, 0.0), 0.99)
    return max(n * (1 - r) / (1 + r), 3.0)


# --------------------------------------------------------------------------
# Single time series
# --------------------------------------------------------------------------

def ols_trend(y, t, alpha=0.05):
    """OLS trend with an autocorrelation-adjusted p-value and CI."""
    y = np.asarray(y, float)
    t = np.asarray(t, float)
    ok = np.isfinite(y)
    y, t = y[ok], t[ok]
    n = len(y)
    if n < 8:
        raise ValueError("Need at least 8 valid points for a trend test.")

    tc = t - t.mean()
    sxx = np.sum(tc ** 2)
    slope = np.sum(tc * (y - y.mean())) / sxx
    intercept = y.mean() - slope * t.mean()
    resid = y - (intercept + slope * t)
    r1 = lag1(resid)
    n_eff = effective_n(n, r1)
    s2 = np.sum(resid ** 2) / (n - 2)
    se = np.sqrt(s2 / sxx) * np.sqrt(n / n_eff)
    dof = max(n_eff - 2, 1.0)
    tval = slope / se if se > 0 else np.inf
    p = 2 * st.t.sf(abs(tval), dof)
    half = st.t.ppf(1 - alpha / 2, dof) * se
    return {
        "slope_per_year": float(slope),
        "slope_per_decade": float(slope * 10),
        "ci_per_decade": [float((slope - half) * 10),
                          float((slope + half) * 10)],
        "p_value": float(p),
        "n": int(n),
        "lag1_autocorr_residuals": float(r1),
        "n_effective": float(n_eff),
        "significant": bool(p < alpha),
    }


def _mk_core(y):
    """Mann-Kendall S, tie-corrected variance, Z, two-sided p."""
    n = len(y)
    diff = np.sign(y[None, :] - y[:, None])
    s = np.sum(np.triu(diff, k=1))
    _, counts = np.unique(y, return_counts=True)
    var = (n * (n - 1) * (2 * n + 5)
           - np.sum(counts * (counts - 1) * (2 * counts + 5))) / 18.0
    if s > 0:
        z = (s - 1) / np.sqrt(var)
    elif s < 0:
        z = (s + 1) / np.sqrt(var)
    else:
        z = 0.0
    return float(s), float(z), float(2 * st.norm.sf(abs(z)))


def sens_slope(y, t):
    i, j = np.triu_indices(len(y), k=1)
    dt = t[j] - t[i]
    keep = dt != 0
    return float(np.median((y[j] - y[i])[keep] / dt[keep]))


def mann_kendall(y, t, alpha=0.05, prewhiten=True):
    """
    Non-parametric trend test with Sen's slope. With prewhiten=True uses
    trend-free pre-whitening (Yue et al. 2002) so serial correlation does not
    inflate significance.
    """
    y = np.asarray(y, float)
    t = np.asarray(t, float)
    ok = np.isfinite(y)
    y, t = y[ok], t[ok]
    if len(y) < 8:
        raise ValueError("Need at least 8 valid points for Mann-Kendall.")

    slope = sens_slope(y, t)
    used = y
    r1 = 0.0
    if prewhiten:
        detr = y - slope * t
        r1 = lag1(detr)
        if r1 > 0:
            pw = detr[1:] - r1 * detr[:-1]
            used = pw + slope * t[1:]
    s, z, p = _mk_core(np.asarray(used))
    return {
        "sens_slope_per_year": slope,
        "sens_slope_per_decade": slope * 10,
        "mk_S": s,
        "mk_Z": z,
        "p_value": p,
        "prewhitened": bool(prewhiten and r1 > 0),
        "lag1_autocorr_detrended": float(r1),
        "n": int(len(y)),
        "significant": bool(p < alpha),
    }


def mean_with_ci(y, alpha=0.05):
    y = np.asarray(y, float)
    y = y[np.isfinite(y)]
    n = len(y)
    n_eff = effective_n(n, lag1(y))
    se = y.std(ddof=1) / np.sqrt(n_eff)
    half = st.t.ppf(1 - alpha / 2, max(n_eff - 1, 1)) * se
    return {"mean": float(y.mean()), "ci": [float(y.mean() - half),
                                           float(y.mean() + half)],
            "std": float(y.std(ddof=1)), "n_effective": float(n_eff)}


def correlation(a, b, alpha=0.05):
    """Pearson r between two anomaly series; dof from effective n."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    n = len(a)
    if n < 8:
        raise ValueError("Need at least 8 paired points.")
    r = float(np.corrcoef(a, b)[0, 1])
    n_eff = min(effective_n(n, lag1(a)), effective_n(n, lag1(b)))
    dof = max(n_eff - 2, 1.0)
    tval = r * np.sqrt(dof / max(1 - r * r, 1e-12))
    p = float(2 * st.t.sf(abs(tval), dof))
    return {"r": r, "p_value": p, "n": int(n), "n_effective": float(n_eff),
            "significant": bool(p < alpha)}


# --------------------------------------------------------------------------
# Fields (T, lat, lon)
# --------------------------------------------------------------------------

def fdr_mask(p, alpha=0.05):
    """Benjamini-Hochberg: True where p survives false-discovery control."""
    p = np.asarray(p, float)
    flat = p.ravel()
    ok = np.isfinite(flat)
    pv = flat[ok]
    m = len(pv)
    keep = np.zeros_like(flat, dtype=bool)
    if m == 0:
        return keep.reshape(p.shape)
    order = np.argsort(pv)
    thresh = alpha * (np.arange(1, m + 1) / m)
    passed = pv[order] <= thresh
    if passed.any():
        cutoff = pv[order][np.max(np.where(passed)[0])]
        keep[np.where(ok)[0]] = pv <= cutoff
    return keep.reshape(p.shape)


def trend_field(anoms, t, alpha=0.05):
    """
    Pixelwise OLS trend (vectorised) with autocorrelation-adjusted p-values,
    then Benjamini-Hochberg FDR for field significance.
    anoms: (T, lat, lon) with NaN over land.
    """
    A = np.asarray(anoms, float)
    T = A.shape[0]
    flat = A.reshape(T, -1)
    valid = np.all(np.isfinite(flat), axis=0)
    slope = np.full(flat.shape[1], np.nan)
    pval = np.full(flat.shape[1], np.nan)

    if valid.any():
        Y = flat[:, valid]
        tc = np.asarray(t, float) - np.mean(t)
        sxx = np.sum(tc ** 2)
        Yc = Y - Y.mean(axis=0)
        b = (tc[:, None] * Yc).sum(axis=0) / sxx
        resid = Yc - tc[:, None] * b
        denom = np.sum(resid ** 2, axis=0)
        num = np.sum(resid[1:] * resid[:-1], axis=0)
        r1 = np.where(denom > 0, num / np.where(denom > 0, denom, 1), 0.0)
        r1 = np.clip(r1, 0, 0.99)
        n_eff = np.maximum(T * (1 - r1) / (1 + r1), 3.0)
        se = np.sqrt(denom / (T - 2) / sxx) * np.sqrt(T / n_eff)
        with np.errstate(divide="ignore", invalid="ignore"):
            tval = np.where(se > 0, b / se, np.inf)
        p = 2 * st.t.sf(np.abs(tval), np.maximum(n_eff - 2, 1.0))
        slope[valid] = b
        pval[valid] = p

    shape = A.shape[1:]
    slope = slope.reshape(shape)
    pval = pval.reshape(shape)
    sig_local = pval < alpha
    sig_fdr = fdr_mask(pval, alpha)
    nvalid = int(np.isfinite(pval).sum())
    return {
        "slope_per_decade": slope * 10,
        "p_value": pval,
        "significant_local": sig_local,
        "significant_fdr": sig_fdr,
        "fraction_significant_local": float(sig_local.sum() / max(nvalid, 1)),
        "fraction_significant_fdr": float(sig_fdr.sum() / max(nvalid, 1)),
    }
