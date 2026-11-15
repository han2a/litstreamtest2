"""Catalog primitives (pure Python, no Streamlit). The catalog holds METADATA
only: names, dataset short names, versions. It never holds data values.
Collection concept IDs are NOT stored; they are resolved live through the
backend (/api/products/add/) from the short name."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    variable: Optional[str] = None      # exact variable name, when you know it
    hints: tuple = ()                    # words matched against the file's variable list
    components: tuple = ()               # option keys; two components = derived magnitude
    description: str = ""

    @property
    def derived(self) -> bool:
        return bool(self.components)


@dataclass(frozen=True)
class Group:
    key: str
    label: str
    short_name: str                      # CMR collection short name
    version: str
    product: str
    temporal: str                        # "monthly" | "daily" | "hourly"
    files_per_month: float               # granules per month (for the file-limit estimate)
    options: tuple
    levels: tuple = ()                   # selectable vertical levels (empty = 2-D)
    default_levels: tuple = ()
    level_unit: str = "hPa"
    source_url: str = ""
    glossary_url: str = ""
    note: str = ""
    coverage: Optional[tuple] = None     # (lat_min, lat_max, lon_min, lon_max)

    def option(self, key: str) -> Option:
        return next(o for o in self.options if o.key == key)


def _norm(s) -> str:
    return re.sub(r"[_\s]+", " ", (s or "").lower()).strip()


def match_variable(option: Option, listing: list):
    """Find the file variable for an option.
    Returns (variable_dict | None, candidates). candidates is non-empty only
    when several variables fit and the user must choose."""
    by_lower = {v["variable"].lower(): v for v in listing if v.get("variable")}
    if option.variable:
        if option.variable.lower() in by_lower:
            return by_lower[option.variable.lower()], []
        if not listing:                  # cannot verify without a sample file
            return {"variable": option.variable}, []
        return None, []
    if not listing:
        return None, []
    for h in option.hints:               # a hint equal to a variable name wins
        if h.lower() in by_lower:
            return by_lower[h.lower()], []
    hints = [_norm(h) for h in option.hints]
    cands = [v for v in listing
             if all(h in _norm(f"{v.get('variable')} {v.get('long_name') or ''}")
                    for h in hints)]
    if len(cands) == 1:
        return cands[0], []
    return None, cands


def bbox_overlaps(bbox: dict, cov: tuple) -> bool:
    lat_ok = bbox["lat_min"] <= cov[1] and bbox["lat_max"] >= cov[0]
    lon_ok = any(bbox["lon_min"] + s <= cov[3] and bbox["lon_max"] + s >= cov[2]
                 for s in (-360, 0, 360))
    return lat_ok and lon_ok


def estimate_files(group: Group, n_months: int) -> int:
    """Rough granule count per product for the period (backend cap: 1500)."""
    return int(math.ceil(group.files_per_month * n_months))
