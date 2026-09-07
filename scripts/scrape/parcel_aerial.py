"""Keyless fallback: an aerial photo of the project site.

Uses Esri's public World Imagery export endpoint (no API key). Always available for
any project that has coordinates, so it guarantees every prominent project shows
*something* even when no rendering is found.
"""

from __future__ import annotations

from scripts.scrape.base import ImageResult, ImageSource, http_get

EXPORT = (
    "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/"
    "export?bbox={minx},{miny},{maxx},{maxy}&bboxSR=4326&imageSR=3857"
    "&size=512,340&format=jpg&f=image"
)
# ~140 m half-window (degrees). Longitude term is close enough at SF's latitude.
DLAT = 0.00063
DLON = 0.00080


class ParcelAerial(ImageSource):
    name = "parcel_aerial"

    def find(self, project: dict) -> ImageResult | None:
        lat, lon = project.get("lat"), project.get("lon")
        if lat is None or lon is None:
            return None
        url = EXPORT.format(
            minx=lon - DLON, miny=lat - DLAT, maxx=lon + DLON, maxy=lat + DLAT
        )
        got = http_get(url, want_binary=True)
        if not got:
            return None
        data, ctype = got
        if not ctype.startswith("image/"):
            ctype = "image/jpeg"
        return ImageResult(
            data=data,
            content_type=ctype,
            caption="The site today - aerial imagery (Esri World Imagery)",
            source=self.name,
            source_url="https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9",
        )
