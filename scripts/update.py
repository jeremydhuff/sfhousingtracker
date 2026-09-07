"""One command to refresh everything.

    python scripts/update.py            # fetch -> build -> scrape images -> snapshot
    python scripts/update.py --no-scrape
    python scripts/update.py --rescrape   # retry images for ALL projects

Prints a short digest. Read data/summary.md, sanity-check, then commit.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import fetch, build  # noqa: E402
from scripts.scrape import run as scrape_run  # noqa: E402

SNAP = ROOT / "data" / "snapshots" / "history.jsonl"
SUMMARY = ROOT / "site" / "data" / "summary.json"
SNAP_KEYS = [
    "under_construction_units", "under_construction_projects",
    "permitted_units", "permitted_projects",
    "active_units", "active_projects",
    "affordable_active_units",
    "completed_this_year_units", "completed_this_year_projects",
    "completed_this_year_affordable",
]


def snapshot() -> None:
    s = json.loads(SUMMARY.read_text("utf-8"))
    row = {"date": dt.date.today().isoformat(), "year": s["year"]}
    row.update({k: s[k] for k in SNAP_KEYS})

    SNAP.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if SNAP.exists():
        kept = [l for l in SNAP.read_text("utf-8").splitlines()
                if l.strip() and json.loads(l).get("date") != row["date"]]
    kept.append(json.dumps(row, separators=(",", ":")))
    SNAP.write_text("\n".join(kept) + "\n", encoding="utf-8")


def main() -> None:
    args = set(sys.argv[1:])

    print("1/4  fetching DataSF ...")
    fetch.main()

    print("\n2/4  building site data ...")
    build.main()

    if "--no-scrape" in args:
        print("\n3/4  skipping image scrape (--no-scrape)")
    else:
        print("\n3/4  scraping project images ...")
        scrape_run(force="--rescrape" in args)
        build.main()  # fold new media into projects.json

    print("\n4/4  recording snapshot ...")
    snapshot()
    build.main()  # timeseries now includes today

    print("\n" + "=" * 60)
    print((ROOT / "data" / "summary.md").read_text("utf-8"))


if __name__ == "__main__":
    main()
