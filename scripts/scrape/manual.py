"""Manual override source.

Drop an image at  media/manual/<slug>.<jpg|png|webp>  and (optionally) a caption in
media/manual/captions.json  as  {"<slug>": "caption text"}.
The <slug> is the project's `slug` field from site/data/projects.json.

This source is listed first, so a hand-picked image always beats a scraped one.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.scrape.base import ImageResult, ImageSource

MANUAL_DIR = Path(__file__).resolve().parent.parent.parent / "media" / "manual"


class ManualImages(ImageSource):
    name = "manual"

    def __init__(self) -> None:
        self._captions = {}
        cap = MANUAL_DIR / "captions.json"
        if cap.exists():
            try:
                self._captions = json.loads(cap.read_text("utf-8"))
            except json.JSONDecodeError:
                pass

    def find(self, project: dict) -> ImageResult | None:
        slug = project["slug"]
        for ext, ctype in ((".jpg", "image/jpeg"), (".jpeg", "image/jpeg"),
                           (".png", "image/png"), (".webp", "image/webp")):
            f = MANUAL_DIR / f"{slug}{ext}"
            if f.exists():
                return ImageResult(
                    data=f.read_bytes(),
                    content_type=ctype,
                    caption=self._captions.get(slug, "Provided image"),
                    source=self.name,
                    source_url=f"local:media/manual/{f.name}",
                )
        return None
