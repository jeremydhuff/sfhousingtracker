# Where I left off — 2026-09-07 (night 2)

SF housing construction tracker. Pipeline runs end to end, the site renders with **no
console errors** in the off-white paper palette (now the only palette — see below),
`update.py` has been run in full (snapshot #1, 66 images), de-dup is in, and the first
commit is done.

## Run it

```bash
python scripts/update.py      # fetch + build + scrape images + snapshot
python scripts/serve.py       # http://localhost:8000   (or: preview "site" in the app)
```

## Current numbers (2026-09-07, after the accuracy pass)

- 3,328 homes under construction / 435 projects (3 from DBI site-work permits)
- 1,790 homes permitted / 126 projects (16 from recent DBI new-construction permits)
- 381 homes completed in 2026 so far — **reporting lag**, not the real pace: the city
  backfills certificates of occupancy for a year+ (2025 ended at 3,034 the same way), plus
  ~-100 net from HOPE SF phased demolition (Sunnydale, 700 Missouri St).
- 561 projects total
- BMR (below-market-rate) share where known: **60.9%** — verified. SF's
  actually-permitted-and-building housing right now is dominated by 100%-BMR projects
  (300 De Haro 425u, 758 Pacific 175u, 1633 Valencia, 2970 16th, Balboa Reservoir...);
  market-rate has stalled. Both stages independently ~60%. Real, not a bug.
  (Term is "BMR" everywhere user-facing now, per your call; data keys stay `affordable_*`.)

Accuracy pass (night 3): re-checked the top ~15 by unit count against SF YIMBY /
developer profiles / DBI permits.
- **750 Golden Gate "Phase 1"**: net_pipeline_units=171 was the full two-phase
  total; Phase 1 (the row under construction) is 75. `UNIT_OVERRIDES` → 75.
- **105 Wisteria Ln** (159): Balboa Reservoir Building A's tower-crane permit,
  filed on its own street address + sub-parcel — a duplicate of the pipeline's
  11 Frida Kahlo Wy (159, under construction). `build_permit_projects` now also
  drops a site-work permit when its assessor *block* carries a pipeline project
  with the same unit count.
- Net: −255 under construction (3,583 → 3,328).
- Verified correct, left alone: 300 De Haro (425), 1101-1123 Sutter (303 / 102
  BMR), 400 Divisadero (203), 1939 Market (187), Balboa Blocks A + E, 758 Pacific.
- 199 Vidal Dr (Parkmerced, BP Issued since 2018) is a genuinely stale
  entitlement but still correctly "permitted, not started" — left in.

Two corrections applied earlier this session:
- **Issued permits only.** `CONSTRUCTION_STATUSES` dropped `"BP Approved"` — a project counts
  as "permitted" only once a construction permit is actually issued (`BP Issued`), not just
  Planning-approved. Cut permitted from 4,197 -> 1,790 homes; removed stale entitlements like
  400 2nd St (case 2012.1384).
- **De-dup** removed 208 double-counted homes: 175 from a DBI permit (758 & 772 Pacific Ave)
  that duplicated a pipeline project across two parcels, and 33 from ~20 pipeline rows that
  were the same small site entered under an old + a new case.

## Done night 2

- **De-duplication (the big one)** — `scripts/build.py`:
  - `build_permit_projects()` rewritten: a DBI permit is dropped if **any** of its
    parcels or addresses matches a pipeline project (before it only checked one row's
    block/lot, so 758 & 772 Pacific Ave slipped through as a 175-home ghost).
  - `_collapse_reentries()`: pipeline rows sharing a block/lot are collapsed when a
    sibling is an obvious re-entry — tiny (<=4 homes), an ADU / "modified" variant, or
    one address string inside the other. Keeps the latest-status row. Genuinely
    distinct buildings on one parcel (11 Frida Kahlo Wy x3 = Balboa Reservoir, Parkmerced)
    are kept — verified.
  - Net effect: **-208 double-counted homes** (7,700 -> 7,492).
- **Completions chart replaced** — the cumulative YTD race (flat near-zero 2026 line,
  looked like a construction collapse) is gone. Now **annual net completions, 2020–2026**,
  current year hatched + `2026→`. Real story: ~5k/yr 2020-21, dip to 1.4k in 2024, 3.0k
  in 2025, 2026 still being reported. `timeseries.json` gains `completions_annual`.
- **Palette is paper-only now** — dropped the `@media (prefers-color-scheme: dark)` block.
  Per the design ("permit placard") and per your call: off-white ground, dark blueprint /
  ochre markers, in every OS theme. `color-scheme: light` on `:root`.
- **serve.py** — `self._range` reset at the top of `send_head` (stale-tuple bug).
- **Address cleanup** — strip trailing unit tags (`750 Presidio Av #0` -> `750 Presidio Av`),
  leading-zero ordinals (`400 02nd St` -> `400 2nd St`), trailing junk (`*`, stray `/`).
  `_strip_unit()` / `_fix_caps()` in `scripts/build.py`.
- **Audit block in `data/summary.md`** every run: re-entries collapsed this build,
  block/lots still shared (kept as distinct — eyeball), permit-vs-pipeline residual
  collisions (should be 0), and the small-"Adds" tail (400 projects / 486 homes =
  **6.5% of active units** but **62% of the project count** — the tail inflates the
  *project* number, not the *homes* number; decide whether to split it out).
- **Metric definition on the site** — new "How to read the counts" box in the footer:
  cumulative stock, net units, not comparable to Census / housingdata.app annual figures.
- **Images** — new `wikimedia` source (keyless Commons API, CC renderings/photos, gated to
  projects >= 120 units). Reality check: only 22 projects clear that bar and almost all are
  bare addresses with no Commons page, so it hits ~never today. Kept because it's cheap and
  will catch named megaprojects as they appear. `base.pdf_first_image()` added (pulls the
  largest embedded JPEG from a PDF) so the commission-packet source is now just missing the
  case-number -> packet-URL lookup.
- **Docs** — README + CLAUDE.md updated to the two-stage model and the "cumulative stock"
  framing; dropped the dead pmtiles/vector-basemap references (we use keyless Esri raster).
- `.claude/launch.json` so the app's preview button serves the site.

## The "middle of a project's life" gap (from the 2918 Mission St question)

The pipeline is not a complete registry of what's building. 2918 Mission St (75 homes,
foundation work underway per SF YIMBY Aug 2026) was missing because:
- not in the current Development Pipeline snapshot at all (entitled 2018, aged off);
- its type-1 new-construction permit is from 2018 - outside our 24-month window;
- its only recent permit is type-3 ("temporary shoring for new construction", 2026).

