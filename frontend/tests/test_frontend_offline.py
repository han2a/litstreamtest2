from api_client import ApiError
from chat_context import series_summary
from workflow import run_analysis


def test_series_summary_ignores_missing_values_and_rounds_numbers():
    summary = series_summary({
        "time": ["2020-01", "2020-02", "2020-03"],
        "value": [1.23456, None, 3.45678],
    })

    assert summary == {
        "first": {"month": "2020-01", "value": 1.235},
        "last": {"month": "2020-03", "value": 3.457},
        "min": {"month": "2020-01", "value": 1.235},
        "max": {"month": "2020-03", "value": 3.457},
        "mean_last_12_months": 2.346,
    }


def test_run_analysis_batches_products_and_merges_responses():
    class Client:
        def __init__(self):
            self.payloads = []

        def analyze(self, payload):
            self.payloads.append(payload)
            labels = [product["label"] for product in payload["products"]]
            return {
                "products": [{"title": label} for label in labels],
                "cross_product_correlation": [{"a": labels[0], "b": labels[-1]}],
            }

    client = Client()
    progress = []
    products = [{"descriptor": {"label": label}} for label in ("A", "B", "C")]
    bbox = {"lat_min": 0, "lat_max": 1, "lon_min": 2, "lon_max": 3}

    result, errors = run_analysis(
        client, products, bbox, "2020-01", "2020-12", 0.05,
        max_products=2, progress=lambda *args: progress.append(args),
    )

    assert [len(payload["products"]) for payload in client.payloads] == [2, 1]
    assert all(payload["figures"] is False and payload["literature"] is False
               for payload in client.payloads)
    assert [product["title"] for product in result["products"]] == ["A", "B", "C"]
    assert result["cross_product_correlation"] == [
        {"a": "A", "b": "B"},
        {"a": "C", "b": "C"},
    ]
    assert result["request"] == {
        "bbox": bbox, "start": "2020-01", "end": "2020-12", "alpha": 0.05,
    }
    assert errors == []
    assert [item[:2] for item in progress] == [(1, 2), (2, 2)]


def test_run_analysis_reports_failed_batch_without_losing_successful_batch():
    class Client:
        def __init__(self):
            self.calls = 0

        def analyze(self, payload):
            self.calls += 1
            if self.calls == 2:
                raise ApiError("backend unavailable")
            return {"products": [{"title": "A"}], "cross_product_correlation": []}

    products = [{"descriptor": {"label": label}} for label in ("A", "B", "C")]
    result, errors = run_analysis(
        Client(), products, {}, "2020-01", "2020-12", 0.05, max_products=2,
    )

    assert result["products"] == [{"title": "A"}]
    assert errors == [{"products": ["C"], "error": "backend unavailable"}]
