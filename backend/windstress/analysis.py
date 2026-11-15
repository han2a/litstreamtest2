"""Orchestrates: stream data -> statistics -> (optional) literature report."""

import numpy as np

from . import datasource, literature, plots, stats


def _area_mean(da):
    w = np.cos(np.deg2rad(da["lat"]))
    w = w / w.sum()
    valid = da.notnull()
    num = (da.fillna(0) * w).sum(dim=["lat", "lon"])
    den = (valid * w).sum(dim=["lat", "lon"])
    return (num / den.where(den > 0)).values


def _clean(a):
    """numpy -> JSON-safe nested lists (NaN -> None)."""
    a = np.asarray(a, dtype=float)
    return np.where(np.isfinite(a), a, None).tolist()


def _stride(n, cap=160):
    return max(1, int(np.ceil(n / cap)))


def analyse_product(token, descriptor, start, end, bbox, alpha, figures):
    product = datasource.normalise_descriptor(descriptor)
    product_id = product["id"]
    da = datasource.load_product(token, product, start, end, bbox)
    product["title"] = product["label"]
    product["units"] = da.attrs.get("units", "")

    times = da["time"].values
    t = stats.decimal_years(times)
    anoms = stats.anomalies(da.values, times)
    mean_series = _area_mean(da)
    anom_series = stats.anomalies(mean_series, times)

    out = {
        "product": product_id,
        "descriptor": product,
        "title": product["title"],
        "resampled_to_monthly": bool(da.attrs.get("resampled_to_monthly")),
        "units": product["units"],
        "n_months": int(len(times)),
        "area_mean": {
            "time": [str(x)[:7] for x in times],
            "value": _clean(mean_series),
            "anomaly": _clean(anom_series),
        },
        "statistics": {
            "mean": stats.mean_with_ci(mean_series, alpha),
            "trend_ols": stats.ols_trend(anom_series, t, alpha),
            "trend_mann_kendall": stats.mann_kendall(anom_series, t, alpha),
        },
    }

    tf = stats.trend_field(anoms, t, alpha)
    la, lo = _stride(da.sizes["lat"]), _stride(da.sizes["lon"])
    lat, lon = da["lat"].values[::la], da["lon"].values[::lo]
    out["trend_map"] = {
        "lat": lat.tolist(), "lon": lon.tolist(),
        "slope_per_decade": _clean(tf["slope_per_decade"][::la, ::lo]),
        "significant_fdr": tf["significant_fdr"][::la, ::lo].tolist(),
        "fraction_significant_local": tf["fraction_significant_local"],
        "fraction_significant_fdr": tf["fraction_significant_fdr"],
        "note": ("Per-pixel OLS trend on deseasonalised anomalies, "
                 "autocorrelation-adjusted; significance via "
                 "Benjamini-Hochberg FDR."),
    }
    clim = np.nanmean(da.values, axis=0)
    out["mean_map"] = {"lat": lat.tolist(), "lon": lon.tolist(),
                       "value": _clean(clim[::la, ::lo])}

    if figures:
        out["figures"] = {
            "trend_map_png_base64": plots.trend_map(
                da["lon"].values, da["lat"].values,
                tf["slope_per_decade"], tf["significant_fdr"],
                product["title"], product["units"]),
            "series_png_base64": plots.series_plot(
                times, mean_series, anom_series,
                product["title"], product["units"]),
        }
    return out, anom_series, t


def run(request):
    """request: validated dict from the view."""
    token, alpha = request["token"], request["alpha"]
    results, anom_by_product, t_ref = [], {}, None
    for desc in request["products"]:
        res, anom, t = analyse_product(
            token, desc, request["start"], request["end"], request["bbox"],
            alpha, request["figures"])
        results.append(res)
        anom_by_product[res["product"]] = anom
        t_ref = t

    response = {"request": {"products": [r["product"] for r in results],
                            **{k: request[k] for k in
                               ("bbox", "start", "end", "alpha")}},
                "products": results}

    ids = list(anom_by_product)
    if len(ids) >= 2:
        response["cross_product_correlation"] = [
            {"a": a, "b": b,
             **stats.correlation(anom_by_product[a], anom_by_product[b],
                                 alpha)}
            for i, a in enumerate(ids) for b in ids[i + 1:]
        ]

    if request["literature"]:
        b = request["bbox"]
        context = {
            "product_titles": [r["title"] for r in results],
            "region": (f"{b['lat_min']} to {b['lat_max']} N, "
                       f"{b['lon_min']} to {b['lon_max']} E"),
            "period": f"{request['start']} to {request['end']}",
            "findings": [
                {"product": r["title"], "units": r["units"],
                 "mean": r["statistics"]["mean"]["mean"],
                 "ols_trend_per_decade":
                     r["statistics"]["trend_ols"]["slope_per_decade"],
                 "ols_p": r["statistics"]["trend_ols"]["p_value"],
                 "mk_p": r["statistics"]["trend_mann_kendall"]["p_value"],
                 "fraction_pixels_significant_fdr":
                     r["trend_map"]["fraction_significant_fdr"]}
                for r in results],
        }
        response["literature"] = literature.literature_report(
            context, request.get("question"), request.get("year_from"))
    return response