**Fixed:** we now also pull type-3 **site-work permits** (shoring / excavation / tower crane
/ soldier piles for new construction, with a unit count, last 24 months) and file them as
*under construction*. Caught 2918 Mission + 3 others (939/951 Eddy, 105 Wisteria Ln);
the rest dedupe against the pipeline. `config/sources.py` -> `GROUNDWORK_*`.

**Residual gap:** a project whose new-construction permit is 3+ years old and which has no
recent site-work permit yet is still invisible. Fully closing this needs permit
*status/inspection* history (DBI PTS milestones), not just permit issuance. Also: site-work
permits carry no demolition info, so their "replaces" text defaults to "a vacant or low-use
lot" even when they cleared a building (2918 Mission replaced a laundromat).

## Still open

1. **Images are still ~90% aerials (66/646, 10% coverage).** The rendering-first goal isn't
   met. Best next move: build the Planning Commission packet crawler — `commission_packets.py`
   has the plan in its docstring and the PDF-image extraction is done (`base.pdf_first_image`);
   it needs a crawl of `sfplanning.org` hearing archives to map case numbers to
   executive-summary PDF URLs. Meanwhile `media/manual/<slug>.jpg` + `captions.json` is the
   hand-place path (slug = the `slug` field in `site/data/projects.json`).
2. **Spot-check the biggest entitlements for staleness.** `400 2nd St` (our #1, 489 homes,
   "permitted") is pipeline case **2012.1384**, status "BP Approved" as of 2023-11-13, no DBI
   permit — a 13-year-old entitlement that may be stalled or changed (historically an
   office-led project). Check it and the other top ~15 against SF Planning / DBI; a quarterly
   "Construction" row could already be finished.
3. **969 Oakdale Av** (two BP-Issued rows, 15 + 11 homes, same block/lot) is the one
   ambiguous residual in the audit — confirm it's two buildings, not a re-entry, or tighten
   `_collapse_reentries`.
4. **Grouping master developments** — 11 Frida Kahlo Wy x3, Parkmerced rows etc. are correct
   but read as duplicates in the table. Consider a "part of <development>" grouping.
5. Run `update.py` a few more times to give the "under construction over time" chart real
   points (only snapshot #1 exists).
6. `1 Avenue Of The Palms` / Treasure Island / Presidio projects sit on federal-ish land —
   confirm we want them in the SF totals (they inflate vs city-permit-based sources).
7. Consider de-duping the completions dataset the same way (lower priority — it's historical
   and less scrutinised, but the annual bars could carry the same multi-row inflation).

## Key files

| file | role |
|---|---|
| `METHODOLOGY.md` | **the data-collection spec** - what counts, every source, every caveat. Start here. |
| `config/sources.py` | dataset IDs, SoQL filters, stage map, neighborhood aliases, "replaces" keyword maps |
| `config/scrape_sources.py` | ordered scraper plugin list + politeness knobs |
| `scripts/build.py` | all transform + digest logic; `derive_change()` = adds/replaces, `audit()` = data checks |
| `scripts/fetch.py` | `build_where()` has every SoQL filter |
| `scripts/scrape/base.py` | `ImageSource` base + http/robots/throttle/save + `pdf_first_image` |
| `scripts/scrape/wikimedia.py` | keyless Commons renderings/photos for the marquee projects |
| `site/app.js` | client (~380 lines, no framework); two-stage model throughout |
| `site/style.css` | "building-permit placard" design system; palette provenance in the header |
