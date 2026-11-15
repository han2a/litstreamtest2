"""Centralised client for the Django backend. All network access to NASA and
to the LLM goes through the backend; nothing secret lives in this front end."""
from __future__ import annotations

import os

import requests

DEFAULT_URL = "http://localhost:8000"


def default_base_url() -> str:
    url = os.environ.get("EARTHEREAL_API_URL")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("EARTHEREAL_API_URL")
        except Exception:
            url = None
    return (url or DEFAULT_URL).rstrip("/")


def default_api_key() -> str | None:
    key = os.environ.get("EARTHEREAL_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("EARTHEREAL_API_KEY")
        except Exception:
            key = None
    return (key or "").strip() or None


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class BackendClient:
    def __init__(self, base_url: str | None = None, token: str | None = None,
                 api_key: str | None = None):
        self.base_url = (base_url or default_base_url()).rstrip("/")
        self.token = (token or "").strip() or None
        self.api_key = (api_key or default_api_key() or "").strip() or None

    def _request(self, method, path, *, params=None, json=None, timeout=60):
        headers = {}
        if self.token:
            headers["X-Earthdata-Token"] = self.token
        if self.api_key:
            headers["X-EarthEReal-API-Key"] = self.api_key
        try:
            r = requests.request(method, f"{self.base_url}{path}", params=params,
                                 json=json, headers=headers, timeout=timeout)
        except requests.ConnectionError:
            raise ApiError(f"Cannot reach the backend at {self.base_url}. "
                           "Check that it is running and the URL is correct.")
        except requests.Timeout:
            raise ApiError("The backend took too long to answer. Try a smaller "
                           "region or a shorter period.")
        try:
            data = r.json()
        except ValueError:
            raise ApiError(f"Backend returned a non-JSON answer (HTTP {r.status_code}).",
                           r.status_code)
        if r.status_code >= 400:
            msg = data.get("error") if isinstance(data, dict) else None
            raise ApiError(msg or f"Backend error (HTTP {r.status_code}).", r.status_code)
        return data

    def health(self):
        return self._request("GET", "/api/health/", timeout=10)

    def search(self, q: str):
        return self._request("GET", "/api/products/search/", params={"q": q}, timeout=60)

    def collection_listing(self, short_name: str):
        """POST /api/products/add/ with no variable -> collection info + variables."""
        data = self._request("POST", "/api/products/add/",
                             json={"collection": short_name}, timeout=180)
        if not data.get("needs_variable"):
            raise ApiError("Unexpected answer from /api/products/add/.")
        return data

    def add_product(self, body: dict):
        data = self._request("POST", "/api/products/add/", json=body, timeout=180)
        if "product" not in data:
            raise ApiError("Unexpected answer from /api/products/add/.")
        return data["product"]

    def analyze(self, payload: dict):
        return self._request("POST", "/api/analyze/", json=payload, timeout=1800)

    def literature(self, context: dict, question: str | None = None):
        return self._request("POST", "/api/literature/",
                             json={"context": context, "question": question or None},
                             timeout=300)

    def chat(self, messages: list, context: dict):
        return self._request("POST", "/api/chat/",
                             json={"messages": messages, "context": context}, timeout=180)
