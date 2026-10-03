"""One command to refresh everything.

    python scripts/update.py            # fetch -> build -> scrape images -> snapshot
    python scripts/update.py --no-scrape
    python scripts/update.py --rescrape   # retry images for ALL projects
    python scripts/update.py --no-push    # refresh locally, don't commit/push

Starts by fast-forwarding to GitHub and ends by committing + pushing, so this folder,
the git repo and the live site all end the run identical. Prints a short digest.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
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


def git(*a: str, check: bool = True) -> str:
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"git {' '.join(a)} failed: {r.stdout}{r.stderr}")
    return r.stdout.strip()


def sync_down() -> None:
    """Fast-forward to origin so the run starts from what GitHub has."""
    git("fetch", "origin")
    git("pull", "--ff-only", "--autostash")


def sync_up(summary_line: str) -> None:
    """Commit everything and push, then confirm local == origin."""
    git("add", "-A")
    if git("status", "--porcelain"):
        git("commit", "-m", f"data refresh {dt.date.today().isoformat()}; {summary_line}")
    git("push", "origin", "HEAD")
    git("fetch", "origin")
    ahead_behind = git("rev-list", "--left-right", "--count", "HEAD...@{u}")
    if ahead_behind.split() != ["0", "0"] or git("status", "--porcelain"):
        sys.exit(f"NOT in sync with GitHub (ahead/behind: {ahead_behind})")
    print(f"synced: local folder == origin == {git('rev-parse', '--short', 'HEAD')}")


def main() -> None:
    args = set(sys.argv[1:])
    push = "--no-push" not in args

    if push:
        print("0/5  syncing from GitHub ...")
        sync_down()

    print("1/4  fetching DataSF ...")
    fetch.main()

    print("\n2/4  building site data ...")
    # build.main() runs up to 3x per refresh below; each rebuild would otherwise read
    # the *previous call's own output* as "the last run" and the real since-last-refresh
    # diff would collapse to zero. Capture the true pre-refresh baseline once and thread
    # it through every call; only the final call (whose output actually sticks) logs it.
    baseline = build.main(log_changes=False)

    if "--no-scrape" in args:
        print("\n3/4  skipping image scrape (--no-scrape)")
    else:
        print("\n3/4  scraping project images ...")
        scrape_run(force="--rescrape" in args)
        build.main(baseline, log_changes=False)  # fold new media into projects.json

    print("\n4/4  recording snapshot ...")
    snapshot()
    build.main(baseline, log_changes=True)  # timeseries now includes today

    print("\n" + "=" * 60)
    summary = (ROOT / "data" / "summary.md").read_text("utf-8")
    print(summary)

    if push:
        print("5/5  committing + pushing ...")

        def n(label: str) -> str:
            m = re.search(rf"\*\*{label}\*\* \((\d+)\)", summary)
            return m[1] if m else "0"

        sync_up(f"{n('Completed')} completed, {n('Newly permitted')} newly permitted, "
                f"{n('Started construction')} broke ground")
    else:
        print("(--no-push: local only; GitHub not updated)")


if __name__ == "__main__":
    main()
