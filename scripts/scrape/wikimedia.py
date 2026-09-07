"""Keyless rendering/photo source: Wikimedia Commons.

The big, named San Francisco projects - Mission Rock, Potrero Power Station,
Treasure Island, Balboa Reservoir, Parkmerced, 5M - have Commons files with
renderings, massing diagrams or construction photos, all under CC licences and
reachable through the keyless MediaWiki API.

Coverage is deliberately narrow: we only try this for large projects (a Commons
file for a 12-unit infill almost never exists) and we only accept a file whose
title clearly matches the project, so a stray "Mission Rock Station platform"
photo doesn't get attached to the Mission Rock development.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlencode

from scripts.scrape.base import ImageResult, ImageSource, http_get

API = "https://commons.wikimedia.org/w/api.php"
MIN_UNITS = 120  # only the marquee projects are on Commons

_STOP = {
    "the", "and", "at", "san", "francisco", "street", "avenue", "boulevard",
    "road", "drive", "place", "court", "phase", "project", "development",
    "modified", "parcel", "block", "mixed", "use", "residential", "building",
    "tower", "apartments", "housing", "north", "south", "east", "west",
}
_GOOD = ("rendering", "render", "massing", "construction", "aerial", "site plan",
         "development", "proposed", "under construction")
_BAD = ("station platform", "muni metro", "light rail", "train", "locomotive",
        "streetcar", "bus ", "logo", "map of", "diagram of the")


def _tokens(name: str, address: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (name or "").lower())
    toks = [w for w in words if len(w) >= 4 and w not in _STOP]
    m = re.match(r"\s*(\d+)\s+([a-z]+)", (address or "").lower())
    if m:
        toks.append(f"{m.group(1)} {m.group(2)}")  # "1500 mission"
    return toks


class WikimediaCommons(ImageSource):
    name = "wikimedia"

    def find(self, project: dict) -> ImageResult | None:
        if project.get("net_units", 0) < MIN_UNITS:
            return None
        toks = _tokens(project.get("name", ""), project.get("address", ""))
        if not toks:
            return None

        params = {
            "action": "query", "format": "json", "formatversion": "2",
            "generator": "search", "gsrnamespace": "6", "gsrlimit": "12",
            "gsrsearch": f'{project.get("name") or project.get("address")} San Francisco',
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "820",
        }
        got = http_get(f"{API}?{urlencode(params)}")
        if not got:
            return None
        try:
            pages = json.loads(got[0].decode("utf-8", "replace"))["query"]["pages"]
        except (KeyError, ValueError, TypeError):
            return None

        for pg in pages:
            title = (pg.get("title") or "").lower()
            if not title.endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue
            if any(b in title for b in _BAD):
                continue
            if not any(t in title for t in toks):
                continue
            ii = (pg.get("imageinfo") or [{}])[0]
            src = ii.get("thumburl") or ii.get("url")
            if not src or not (ii.get("mime") or "").startswith("image/"):
                continue
            img = http_get(src, want_binary=True)
            if not img:
                continue
            meta = ii.get("extmetadata") or {}
            lic = (meta.get("LicenseShortName") or {}).get("value", "CC")
            artist = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()
            disp = pg["title"].split(":", 1)[-1].rsplit(".", 1)[0]
            cap = f"{disp} - {lic}" + (f", {artist}" if artist else "") + " (Wikimedia Commons)"
            return ImageResult(
                data=img[0],
                content_type=img[1] or ii.get("mime", "image/jpeg"),
                caption=cap[:200],
                source=self.name,
                source_url=ii.get("descriptionurl", "https://commons.wikimedia.org"),
            )
        return None
