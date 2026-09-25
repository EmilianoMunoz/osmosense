import unittest

import pandas as pd

from frontend.map import categorical_map_figure, compact_map_geojson


class CompactMapRenderingTest(unittest.TestCase):
    def setUp(self):
        self.geojson = {
            "type": "FeatureCollection",
            "source": "test",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
                    },
                    "properties": {
                        "parcela_id": 1,
                        "prioridad_visual": "critica",
                        "payload_innecesario": "x" * 100,
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[1, 1], [2, 1], [2, 2], [1, 1]]],
                    },
                    "properties": {
                        "parcela_id": 2,
                        "prioridad_visual": "baja",
                        "payload_innecesario": "y" * 100,
                    },
                },
            ],
        }

    def test_compact_geojson_filters_and_keeps_only_feature_key(self):
        result = compact_map_geojson(self.geojson, {2})

        self.assertEqual(len(result["features"]), 1)
        self.assertEqual(result["features"][0]["properties"], {"parcela_id": 2})

    def test_categorical_figure_uses_one_geometry_trace(self):
        data = compact_map_geojson(self.geojson, {1, 2})
        frame = pd.DataFrame(
            {
                "parcela_id": [1, 2],
                "cultivo": ["vid", "olivo"],
                "prioridad_visual": ["critica", "baja"],
            }
        )

        figure = categorical_map_figure(
            data,
            frame,
            color_by="prioridad_visual",
            color_map={"critica": "#d73027", "baja": "#1a9850"},
            category_order=["critica", "alta", "media", "baja"],
            hover_data={"cultivo": True, "parcela_id": False},
            center={"lat": -34.6, "lon": -68.35},
            zoom=8.3,
            opacity=0.68,
        )

        geometry_traces = [
            trace for trace in figure.data if trace.type == "choroplethmapbox"
        ]
        self.assertEqual(len(geometry_traces), 1)
        self.assertEqual(list(geometry_traces[0].locations), [1, 2])
        self.assertEqual(
            geometry_traces[0].geojson["features"][0]["properties"],
            {"parcela_id": 1},
        )
        self.assertEqual(
            [trace.name for trace in figure.data if trace.type == "scattermapbox"],
            ["critica", "baja"],
        )


if __name__ == "__main__":
    unittest.main()
