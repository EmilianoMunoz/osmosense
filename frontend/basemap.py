from __future__ import annotations

import os
from urllib.parse import quote

from dotenv import load_dotenv

CARTO_RASTER_TEMPLATE = (
    "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"
)
CARTO_ATTRIBUTION = "© OpenStreetMap contributors © CARTO"


def carto_raster_url() -> str | None:
    load_dotenv()
    api_key = "".join(os.getenv("CARTO_BASEMAP_API_KEY", "").split())
    if not api_key:
        return None
    return f"{CARTO_RASTER_TEMPLATE}?key={quote(api_key, safe='')}"


def apply_carto_basemap(fig) -> None:
    tile_url = carto_raster_url()
    if tile_url is None:
        fig.update_layout(mapbox_style="open-street-map")
        return

    fig.update_layout(
        mapbox_style="white-bg",
        mapbox_layers=[
            {
                "below": "traces",
                "sourcetype": "raster",
                "source": [tile_url],
                "sourceattribution": CARTO_ATTRIBUTION,
            }
        ],
    )
