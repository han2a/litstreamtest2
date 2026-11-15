"""Selection -> backend 'add' calls -> batched /analyze. No Streamlit here."""
from __future__ import annotations

from dataclasses import dataclass, field

from api_client import ApiError
from catalog.base import match_variable


@dataclass
class Prepared:
    products: list = field(default_factory=list)   # {"descriptor","group","option","level","label"}
    ambiguous: dict = field(default_factory=dict)  # (group_key, option_key) -> candidates
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _fmt_level(level, unit):
    return "" if level is None else f" @ {level:g} {unit}"


def prepare(groups, selections, listing_fn, add_fn) -> Prepared:
    """selections: {group_key: {"options": [...], "levels": [...], "choices": {option_key: variable}}}"""
    prep = Prepared()
    for g in groups:
        sel = selections.get(g.key) or {}
        opt_keys = sel.get("options") or []
        if not opt_keys:
            continue
        try:
            listing = listing_fn(g.short_name)
        except ApiError as exc:
            prep.errors.append(f"{g.label}: {exc}")
            continue
        info = listing.get("collection") or {}
        cid = info.get("collection")
        variables = listing.get("variables") or []
        if info.get("version") and info["version"] != g.version:
            prep.warnings.append(
                f"{g.short_name}: the backend resolved version {info['version']}, expected {g.version}.")
        if not variables:
            prep.warnings.append(
                f"{g.short_name}: no variable list available (set an Earthdata token to read it from a "
                "sample file). Variables chosen by exact name could not be verified in advance.")
        for ok in opt_keys:
            opt = g.option(ok)
            comps = [g.option(k) for k in opt.components] if opt.derived else [opt]
            resolved, choices = [], sel.get("choices") or {}
            for c in comps:
                if choices.get(c.key):
                    pick = choices[c.key]
                    meta = next((v for v in variables if v["variable"] == pick), {"variable": pick})
                    cands = []
                else:
                    meta, cands = match_variable(c, variables)
                if meta is None:
                    if cands:
                        prep.ambiguous[(g.key, c.key)] = cands
                    elif not variables and not c.variable:
                        prep.errors.append(
                            f"{c.label}: needs the variable list of {g.short_name}, which requires an Earthdata token.")
                    else:
                        names = ", ".join(v["variable"] for v in variables[:20])
                        wanted = c.variable or "/".join(c.hints)
                        prep.errors.append(
                            f"{c.label}: '{wanted}' not found in {g.short_name}. Available: {names or 'none listed'}.")
                    break
                resolved.append(meta)
            if len(resolved) != len(comps):
                continue

            has_levels = any(m.get("has_levels", bool(g.levels)) for m in resolved)
            if g.levels and variables and not has_levels:
                prep.errors.append(
                    f"{opt.label}: the backend did not detect a vertical dimension in this file, so it cannot "
                    "select a pressure level. See the README (LEV_NAMES in grid.py).")
                continue
            if has_levels and not g.levels:
                prep.errors.append(f"{opt.label}: variable has vertical levels but the catalog lists none.")
                continue
            levels = list(sel.get("levels") or []) if has_levels else [None]
            if has_levels and not levels:
                prep.errors.append(f"{opt.label}: choose at least one pressure level.")
                continue

            names = [m["variable"] for m in resolved]
            for lvl in levels:
                body = {"collection": cid,
                        "label": (opt.label + _fmt_level(lvl, g.level_unit))[:120]}
                if opt.derived:
                    body["variables"], body["derive"] = names, "magnitude"
                else:
                    body["variable"] = names[0]
                if lvl is not None:
                    body["level"] = lvl
                try:
                    desc = add_fn(body)
                except ApiError as exc:
                    prep.errors.append(f"{body['label']}: {exc}")
                    continue
                prep.products.append({"descriptor": desc, "group": g.key, "option": ok,
                                      "level": lvl, "label": desc.get("label") or body["label"]})
    return prep


def run_analysis(client, products, bbox, start, end, alpha, max_products=3, progress=None):
    """Split into backend-sized batches (max products per request) and merge."""
    descs = [p["descriptor"] for p in products]
    batches = [descs[i:i + max_products] for i in range(0, len(descs), max_products)]
    merged = {"request": {"bbox": bbox, "start": start, "end": end, "alpha": alpha},
              "products": [], "cross_product_correlation": []}
    errors = []
    for i, batch in enumerate(batches, 1):
        if progress:
            progress(i, len(batches), [d.get("label") for d in batch])
        try:
            resp = client.analyze({"products": batch, "bbox": bbox, "start": start,
                                   "end": end, "alpha": alpha,
                                   "figures": False, "literature": False})
        except ApiError as exc:
            errors.append({"products": [d.get("label") for d in batch], "error": str(exc)})
            continue
        merged["products"] += resp.get("products", [])
        merged["cross_product_correlation"] += resp.get("cross_product_correlation", [])
    return merged, errors
