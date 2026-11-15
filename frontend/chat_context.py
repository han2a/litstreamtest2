"""Compact, JSON-safe summary of the selection and the backend's results, sent
to the chatbot. Only numbers the backend computed are included."""
from __future__ import annotations


def _r(x, n=4):
    if x is None:
        return None
    try:
        return float(f"{float(x):.{n}g}")
    except (TypeError, ValueError):
        return None


def series_summary(area_mean: dict) -> dict:
    pts = [(t, v) for t, v in zip(area_mean.get("time", []), area_mean.get("value", []))
           if v is not None]
    if not pts:
        return {}
    vals = [v for _, v in pts]
    lo = min(pts, key=lambda p: p[1])
    hi = max(pts, key=lambda p: p[1])
    last12 = vals[-12:]
    return {"first": {"month": pts[0][0], "value": _r(pts[0][1])},
            "last": {"month": pts[-1][0], "value": _r(pts[-1][1])},
            "min": {"month": lo[0], "value": _r(lo[1])},
            "max": {"month": hi[0], "value": _r(hi[1])},
            "mean_last_12_months": _r(sum(last12) / len(last12))}


def summarize_product(p: dict) -> dict:
    d, st = p.get("descriptor", {}), p.get("statistics", {})
    mean, ols, mk = st.get("mean", {}), st.get("trend_ols", {}), st.get("trend_mann_kendall", {})
    tm = p.get("trend_map", {})
    return {
        "label": p.get("title"), "units": p.get("units"),
        "collection": d.get("collection"), "variables": d.get("variables"),
        "derive": d.get("derive"), "level": d.get("level"),
        "months": p.get("n_months"),
        "resampled_from_finer_time_steps_to_monthly": p.get("resampled_to_monthly"),
        "area_mean": {"mean": _r(mean.get("mean")), "ci": [_r(c) for c in mean.get("ci", [])],
                      "std": _r(mean.get("std"))},
        "ols_trend_per_decade": {"slope": _r(ols.get("slope_per_decade")),
                                 "ci": [_r(c) for c in ols.get("ci_per_decade", [])],
                                 "p": _r(ols.get("p_value")), "significant": ols.get("significant")},
        "mann_kendall": {"sens_slope_per_decade": _r(mk.get("sens_slope_per_decade")),
                         "p": _r(mk.get("p_value")), "significant": mk.get("significant")},
        "fraction_grid_points_with_significant_trend_fdr": _r(tm.get("fraction_significant_fdr")),
        "series": series_summary(p.get("area_mean", {})),
    }


def build_context(tab, selected, request, analysis, stale, other_tab_has_results=False):
    ctx = {"active_tab": tab, "selected_variables": selected,
           "region_and_period": request,
           "analysis_available": bool(analysis and analysis.get("results")),
           "analysis_stale": bool(stale),
           "other_tab_has_results": other_tab_has_results}
    if ctx["analysis_available"]:
        res = analysis["results"]
        ctx["latest_analysis"] = {
            "request": res.get("request"),
            "products": [summarize_product(p) for p in res.get("products", [])],
            "cross_product_correlation": [
                {"a": c["a"], "b": c["b"], "r": _r(c.get("r")), "p": _r(c.get("p_value")),
                 "n": c.get("n"), "significant": c.get("significant")}
                for c in res.get("cross_product_correlation", [])],
            "failed_requests": analysis.get("errors", []),
        }
    return ctx


def literature_context(results: dict, request: dict) -> dict:
    """Same shape the backend builds in analysis.run for its literature step."""
    b = request["bbox"]
    prods = results.get("products", [])
    return {
        "product_titles": [p["title"] for p in prods],
        "region": f"{b['lat_min']} to {b['lat_max']} N, {b['lon_min']} to {b['lon_max']} E",
        "period": f"{request['start']} to {request['end']}",
        "findings": [
            {"product": p["title"], "units": p.get("units"),
             "mean": p["statistics"]["mean"]["mean"],
             "ols_trend_per_decade": p["statistics"]["trend_ols"]["slope_per_decade"],
             "ols_p": p["statistics"]["trend_ols"]["p_value"],
             "mk_p": p["statistics"]["trend_mann_kendall"]["p_value"],
             "fraction_pixels_significant_fdr": p["trend_map"]["fraction_significant_fdr"]}
            for p in prods],
    }
