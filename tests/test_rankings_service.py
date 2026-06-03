import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

import backend.app.services.rankings as rankings


class RankingsServiceTest(unittest.TestCase):
    def test_latest_ranking_from_local_csv_respects_limit(self):
        with patch.object(rankings, "database_url", return_value=None):
            result = rankings.latest_ranking(limit=2)

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["items"]), 2)

    def test_latest_geojson_from_local_files_returns_feature_collection(self):
        with patch.object(rankings, "database_url", return_value=None):
            result = rankings.latest_geojson()

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertGreater(len(result["features"]), 0)

    def test_latest_geojson_cliente_from_local_files_filters_features(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clientes_path = Path(tmpdir) / "clientes.csv"
            relaciones_path = Path(tmpdir) / "cliente_parcela.csv"
            with patch.object(rankings, "database_url", return_value=None):
                latest = rankings.latest_geojson()
            parcela_id = latest["features"][0]["properties"]["parcela_id"]
            pd.DataFrame(
                [{"cliente_id": 1, "nombre": "Cliente demo", "tipo": "particular"}]
            ).to_csv(clientes_path, index=False)
            pd.DataFrame(
                [{"cliente_id": 1, "parcela_id": parcela_id, "etiqueta": "Finca A"}]
            ).to_csv(relaciones_path, index=False)

            with (
                patch.object(rankings, "database_url", return_value=None),
                patch.object(rankings, "CLIENTES_CSV", str(clientes_path)),
                patch.object(rankings, "CLIENTE_PARCELA_CSV", str(relaciones_path)),
            ):
                result = rankings.latest_geojson_cliente(1)

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["cliente_id"], 1)
        self.assertEqual(result["total_count"], 1)
        self.assertEqual(result["features"][0]["properties"]["parcela_id"], parcela_id)

    def test_regional_um_latest_from_local_files_returns_items(self):
        with patch.object(rankings, "database_url", return_value=None):
            result = rankings.regional_um_latest(limit=2)

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["items"]), 2)
        self.assertIn("um_id", result["items"][0])

    def test_regional_um_latest_geojson_from_local_files_returns_features(self):
        with patch.object(rankings, "database_url", return_value=None):
            result = rankings.regional_um_latest_geojson()

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertGreater(len(result["features"]), 0)
        self.assertIn("um_id", result["features"][0]["properties"])

    def test_regional_um_parcelas_geojson_from_local_files_filters_features(self):
        with patch.object(rankings, "database_url", return_value=None):
            regional = rankings.regional_um_latest(limit=1)
            um_id = int(regional["items"][0]["um_id"])
            result = rankings.regional_um_parcelas_latest_geojson(um_id)

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["um_id"], um_id)
        self.assertGreater(result["total_count"], 0)
        self.assertGreater(len(result["features"]), 0)

    def test_ranking_by_fecha_from_local_csv_respects_limit(self):
        with patch.object(rankings, "database_url", return_value=None):
            result = rankings.ranking_by_fecha("2024-12-31", limit=3)

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["fecha"], "2024-12-31")
        self.assertEqual(result["count"], 3)
        self.assertEqual(len(result["items"]), 3)

    def test_read_ranking_csv_fails_when_required_column_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ranking.csv"
            df = pd.DataFrame(
                [
                    {
                        "fecha_actual": "2024-12-31",
                        "parcela_id": 1,
                        "cultivo": "vid",
                        "ranking_global": 1,
                        "ranking_por_cultivo": 1,
                        "prioridad": "critica",
                        "prioridad_score": 90,
                        "riesgo_actual": 80,
                        "riesgo_pred_5d": 85,
                        "riesgo_pred_10d": 88,
                        "delta_5d": 5,
                    }
                ]
            )
            df.to_csv(path, index=False)

            with self.assertRaisesRegex(ValueError, "delta_10d"):
                rankings._read_ranking_csv(path)

    def test_read_parcelas_geojson_fails_when_id_column_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "parcelas.geojson"
            gdf = gpd.GeoDataFrame(
                {"otro_id": [1]},
                geometry=[Point(-68.3, -34.6)],
                crs="EPSG:4326",
            )
            gdf.to_file(path, driver="GeoJSON")

            with self.assertRaisesRegex(ValueError, "fid"):
                rankings._read_parcelas_geojson(path)


if __name__ == "__main__":
    unittest.main()
