"""Pull the raw datasets from DataSF into data/raw/, plus a manifest.

Each query uses $select (only the columns we need) and $where (server-side filtering)
so the files stay small. Run:  python scripts/fetch.py
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import sources as S  # noqa: E402
from scripts.socrata import query, metadata  # noqa: E402

RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "manifest.json"


def _quote_list(values: list[str]) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)


def _jan1(year: int) -> str:
    return f"{year}-01-01T00:00:00"


def build_where(src: dict) -> str | None:
    name = src["name"]
    today = dt.date.today()

    if name == "pipeline":
        statuses = list(S.CONSTRUCTION_STATUSES)
        if S.INCLUDE_BP_FILED:
            statuses.append("BP Filed")
        return (
            f"current_status in ({_quote_list(statuses)}) "
            "and (net_pipeline_units::number) > 0"
        )

    if name == "permits":
        cutoff = (today - dt.timedelta(days=30 * S.PERMIT_LOOKBACK_MONTHS)).isoformat()
        return (
            "permit_type in ('1', '2') "               # new construction only
            "and status in ('issued', 'reinstated') "
            "and proposed_units IS NOT NULL "
            "and (proposed_units::number) >= 1 "        # must add homes
            f"and issued_date > '{cutoff}T00:00:00'"
        )

    if name == "completions":
        start = _jan1(today.year - src.get("years_back", 6))
        return f"latest_completion_date >= '{start}'"

    if name == "completion_certs":
        start = _jan1(today.year - src.get("years_back", 6))
        return f"date_issued >= '{start}'"

    return None  # affordable: no filter


def fetch_source(src: dict) -> dict:
    params: dict[str, str] = {}
    select = src.get("select", ["*"])
    if select != ["*"]:
        params["$select"] = ", ".join(select)
    where = build_where(src)
    if where:
        params["$where"] = where
    params["$order"] = ":id"

    rows = query(src["resource"], params)

    try:
        meta = metadata(src["resource"])
        updated = meta.get("rowsUpdatedAt")
        source_updated = (
            dt.datetime.fromtimestamp(updated, dt.timezone.utc).isoformat()
            if updated else None
        )
    except Exception:
        source_updated = None

    (RAW / f"{src['name']}.json").write_text(
        json.dumps(rows, separators=(",", ":")), encoding="utf-8"
    )

    return {
        "source": src["name"],
        "title": src["title"],
        "resource_id": src["resource"],
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_updated_at": source_updated,
        "row_count": len(rows),
        "where": where or "",
    }


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "sources": []}

    for src in S.ALL_SOURCES:
        try:
            entry = fetch_source(src)
            manifest["sources"].append(entry)
            print(f"  {src['name']:16s} {entry['row_count']:>6d} rows  "
                  f"(updated {entry['source_updated_at'] or 'n/a'})")
        except Exception as e:
            if src.get("optional"):
                print(f"  {src['name']:16s} skipped ({e.__class__.__name__})")
                continue
            raise

    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nwrote {MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
