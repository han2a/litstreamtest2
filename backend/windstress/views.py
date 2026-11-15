"""
JSON API only: no templates, no forms, no buttons.

GET  /api/health/                          server up, token set
GET  /api/products/search/?q=wind+stress   search bar (live NASA catalog)
POST /api/products/add/                    "Add product": validate + describe
POST /api/analyze/                         map box + added products + period
POST /api/literature/                  literature report for supplied findings
POST /api/chat/                        context-aware chat (conversation + context)
"""

import json

import pandas as pd
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import analysis, chat, cmr, datasource, literature
from . import app_config as config

@csrf_exempt  # Allows external POST requests without a CSRF token
def run_backend(request):
    if request.method == "POST":
        # Execute your backend logic here
        return JsonResponse({"status": "executed"})
    return JsonResponse({"error": "POST required"}, status=405)
    
def _error(msg, status=400):
    return JsonResponse({"error": msg}, status=status)


def _body(request):
    try:
        body = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Body must be valid JSON.")

    if not isinstance(body, dict):
        raise ValueError("JSON body must be an object.")

    return body


# prints the full error in the terminal, same as search
def _show_traceback(title):
    import traceback
    print("\n========== " + title + " ==========")
    traceback.print_exc()
    print("======================================\n")


def _token(request):
    return (request.headers.get("X-Earthdata-Token")
            or config.env("EARTHDATA_TOKEN"))


def _validate(body, token):
    products = body.get("products")
    if (not isinstance(products, list) or not products
            or len(products) > config.MAX_PRODUCTS):
        raise ValueError(
            f"'products' must be a list of 1-{config.MAX_PRODUCTS} added products.")
    products = [datasource.normalise_descriptor(p) for p in products]

    bbox = body.get("bbox") or {}
    try:
        bbox = {k: float(bbox[k]) for k in
                ("lat_min", "lat_max", "lon_min", "lon_max")}
    except (KeyError, TypeError, ValueError):
        raise ValueError(
            "'bbox' needs numeric lat_min, lat_max, lon_min, lon_max.")
    if not (-90 <= bbox["lat_min"] < bbox["lat_max"] <= 90):
        raise ValueError("Latitude range invalid.")
    # -180 to 180 and 0 to 360 both work, so 120 to 240 (Pacific) is fine
    if not (-180 <= bbox["lon_min"] < bbox["lon_max"] <= 360
            and bbox["lon_max"] - bbox["lon_min"] <= 360):
        raise ValueError("Longitude range invalid. lon_min must be below lon_max, within -180 to 360 and at most 360 apart.")
    try:
        start, end = pd.Period(body["start"], "M"), pd.Period(body["end"], "M")
    except Exception:
        raise ValueError("'start' and 'end' must be YYYY-MM.")
    if start > end:
        raise ValueError("'start' is after 'end'.")

    alpha = float(body.get("alpha", 0.05))
    if not 0 < alpha < 0.5:
        raise ValueError("'alpha' must be between 0 and 0.5.")

    return {
        "token": token, "products": products, "bbox": bbox,
        "start": str(start), "end": str(end), "alpha": alpha,
        "figures": bool(body.get("figures", False)),
        "literature": bool(body.get("literature", False)),
        "question": body.get("question"),
        "year_from": body.get("year_from"),
    }



# for the status pill: server up, token set, archives searched
@require_GET
def health(request):
    return JsonResponse({
        "status": "online",
        "earthdata_token_set": bool(config.env("EARTHDATA_TOKEN")),
        "providers": config.providers(),
        "max_products": config.MAX_PRODUCTS,
        "literature_enabled": bool(config.env("ANTHROPIC_API_KEY")),
        "chat_enabled": bool(config.env("ANTHROPIC_API_KEY")),
    })


@require_GET
def search(request):
    import traceback

    try:
        result = cmr.search(request.GET.get("q", ""))
        return JsonResponse(result)

    except Exception as exc:
        print("\n========== CMR SEARCH ERROR ==========")
        traceback.print_exc()
        print("======================================\n")

        return _error(
            f"Catalog search failed: {type(exc).__name__}: {exc}",
            502
        )


@csrf_exempt
@require_POST
def add_product(request):
    """
    'Add product'. Body: {"collection": "C...-GES_DISC", "variable": "SLP"}
    (or "variables": [u, v] with "derive": "magnitude"; "level": 500 for 3-D).
    With no variable, returns the collection's variables to choose from.
    """
    try:
        body = _body(request)
        # short name (M2TMNXSLV) to id first
        body["collection"] = cmr.resolve_collection(body.get("collection"))
        if not (body.get("variable") or body.get("variables")):
            cid = body.get("collection")
            listed = datasource.list_variables(_token(request), cid)
            reply = {"needs_variable": True,
                     "collection": cmr.collection_info(cid),
                     "variables": listed}
            if not listed:
                reply["note"] = ("No variables listed. Send X-Earthdata-Token to read them from a sample file, "
                                 "or send the variable name yourself.")
            return JsonResponse(reply)
        return JsonResponse(
            {"product": datasource.add_product(_token(request), body)})
    except ValueError as exc:
        return _error(str(exc))
    except Exception as exc:
        _show_traceback("ADD PRODUCT ERROR")
        return _error(f"{type(exc).__name__}: {exc}", 502)


@csrf_exempt
@require_POST
def analyze(request):
    try:
        req = _validate(_body(request), _token(request))
        return JsonResponse(analysis.run(req), safe=False)
    except PermissionError as exc:
        return _error(str(exc), 401)
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception as exc:                      # upstream / data problems
        _show_traceback("ANALYZE ERROR")
        return _error(f"{type(exc).__name__}: {exc}", 502)


@csrf_exempt
@require_POST
def literature_only(request):
    try:
        body = _body(request)
        context = body["context"]
        return JsonResponse(literature.literature_report(
            context, body.get("question"), body.get("year_from")))
    except KeyError:
        return _error("'context' is required.")
    except ValueError as exc:
        return _error(str(exc))
    except Exception as exc:
        return _error(f"{type(exc).__name__}: {exc}", 502)


@csrf_exempt
@require_POST
def chat_endpoint(request):
    """Body: {"messages": [{"role": "user", "content": "..."}, ...],
              "context": {...selection and analysis summary...}}"""
    try:
        body = _body(request)
        text = chat.reply(body.get("messages"), body.get("context"))
        return JsonResponse({"reply": text, "model": config.claude_model()})
    except chat.ChatUnavailable as exc:
        return _error(str(exc), 503)
    except ValueError as exc:
        return _error(str(exc))
    except Exception as exc:
        return _error(f"{type(exc).__name__}: {exc}", 502)
