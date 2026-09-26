import unittest

import pandas as pd

from frontend.components.tables import (
    build_table_dataframe,
    review_cases_dataframe,
)


class AdminTablePresentationTest(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame(
            {
                "ranking_global": [2, 1],
                "ranking_por_cultivo": [2, 1],
                "parcela_id": [20, 10],
                "cultivo": ["olivo", "vid"],
                "prioridad_visual": ["alta", "critica"],
                "prioridad": ["alta", "critica"],
                "prioridad_score": [52.3456, 61.8765],
                "riesgo_actual": [60.248, 89.9493],
                "riesgo_operativo_5d": [64.456, 95.2393],
                "riesgo_operativo_10d": [70.678, 100.0],
                "delta_operativo_10d": [10.43, 10.0507],
                "riesgo_pred_5d": [59.2345, 87.4629],
            }
        )

    def test_operational_table_keeps_only_decision_columns(self):
        result = build_table_dataframe(
            self.frame,
            admin_mode=True,
            technical=False,
        )

        self.assertEqual(
            result.columns.tolist(),
            [
                "Ranking",
                "Parcela",
                "Cultivo",
                "Prioridad",
                "Riesgo actual",
                "Proyección 5 días",
                "Proyección 10 días",
                "Cambio proyectado 10 días",
            ],
        )
        self.assertEqual(result.iloc[0]["Parcela"], 10)
        self.assertEqual(result.iloc[0]["Riesgo actual"], 89.9)
        self.assertNotIn("Predicción 5 días", result.columns)

    def test_technical_table_keeps_model_columns(self):
        result = build_table_dataframe(
            self.frame,
            admin_mode=True,
            technical=True,
        )

        self.assertIn("Score", result.columns)
        self.assertIn("Predicción 5 días", result.columns)
        self.assertEqual(result.iloc[0]["Score"], 61.88)


class ReviewCasesPresentationTest(unittest.TestCase):
    def test_empty_review_returns_empty_frame(self):
        frame = pd.DataFrame(
            {
                "parcela_id": [1],
                "ranking_global": [1],
                "confianza_lectura": ["alta"],
            }
        )

        self.assertTrue(review_cases_dataframe(frame).empty)

    def test_review_frame_uses_human_labels(self):
        frame = pd.DataFrame(
            {
                "parcela_id": [1],
                "ranking_global": [1],
                "confianza_lectura": ["baja"],
                "riesgo_actual": [55.678],
            }
        )

        result = review_cases_dataframe(frame)

        self.assertEqual(
            result.columns.tolist(),
            ["Ranking", "Parcela", "Confianza", "Riesgo actual"],
        )
        self.assertEqual(result.iloc[0]["Riesgo actual"], 55.68)


if __name__ == "__main__":
    unittest.main()
