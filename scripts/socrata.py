"""Tiny Socrata SODA client — standard library only.

Usage:
    from scripts.socrata import query
    rows = query("6jgi-cpb4", {"$select": "count(1)"})

Handles pagination, optional app token (SF_APP_TOKEN env var), and 429/5xx backoff.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://data.sfgov.org/resource/{rid}.json"
PAGE = 50_000            # Socrata hard max rows per page
TIMEOUT = 60
MAX_RETRIES = 5
USER_AGENT = "sf-housing-tracker/0.1 (local research; open data)"


def _request(url: str) -> list[dict]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    token = os.environ.get("SF_APP_TOKEN")
    if token:
        headers["X-App-Token"] = token

    delay = 2.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"Socrata HTTP {e.code} for {url}\n{body}") from None
        except urllib.error.URLError:
            if attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    return []


def query(resource_id: str, params: dict | None = None, *, paginate: bool = True) -> list[dict]:
    """Run one SoQL query. Auto-paginates unless the caller sets its own $limit."""
    params = dict(params or {})
    base_url = BASE.format(rid=resource_id)

    if not paginate or "$limit" in params:
        qs = urllib.parse.urlencode(params, safe="()*:,'/ =><")
        return _request(f"{base_url}?{qs}")

    out: list[dict] = []
    offset = 0
    while True:
        page_params = {**params, "$limit": PAGE, "$offset": offset}
        qs = urllib.parse.urlencode(page_params, safe="()*:,'/ =><")
        rows = _request(f"{base_url}?{qs}")
        out.extend(rows)
        if len(rows) < PAGE:
            break
        offset += PAGE
    return out


def metadata(resource_id: str) -> dict:
    """Fetch dataset metadata (name, rowsUpdatedAt, columns)."""
    url = f"https://data.sfgov.org/api/views/{resource_id}.json"
    data = _request(url)
    return data if isinstance(data, dict) else {}
