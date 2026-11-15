"""
Live product discovery through NASA's Common Metadata Repository (CMR), the
public catalog behind Earthdata Search. This is what turns whatever the user
types in the search bar into real atmosphere / ocean products; nothing is
hard-coded.

Giovanni itself does not publish its variable list as an API, so "Giovanni
products" here means: atmosphere and ocean collections from the Giovanni
data archive (GES DISC by default) that can be read over OPeNDAP.

NOT TESTED LIVE (written without network access). Response field names follow
CMR's documented JSON; if one differs, the parsing helpers below are the only
place to adjust.
"""

import re
from datetime import date

import requests

from . import app_config as config
from .grid import valid_collection_id


def _get(path, params, headers=None):
    r = requests.get(f"{config.CMR_URL}/{path}", params=params,
                     headers=headers or {}, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    return r

def _json_object(response, endpoint):
    """Ensure CMR returned a JSON object."""
    try:
        data = response.json()
    except ValueError:
        raise ValueError(
            f"CMR returned invalid JSON from {endpoint}: "
            f"{response.text[:500]}"
        )

    if not isinstance(data, dict):
        raise ValueError(
            f"CMR returned {type(data).__name__} instead of a JSON "
            f"object from {endpoint}: {str(data)[:500]}"
        )

    return data

def _topic_filter():
    p = [(f"science_keywords[{i}][topic]", t)
         for i, t in enumerate(config.SCIENCE_TOPICS)]
    p.append(("options[science_keywords][or]", "true"))
    return p


def _provider_params():
    return [("provider", p) for p in config.providers()]


# --------------------------------------------------------------------------
# Parsing helpers (pure; unit-tested with canned responses)
# --------------------------------------------------------------------------

# def parse_collection(e):
#     return {
#         "collection": e.get("id"),
#         "short_name": e.get("short_name"),
#         "version": e.get("version_id"),
#         "title": e.get("title") or e.get("dataset_id"),
#         "summary": (e.get("summary") or "")[:300],
#         "time_start": e.get("time_start"),
#         "time_end": e.get("time_end"),
#         "provider": e.get("data_center"),
#     }


# def parse_variable(item):
#     umm = item.get("umm", {})
#     colls = [c.get("concept-id") for c in
#              (item.get("associations", {}).get("collections", []))]
#     return {
#         "variable": umm.get("Name"),
#         "long_name": umm.get("LongName"),
#         "units": umm.get("Units"),
#         "collections": [c for c in colls if c],
#     }

def parse_collection(e):
    if not isinstance(e, dict):
        raise ValueError(
            f"Expected collection dictionary, got {type(e).__name__}: {str(e)[:200]}"
        )

    return {
        "collection": e.get("id"),
        "short_name": e.get("short_name"),
        "version": e.get("version_id"),
        "title": e.get("title") or e.get("dataset_id"),
        "summary": (e.get("summary") or "")[:300],
        "time_start": e.get("time_start"),
        "time_end": e.get("time_end"),
        "provider": e.get("data_center"),
    }


# variables.json has name, long_name and concept_id at the top, umm_json has them under "umm". Both are read.

def parse_variable(item):
    if not isinstance(item, dict):
        raise ValueError(
            f"Expected variable dictionary, got {type(item).__name__}"
        )

    umm = item.get("umm") or {}
    if not isinstance(umm, dict):
        raise ValueError("CMR variable UMM is not a dictionary.")

    meta = item.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}

    associations = (
        item.get("associations")
        or meta.get("associations")
        or {}
    )

    if not isinstance(associations, dict):
        raise ValueError(
            "CMR variable associations is not a dictionary."
        )

    raw_collections = associations.get("collections") or []
    colls = []

    if isinstance(raw_collections, list):
        for collection in raw_collections:
            if isinstance(collection, dict):
                cid = (
                    collection.get("concept-id")
                    or collection.get("concept_id")
                )
            elif isinstance(collection, str):
                cid = collection
            else:
                continue

            if cid:
                colls.append(cid)

    variable_name = (
        umm.get("Name")
        or item.get("name")
        or item.get("definition")
    )

    long_name = (
        umm.get("LongName")
        or item.get("long_name")
        or variable_name
    )

    units = (
        umm.get("Units")
        or umm.get("units")
        or item.get("units")
        or item.get("Units")
    )

    return {
        "variable": variable_name,
        "long_name": long_name,
        "units": units,
        "collections": colls,
    }




def opendap_url(granule_entry):
    """Pick the OPeNDAP link out of a granule's CMR links."""
    for link in granule_entry.get("links", []):
        href = link.get("href", "")
        rel = link.get("rel", "")
        title = link.get("title") or ""
        if rel.endswith("service#") and (
                "opendap" in href.lower() or "opendap" in title.lower()):
            return re.sub(r"\.(html|dds|das|dods)$", "", href)
    return None


# --------------------------------------------------------------------------
# Search bar
# --------------------------------------------------------------------------


