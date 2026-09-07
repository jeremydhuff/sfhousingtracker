"""Shared plumbing for image-scraper plugins.

A plugin subclasses ImageSource and implements find(project) -> ImageResult | None.
Everything network- or file-related (throttling, robots, size guards, saving) lives
here so plugins stay tiny.
"""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass
from pathlib import Path

from config import scrape_sources as CFG

_last_hit: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser] = {}

# Save guard: without a resizing library we simply refuse very large files.
MAX_SAVE_BYTES = 1_100_000
MIN_SAVE_BYTES = 2_500
_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


@dataclass
class ImageResult:
    data: bytes
    content_type: str
    caption: str
    source: str          # plugin name
    source_url: str       # page or endpoint the image came from


def _host(url: str) -> str:
    return urllib.parse.urlparse(url).netloc


def throttle(url: str) -> None:
    h = _host(url)
    wait = CFG.PER_HOST_DELAY - (time.time() - _last_hit.get(h, 0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[h] = time.time()


def robots_ok(url: str) -> bool:
    h = _host(url)
    rp = _robots.get(h)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(f"https://{h}/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None  # unreadable robots -> assume allowed
        _robots[h] = rp
    return True if rp is None else rp.can_fetch(CFG.USER_AGENT, url)


def http_get(url: str, *, want_binary: bool = False) -> tuple[bytes, str] | None:
    """GET with UA, timeout, robots check, throttle and a hard size cap."""
    if not robots_ok(url):
        return None
    throttle(url)
    req = urllib.request.Request(url, headers={"User-Agent": CFG.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=CFG.REQUEST_TIMEOUT) as resp:
            ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
            cap = CFG.MAX_IMAGE_BYTES if want_binary else 3_000_000
            data = resp.read(cap + 1)
            if len(data) > cap:
                return None
            return data, ctype
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None


def save_image(result: ImageResult, dest_dir: Path, slug: str,
               *, allow_large: bool = False) -> str | None:
    """Write the image if it passes the size/type guards. Returns relative path or None."""
    ext = _EXT.get(result.content_type)
    if not ext:
        if result.data[:3] == b"\xff\xd8\xff":
            ext = ".jpg"
        elif result.data[:8] == b"\x89PNG\r\n\x1a\n":
            ext = ".png"
        elif result.data[:4] == b"RIFF" and result.data[8:12] == b"WEBP":
            ext = ".webp"
        else:
            return None
    hi = 6_000_000 if allow_large else MAX_SAVE_BYTES
    if not (MIN_SAVE_BYTES <= len(result.data) <= hi):
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{slug}{ext}"
    (dest_dir / fname).write_bytes(result.data)
    return fname


_JPEG_IN_PDF = re.compile(
    rb"/Subtype\s*/Image\b[^>]*?/Filter\s*/DCTDecode\b[^>]*?stream\r?\n(.*?)\r?\nendstream",
    re.DOTALL,
)


def pdf_first_image(pdf: bytes, *, min_bytes: int = 15_000) -> bytes | None:
    """Pull the largest embedded JPEG out of a PDF, stdlib only.

    Handles DCTDecode (JPEG) image streams - which is what architectural
    renderings in Planning Commission packets almost always are. FlateDecode
    raster images would need to be reassembled into a PNG and are skipped.
    Returns raw JPEG bytes or None.
    """
    best = b""
    for m in _JPEG_IN_PDF.finditer(pdf):
        blob = m.group(1)
        if blob[:3] == b"\xff\xd8\xff" and len(blob) > len(best):
            best = blob
    return best if len(best) >= min_bytes else None


class ImageSource:
    name = "base"

    def find(self, project: dict) -> ImageResult | None:  # pragma: no cover - interface
        raise NotImplementedError
