"""Transform data/raw/*.json into the small JSON files the site reads, plus a digest.

Pure transform - no network. Run:  python scripts/build.py
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import sources as S  # noqa: E402

RAW = ROOT / "data" / "raw"
SNAP = ROOT / "data" / "snapshots" / "history.jsonl"
MEDIA_JSON = ROOT / "data" / "media.json"
SUMMARY_MD = ROOT / "data" / "summary.md"
OUT = ROOT / "site" / "data"
MANIFEST = ROOT / "data" / "manifest.json"

YEAR = dt.date.today().year


# --------------------------------------------------------------------------- utils
def num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def iint(x) -> int:
    return int(round(num(x)))


def load(name: str) -> list[dict]:
    p = RAW / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def norm_blocklot(*vals) -> str:
    for v in vals:
        if v:
            s = re.sub(r"[^0-9A-Za-z]", "", str(v)).upper()
            if s:
                return s
    return ""


def slugify(s: str) -> str:
    return re.sub(r"[^0-9a-z]+", "-", (s or "").lower()).strip("-") or "x"


_ORD = re.compile(r"\b(\d+)(st|nd|rd|th)\b", re.I)
# Trailing unit designators the city tacks on: "750 Presidio Av #0", "123 Main St Unit 4B".
_UNIT_TAG = re.compile(r"\s*(?:#\s*[\w-]+|\b(?:unit|apt\.?|ste\.?)\s+[\w-]+)\s*$", re.I)


def _strip_unit(s: str) -> str:
    s = _UNIT_TAG.sub("", s).strip()
    return re.sub(r"[\s*#.,\-/&]+$", "", s).strip()


def _fix_caps(s: str) -> str:
    out = s.title() if s.isupper() else s
    # lowercase ordinal suffix and drop any leading zero: "400 02ND ST" -> "400 2nd St"
    return _ORD.sub(lambda m: str(int(m.group(1))) + m.group(2).lower(), out)


def street_address(nameaddr: str) -> str:
    """Best-effort street address for map/scrape lookups."""
    raw = (nameaddr or "").split(" - ")[0].strip()
    s = raw.split("/")[0].split("&")[0].strip()
    if re.fullmatch(r"\d+", s):
        # the split ate the street name ("758 & 772 Pacific Ave" -> "758"):
        # keep the first number and the shared street name.
        s = re.sub(r"^(\d[\d-]*)\s*[&/,]\s*\d[\d-]*\s+", r"\1 ", raw)
    s = re.sub(r"\s+", " ", s)
    return _strip_unit(_fix_caps(s))


def clean_name(nameaddr: str, address: str) -> str:
    s = (nameaddr or address or "").strip()
    s = re.sub(r"\s*-\s*(modified project|modified|revised|phase.*|rev\.?)\s*$", "", s, flags=re.I)
    return _strip_unit(_fix_caps(s)) or address


def human_join(parts: list[str]) -> str:
    parts = [p for p in parts if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} and {parts[1]}"


_ADU_KW = ("adu", "accessory dwelling", "accessory unit", "in-law", "in law",
           "secondary unit", "unit legalization", "legalize", "backyard cottage")
# Narrow: only whole-building teardowns. "demolish existing garage/deck/roof" must NOT match.
_TEARDOWN_KW = (
    "demolish the existing building", "demolition of the existing building",
    "demolish existing building", "demolition of existing building",
    "demolish the existing residential", "demolition of the existing residential",
    "demolish the existing dwelling", "demolition of the existing dwelling",
    "demolish existing dwelling", "demolition of existing dwelling",
    "demolish (e) building", "demo existing building", "raze the existing",
    "demolish the existing structure", "demolition of the existing structure",
)


def norm_nb(name: str) -> str:
    if not name:
        return "Unknown"
    return S.NEIGHBORHOOD_ALIASES.get(name.strip().lower(), name.strip())


def derive_change(existing_units, demo_units, row: dict, *descriptions,
                  net: int = 0, new_building: bool = False) -> str:
    """Verb + object describing the land-use change.

    Definitions (per project owner):
      "Adds"     - homes added with nothing demolished: an ADU, or a new structure
                   alongside an existing building that stays.
      "Replaces" - the previous use is gone: a building demolished, OR new
                   construction on a vacant / parking / commercial lot.

    We trust the structured `demo_units` count; `new_building` forces the replace
    reading for datasets (DBI permits) that describe ground-up construction but
    don't carry a demo count.
    """
    ex = num(existing_units)
    demo = abs(num(demo_units))
    text = " ".join(d for d in descriptions if d).lower()
    is_adu = any(k in text for k in _ADU_KW)
    teardown = demo >= 1 or any(k in text for k in _TEARDOWN_KW)
    homes = "a home" if net == 1 else (f"{net} homes" if net > 1 else "homes")

    nonres = next((p for f, p in S.NONRES_EXISTING if num(row.get(f)) > 0), "")
    kw = next((p for k, p in S.REPLACES_KEYWORDS if k in text), "")

    # ADDS: an existing building stays and nothing is torn down.
    if not teardown and not new_building and ex >= 1:
        if is_adu:
            return ("Adds a backyard cottage" if "cottage" in text
                    else "Adds an ADU" if net <= 1 else f"Adds {net} ADUs")
        base = "a single-family home" if ex == 1 else f"a {int(ex)}-unit building"
        return f"Adds {homes} to {base}"

    # REPLACES: teardown, or ground-up construction on a non-residential site.
    if teardown and ex >= 1:
        return f"Replaces a {int(ex)}-unit building" + (f" and {nonres}" if nonres else "")
    if kw:
        return f"Replaces {kw}"
    if nonres:
        return f"Replaces {nonres}"
    if teardown:
        return "Replaces an older building"
    return "Replaces a vacant or low-use lot"


def pim_url(address: str, blocklot: str) -> str:
    from urllib.parse import quote
    q = address or blocklot
    return f"https://sfplanninggis.org/pim/?search={quote(q)}"


# ---------------------------------------------------------------------- transforms
def build_projects(media: dict) -> list[dict]:
    out = []
    for r in load("pipeline"):
        units = iint(r.get("net_pipeline_units"))
        if units <= 0:
            continue
        case_no = (r.get("case_no") or "").strip()
        blklot = norm_blocklot(r.get("blklot"))
        pid = case_no or f"BL{blklot}"
        addr = street_address(r.get("nameaddr", ""))
        lat, lon = num(r.get("latitude")), num(r.get("longitude"))
        rec = {
            "id": pid,
            "slug": slugify(pid),
            "name": clean_name(r.get("nameaddr", ""), addr),
            "address": addr,
            "lat": round(lat, 6) or None,
            "lon": round(lon, 6) or None,
            "neighborhood": norm_nb(r.get("nhood41")),
            "stage": S.STAGE_OF_STATUS.get(r.get("current_status"), "permitted"),
            "status": r.get("current_status"),
            "status_date": (r.get("current_status_date") or "")[:10] or None,
            "net_units": units,
            # pipeline_affordable_units is a gross count; a few 100%-affordable projects
            # that replace existing units report more affordable than *net* new. Cap it.
            "affordable_units": min(iint(r.get("pipeline_affordable_units")), units),
            "affordable_known": True,
            "demo_units": abs(iint(r.get("demo_units"))),
            "change": derive_change(
                r.get("existing_units"), r.get("demo_units"), r,
                r.get("description_planning"), net=units,
            ),
            "zoning": r.get("zoning_district") or None,
            "blocklot": blklot,
            "source": "pipeline",
            "pim_url": pim_url(addr, blklot),
            "media": media.get(pid),
        }
        out.append(rec)
    return out


def _collapse_reentries(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Drop pipeline rows that are the same site re-entered under a new case.

    A project often appears twice: an old case plus a newer one, an ADU variant
    plus the main entitlement, or per-parcel rows plus a combined row. We keep the
    row with the latest status date and drop a sibling on the same block/lot only
    when it's an obvious re-entry - a tiny (<=4 home) project, an ADU / "modified"
    variant, or one address string contained in the other. Genuinely distinct
    buildings on one assessor parcel (a phased megaproject) keep every row.
    """
    by_bl: dict[str, list[dict]] = defaultdict(list)
    for i, r in enumerate(records):
        by_bl[r["blocklot"] or f"_solo{i}"].append(r)

    kept: list[dict] = []
    dropped: list[dict] = []
    for group in by_bl.values():
        if len(group) == 1:
            kept.append(group[0])
            continue
        group.sort(key=lambda r: (r.get("status_date") or "", r["net_units"]), reverse=True)
        anchor = group[0]
        kept.append(anchor)
        for r in group[1:]:
            a, b = anchor["address"].lower(), r["address"].lower()
            name = r["name"].lower()
            reentry = (
                (r["net_units"] <= 4 and anchor["net_units"] <= 4)
                or "adu" in name or "modified" in name
                or (a != b and (a in b or b in a))
            )
            (dropped if reentry else kept).append(r)
    return kept, dropped


