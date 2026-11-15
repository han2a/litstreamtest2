"""Optional PNG figures (base64) for clients that want them."""

import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def trend_map(lon, lat, trend, sig_fdr, title, units):
    fig, ax = plt.subplots(figsize=(11, 4))
    lim = np.nanmax(np.abs(trend)) or 1.0
    m = ax.pcolormesh(lon, lat, trend, cmap="RdBu_r", vmin=-lim, vmax=lim,
                      shading="auto")
    yy, xx = np.meshgrid(lat, lon, indexing="ij")
    ax.scatter(xx[sig_fdr], yy[sig_fdr], s=2, c="k", marker=".")
    fig.colorbar(m, ax=ax).set_label(f"{units} per decade")
    ax.set_title(f"{title}: trend (dots = significant after FDR)")
    ax.set_xlabel("Longitude (E)")
    ax.set_ylabel("Latitude")
    return _b64(fig)


def series_plot(times, values, anomalies, title, units):
    fig, ax = plt.subplots(2, 1, figsize=(11, 5), sharex=True)
    ax[0].plot(times, values, lw=1)
    ax[0].set_ylabel(units)
    ax[0].set_title(f"{title}: area mean")
    ax[1].plot(times, anomalies, lw=1, c="C1")
    ax[1].axhline(0, c="k", lw=0.5)
    ax[1].set_ylabel(f"anomaly ({units})")
    fig.autofmt_xdate()
    return _b64(fig)
