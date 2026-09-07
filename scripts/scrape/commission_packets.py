"""Best-effort rendering source: SF Planning Commission case reports (PDFs).

STATUS: template / stub. The Commission publishes weekly agenda packets and per-case
"Executive Summary" PDFs that contain renderings, but there is no keyless per-case
index to look them up by address or case number. Implementing this well means either:
  * crawling the weekly hearing archive at sfplanning.org/hearings/planning-commission
    and matching case numbers, or
  * using the Commission's Legistar/Granicus calendar if one is exposed.

Until then this returns None for every project (the runner just moves on).

The PDF-image plumbing is already done: `base.pdf_first_image(pdf_bytes)` pulls the
largest embedded JPEG (renderings are DCTDecode streams) out of a packet. What's
missing is the address/case-number -> packet-URL lookup. Build-out sketch:

    pdf = http_get(packet_url, want_binary=True)          # from the hearing archive
    jpg = pdf_first_image(pdf[0])
    return ImageResult(jpg, "image/jpeg", caption, self.name, packet_url)
"""

from __future__ import annotations

from scripts.scrape.base import ImageResult, ImageSource, pdf_first_image  # noqa: F401


class CommissionPacket(ImageSource):
    name = "commission_packets"
    enabled = False  # runner skips sources with enabled = False

    def find(self, project: dict) -> ImageResult | None:
        return None