def build_permit_projects(existing_blocklots: set[str], existing_addr_keys: set[str],
                          media: dict) -> list[dict]:
    """DBI new-construction permits, folded into the 'permitted' stage.

    These fill the gap between quarterly pipeline snapshots. They carry no
    affordable count and no demo count, so `change` uses new_building=True.

    A permit can span several parcels/addresses; if *any* of them is already a
    pipeline project (by block/lot or by address) the whole permit is a
    duplicate and dropped.
    """
    by_permit: dict[str, list[dict]] = defaultdict(list)
    for r in load("permits"):
        if num(r.get("proposed_units")) < 1:
            continue
        pnum = (r.get("permit_number") or "").strip()
        if pnum:
            by_permit[pnum].append(r)

    out: list[dict] = []
    for pnum, group in by_permit.items():
        blks = {norm_blocklot((r.get("block") or "") + (r.get("lot") or "")) for r in group}
        addrs = {
            _addr_key(" ".join(p for p in [r.get("street_number"), r.get("street_name")] if p))
            for r in group
        }
        if (blks & existing_blocklots) or (addrs & existing_addr_keys):
            continue  # same site as a pipeline project

        r = next((x for x in group
                  if str(x.get("primary_address_flag", "")).lower() in ("true", "1", "y")),
                 group[0])
        proposed = num(r.get("proposed_units"))
        blk = norm_blocklot((r.get("block") or "") + (r.get("lot") or ""))

        loc = r.get("location") or {}
        coords = (loc.get("coordinates") if isinstance(loc, dict) else None) or [None, None]
        addr = _fix_caps(" ".join(
            p for p in [r.get("street_number"), r.get("street_name"), r.get("street_suffix")] if p
        ).strip())
        pid = f"PERMIT-{pnum}"
        is_adu = str(r.get("adu", "")).lower() in ("true", "1", "y")
        rec = {
            "id": pid,
            "slug": slugify(pid),
            "name": addr,
            "address": addr,
            "lat": coords[1],
            "lon": coords[0],
            "neighborhood": norm_nb(r.get("neighborhoods_analysis_boundaries")),
            "stage": "permitted",
            "status": "Permit issued (DBI)",
            "status_date": (r.get("issued_date") or "")[:10] or None,
            "net_units": int(round(proposed)),
            "affordable_units": 0,
            "affordable_known": False,
            "demo_units": 0,
            "change": ("Adds an ADU" if is_adu else derive_change(
                r.get("existing_units"), 0, {},
                r.get("existing_use"), r.get("description"),
                net=int(round(proposed)), new_building=True,
            )),
            "zoning": None,
            "blocklot": blk,
            "source": "permit",
            "permit_number": pnum,
            "pim_url": pim_url(addr, blk),
            "media": media.get(pid),
        }
        out.append(rec)
    return out


