# SF Housing Construction Tracker — update runbook

A local, occasionally-updated site tracking housing that is **under construction** or has an
**issued building permit** in San Francisco, plus **homes completed this year** (rolls
over automatically on Jan 1). Data from the DataSF open-data portal. No API key required.

## The one command

```bash
python scripts/update.py
```

Runs: fetch DataSF → build site JSON → scrape missing project images → record a dated snapshot →
rebuild. Then it prints `data/summary.md`. Read that digest, sanity-check the numbers, then:

```bash
git add -A && git commit -m "data refresh $(date +%F)"
```

Preview locally any time:

```bash
python scripts/serve.py        # http://localhost:8000
```

### Flags

- `--no-scrape` — skip image fetching (fast; data only).
- `--rescrape` — retry images for **every** project, not just ones missing an image.

## How token usage is kept low

- `data/raw/` (the full API pulls) is **gitignored and should not be read wholesale**. Filtering
  and aggregation happen in the SoQL query (`scripts/fetch.py`) and in `scripts/build.py`.
- The scraper writes only `data/media.json` (a small manifest). It never surfaces scraped HTML/PDF.
- To review a run, read **`data/summary.md`** (~20 lines) and the `update.py` stdout diff.

## Common changes

| Want to… | Do this |
|---|---|
| Include projects that have only *applied* for a permit | `config/sources.py` → `INCLUDE_BP_FILED = True` |
| Change what counts as "under construction" | `config/sources.py` → `CONSTRUCTION_STATUSES` |
| Widen the "recent permits" window | `config/sources.py` → `PERMIT_LOOKBACK_MONTHS` |
| Add a hand-picked rendering for a project | drop `media/manual/<slug>.jpg` (slug = `slug` field in `site/data/projects.json`) and add `{"<slug>": "caption"}` to `media/manual/captions.json`, then `python -m scripts.scrape --rescrape` |
| Fetch images for more/smaller projects | `config/scrape_sources.py` → `MIN_UNITS_FOR_IMAGE`, `MAX_IMAGES` |
| Add a new image source | new file in `scripts/scrape/` subclassing `ImageSource`; add the class to `ENABLED_SOURCES` in `config/scrape_sources.py` |

## Data sources (resource IDs)

- `6jgi-cpb4` — SF Development Pipeline (quarterly): status, unit counts, existing use.
- `i98e-djp9` — Building Permits (nightly): recently issued new-construction permits.
- `xdht-4php` — Housing Production 2005-present: dated completions → "completed this year".
- `j67f-aayr` — Dwelling Unit Completion Counts (TCO/CofO cross-check, currently unused downstream).
- Affordable Housing Pipeline: configured but the endpoint 404s right now, so it's skipped.

## Notes / known limits

- **These are a cumulative stock, not annual flow.** "Under construction" / "permitted" count
  every active project right now (net homes), including a long ADU/added-unit tail. Not comparable
  to Census-survey permit or completion counts. `data/summary.md` prints a "Data checks" block
  each run.
- **De-duplication.** `build.py` collapses pipeline rows that are the same site re-entered under
  a new case (`_collapse_reentries`, keyed on block/lot) and drops any DBI permit whose parcel
  *or* address matches a pipeline project. Rows sharing a block/lot that look like real distinct
  buildings (phased megaprojects) are kept and listed in the digest for a human to check.
- **Completions lag.** The city backfills `xdht-4php` for a year or more, so the current-year
  bar in the "Homes completed per year" chart is always far from final. The chart says so.
- **Palette is paper-only** — no dark mode. Off-white ground, dark blueprint/ochre map markers,
  in every OS theme (`site/style.css`, `:root { color-scheme: light }`).
- **Renderings are sparse.** `parcel_aerial` (keyless Esri aerial) covers essentially every
  project. `wikimedia` finds CC renderings/construction photos for the marquee projects
  (net units ≥ 120); `sf_planning` rarely hits; `commission_packets` is a stub (PDF image
  extraction is wired via `base.pdf_first_image`, the case→packet-URL lookup is not). Use
  `media/manual/<slug>.jpg` for projects you want a specific rendering on.
- Basemap is keyless Esri "Light Gray Canvas" raster tiles via Leaflet (needs internet). The
  vector/`pmtiles` path from the original plan was dropped in favour of keyless raster.
