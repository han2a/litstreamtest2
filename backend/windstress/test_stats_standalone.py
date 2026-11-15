"""Standalone checks with known answers:  python test_stats_standalone.py"""
import importlib.util
import pathlib
import numpy as np

spec = importlib.util.spec_from_file_location(
    "stats_mod", pathlib.Path(__file__).with_name("stats.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

rng = np.random.default_rng(0)
months = np.arange("1990-01", "2020-01", dtype="datetime64[M]")
t = S.decimal_years(months)
n = len(t)

# 1. seasonal cycle + known trend 0.02/yr + white noise
season = np.sin(2 * np.pi * (S.month_of_year(months)) / 12)
y = 0.02 * (t - t[0]) + season + rng.normal(0, 0.3, n)
a = S.anomalies(y, months)
r = S.ols_trend(a, t)
assert abs(r["slope_per_year"] - 0.02) < 0.004, r
assert r["significant"], r
m = S.mann_kendall(a, t)
assert abs(m["sens_slope_per_year"] - 0.02) < 0.004, m
assert m["significant"], m

# 2. pure noise -> rarely significant (false-positive rate ~ alpha)
fp = 0
for _ in range(300):
    z = rng.normal(0, 1, n)
    fp += S.ols_trend(z, t)["significant"]
assert fp / 300 < 0.10, fp / 300

# 3. AR(1) noise: adjusted test must not be wildly over-confident
fp = 0
for _ in range(300):
    z = np.zeros(n)
    e = rng.normal(0, 1, n)
    for i in range(1, n):
        z[i] = 0.7 * z[i - 1] + e[i]
    fp += S.ols_trend(z, t)["significant"]
rate = fp / 300
print("AR(1) false-positive rate (alpha=.05):", round(rate, 3))
assert rate < 0.15, rate

# 4. field: half the pixels have a trend, half noise; FDR keeps few noise
F = rng.normal(0, 1, (n, 20, 20))
F[:, :, :10] += 0.03 * (t - t[0])[:, None, None]
F[:, 0, 0] = np.nan
res = S.trend_field(F, t)
left = res["significant_fdr"][:, :10].mean()
right = res["significant_fdr"][:, 10:].mean()
print("FDR hits trending half:", round(left, 2), " noise half:", round(right, 3))
assert left > 0.7 and right < 0.05
assert not np.isfinite(res["p_value"][0, 0])

# 5. correlation
b = a * 0.5 + rng.normal(0, 0.2, n)
c = S.correlation(a, b)
assert c["r"] > 0.6 and c["significant"]

# 6. BH sanity
p = np.array([0.001, 0.008, 0.039, 0.041, 0.6])
assert S.fdr_mask(p, 0.05).tolist() == [True, True, False, False, False]

print("all stats checks passed")