def build_completions() -> tuple[list[dict], dict, dict]:
    rows = load("completions")
    this_year, monthly = [], defaultdict(lambda: defaultdict(float))

    for r in rows:
        d = (r.get("latest_completion_date") or "")[:10]
        if not d:
            continue
        y, m = int(d[:4]), int(d[5:7])
        monthly[y][m] += num(r.get("net_units_completed"))
        if y == YEAR:
            this_year.append({
                "address": street_address(r.get("address", "")),
                "neighborhood": r.get("analysis_neighborhood") or "Unknown",
                "net_units": iint(r.get("net_units_completed")),
                "affordable_units": iint(r.get("affordable_units")),
                "market_rate": iint(r.get("market_rate")),
                "completion_date": d,
                "blocklot": norm_blocklot(r.get("blocklot")),
                "change": derive_change(
                    r.get("pts_existing_units"), 0, {}, r.get("description"),
                    net=iint(r.get("net_units_completed")),
                ),
                "description": (r.get("description") or "").strip()[:240],
            })

    this_year.sort(key=lambda x: x["completion_date"], reverse=True)

    def cumulative(y: int) -> list[float]:
        run, series = 0.0, []
        for mo in range(1, 13):
            run += monthly.get(y, {}).get(mo, 0.0)
            series.append(round(run, 1))
        return series

    monthly_out = {
        str(YEAR): cumulative(YEAR),
        str(YEAR - 1): cumulative(YEAR - 1),
    }
    # Annual net completions for every year we pulled - the honest trend view.
    # The current year (and often the prior one) is still being reported: the city
    # backfills certificates of occupancy for a year or more.
    annual = {
        str(y): round(sum(monthly.get(y, {}).values()), 1)
        for y in sorted(monthly)
        if y >= YEAR - 6
    }
    return this_year, monthly_out, annual


