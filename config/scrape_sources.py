"""Ordered list of image-scraper plugins.

The scrape runner tries these in order for each project that has no image yet, and
stops at the first hit. Put rendering sources before fallbacks. `manual` is handled
specially by the runner and always wins when a file is present, regardless of order.

To add a source: drop a new module in scripts/scrape/ that subclasses ImageSource,
then add its class here.
"""

from scripts.scrape.manual import ManualImages
from scripts.scrape.wikimedia import WikimediaCommons
from scripts.scrape.sf_planning import SFPlanningPage
from scripts.scrape.commission_packets import CommissionPacket
from scripts.scrape.parcel_aerial import ParcelAerial

# Order matters. Renderings / real photos first, keyless aerial last as the backstop.
ENABLED_SOURCES = [
    ManualImages,        # hand-picked, always wins
    WikimediaCommons,    # CC renderings + construction photos for the marquee projects
    CommissionPacket,    # stub - Planning Commission packet PDFs (see module docstring)
    SFPlanningPage,      # og:image from sfplanning.org/project/<slug>, rarely hits
    ParcelAerial,        # keyless Esri aerial - covers everything else
]

# Only fetch images for projects at least this big, capped at MAX_IMAGES total
# (keeps the committed site/media/ folder small). Raise if you want more coverage.
MIN_UNITS_FOR_IMAGE = 10
MAX_IMAGES = 150

# Politeness / safety knobs shared by all sources.
REQUEST_TIMEOUT = 20          # seconds
PER_HOST_DELAY = 1.2          # seconds between requests to the same host
MAX_IMAGE_BYTES = 4_000_000   # skip anything larger
THUMB_MAX_PX = 900            # longest edge of the saved thumbnail
USER_AGENT = (
    "sf-housing-tracker/0.1 (local research project; "
    "https://data.sfgov.org open data)"
)
