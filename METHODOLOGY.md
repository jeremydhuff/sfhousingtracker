# Data methodology

How this project decides what counts as "housing getting built in San Francisco",
where every number comes from, and every known way the data can mislead you.
Read this before changing a filter or trusting a headline figure.

If you're just refreshing the data, the loop is in [CLAUDE.md](CLAUDE.md); come
back here when a number looks wrong.

---

## 1. What we're measuring

A **cumulative stock**, not an annual flow: every residential project in SF that,
right now, is either

- **under construction** — a builder is on site, or
- **permitted** — a construction permit is issued and work hasn't started,

plus a rolling **"homes completed this year"** counter.

We count **net new homes** (proposed − existing − demolished). We do **not**
count projects that are only entitled/approved, only applied-for, or purely
commercial.

This is deliberately not comparable to the Census Building Permits Survey, HCD
APR, or dashboards built on them — those are one year of permit or completion
*activity*; this is the standing backlog. Expect our numbers to look higher.

---

## 2. Sources (all DataSF / Socrata, keyless)

| id | dataset | cadence | what we take from it |
|---|---|---|---|
| `6jgi-cpb4` | SF Development Pipeline | quarterly | the spine: status, `net_pipeline_units`, `pipeline_affordable_units`, existing use, demo count, lat/long |
| `i98e-djp9` | Building Permits (DBI) | nightly | new-construction + site-work permits the quarterly pipeline hasn't caught |
| `xdht-4php` | Housing Production 2005–present | ~daily | dated completions → "completed this year" and the annual-completions chart |
| `j67f-aayr` | Dwelling Unit Completion Counts | ~daily | pulled for cross-checking; not used downstream yet |

Affordable Housing Pipeline (`i88b-cd6x`) is configured but its endpoint 404s, so
it's skipped every run.

All filtering is server-side in the SoQL `$where` (`scripts/fetch.py` →
`build_where`) so `data/raw/*.json` stays small. `data/raw/` is gitignored and
should never be read wholesale.

---

## 3. Exactly what's included

### Under construction

1. **Pipeline rows with `current_status = "Construction"`** and
   `net_pipeline_units > 0`.
2. **DBI "site-work" permits** — `permit_type = '3'`, status `issued`/`reinstated`,
   `proposed_units >= GROUNDWORK_MIN_UNITS` (10), issued in the last
   `GROUNDWORK_LOOKBACK_MONTHS` (24), and the description contains one of
   `GROUNDWORK_PHRASES` (shoring for new / excavation for new / tower crane /
   soldier pile …). These are the filing that actually tracks "digging now".
   **Why they exist:** a large project pulls its type-1 new-construction permit
   3–8 years before breaking ground, so that permit is outside the 24-month
   window by the time construction starts, and the quarterly pipeline may not
   list the project at all. 2918 Mission St (entitled + permitted 2018,
   foundation work 2026) is the canonical example.

### Permitted (not yet started)

1. **Pipeline rows with `current_status = "BP Issued"`** — construction permit
   issued, work not started.
2. **DBI new-construction permits** — `permit_type in ('1','2')`, status
   `issued`/`reinstated`, `proposed_units >= 1`, issued in the last
   `PERMIT_LOOKBACK_MONTHS` (24).

### Deliberately excluded

- `current_status = "BP Approved"` — Planning approved it, DBI hasn't issued the
  permit. Approval can lapse; this is where stale mega-entitlements live
  (e.g. 400 2nd St, case 2012.1384). Flip `CONSTRUCTION_STATUSES` in
  `config/sources.py` to change this.
- `current_status = "BP Filed"` — permit only applied for. `INCLUDE_BP_FILED`
  toggles it.
- Permits with `proposed_units < 1` — offices, garages, consulates, pure
  commercial. (An early bug counted these because `existing_units` is always
  null for permit types 1/2; the fix is the explicit `>= 1`.)

### Completed this year

`xdht-4php` rows with `latest_completion_date` in the current calendar year
(rolls over automatically on Jan 1). We sum `net_units_completed` and
`affordable_units`. The annual-completions chart pulls the last 7 years so the
trend is visible offline.

---

## 4. Units and BMR

- **`net_units`** = the pipeline's `net_pipeline_units` (proposed − existing −
  demo) for pipeline rows; `proposed_units` for permit rows (which carry no
  existing/demo figure — treated as ground-up).
- **BMR** (below-market-rate / deed-restricted affordable) = the pipeline's
  `pipeline_affordable_units`, **capped at `net_units`**. That cap matters: a few
  100%-BMR projects that replace existing units report more affordable homes than
  *net* new (300 De Haro 425/425, 758 Pacific, 1633 Valencia, 1687 Market,
  898 La Salle), because the affordable count is gross and the net count isn't.
- BMR is **unknown** for DBI permit rows (`affordable_known = false`) — shown as
  `?`. The BMR % is computed only over rows where it's known.
- The current ~60% BMR share is real and verified — it holds independently in
  both stages. SF's market-rate pipeline has stalled; publicly-financed 100%-BMR
  projects kept moving.

---

## 5. De-duplication

Layered, in `scripts/build.py`:

1. **Pipeline re-entries** (`_collapse_reentries`) — rows sharing a block/lot are
   collapsed when a sibling is an obvious re-entry: a tiny (≤4-home) project, an
   ADU / "modified" variant, or one address string contained in the other. Keep
   the latest-status row. Genuinely distinct buildings on one assessor parcel
   (phased megaprojects — 11 Frida Kahlo Wy ×3 = Balboa Reservoir, Parkmerced)
   keep every row.