def prev_year_to_date(monthly_cumulative: dict) -> int:
    """Prior-year completions through the same day-of-year as today (fair comparison)."""
    today = dt.date.today()
    series = monthly_cumulative.get(str(YEAR - 1), [0] * 12)
    # month index just completed
    idx = today.month - 2
    if idx < 0:
        return 0
    base = series[idx]
    # linear share of the current month
    nxt = series[min(idx + 1, 11)]
    frac = (today.day - 1) / 30.0
    return int(round(base + (nxt - base) * frac))


# ------------------------------------------------------------------------- summary
def build_summary(projects, completions_year, monthly) -> dict:
    uc = [p for p in projects if p["stage"] == "under_construction"]
    permitted = [p for p in projects if p["stage"] == "permitted"]

    by_nb = defaultdict(lambda: {"units": 0, "projects": 0})
    for p in projects:
        by_nb[p["neighborhood"]]["units"] += p["net_units"]
        by_nb[p["neighborhood"]]["projects"] += 1
    by_neighborhood = sorted(
        ({"neighborhood": k, **v} for k, v in by_nb.items()),
        key=lambda x: -x["units"],
    )

    uc_units = sum(p["net_units"] for p in uc)
    permit_units = sum(p["net_units"] for p in permitted)
    active_units = uc_units + permit_units
    # affordable share is only meaningful where the count is known (pipeline rows)
    known = [p for p in projects if p.get("affordable_known")]
    known_units = sum(p["net_units"] for p in known)
    aff_active = sum(p["affordable_units"] for p in known)
    done_units = sum(c["net_units"] for c in completions_year)
    done_aff = sum(c["affordable_units"] for c in completions_year)
    prev_full = int(round(monthly.get(str(YEAR - 1), [0] * 12)[-1]))

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "year": YEAR,
        "under_construction_units": uc_units,
        "under_construction_projects": len(uc),
        "permitted_units": permit_units,
        "permitted_projects": len(permitted),
        "permitted_from_permits": sum(1 for p in permitted if p["source"] == "permit"),
        "active_units": active_units,
        "active_projects": len(projects),
        "affordable_active_units": aff_active,
        "affordable_active_pct": round(100 * aff_active / known_units, 1) if known_units else 0,
        "completed_this_year_units": done_units,
        "completed_this_year_projects": len(completions_year),
        "completed_this_year_affordable": done_aff,
        "completed_prev_year_full": prev_full,
        "completed_prev_year_to_date": prev_year_to_date(monthly),
        "by_neighborhood": by_neighborhood[:15],
    }


