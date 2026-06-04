import unittest

import pandas as pd

from frontend.logic import (
    add_dynamic_priority,
    add_regional_dynamic_priority,
    display_delta,
    display_risk,
    review_priority,
)
from frontend import data as frontend_data
from frontend.data import filtered_geojson
from frontend.map import enrich_map_hover, map_hover_data, risk_animation_frame
from frontend.components.charts import parcela_label
from frontend.components.client_overview import client_status_summary
from frontend.table_config import CLIENT_FORBIDDEN_COLUMNS, column_labels, table_columns


class FrontendLogicTest(unittest.TestCase):
    def test_display_risk_uses_operational_projection_for_admin(self):
        row = pd.Series(
            {
                "riesgo_pred_5d": 62.7,
                "riesgo_operativo_5d": 65.9,
            }
        )

        self.assertEqual(display_risk(row, 5, admin_mode=True), 65.9)

    def test_display_risk_uses_operational_projection_for_client(self):
        row = pd.Series(
            {
                "riesgo_pred_5d": 62.7,
                "riesgo_operativo_5d": 65.9,
            }
        )

        self.assertEqual(display_risk(row, 5, admin_mode=False), 65.9)

    def test_display_risk_falls_back_to_raw_prediction_for_old_rankings(self):
        row = pd.Series({"riesgo_pred_10d": 60.8})

        self.assertEqual(display_risk(row, 10, admin_mode=False), 60.8)

    def test_display_delta_uses_operational_delta_for_client(self):
        row = pd.Series(
            {
                "delta_10d": -3.6,
                "delta_operativo_10d": 2.9,
            }
        )

        self.assertEqual(display_delta(row, 10, admin_mode=False), 2.9)

    def test_dynamic_priority_does_not_modify_priority_score(self):
        df = pd.DataFrame(
            {
                "ranking_global": list(range(1, 11)),
                "prioridad": ["baja"] * 10,
                "prioridad_score": [100.0, 90.0, 80.0, 70.0, 60.0, 50.0, 40.0, 30.0, 20.0, 10.0],
            }
        )

        result = add_dynamic_priority(df, "Relativa por percentiles")

        self.assertEqual(
            result["prioridad_score"].tolist(),
            [100.0, 90.0, 80.0, 70.0, 60.0, 50.0, 40.0, 30.0, 20.0, 10.0],
        )
        self.assertEqual(result["prioridad_visual"].iloc[0], "critica")
        self.assertEqual(result["prioridad_visual"].iloc[1], "alta")
        self.assertEqual(result["prioridad_visual"].iloc[3], "media")
        self.assertEqual(result["prioridad_visual"].iloc[-1], "baja")

    def test_regional_dynamic_priority_uses_weighted_regional_score(self):
        df = pd.DataFrame(
            {
                "prioridad_regional": ["baja"] * 10,
                "prioridad_score_prom_pond": [
                    100.0,
                    90.0,
                    80.0,
                    70.0,
                    60.0,
                    50.0,
                    40.0,
                    30.0,
                    20.0,
                    10.0,
                ],
            }
        )

        result = add_regional_dynamic_priority(df, "Relativa por percentiles")

        self.assertEqual(result["prioridad_regional"].tolist(), ["baja"] * 10)
        self.assertEqual(result["prioridad_regional_visual"].iloc[0], "critica")
        self.assertEqual(result["prioridad_regional_visual"].iloc[1], "alta")
        self.assertEqual(result["prioridad_regional_visual"].iloc[3], "media")
        self.assertEqual(result["prioridad_regional_visual"].iloc[-1], "baja")

    def test_client_hover_uses_operational_projection(self):
        df = pd.DataFrame(
            {
                "riesgo_pred_5d": [62.7],
                "riesgo_pred_10d": [60.8],
                "delta_10d": [-3.6],
                "riesgo_operativo_5d": [65.9],
                "riesgo_operativo_10d": [67.4],
                "delta_operativo_10d": [2.9],
            }
        )

        result = enrich_map_hover(df, admin_mode=False)

        self.assertEqual(result["riesgo_5_dias"].iloc[0], 65.9)
        self.assertEqual(result["riesgo_10_dias"].iloc[0], 67.4)
        self.assertEqual(result["delta_10_dias"].iloc[0], 2.9)

    def test_admin_hover_uses_operational_projection(self):
        df = pd.DataFrame(
            {
                "riesgo_pred_5d": [62.7],
                "riesgo_pred_10d": [60.8],
                "delta_10d": [-3.6],
                "riesgo_operativo_5d": [65.9],
                "riesgo_operativo_10d": [67.4],
                "delta_operativo_10d": [2.9],
            }
        )

        result = enrich_map_hover(df, admin_mode=True)

        self.assertEqual(result["riesgo_5_dias"].iloc[0], 65.9)
        self.assertEqual(result["riesgo_10_dias"].iloc[0], 67.4)
        self.assertEqual(result["delta_10_dias"].iloc[0], 2.9)

    def test_risk_animation_frame_interpolates_days_and_categories(self):
        df = pd.DataFrame(
            {
                "parcela_id": list(range(1, 11)),
                "riesgo_actual": [20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 10.0, 5.0],
                "riesgo_5_dias": [25.0, 35.0, 45.0, 55.0, 65.0, 75.0, 85.0, 95.0, 15.0, 10.0],
                "riesgo_10_dias": [30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 20.0, 15.0],
            }
        )

        result = risk_animation_frame(df)

        self.assertEqual(sorted(result["dia_proyeccion"].unique().tolist()), list(range(11)))
        first = result[(result["dia_proyeccion"] == 0) & (result["parcela_id"] == 1)]
        top = result[(result["dia_proyeccion"] == 0) & (result["parcela_id"] == 8)]
        self.assertEqual(first["riesgo_mapa"].iloc[0], 20.0)
        self.assertEqual(top["riesgo_categoria"].iloc[0], "critica")
        self.assertEqual(first["riesgo_categoria"].iloc[0], "baja")

    def test_client_table_does_not_expose_technical_columns(self):
        available = {
            "parcela_id",
            "cultivo",
            "prioridad_visual",
            "riesgo_actual",
            "riesgo_pred_5d",
            "riesgo_pred_10d",
            "riesgo_operativo_5d",
            "riesgo_operativo_10d",
            "diagnostico_outlier",
            "motivo_ruido",
            "accion_recomendada",
            "confianza_lectura",
        }

        cols = table_columns(admin_mode=False, available_columns=available)

        self.assertIn("riesgo_operativo_5d", cols)
        self.assertIn("riesgo_operativo_10d", cols)
        self.assertTrue(CLIENT_FORBIDDEN_COLUMNS.isdisjoint(cols))

    def test_smoothed_conflict_is_not_pending_review(self):
        row = pd.Series(
            {
                "score_suavizado": True,
                "accion_recomendada": "revisar_visual_antes_de_suavizar",
                "outlier_especial": False,
                "outlier_espacial": True,
            }
        )

        self.assertEqual(review_priority(row), 99)

    def test_admin_table_keeps_raw_and_operational_prediction_columns(self):
        available = {
            "parcela_id",
            "riesgo_pred_5d",
            "riesgo_pred_10d",
            "riesgo_operativo_5d",
            "riesgo_operativo_10d",
            "diagnostico_outlier",
        }

        cols = table_columns(admin_mode=True, available_columns=available)

        self.assertIn("riesgo_operativo_5d", cols)
        self.assertIn("riesgo_operativo_10d", cols)
        self.assertIn("riesgo_pred_5d", cols)
        self.assertIn("riesgo_pred_10d", cols)
        self.assertLess(cols.index("riesgo_operativo_5d"), cols.index("riesgo_pred_5d"))
        self.assertIn("diagnostico_outlier", cols)

    def test_client_table_labels_are_human_readable(self):
        labels = column_labels(["prioridad_visual", "riesgo_operativo_5d", "delta_operativo_10d"])

        self.assertEqual(labels["prioridad_visual"], "Prioridad")
        self.assertEqual(labels["riesgo_operativo_5d"], "Proyección 5 días")
        self.assertEqual(labels["delta_operativo_10d"], "Cambio proyectado 10 días")

    def test_client_status_summary_uses_operational_projection(self):
        df = pd.DataFrame(
            {
                "ranking_global": [1, 2, 3, 4],
                "prioridad_visual": ["critica", "alta", "media", "baja"],
                "riesgo_actual": [60.0, 50.0, 30.0, 20.0],
                "riesgo_operativo_10d": [68.0, 56.0, 33.0, 21.0],
            }
        )

        summary = client_status_summary(df)

        self.assertEqual(summary["high_or_critical"], 2)
        self.assertEqual(summary["critical"], 1)
        self.assertEqual(summary["status"], "Atención alta")
        self.assertAlmostEqual(summary["projected_change"], 4.5)

    def test_client_parcela_label_hides_ranking_and_score(self):
        row = pd.Series(
            {
                "ranking_global": 12,
                "parcela_id": 43070,
                "cultivo": "vid",
                "prioridad": "alta",
                "prioridad_visual": "critica",
                "prioridad_score": 88.2,
            }
        )

        label = parcela_label(row, admin_mode=False)

        self.assertEqual(label, "Parcela 43070 · vid · Prioridad crítica")
        self.assertNotIn("#12", label)
        self.assertNotIn("score", label)

    def test_client_hover_hides_ranking_score_and_technical_fields(self):
        df = pd.DataFrame(
            {
                "confianza_lectura": ["alta"],
                "diagnostico_outlier": ["indeterminado"],
                "motivo_ruido": ["x"],
                "ranking_global": [1],
                "prioridad_score": [90.0],
            }
        )

        hover = map_hover_data(admin_mode=False, df=df)

        self.assertIn("confianza_lectura", hover)
        self.assertNotIn("ranking_global", hover)
        self.assertNotIn("prioridad_score", hover)
        self.assertNotIn("diagnostico_outlier", hover)
        self.assertNotIn("motivo_ruido", hover)

    def test_admin_hover_ignores_missing_optional_estado_cobertura(self):
        df = pd.DataFrame(
            {
                "cultivo": ["vid"],
                "prioridad_visual_label": ["Alta"],
                "prioridad_score": [50.0],
                "riesgo_actual": [60.0],
                "riesgo_5_dias": [62.0],
                "riesgo_10_dias": [64.0],
                "delta_10_dias": [4.0],
                "ranking_global": [1],
                "parcela_id": [123],
            }
        )

        hover = map_hover_data(admin_mode=True, df=df)

        self.assertNotIn("estado_cobertura", hover)
        self.assertIn("ranking_global", hover)

    def test_filtered_geojson_keeps_only_geometry_and_parcela_id(self):
        data = {
            "type": "FeatureCollection",
            "source": "test",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {
                        "parcela_id": 1,
                        "ranking_global": 10,
                        "prioridad_score": 55.0,
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [1, 1]},
                    "properties": {"parcela_id": 2, "ranking_global": 20},
                },
            ],
        }

        result = filtered_geojson(data, {1})

        self.assertEqual(len(result["features"]), 1)
        self.assertEqual(result["features"][0]["properties"], {"parcela_id": 1})
        self.assertEqual(result["features"][0]["geometry"]["type"], "Point")

    def test_admin_disponibles_to_geojson_converts_items_to_features(self):
        data = {
            "source": "postgis",
            "count": 1,
            "items": [
                {
                    "parcela_id": 10,
                    "cultivo_original": "FRUTALES",
                    "cultivo_oficial": "frutales",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                }
            ],
        }

        result = frontend_data.admin_disponibles_to_geojson(data)

        self.assertEqual(result["source"], "postgis")
        self.assertEqual(result["features"][0]["properties"]["parcela_id"], 10)
        self.assertEqual(result["features"][0]["properties"]["cultivo_original"], "FRUTALES")
        self.assertNotIn("geometry", result["features"][0]["properties"])

    def test_regional_um_parcelas_fallback_keeps_full_properties(self):
        geojson = {
            "type": "FeatureCollection",
            "source": "local",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {
                        "parcela_id": 1,
                        "prioridad": "alta",
                        "ranking_global": 10,
                    },
                }
            ],
        }
        mapping = pd.DataFrame({"um_id": [7], "parcela_id": [1]})

        with (
            unittest.mock.patch.object(
                frontend_data,
                "fetch_regional_um_parcelas_geojson_from_api",
                return_value=None,
            ),
            unittest.mock.patch.object(frontend_data, "load_parcelas_um", return_value=mapping),
            unittest.mock.patch.object(frontend_data, "load_geojson", return_value=geojson),
        ):
            result = frontend_data.load_regional_um_parcelas_geojson(7)

        self.assertEqual(result["features"][0]["properties"]["prioridad"], "alta")
        self.assertEqual(result["features"][0]["properties"]["ranking_global"], 10)


if __name__ == "__main__":
    unittest.main()
