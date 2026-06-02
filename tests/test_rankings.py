import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

import app.services.rankings as rankings
from app import main


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


class RankingsApiHandlersTest(unittest.TestCase):
    def test_health_handler(self):
        self.assertEqual(main.health(), {"status": "ok"})

    def test_latest_ranking_handler(self):
        with patch.object(rankings, "database_url", return_value=None):
            result = main.get_latest_ranking(limit=2)

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["count"], 2)

    def test_latest_geojson_handler(self):
        with patch.object(rankings, "database_url", return_value=None):
            result = main.get_latest_ranking_geojson()

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertGreater(len(result["features"]), 0)

    def test_ranking_by_fecha_handler(self):
        with patch.object(rankings, "database_url", return_value=None):
            result = main.get_ranking_by_fecha("2024-12-31", limit=3)

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["fecha"], "2024-12-31")
        self.assertEqual(result["count"], 3)

    def test_regional_um_latest_handler(self):
        with patch.object(rankings, "database_url", return_value=None):
            result = main.get_regional_um_latest(limit=2)

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["count"], 2)

    def test_regional_um_latest_geojson_handler(self):
        with patch.object(rankings, "database_url", return_value=None):
            result = main.get_regional_um_latest_geojson()

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["type"], "FeatureCollection")

    def test_regional_um_parcelas_latest_geojson_handler(self):
        with patch.object(rankings, "database_url", return_value=None):
            regional = rankings.regional_um_latest(limit=1)
            um_id = int(regional["items"][0]["um_id"])
            result = main.get_regional_um_parcelas_latest_geojson(um_id)

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["um_id"], um_id)
        self.assertGreater(result["total_count"], 0)

    def test_admin_clientes_handler_delegates_to_service(self):
        expected = {"source": "postgis", "count": 1, "items": [{"cliente_id": 1}]}
        with patch.object(main, "admin_clientes", return_value=expected) as mocked:
            result = main.get_admin_clientes(limit=10)

        mocked.assert_called_once_with(limit=10)
        self.assertEqual(result, expected)

    def test_admin_create_cliente_handler_delegates_to_service(self):
        payload = main.ClienteCreate(nombre="Demo", tipo="particular")
        expected = {"source": "postgis", "item": {"cliente_id": 3}}
        with patch.object(main, "admin_create_cliente", return_value=expected) as mocked:
            result = main.post_admin_cliente(payload)

        mocked.assert_called_once_with(
            {
                "cliente_id": None,
                "nombre": "Demo",
                "tipo": "particular",
                "descripcion": None,
                "activo": True,
            }
        )
        self.assertEqual(result, expected)

    def test_admin_update_cliente_handler_delegates_only_set_fields(self):
        payload = main.ClienteUpdate(nombre="Nuevo nombre")
        expected = {"source": "postgis", "item": {"cliente_id": 1}}
        with patch.object(main, "admin_update_cliente", return_value=expected) as mocked:
            result = main.put_admin_cliente(1, payload)

        mocked.assert_called_once_with(1, {"nombre": "Nuevo nombre"})
        self.assertEqual(result, expected)

    def test_admin_cliente_parcelas_handler_delegates_to_service(self):
        expected = {"source": "postgis", "count": 1, "items": [{"parcela_id": 10}]}
        with patch.object(main, "admin_cliente_parcelas", return_value=expected) as mocked:
            result = main.get_admin_cliente_parcelas(1)

        mocked.assert_called_once_with(1)
        self.assertEqual(result, expected)

    def test_admin_assign_cliente_parcela_handler_delegates_to_service(self):
        payload = main.ClienteParcelaAssign(parcela_id=10, etiqueta="Cuadro norte")
        expected = {"source": "postgis", "item": {"cliente_id": 1, "parcela_id": 10}}
        with patch.object(main, "admin_assign_cliente_parcela", return_value=expected) as mocked:
            result = main.post_admin_cliente_parcela(1, payload)

        mocked.assert_called_once_with(1, 10, "Cuadro norte")
        self.assertEqual(result, expected)

    def test_admin_delete_cliente_parcela_handler_delegates_to_service(self):
        expected = {"source": "postgis", "deleted": True, "cliente_id": 1, "parcela_id": 10}
        with patch.object(main, "admin_delete_cliente_parcela", return_value=expected) as mocked:
            result = main.delete_admin_cliente_parcela(1, 10)

        mocked.assert_called_once_with(1, 10)
        self.assertEqual(result, expected)

    def test_admin_parcelas_handler_delegates_to_service(self):
        expected = {"source": "postgis", "count": 1, "items": [{"parcela_id": 10}]}
        with patch.object(main, "admin_parcelas", return_value=expected) as mocked:
            result = main.get_admin_parcelas(limit=10, cultivo="vid", activo=True)

        mocked.assert_called_once_with(limit=10, cultivo="vid", activo=True)
        self.assertEqual(result, expected)

    def test_admin_parcela_handler_delegates_to_service(self):
        expected = {"source": "postgis", "item": {"parcela_id": 10}}
        with patch.object(main, "admin_parcela", return_value=expected) as mocked:
            result = main.get_admin_parcela(10)

        mocked.assert_called_once_with(10)
        self.assertEqual(result, expected)

    def test_admin_parcelas_disponibles_handler_delegates_to_service(self):
        expected = {"source": "postgis", "count": 1, "items": [{"parcela_id": 20}]}
        with patch.object(main, "admin_parcelas_disponibles", return_value=expected) as mocked:
            result = main.get_admin_parcelas_disponibles(limit=5)

        mocked.assert_called_once_with(limit=5)
        self.assertEqual(result, expected)

    def test_admin_activar_parcela_disponible_handler_delegates_to_service(self):
        payload = main.ParcelaDisponibleActivar(
            cultivo_oficial="vid",
            cliente_id=1,
            etiqueta="Nuevo cuadro",
        )
        expected = {"source": "postgis", "item": {"parcela_id": 20}}
        with patch.object(
            main,
            "admin_activar_parcela_disponible",
            return_value=expected,
        ) as mocked:
            result = main.post_admin_activar_parcela_disponible(20, payload)

        mocked.assert_called_once_with(
            parcela_id=20,
            cultivo_oficial="vid",
            cliente_id=1,
            etiqueta="Nuevo cuadro",
        )
        self.assertEqual(result, expected)

    def test_admin_create_parcela_handler_delegates_to_service(self):
        geometry = {
            "type": "Polygon",
            "coordinates": [
                [
                    [-68.4, -34.7],
                    [-68.399, -34.7],
                    [-68.399, -34.699],
                    [-68.4, -34.699],
                    [-68.4, -34.7],
                ]
            ],
        }
        payload = main.ParcelaCreate(
            parcela_id=900001,
            cultivo_oficial="vid",
            geometry=geometry,
            fuente="manual",
            cultivo_original="FRUTALES",
        )
        expected = {"source": "postgis", "item": {"parcela_id": 900001}}
        with patch.object(main, "admin_create_parcela", return_value=expected) as mocked:
            result = main.post_admin_parcela(payload)

        mocked.assert_called_once_with(
            {
                "parcela_id": 900001,
                "cultivo_oficial": "vid",
                "geometry": geometry,
                "area_m2": None,
                "fuente": "manual",
                "globalid": None,
                "cultivo_original": "FRUTALES",
                "activo": True,
            }
        )
        self.assertEqual(result, expected)

    def test_admin_update_parcela_handler_delegates_only_set_fields(self):
        payload = main.ParcelaUpdate(cultivo_oficial="olivo")
        expected = {"source": "postgis", "item": {"parcela_id": 10}}
        with patch.object(main, "admin_update_parcela", return_value=expected) as mocked:
            result = main.put_admin_parcela(10, payload)

        mocked.assert_called_once_with(10, {"cultivo_oficial": "olivo"})
        self.assertEqual(result, expected)

    def test_admin_delete_parcela_handler_delegates_to_service(self):
        expected = {"source": "postgis", "deleted": True, "parcela_id": 10}
        with patch.object(main, "admin_deactivate_parcela", return_value=expected) as mocked:
            result = main.delete_admin_parcela(10)

        mocked.assert_called_once_with(10)
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