def _addr_key(a: str) -> str:
    m = re.match(r"\s*(\d+)\s+([a-z]+)", (a or "").lower())
    return f"{m.group(1)} {m.group(2)[:5]}" if m else ""


def audit(projects: list[dict]) -> dict:
    """Cheap self-checks surfaced in the digest so the totals stay honest.

    None of these are automatically corrected - they're flags to eyeball each run.
    """
    active = [p for p in projects if p["stage"] in ("under_construction", "permitted")]

    by_bl: dict[str, list[dict]] = defaultdict(list)
    for p in active:
        if p.get("blocklot"):
            by_bl[p["blocklot"]].append(p)
    dup_bl = {k: v for k, v in by_bl.items() if len(v) > 1}
    dup_bl_extra_units = sum(
        sum(x["net_units"] for x in v) - max(x["net_units"] for x in v)
        for v in dup_bl.values()
    )

    pipe_addr = {_addr_key(p["address"]) for p in active if p["source"] == "pipeline"}
    pipe_addr.discard("")
    permit_addr_dups = [
        p for p in active
        if p["source"] == "permit" and _addr_key(p["address"]) in pipe_addr
    ]

    tail = [p for p in active if p["change"].startswith("Adds") and p["net_units"] <= 4]
    tail_units = sum(p["net_units"] for p in tail)
    active_units = sum(p["net_units"] for p in active)

    return {
        "dup_blocklots": len(dup_bl),
        "dup_blocklot_extra_units": dup_bl_extra_units,
        "dup_blocklot_examples": [v[0]["address"] or k for k, v in list(dup_bl.items())[:5]],
        "permit_addr_dups": len(permit_addr_dups),
        "permit_addr_dup_examples": [p["address"] for p in permit_addr_dups[:5]],
        "small_adds_projects": len(tail),
        "small_adds_units": tail_units,
        "small_adds_unit_pct": round(100 * tail_units / active_units, 1) if active_units else 0,
    }


