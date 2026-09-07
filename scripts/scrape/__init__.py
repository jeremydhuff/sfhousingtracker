"""Scrape runner: give every prominent project an image, cheaply and idempotently.

`run()` only looks at projects that don't already have an image in data/media.json,
so re-running after a data refresh costs almost nothing. Called by scripts/update.py;
also runnable directly:  python -m scripts.scrape  [--force] [--limit N]
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from config import scrape_sources as CFG  # noqa: E402
from scripts.scrape.base import save_image  # noqa: E402

PROJECTS = ROOT / "site" / "data" / "projects.json"
MEDIA_JSON = ROOT / "data" / "media.json"
SITE_MEDIA = ROOT / "site" / "media"


def _load_media() -> dict[str, dict]:
    if MEDIA_JSON.exists():
        return {m["project_id"]: m for m in json.loads(MEDIA_JSON.read_text("utf-8"))}
    return {}


def _save_media(media: dict[str, dict]) -> None:
    rows = sorted(media.values(), key=lambda m: m["project_id"])
    MEDIA_JSON.write_text(json.dumps(rows, indent=1), encoding="utf-8")


def run(*, force: bool = False, limit: int | None = None) -> dict:
    projects = json.loads(PROJECTS.read_text("utf-8"))
    media = _load_media()

    sources = [cls() for cls in CFG.ENABLED_SOURCES if getattr(cls, "enabled", True)]

    candidates = [
        p for p in projects
        if p["net_units"] >= CFG.MIN_UNITS_FOR_IMAGE
        and (force or p["id"] not in media)
    ]
    candidates.sort(key=lambda p: -p["net_units"])
    candidates = candidates[: (limit or CFG.MAX_IMAGES)]

    added = 0
    by_source: dict[str, int] = {}
    for p in candidates:
        for src in sources:
            try:
                res = src.find(p)
            except Exception as e:  # a flaky source must never break the run
                print(f"  ! {src.name} errored on {p['id']}: {e.__class__.__name__}")
                res = None
            if not res:
                continue
            rel = save_image(res, SITE_MEDIA, p["slug"],
                             allow_large=(res.source == "manual"))
            if not rel:
                continue
            media[p["id"]] = {
                "project_id": p["id"],
                "slug": p["slug"],
                "path": f"media/{rel}",
                "source": res.source,
                "source_url": res.source_url,
                "caption": res.caption,
                "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "bytes": len(res.data),
            }
            added += 1
            by_source[res.source] = by_source.get(res.source, 0) + 1
            break

    _save_media(media)
    stats = {"added": added, "total": len(media), "candidates": len(candidates),
             "by_source": by_source}
    print(f"  images: +{added} new, {len(media)} total  {by_source or ''}")
    return stats


def _main() -> None:
    force = "--force" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    run(force=force, limit=limit)


if __name__ == "__main__":
    _main()
