import unittest
from unittest.mock import patch

import backend.app.services.rankings as rankings
from backend.app import main


class RankingsApiHandlersTest(unittest.TestCase):
    def setUp(self):
        self.production_patch = patch.object(rankings, "is_production", return_value=False)
        self.production_patch.start()

    def tearDown(self):
        self.production_patch.stop()

    def test_health_handler(self):
        self.assertEqual(main.health(), {"status": "ok"})

    def test_auth_login_handler_delegates_to_service(self):
        payload = main.LoginRequest(email="admin@osmosense.local", password="admin123")
        expected = {
            "source": "postgis",
            "token_type": "bearer",
            "access_token": "token",
            "user": {"email": "admin@osmosense.local", "view_mode": "Admin"},
        }
        with patch.object(main, "authenticate_user", return_value=expected) as mocked:
            result = main.post_auth_login(payload)

        mocked.assert_called_once_with("admin@osmosense.local", "admin123")
        self.assertEqual(result, expected)

    def test_me_handler_returns_token_user(self):
        user = {
            "usuario_id": 7,
            "email": "prod@osmosense.local",
            "rol": "productor",
            "cliente_id": 3,
        }

        result = main.get_me(user)

        self.assertEqual(result["source"], "token")
        self.assertEqual(result["user"], user)

    def test_require_productor_with_cliente_rejects_non_productor(self):
        with self.assertRaises(main.HTTPException) as context:
            main.require_productor_with_cliente({"rol": "admin", "cliente_id": None})

        self.assertEqual(context.exception.status_code, 403)

    def test_require_productor_with_cliente_rejects_productor_without_cliente(self):
        with self.assertRaises(main.HTTPException) as context:
            main.require_productor_with_cliente({"rol": "productor", "cliente_id": None})

        self.assertEqual(context.exception.status_code, 403)

    def test_my_latest_geojson_uses_cliente_id_from_token(self):
        user = {"rol": "productor", "cliente_id": 12}
        expected = {
            "source": "postgis",
            "type": "FeatureCollection",
            "cliente_id": 12,
            "features": [],
        }

        with patch.object(main, "latest_geojson_cliente", return_value=expected) as mocked:
            result = main.get_my_latest_ranking_geojson(user)

        mocked.assert_called_once_with(12)
        self.assertEqual(result, expected)

    def test_my_parcelas_uses_cliente_id_from_token(self):
        user = {"rol": "productor", "cliente_id": 12}
        expected = {"source": "postgis", "count": 1, "items": [{"parcela_id": 10}]}

        with patch.object(main, "admin_cliente_parcelas", return_value=expected) as mocked:
            result = main.get_my_parcelas(user)

        mocked.assert_called_once_with(12)
        self.assertEqual(result, expected)

    def test_latest_ranking_handler(self):
        with patch.object(rankings, "database_url", return_value=None):
            result = main.get_latest_ranking(limit=2)

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["count"], 2)

    def test_latest_ranking_handler_reports_missing_database_url_as_503_in_production(self):
        with (
            patch.object(rankings, "is_production", return_value=True),
            patch.object(rankings, "database_url", return_value=None),
        ):
            with self.assertRaises(main.HTTPException) as context:
                main.get_latest_ranking(limit=2)

        self.assertEqual(context.exception.status_code, 503)
        self.assertIn("DATABASE_URL", context.exception.detail)

    def test_latest_geojson_handler(self):
        with patch.object(rankings, "database_url", return_value=None):
            result = main.get_latest_ranking_geojson()

        self.assertEqual(result["source"], "csv")
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertGreater(len(result["features"]), 0)

    def test_latest_geojson_handler_accepts_simplify_meters(self):
        expected = {
            "source": "postgis",
            "type": "FeatureCollection",
            "geometry_simplify_meters": 2.0,
            "features": [],
        }
        with patch.object(main, "latest_geojson", return_value=expected) as mocked:
            result = main.get_latest_ranking_geojson(simplify_meters=2.0)

        mocked.assert_called_once_with(simplify_meters=2.0)
        self.assertEqual(result, expected)

    def test_pipeline_state_handler_delegates_to_service(self):
        expected = {
            "source": "state_file",
            "exists": True,
            "state": {"skipped": True},
            "ranking_summary": {},
        }
        with patch.object(main, "pipeline_state", return_value=expected) as mocked:
            result = main.get_pipeline_state()

        mocked.assert_called_once_with()
        self.assertEqual(result, expected)

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

    def test_admin_usuarios_handler_delegates_to_service(self):
        expected = {"source": "postgis", "count": 1, "items": [{"usuario_id": 1}]}
        with patch.object(main, "admin_usuarios", return_value=expected) as mocked:
            result = main.get_admin_usuarios(limit=10, activo=True)

        mocked.assert_called_once_with(limit=10, activo=True)
        self.assertEqual(result, expected)

    def test_admin_create_usuario_handler_delegates_to_service(self):
        payload = main.UsuarioCreate(
            email="productor.demo@osmosense.local",
            nombre="Productor",
            apellido="Demo",
            dni="30111222",
            rol="productor",
            password="cliente123",
        )
        expected = {"source": "postgis", "item": {"usuario_id": 1}}
        with patch.object(main, "admin_create_usuario", return_value=expected) as mocked:
            result = main.post_admin_usuario(payload)

        mocked.assert_called_once_with(
            {
                "email": "productor.demo@osmosense.local",
                "nombre": "Productor",
                "apellido": "Demo",
                "dni": "30111222",
                "rol": "productor",
                "cliente_id": None,
                "password": "cliente123",
                "activo": True,
            }
        )
        self.assertEqual(result, expected)

    def test_admin_update_usuario_handler_delegates_only_set_fields(self):
        payload = main.UsuarioUpdate(rol="regional", cliente_id=None)
        expected = {"source": "postgis", "item": {"usuario_id": 1}}
        with patch.object(main, "admin_update_usuario", return_value=expected) as mocked:
            result = main.put_admin_usuario(1, payload)

        mocked.assert_called_once_with(1, {"rol": "regional", "cliente_id": None})
        self.assertEqual(result, expected)

    def test_admin_delete_usuario_handler_delegates_to_service(self):
        expected = {"source": "postgis", "deleted": True, "usuario_id": 1}
        with patch.object(main, "admin_deactivate_usuario", return_value=expected) as mocked:
            result = main.delete_admin_usuario(1)

        mocked.assert_called_once_with(1)
        self.assertEqual(result, expected)

    def test_admin_parcelas_handler_delegates_to_service(self):
        expected = {"source": "postgis", "count": 1, "items": [{"parcela_id": 10}]}
        with patch.object(main, "admin_parcelas", return_value=expected) as mocked:
            result = main.get_admin_parcelas(limit=10, cultivo="vid", activo=True)

        mocked.assert_called_once_with(limit=10, cultivo="vid", activo=True, sin_asignar=False)
        self.assertEqual(result, expected)

    def test_admin_parcelas_handler_delegates_sin_asignar(self):
        expected = {"source": "postgis", "count": 1, "items": [{"parcela_id": 10}]}
        with patch.object(main, "admin_parcelas", return_value=expected) as mocked:
            result = main.get_admin_parcelas(
                limit=10,
                cultivo=None,
                activo=True,
                sin_asignar=True,
            )

        mocked.assert_called_once_with(
            limit=10,
            cultivo=None,
            activo=True,
            sin_asignar=True,
        )
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