def search(query, limit=15):
    """
    Free text -> atmosphere/ocean collections and matching variables.
    """
    query = (query or "").strip()

    if not query:
        return {"collections": [], "variables": []}

    coll_params = [
        ("keyword", query),
        ("page_size", limit),
        ("sort_key[]", "-usage_score"),
        *_provider_params(),
        *_topic_filter()
    ]

    # Search collections
    response = _get("collections.json", coll_params)
    data = _json_object(response, "collections.json")

    feed = data.get("feed", {})

    if not isinstance(feed, dict):
        raise ValueError("Invalid CMR collections feed.")

    entries = feed.get("entry", [])

    if not isinstance(entries, list):
        raise ValueError("Invalid CMR collections entry list.")

    if any(not isinstance(e, dict) for e in entries):
        raise ValueError("CMR returned an unexpected collection entry.")

    collections = [parse_collection(e) for e in entries]

    # Search variables
    variables = []

    try:
        response = _get(
        "variables.json",
        [
            ("keyword", query),
            ("page_size", 30),
            *_provider_params(),
        ]
    )

        # data = _json_object(response, "variables.json")
        # items = data.get("items", [])

        data = _json_object(response, "variables.json")
        items = data.get("items", [])

        print("\n===== CMR VARIABLE DEBUG =====")
        print("Response keys:", list(data.keys()))
        print("Number of variable records:", len(items))

        if items:
            print("First variable record:")
            print(items[0])
            print("FIRST VARIABLE KEYS:", list(items[0].keys()))
            print("FIRST VARIABLE RECORD:", items[0])
        print("===== END DEBUG =====\n")

        if not isinstance(items, list):
            raise ValueError("Invalid CMR variables item list.")

        if any(not isinstance(i, dict) for i in items):
            raise ValueError("CMR returned an unexpected variable entry.")

        hits = [parse_variable(i) for i in items]

        ids = sorted({
            c for h in hits
            for c in h["collections"]
        })

        ok = _allowed_collections(ids)

        for h in hits:
            for cid in h["collections"]:
                if cid in ok:
                    variables.append({
                        "collection": cid,
                        "collection_title": ok[cid]["title"],
                        "variable": h["variable"],
                        "long_name": h["long_name"],
                        "units": h["units"],
                    })

    except requests.RequestException:
        pass

    return {
        "collections": collections,
        "variables": variables[:limit * 2]
    }



def _allowed_collections(ids):
    """Subset of concept ids that are atmosphere/ocean in our providers."""
    ids = [i for i in ids if valid_collection_id(i)][:100]
    if not ids:
        return {}
    params = [("concept_id[]", i) for i in ids] + [
        ("page_size", 100), *_provider_params(), *_topic_filter()]
    entries = _get("collections.json", params).json() \
        .get("feed", {}).get("entry", [])
    return {e["id"]: parse_collection(e) for e in entries}


def collection_info(collection_id):
    if not valid_collection_id(collection_id):
        raise ValueError("Invalid collection id.")
    entries = _get("collections.json", [("concept_id", collection_id)]) \
        .json().get("feed", {}).get("entry", [])
    if not entries:
        raise ValueError(f"Collection {collection_id} not found.")
    return parse_collection(entries[0])


# The id (C1276812863-GES_DISC) passes through. A short name (M2TMNXSLV) is searched in the same catalog as the search bar.
def resolve_collection(value):
    if isinstance(value, str) and valid_collection_id(value.strip()):
        return value.strip()
    if not isinstance(value, str) or not re.match(r"^[A-Za-z0-9_.\-]{2,80}$", value.strip()):
        raise ValueError(
            "'collection' needs the id from the search (like C1276812863-GES_DISC) or its short name (like M2TMNXSLV).")
    short = value.strip()
    params = [("short_name", short), ("page_size", 5), ("sort_key[]", "-usage_score"),
              *_provider_params(), *_topic_filter()]
    data = _json_object(_get("collections.json", params), "collections.json")
    entries = (data.get("feed") or {}).get("entry") or []
    if not entries:
        raise ValueError(
            "No collection with the short name '" + short + "' in " + ", ".join(config.providers())
            + ". Use the id from /api/products/search/ instead.")
    return entries[0]["id"]


# CMR may answer 400 here, collection_concept_id is not one of its variable search parameters.
# So a failed lookup gives an empty list. The sample file (needs the token) is the sure way to list them.
def collection_variables(collection_id):
    """Variables CMR has on record for the collection (may be empty)."""
    try:
        items = _get("variables.json", [("collection_concept_id", collection_id),
                                        ("page_size", 200)]).json().get("items", [])
    except (requests.RequestException, ValueError):
        return []
    return [{"variable": v["variable"], "long_name": v["long_name"],
             "units": v["units"]}
            for v in (parse_variable(i) for i in items) if v["variable"]]


# --------------------------------------------------------------------------
# Granules for a time range
# --------------------------------------------------------------------------

def _month_bounds(start, end):
    """'YYYY-MM' pandas Periods -> ISO temporal string for CMR."""
    s = date(start.year, start.month, 1)
    e = end.end_time
    return f"{s.isoformat()}T00:00:00Z,{e.strftime('%Y-%m-%dT%H:%M:%SZ')}"


def granule_urls(collection_id, start, end, limit=None):
    """OPeNDAP URLs of every granule overlapping [start, end] (Periods)."""
    limit = limit or config.MAX_GRANULES
    temporal = _month_bounds(start, end)
    urls, page = [], 1
    while True:
        r = _get("granules.json", {
            "collection_concept_id": collection_id, "temporal": temporal,
            "page_size": 2000, "page_num": page, "sort_key": "start_date"})
        hits = int(r.headers.get("CMR-Hits", 0))
        if hits > limit:
            raise ValueError(
                f"{hits} files match this range (limit {limit}). Shorten the "
                f"period or pick a monthly product.")
        entries = r.json().get("feed", {}).get("entry", [])
        for e in entries:
            u = opendap_url(e)
            if u:
                urls.append(u)
        if not entries or len(urls) >= hits or page * 2000 >= hits:
            break
        page += 1
    if not urls:
        raise ValueError(
            "No OPeNDAP-readable files found for this product and period.")
    return urls


def sample_granule_url(collection_id):
    entries = _get("granules.json", {"collection_concept_id": collection_id,
                                     "page_size": 1,
                                     "sort_key": "-start_date"}) \
        .json().get("feed", {}).get("entry", [])
    for e in entries:
        u = opendap_url(e)
        if u:
            return u
    raise ValueError("This collection has no OPeNDAP-readable files.")
