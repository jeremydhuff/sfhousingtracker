"""Hand-curated "entitled megaprojects with site work underway" list.

These are NOT counted in the headline numbers (which require an issued *building* permit
for housing — see METHODOLOGY.md §3). They are master-planned projects that are entitled
and have begun infrastructure / site work, or are building out in phases, but whose
remaining homes have no issued building permit yet. The site lists them in a separate
section so they aren't invisible.

Maintenance: review each entry on every refresh. Move a project out of this list once its
buildings show up in the pipeline as `Construction` / `BP Issued` (they then count
automatically). Every entry needs a dated source; keep `homes` as the full-buildout plan
figure, never as a "being built now" count.

Fields: name, area, homes (int, approx full buildout), homes_note (optional caveat on the
figure), status (what has actually started), gap (why the tracker doesn't count it),
source_label, source_url (optional), as_of (YYYY-MM-DD the status was last checked).
"""

AS_OF = "2026-09-20"

MEGAPROJECTS = [
    {
        "name": "Candlestick Point",
        "area": "Bayview Hunters Point",
        "homes": 7200,
        "homes_note": "plan of ~7,200 homes plus 2.8M sq ft office (Pipeline row still shows 9,637 for the old combined Candlestick / Shipyard II plan)",
        "status": "Developer FivePoint broke ground on site infrastructure (roads, sidewalks, utilities) in Sept 2026. First building, ~40% affordable, follows the infrastructure.",
        "gap": "Entitled ('PL Approved'); no housing building permit issued or filed.",
        "source_label": "The Standard, Sept 2026",
        "source_url": "",
        "as_of": AS_OF,
    },
    {
        "name": "Potrero Power Station",
        "area": "Central Waterfront",
        "homes": 2600,
        "homes_note": "master-plan figure; Pipeline row shows 2,228",
        "status": "Phased build-out under way: first affordable building (105 homes) opened; excavation reported under way on Block 2 in Feb 2026.",
        "gap": "Individual buildings count once permitted; the unpermitted remainder of the master plan does not.",
        "source_label": "SF YIMBY, Feb 2026",
        "source_url": "https://sfyimby.com/2026/02/excavation-work-underway-for-potrero-power-station-block-2-san-francisco.html",
        "as_of": AS_OF,
    },
    {
        "name": "Treasure Island / Yerba Buena Island",
        "area": "Treasure Island",
        "homes": 8000,
        "homes_note": "full build-out; ~2,700 affordable",
        "status": "Phase I infrastructure and two housing developments (229 homes) complete; a 100-home senior building was expected to start in Sept 2026.",
        "gap": "Long phased build-out; the remaining phases have no issued building permits.",
        "source_label": "SF YIMBY, July 2026",
        "source_url": "https://sfyimby.com/2026/07/phase-one-of-treasure-island-redevelopment-opens-san-francisco.html",
        "as_of": AS_OF,
    },
    {
        "name": "Balboa Reservoir",
        "area": "West of Twin Peaks",
        "homes": 1100,
        "homes_note": "Blocks A (159) and E (128) are already counted as under construction (11 Frida Kahlo Wy)",
        "status": "Phase 1A infrastructure began Nov 2025. Permits reported filed for 704 more homes in Sept 2026.",
        "gap": "Only the permitted blocks count; later phases are entitled but unpermitted.",
        "source_label": "Hoodline, Sept 2026",
        "source_url": "https://hoodline.com/2026/09/balboa-reservoir-project-files-permits-for-704-more-homes-near-city-college/",
        "as_of": AS_OF,
    },
    {
        "name": "HOPE SF: Potrero and Sunnydale",
        "area": "Potrero Hill / Visitacion Valley",
        "homes": 3100,
        "homes_note": "Potrero 1,400-1,700 and Sunnydale ~1,700 at full build-out; rough sum",
        "status": "City-funded infrastructure and phase-by-phase rebuilds of public-housing sites are under way; some buildings (e.g. on Sunnydale Ave) already count.",
        "gap": "Later phases are entitled but unpermitted; early phases demolish before replacements finish, which also depresses completions.",
        "source_label": "SF.gov HOPE SF announcements",
        "source_url": "https://www.sf.gov/news--city-announces-groundbreaking-critical-infrastructure-sunnydale-and-hunters-view-hope-sf-sites",
        "as_of": AS_OF,
    },
]

# Checked and deliberately NOT listed (see METHODOLOGY.md §7):
#   Stonestown (3,491 entitled 2024)  - Jan 2026 financing plan approved; no site work found.
#   India Basin (1,575 entitled)      - only park construction; developer Build Inc. in loan
#                                       default (Sept 2026); no housing work.
#   Mission Rock, Pier 70, Schlage Lock, Parkmerced, Hunters Point Shipyard - not researched
#                                       this pass; add if a fresh source shows site work.
