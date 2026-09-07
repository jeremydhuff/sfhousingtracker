"""Best-effort rendering source: SF Planning project pages.

SF Planning publishes pages for many notable projects at sfplanning.org/project/<slug>,
each with an OpenGraph image that is usually the project rendering. We find the page
two ways:
  1. guess the slug from the street address (fast, no extra request when it hits);
  2. fall back to the site's WordPress search (?s=<address>) and take the first
     /project/ link.
Coverage is partial by nature - smaller projects have no page. That's expected;
parcel_aerial covers the rest.
"""

from __future__ import annotations

import re
from html import unescape

from scripts.scrape.base import ImageResult, ImageSource, http_get

BASE = "https://sfplanning.org"
OG = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', re.I)
PROJ_LINK = re.compile(r'href=["\'](https?://[^"\']*sfplanning\.org/project/[^"\'?#]+)', re.I)
TITLE = re.compile(r"<title>([^<]+)</title>", re.I)


_TYPES = {"st": "street", "ave": "avenue", "blvd": "boulevard", "rd": "road",
          "dr": "drive", "ln": "lane", "pl": "place", "ct": "court", "ter": "terrace"}


def _slug_variants(address: str) -> list[str]:
    words = re.sub(r"[^0-9a-z ]", "", (address or "").lower()).split()
    if not words:
        return []
    expanded = [_TYPES.get(w, w) for w in words]
    bare = [w for w in words if w not in _TYPES and w not in _TYPES.values()]
    seen, out = set(), []
    for parts in (expanded, words, bare):
        s = "-".join(parts)
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _extract_image(html: str, page_url: str) -> ImageResult | None:
    m = OG.search(html)
    if not m:
        return None
    img_url = unescape(m.group(1))
    if img_url.startswith("/"):
        img_url = BASE + img_url
    if not re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", img_url, re.I):
        return None
    got = http_get(img_url, want_binary=True)
    if not got:
        return None
    data, ctype = got
    tm = TITLE.search(html)
    caption = unescape(tm.group(1).split("|")[0].strip()) if tm else "SF Planning project page"
    return ImageResult(
        data=data,
        content_type=ctype or "image/jpeg",
        caption=f"Rendering via SF Planning — {caption}"[:200],
        source="sf_planning",
        source_url=page_url,
    )


class SFPlanningPage(ImageSource):
    name = "sf_planning"

    def find(self, project: dict) -> ImageResult | None:
        addr = project.get("address") or ""
        for slug in _slug_variants(addr):
            page_url = f"{BASE}/project/{slug}"
            got = http_get(page_url)
            if got:
                res = _extract_image(got[0].decode("utf-8", "replace"), page_url)
                if res:
                    return res

        from urllib.parse import quote
        got = http_get(f"{BASE}/?s={quote(addr)}")
        if not got:
            return None
        for link in PROJ_LINK.findall(got[0].decode("utf-8", "replace"))[:3]:
            page = http_get(link)
            if page:
                res = _extract_image(page[0].decode("utf-8", "replace"), link)
                if res:
                    return res
        return None