2. **Permit vs pipeline** (`build_permit_projects`) — a DBI permit is dropped if
   **any** of its parcels *or* addresses matches a pipeline project. (An earlier
   bug checked only one address row at a time, so a permit spanning two lots —
   one matching, one not — slipped through: 758 & 772 Pacific Ave was a 175-home
   ghost.)
3. **Groundwork vs new-construction permit** — if a site has both, the groundwork
   permit wins (it's the "under construction" signal); the other is dropped.
4. Everything that's left and still shares a block/lot is **kept** but **listed
   in the digest** for a human to eyeball (see §8).

---

## 6. "Adds" vs "Replaces"

`derive_change()`. Definitions come from the project owner:

- **Adds** — nothing demolished and an existing building stays: ADUs, extra
  units, additions. Rule: `demo_units == 0` AND `existing_units >= 1` AND no
  whole-building teardown phrase.
- **Replaces** — the prior use is gone: a building demolished (`demo_units >= 1`
  or a *narrow* whole-building teardown phrase), OR ground-up construction on a
  vacant / parking / commercial lot.

Trusts the structured `demo_units` field. The teardown keyword list
(`_TEARDOWN_KW`) is intentionally narrow — "demolish existing garage/deck/roof"
must not trigger a "Replaces".

---

## 7. Known limitations — read before trusting a number

| gotcha | effect | mitigation |
|---|---|---|
| **The pipeline is not a complete registry.** Projects entitled years ago that are only now starting can be absent entirely. | Undercount of "under construction". | Site-work permits (§3) close much of this. A project with an old new-construction permit and no recent site-work permit is still invisible — fully fixing needs DBI permit *status/inspection* history. |
| **`net_pipeline_units` can be stale** when a project is revised. 1580 Beach St shows 9; the description says it was cut to 3 ADUs "not six as previously proposed". | Small per-project overcount. | Digest flags the "revised down to N units" construction (`stale_unit_count`). Confirm against SF Planning, then add a `config/sources.py` → `UNIT_OVERRIDES` entry keyed by `case_no` (1580 Beach → 3 is already there). |
| **Completions lag.** DBI files certificates of occupancy for a year+ after buildings open. | Current-year completions read far too low (2025 sat low all year, ended at 3,034). | Chart shows annual bars with the current year hatched + "still being reported"; comparison figure is prior-year *full*. |
| **Quarterly snapshot.** A pipeline row marked "Construction" could already be finished. | Stale "under construction" entries. | Spot-check the top ~15 each refresh against SF Planning / DBI. |
| **`demo_units` is under-populated** (~29 of ~560 rows). | A real teardown with a blank demo count reads as "Adds". | Charitable reading, follows the city's own field; noted in the site footer. |
| **Site-work permits carry no demolition info.** | Their "replaces" text defaults to "a vacant or low-use lot" even when a building was cleared (2918 Mission replaced a laundromat). | Accept, or join to the type-6 demolition permit on the same parcel (not done). |
| **Federal / island land.** Presidio and Treasure Island projects are in the pipeline but may bypass SF DBI. | Inflates totals vs city-permit-based sources; "1 Avenue Of The Palms" etc. | Decide whether to exclude by neighborhood. Not currently excluded. |
| **The small-"Adds" tail.** ~350 projects of ≤4 net homes = ~8% of units but ~60% of the *project count*. | Inflates project count, not homes. | Digest quantifies it every run; decide whether to split it into its own line. |
| **BMR gross/net seam** (§4). | Slightly overstates BMR share before the cap. | Capped at `net_units` per project. |

---

## 8. The "Data checks" block in `data/summary.md`

Printed every run. Not auto-corrected — these are flags for a human:

- **Collapsed pipeline re-entries this build** — how many rows §5.1 removed and
  the homes count. Expect ~19, ~27 homes.
- **Still sharing a block/lot** — groups kept as distinct buildings. Eyeball the
  named ones (11 Frida Kahlo Wy = Balboa Reservoir, real; 969 Oakdale Av =
  ambiguous, two permits on one lot).
- **DBI permits dropped as pipeline duplicates** — residual address collisions
  here should be **0**; if not, the dedup regressed.
- **Possibly stale `net_pipeline_units`** — the "revised down" flag. Check each
  against SF Planning.
- **Small "Adds" tail** — count, homes, % of units.

---

## 9. Where to tune

| want to… | file → knob |
|---|---|
| include only-approved projects | `config/sources.py` → `CONSTRUCTION_STATUSES` |
| include applied-for permits | `config/sources.py` → `INCLUDE_BP_FILED` |
| widen the new-construction permit window | `PERMIT_LOOKBACK_MONTHS` |
| tune the "breaking ground" signal | `GROUNDWORK_PHRASES`, `GROUNDWORK_MIN_UNITS`, `GROUNDWORK_LOOKBACK_MONTHS` |
| change neighborhood name reconciliation | `NEIGHBORHOOD_ALIASES` |
| adjust "replaces" phrasing | `NONRES_EXISTING`, `REPLACES_KEYWORDS`, `_TEARDOWN_KW` in `build.py` |
| correct a wrong unit count | `config/sources.py` → `UNIT_OVERRIDES[case_no] = n` (only after confirming) |
| all SoQL filters | `scripts/fetch.py` → `build_where` |
| all transform + dedup + audit logic | `scripts/build.py` |

---

## 10. Refresh workflow

```bash
python scripts/update.py        # fetch → build → de-dup → scrape images → snapshot → rebuild
```

Then **read `data/summary.md`** (the digest, ~25 lines): sanity-check the
headline numbers and the Data checks block. Spot-check anything flagged and the
top few projects against SF Planning's project pages / the DBI permit tracker.
Then `git add -A && git commit`.

`data/snapshots/history.jsonl` gains one row per day → the "under construction
over time" chart.
