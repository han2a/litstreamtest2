"""Pure-numpy grid helpers (no xarray) so they can be tested alone."""

import re

import numpy as np

LAT_NAMES = ("lat", "latitude", "y", "nav_lat")
LON_NAMES = ("lon", "longitude", "x", "nav_lon")
TIME_NAMES = ("time", "t", "valid_time")
LEV_NAMES = ("lev", "level", "plev", "pressure", "isobaricinhpa", "depth",
             "z", "height", "stdpressurelev")   # AIRS Level 3 pressure axis (verify on a real file)


def find_name(names, candidates):
    """Case-insensitive match of a dataset's dim/coord names."""
    lower = {n.lower(): n for n in names}
    for c in candidates:
        if c in lower:
            return lower[c]
    return None


def contiguous_runs(idx):
    """Sorted integer indices -> list of (start, stop) contiguous runs."""
    idx = np.asarray(idx)
    if len(idx) == 0:
        return []
    breaks = np.where(np.diff(idx) > 1)[0] + 1
    return [(int(g[0]), int(g[-1]) + 1) for g in np.split(idx, breaks)]


def lon_indices(lon_values, lon_min, lon_max):
    """Indices of grid longitudes inside [lon_min, lon_max] (0-360 box,
    may wrap across 0/360), whatever convention the file uses."""
    # 360 wide or more is the whole globe, the wrap below would keep one column
    if lon_max - lon_min >= 360:
        return np.arange(len(lon_values))
    lon360 = np.asarray(lon_values) % 360
    lon_min, lon_max = lon_min % 360, lon_max % 360
    if lon_min <= lon_max:
        mask = (lon360 >= lon_min) & (lon360 <= lon_max)
    else:
        mask = (lon360 >= lon_min) | (lon360 <= lon_max)
    return np.where(mask)[0]


def lat_slice(lat_values, lat_min, lat_max):
    lat = np.asarray(lat_values)
    idx = np.where((lat >= lat_min) & (lat <= lat_max))[0]
    if len(idx) == 0:
        return None
    return slice(int(idx[0]), int(idx[-1]) + 1)


def nearest_index(values, target):
    return int(np.argmin(np.abs(np.asarray(values, float) - target)))


_CONCEPT_RE = re.compile(r"^C\d+-[A-Z0-9_]+$")
_VAR_RE = re.compile(r"^[A-Za-z0-9_./\-]{1,80}$")


def valid_collection_id(s):
    return isinstance(s, str) and bool(_CONCEPT_RE.match(s))


def valid_variable_name(s):
    return isinstance(s, str) and bool(_VAR_RE.match(s))
