"""Data source configuration for the SF housing tracker.

Every dataset is on the DataSF Socrata portal (https://data.sfgov.org). No API key is
required; set the SF_APP_TOKEN env var only if you start hitting rate limits.

All resource IDs and filters here were verified live against the API. If the city
retires a dataset, update the id / field map below — nothing else needs to change.
"""

DOMAIN = "data.sfgov.org"

# --- "Real progress" definition -------------------------------------------------
# Which pipeline statuses count as "actually being built". Order = display order.
# Only statuses where a construction permit has actually been ISSUED:
#   "Construction" - permit issued and building underway
#   "BP Issued"    - construction permit issued, work not yet started
# "BP Approved" (Planning signed off but DBI hasn't issued the permit) and
# "BP Filed" (permit only applied for) are deliberately excluded.
CONSTRUCTION_STATUSES = ["Construction", "BP Issued"]
# Flip on to also include projects that have only *applied* for a building permit.
INCLUDE_BP_FILED = False

# How far back the "recently issued permits" freshness layer looks.
PERMIT_LOOKBACK_MONTHS = 24

# --- "Breaking ground now" signal ---------------------------------------------
# A big project pulls its type-1 new-construction permit years before it starts,
# so by the time it's actually under construction that permit is outside the
# 24-month window above and the quarterly pipeline may not list it yet
# (e.g. 2918 Mission St: entitled 2018, type-1 permit 2018, groundwork 2026).
# DBI *groundwork* permits - tower crane, shoring, excavation, soldier piles for
# new construction - are the filing that actually tracks "digging now". We pull
# type-3 permits whose description matches these phrases, carry a unit count, and
# were issued recently, and file them as UNDER CONSTRUCTION.
GROUNDWORK_LOOKBACK_MONTHS = 24
GROUNDWORK_MIN_UNITS = 10
GROUNDWORK_PHRASES = [
    "shoring for new", "shoring and excavation", "excavation for new",
    "foundation for new", "tower crane", "soldier pile", "soldier beam",
]

# --- Datasets -----------------------------------------------------------------

PIPELINE = {
    "name": "pipeline",
    "resource": "6jgi-cpb4",
    "title": "San Francisco Development Pipeline",
    "select": [
        "blklot", "nameaddr", "case_no", "current_status", "current_status_date",
        "net_pipeline_units", "pipeline_affordable_units",
        "existing_units", "demo_units",
        "ret_exist", "pdr_exist", "cie_exist", "mips_exist", "med_exist", "visit_exist",
        "description_planning", "nhood41", "zoning_district",
        "latitude", "longitude",
    ],
    # $where is built at fetch time from CONSTRUCTION_STATUSES / INCLUDE_BP_FILED.
}

PERMITS = {
    "name": "permits",
    "resource": "i98e-djp9",
    "title": "Building Permits",
    "select": [
        "permit_number", "permit_type", "permit_type_definition", "status",
        "issued_date", "primary_address_flag", "adu",
        "street_number", "street_name", "street_suffix",
        "description", "existing_use", "existing_units", "proposed_use", "proposed_units",
        "estimated_cost", "block", "lot",
        "neighborhoods_analysis_boundaries", "supervisor_district", "location",
    ],
    # $where built at fetch time (new-construction, issued, adds units, recent).
}

COMPLETIONS = {
    "name": "completions",
    "resource": "xdht-4php",
    "title": "Housing Production 2005-present",
    "select": [
        "bpa", "address", "description", "blocklot",
        "pts_existing_units", "proposed_units", "net_units", "net_units_completed",
        "affordable_units", "market_rate",
        "first_completion_date", "latest_completion_date",
        "analysis_neighborhood", "supervisor_district", "zoning_district",
        "permit_type", "issued_date",
    ],
    # $where built at fetch time: latest_completion_date >= Jan 1 of YEAR (see build).
    # We pull the last ~6 completed years so year-over-year comparisons work offline.
    "years_back": 6,
}

# Cross-check only — finer-grained TCO/CofO unit counts by permit.
COMPLETION_CERTS = {
    "name": "completion_certs",
    "resource": "j67f-aayr",
    "title": "Dwelling Unit Completion Counts by Building Permit",
    "select": [
        "building_permit_application", "building_address",
        "date_issued", "document_type", "number_of_units_certified",
    ],
    "years_back": 6,
}

ALL_SOURCES = [PIPELINE, PERMITS, COMPLETIONS, COMPLETION_CERTS]

# --- Two-stage model --------------------------------------------------------
# The site shows exactly two categories. Pipeline statuses and DBI permits map in.
STAGE_OF_STATUS = {
    "Construction": "under_construction",
    "BP Issued": "permitted",       # construction permit issued, not yet started
    "BP Filed": "permitted",        # only reached if INCLUDE_BP_FILED is set
}
STAGE_LABEL = {"under_construction": "under construction", "permitted": "permitted"}

# Manual net-unit corrections, keyed by pipeline case_no. Use ONLY when the digest's
# "possibly stale net_pipeline_units" check flags a row and you've confirmed the real
# current scope against SF Planning. Keep a one-line note with the source.
UNIT_OVERRIDES = {
    # 1580 Beach St: net_pipeline_units=9, but case 2025-000742PRJ was revised to
    # "add a total of three ADU units ... not six as previously proposed".
    "2025-000742PRJ": 3,
}

# DBI's "analysis neighborhood" names vs the pipeline's nhood41 names.
NEIGHBORHOOD_ALIASES = {
    "castro/upper market": "Castro - Upper Market",
    "financial district/south beach": "Financial District - South Beach",
    "lone mountain/usf": "Lone Mountain - USF",
    "oceanview/merced/ingleside": "Oceanview - Merced - Ingleside",
    "": "Unknown",
}

# --- Non-residential "what it replaces" hints --------------------------------
# field on the pipeline row -> human phrase, checked in this order.
NONRES_EXISTING = [
    ("ret_exist", "ground-floor retail"),
    ("pdr_exist", "light industrial (PDR)"),
    ("mips_exist", "office space"),
    ("cie_exist", "institutional / community space"),
    ("med_exist", "medical office"),
    ("visit_exist", "hotel / visitor space"),
]

# keyword -> phrase, scanned against planning + permit descriptions (lowercased).
REPLACES_KEYWORDS = [
    ("surface parking", "a surface parking lot"),
    ("parking lot", "a surface parking lot"),
    ("gas station", "a gas station"),
    ("service station", "a gas station"),
    ("vacant lot", "a vacant lot"),
    ("vacant building", "a vacant building"),
    ("vacant", "a vacant lot"),
    ("warehouse", "a warehouse"),
    ("car wash", "a car wash"),
    ("auto repair", "an auto shop"),
    ("one story", "a one-story commercial building"),
    ("single story", "a one-story commercial building"),
]
