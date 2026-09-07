# SF Housing Construction Tracker

A small, locally-run site that tracks housing **actually getting built** in San Francisco:
homes under construction, homes with an issued building permit, and homes
**completed so far this year** (the counter rolls over automatically on January 1).

All data comes from the City & County of San Francisco open data portal
([data.sfgov.org](https://data.sfgov.org)). No API key, no build step, no framework.

## Quick start

```bash
python scripts/update.py     # pull fresh data + images  (~3 min the first time)
python scripts/serve.py      # open http://localhost:8000
```

Requires Python 3.10+ only. Internet is needed to fetch data and map tiles.

## How it fits together

```
config/         dataset IDs, filters, "what it replaces" rules, scraper list
scripts/
  fetch.py      DataSF  ->  data/raw/*.json      (server-side filtered, gitignored)
  build.py      data/raw ->  site/data/*.json + data/summary.md
  scrape/       pluggable image sources (aerials always; renderings best-effort)
  update.py     fetch -> build -> scrape -> snapshot -> build   (the one command)
  serve.py      static server for site/  (with HTTP Range support)
site/           index.html + app.js + style.css + vendored Leaflet & fonts
data/
  summary.md    ~20-line digest to read after each update
  snapshots/    one row per update -> the "over time" chart
```

See **[METHODOLOGY.md](METHODOLOGY.md)** for exactly what counts and every data caveat,
**CLAUDE.md** for the update runbook and common tweaks, and **WHERE_I_LEFT_OFF.md** for
current build status.

## What the labels mean

Two stages only:

- **Under construction** — Planning Department Development Pipeline `current_status = Construction`.
- **Permitted** — pipeline status `BP Issued` (construction permit issued, work not started),
  plus new-construction permits the Dept. of Building Inspection issued in the last 24 months
  that the quarterly pipeline snapshot hasn't picked up yet (deduped against the pipeline by
  block/lot). Projects that are only *approved* (permit not yet issued) or *applied for* are
  excluded.
- **Completed this year** — net units from certificates of occupancy (Housing Production
  dataset). Runs low early in the year because the city backfills it for months.
- **"Adds" vs "Replaces"** — derived from the project's recorded demolition and existing-use
  fields. "Adds" when nothing is torn down and an existing building stays (ADUs, additions);
  "Replaces" for a demolition, or ground-up construction on a vacant / parking / commercial lot.

The counts are a **cumulative stock** (every active project right now, counting *net* new
homes) — not one year's permits or completions, and not comparable to Census-survey figures.
