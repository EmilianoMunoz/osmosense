import os
import unittest
from unittest.mock import patch

import plotly.graph_objects as go

from frontend.basemap import apply_carto_basemap, carto_raster_url


class CartoBasemapTest(unittest.TestCase):
    def test_builds_authenticated_raster_url(self):
        with patch.dict(
            os.environ,
            {"CARTO_BASEMAP_API_KEY": " test_key "},
            clear=False,
        ):
            url = carto_raster_url()

        self.assertEqual(
            url,
            "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=test_key",
        )

    def test_uses_authenticated_raster_layer(self):
        fig = go.Figure()

        with patch.dict(
            os.environ,
            {"CARTO_BASEMAP_API_KEY": "test_key"},
            clear=False,
        ):
            apply_carto_basemap(fig)

        self.assertEqual(fig.layout.mapbox.style, "white-bg")
        self.assertEqual(len(fig.layout.mapbox.layers), 1)
        self.assertIn("?key=test_key", fig.layout.mapbox.layers[0].source[0])

    def test_falls_back_to_openstreetmap_without_key(self):
        fig = go.Figure()

        with patch.dict(
            os.environ,
            {"CARTO_BASEMAP_API_KEY": ""},
            clear=True,
        ):
            apply_carto_basemap(fig)

        self.assertEqual(fig.layout.mapbox.style, "open-street-map")
        self.assertEqual(len(fig.layout.mapbox.layers), 0)


if __name__ == "__main__":
    unittest.main()