def write_digest(summary: dict, projects: list[dict], reentries: list[dict] | None = None) -> None:
    today = dt.date.today().isoformat()
    prev = None
    if SNAP.exists():
        for line in reversed(SNAP.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("date") != today:   # compare against a prior day, not today's run
                prev = row
                break

    def delta(key: str) -> str:
        if not prev or key not in prev:
            return ""
        d = summary[key] - prev[key]
        return f" ({d:+d} since last update)" if d else " (no change)"

    covered = sum(1 for p in projects if p.get("media"))
    lines = [
        f"# SF housing tracker - digest ({summary['generated_at'][:10]})",
        "",
        f"- Under construction: **{summary['under_construction_units']:,} homes** "
        f"in {summary['under_construction_projects']} projects{delta('under_construction_units')}",
        f"- Permitted (not yet started): **{summary['permitted_units']:,} homes** "
        f"in {summary['permitted_projects']} projects{delta('permitted_units')} "
        f"({summary['permitted_from_permits']} from recent DBI permits)",
        f"- Completed in {summary['year']} so far: **{summary['completed_this_year_units']:,} homes** "
        f"({summary['completed_this_year_affordable']:,} BMR) "
        f"in {summary['completed_this_year_projects']} projects{delta('completed_this_year_units')}",
        f"  - {summary['year'] - 1} full year: {summary['completed_prev_year_full']:,} "
        f"(city backfills completions for months, so {summary['year']} runs low)",
        f"- BMR (below-market-rate) share where known: {summary['affordable_active_pct']}%",
        f"- Project images on file: {covered}/{len(projects)} "
        f"({round(100 * covered / len(projects)) if projects else 0}%)",
        "",
        "## Biggest active projects",
    ]
    for p in projects[:8]:
        lines.append(
            f"- {p['net_units']:,} homes - {p['name']} "
            f"({S.STAGE_LABEL[p['stage']]}, {p['neighborhood']}) - {p['change'].lower()}"
        )

    a = audit(projects)
    reentries = reentries or []
    lines += [
        "",
        "## Data checks",
        f"- Collapsed pipeline re-entries this build: **{len(reentries)}** "
        f"(-{sum(r['net_units'] for r in reentries):,} double-counted homes removed). "
        f"{', '.join(r['name'] for r in reentries[:6]) or 'none'}",
        f"- Still sharing a block/lot after that (kept as distinct buildings - eyeball): "
        f"{a['dup_blocklots']} groups, ~{a['dup_blocklot_extra_units']:,} homes past the "
        f"largest row on each. {', '.join(a['dup_blocklot_examples']) or 'none'}",
        f"- DBI permits dropped as pipeline duplicates: handled in build_permit_projects; "
        f"residual address collisions here should be 0 -> got {a['permit_addr_dups']}.",
        f"- Small 'Adds' tail (<=4 homes, nothing demolished): {a['small_adds_projects']} "
        f"projects = {a['small_adds_units']:,} homes ({a['small_adds_unit_pct']}% of active). "
        f"Decide if these belong in the headline or a separate line.",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------- main
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    media = {}
    if MEDIA_JSON.exists():
        media = {m["project_id"]: m for m in json.loads(MEDIA_JSON.read_text("utf-8"))}

    pipeline = build_projects(media)
    pipeline, reentries = _collapse_reentries(pipeline)
    blocklots = {p["blocklot"] for p in pipeline if p["blocklot"]}
    addr_keys = {_addr_key(p["address"]) for p in pipeline}
    addr_keys.discard("")
    permit_projects = build_permit_projects(blocklots, addr_keys, media)
    projects = pipeline + permit_projects
    projects.sort(key=lambda x: -x["net_units"])
    if reentries:
        print(f"  collapsed {len(reentries)} pipeline re-entries "
              f"(-{sum(r['net_units'] for r in reentries):,} double-counted homes)")

    completions_year, monthly, annual = build_completions()
    summary = build_summary(projects, completions_year, monthly)

    history = []
    if SNAP.exists():
        history = [json.loads(l) for l in SNAP.read_text("utf-8").splitlines() if l.strip()]

    timeseries = {
        "history": history,
        "completions_monthly": monthly,
        "completions_annual": annual,
    }

    def dump(name, obj):
        (OUT / name).write_text(json.dumps(obj, separators=(",", ":")), encoding="utf-8")

    dump("projects.json", projects)
    dump("completions.json", completions_year)
    dump("summary.json", summary)
    dump("timeseries.json", timeseries)
    dump("media.json", list(media.values()))
    if MANIFEST.exists():
        dump("manifest.json", json.loads(MANIFEST.read_text("utf-8")))

    write_digest(summary, projects, reentries)

    print(f"  under construction  {summary['under_construction_units']:>6,d} homes / "
          f"{summary['under_construction_projects']} projects")
    print(f"  permitted           {summary['permitted_units']:>6,d} homes / "
          f"{summary['permitted_projects']} projects "
          f"(+{len(permit_projects)} from DBI permits)")
    print(f"  completed {YEAR}       {summary['completed_this_year_units']:>6,d} homes")
    print(f"  wrote {OUT.relative_to(ROOT)}/*.json and {SUMMARY_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
