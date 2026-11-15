"""Plotly figures built ONLY from what /api/analyze returned."""
from __future__ import annotations

import re
from collections import OrderedDict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PALETTE = ["#22d3c5", "#f59e0b", "#a78bfa", "#f472b6", "#60a5fa", "#34d399", "#fb7185"]
BG, GRID, TXT = "#0c1c2e", "#1b3045", "#b7c9da"


def _style(fig, height=380):
    fig.update_layout(height=height, paper_bgcolor=BG, plot_bgcolor=BG,
                      font=dict(color=TXT), margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", y=1.12))
    fig.update_xaxes(gridcolor=GRID)
    fig.update_yaxes(gridcolor=GRID)
    return fig


def series_figure(products, kind="value"):
    """kind: 'value' (area mean) or 'anomaly' (deseasonalised). One row per unit."""
    groups = OrderedDict()
    for i, p in enumerate(products):
        groups.setdefault(p.get("units") or "", []).append((i, p))
    fig = make_subplots(rows=len(groups), cols=1, shared_xaxes=True, vertical_spacing=0.08)
    for row, (units, items) in enumerate(groups.items(), 1):
        for i, p in items:
            am = p["area_mean"]
            fig.add_trace(go.Scatter(x=am["time"], y=am[kind], mode="lines", name=p["title"],
                                     line=dict(width=2, color=PALETTE[i % len(PALETTE)])),
                          row=row, col=1)
        label = f"anomaly ({units})" if kind == "anomaly" else (units or "value")
        fig.update_yaxes(title_text=label, row=row, col=1)
    return _style(fig, 300 + 160 * len(groups))


def _display_lon(lon, z):
    """Backend longitudes are 0-360. Use -180..180 when that gives a tighter box."""
    lon = np.asarray(lon, float)
    alt = np.where(lon > 180, lon - 360, lon)
    if np.ptp(alt) < np.ptp(lon):
        order = np.argsort(alt)
        return alt[order], np.asarray(z)[:, order]
    return lon, np.asarray(z)


def _grid(m, key):
    z = np.array(m[key], dtype=float)
    lon, z = _display_lon(m["lon"], z)
    return np.asarray(m["lat"], float), lon, z


def has_values(m, key) -> bool:
    return bool(m) and bool(np.isfinite(np.array(m[key], dtype=float)).any())


def mean_map_figure(p):
    lat, lon, z = _grid(p["mean_map"], "value")
    fig = go.Figure(go.Heatmap(x=lon, y=lat, z=z, colorscale="Viridis", hoverongaps=False,
                               colorbar=dict(title=dict(text=p.get("units") or ""))))
    fig.update_xaxes(title="Longitude (E)")
    fig.update_yaxes(title="Latitude")
    fig.update_layout(title=f"{p['title']}: period mean")
    return _style(fig, 420)


def trend_map_figure(p):
    tm = p["trend_map"]
    lat, lon, z = _grid(tm, "slope_per_decade")
    lim = float(np.nanmax(np.abs(z))) if np.isfinite(z).any() else 1.0
    fig = go.Figure(go.Heatmap(x=lon, y=lat, z=z, colorscale="RdBu_r", zmid=0,
                               zmin=-lim, zmax=lim, hoverongaps=False,
                               colorbar=dict(title=dict(text=f"{p.get('units') or ''} / decade"))))
    sig = np.array(tm["significant_fdr"], dtype=bool)
    _, _, sig_o = _display_lon(tm["lon"], sig.astype(float))
    yy, xx = np.meshgrid(lat, lon, indexing="ij")
    mask = sig_o > 0.5
    if mask.sum():
        step = max(1, int(np.ceil(mask.sum() / 3000)))
        fig.add_trace(go.Scatter(x=xx[mask][::step], y=yy[mask][::step], mode="markers",
                                 marker=dict(size=3, color="black"), name="significant (FDR)",
                                 hoverinfo="skip"))
    fig.update_xaxes(title="Longitude (E)")
    fig.update_yaxes(title="Latitude")
    fig.update_layout(title=f"{p['title']}: trend (dots = significant after FDR)")
    return _style(fig, 420)


def _profile_points(products):
    """Series of (level, mean, lo, hi). Either one variable at several levels,
    or geopotential height variables named H<level> (H1000, H850, ...)."""
    series, hvars = OrderedDict(), []
    for p in products:
        d = p["descriptor"]
        mean = p["statistics"]["mean"]
        pt = (mean["mean"], mean["ci"][0], mean["ci"][1])
        v = (d.get("variables") or [""])[0]
        m = re.fullmatch(r"H(\d{1,4})", v)
        if m and not d.get("derive"):
            hvars.append((float(m.group(1)),) + pt)
        elif d.get("level") is not None:
            key = re.sub(r"\s@.*$", "", p["title"])
            series.setdefault(key, []).append((float(d["level"]),) + pt)
    if len(hvars) >= 2:
        series["Geopotential height"] = hvars
    return {k: sorted(v) for k, v in series.items() if len(v) >= 2}


def profile_figure(products):
    series = _profile_points(products)
    if not series:
        return None
    fig = go.Figure()
    for i, (name, pts) in enumerate(series.items()):
        lv = [p[0] for p in pts]
        fig.add_trace(go.Scatter(
            x=[p[1] for p in pts], y=lv, mode="lines+markers", name=name,
            line=dict(color=PALETTE[i % len(PALETTE)]),
            error_x=dict(type="data", symmetric=False,
                         array=[p[3] - p[1] for p in pts], arrayminus=[p[1] - p[2] for p in pts])))
    fig.update_yaxes(title="Pressure level (hPa)", type="log", autorange="reversed")
    fig.update_xaxes(title="Period area mean (bars: confidence interval)")
    fig.update_layout(title="Vertical profile of period-mean values")
    return _style(fig, 420)


def difference_figure(pa, pb):
    """A minus B, computed in the dashboard from the backend's area-mean series."""
    a = dict(zip(pa["area_mean"]["time"], pa["area_mean"]["value"]))
    b = dict(zip(pb["area_mean"]["time"], pb["area_mean"]["value"]))
    t = [k for k in a if k in b and a[k] is not None and b[k] is not None]
    fig = go.Figure(go.Scatter(x=t, y=[a[k] - b[k] for k in t], mode="lines",
                               line=dict(color=PALETTE[1], width=2)))
    fig.add_hline(y=0, line_color="#31536a")
    fig.update_yaxes(title=f"difference ({pa.get('units') or ''})")
    fig.update_layout(title=f"{pa['title']} minus {pb['title']} (derived in the dashboard)")
    return _style(fig, 340)


def stats_dataframe(products) -> pd.DataFrame:
    rows = []
    for p in products:
        s = p["statistics"]
        m, o, k = s["mean"], s["trend_ols"], s["trend_mann_kendall"]
        rows.append({
            "Product": p["title"], "Units": p.get("units"), "Months": p.get("n_months"),
            "Mean": round(m["mean"], 4), "Mean CI": f"{m['ci'][0]:.4g} to {m['ci'][1]:.4g}",
            "OLS trend / decade": round(o["slope_per_decade"], 4),
            "OLS CI": f"{o['ci_per_decade'][0]:.4g} to {o['ci_per_decade'][1]:.4g}",
            "OLS p": round(o["p_value"], 4),
            "Sen slope / decade": round(k["sens_slope_per_decade"], 4),
            "MK p": round(k["p_value"], 4),
            "Grid pts significant (FDR)": f"{100 * p['trend_map']['fraction_significant_fdr']:.1f}%",
            "Resampled to monthly": bool(p.get("resampled_to_monthly")),
        })
    return pd.DataFrame(rows)
