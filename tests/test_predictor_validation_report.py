import unittest

import pandas as pd

from backend.scripts.modeling.generar_reporte_validacion_predictor_hidrico import (
    aggregate_summary,
    detail_metrics,
    worst_dates,
)


class PredictorValidationReportTest(unittest.TestCase):
    def test_aggregate_summary_uses_weighted_metrics(self):
        summary = pd.DataFrame(
            {
                "fecha": ["2024-01-01", "2024-01-06"],
                "cultivo": ["global", "global"],
                "horizon_days": [5, 5],
                "n": [100, 300],
                "mae": [2.0, 6.0],
                "rmse": [3.0, 7.0],
                "bias": [1.0, -1.0],
                "spearman": [0.9, 0.7],
                "top10_overlap": [0.8, 0.4],
            }
        )

        result = aggregate_summary(summary)
        row = result.iloc[0]

        self.assertEqual(row["fechas"], 2)
        self.assertAlmostEqual(row["mae"], 5.0)
        self.assertAlmostEqual(row["spearman"], 0.75)

    def test_detail_metrics_reports_error_tolerance_and_direction(self):
        detail = pd.DataFrame(
            {
                "cultivo": ["vid", "vid", "olivo"],
                "riesgo_pred_5d": [55.0, 40.0, 70.0],
                "riesgo_obs_5d": [52.0, 52.0, 65.0],
                "delta_5d": [5.0, -2.0, 4.0],
                "delta_obs_5d": [4.0, 3.0, 5.0],
                "error_5d": [3.0, -12.0, 5.0],
                "riesgo_pred_10d": [60.0, 42.0, 75.0],
                "riesgo_obs_10d": [58.0, 50.0, 70.0],
                "delta_10d": [10.0, 0.0, 7.0],
                "delta_obs_10d": [9.0, 1.0, 8.0],
                "error_10d": [2.0, -8.0, 5.0],
            }
        )

        result = detail_metrics(detail)
        vid_5d = result[(result["cultivo"] == "vid") & (result["horizon_days"] == 5)].iloc[0]
        global_10d = result[
            (result["cultivo"] == "global") & (result["horizon_days"] == 10)
        ].iloc[0]

        self.assertAlmostEqual(vid_5d["pct_error_le_5"], 0.5)
        self.assertAlmostEqual(vid_5d["direction_accuracy"], 0.5)
        self.assertAlmostEqual(global_10d["pct_error_le_10"], 1.0)

    def test_worst_dates_combines_mae_and_spearman_criteria(self):
        summary = pd.DataFrame(
            {
                "fecha": ["2024-01-01", "2024-01-06", "2024-01-11"],
                "estacion": ["verano", "verano", "verano"],
                "cultivo": ["global", "global", "vid"],
                "horizon_days": [5, 5, 5],
                "n": [100, 100, 50],
                "mae": [2.0, 8.0, 10.0],
                "rmse": [3.0, 9.0, 11.0],
                "bias": [0.0, 1.0, 2.0],
                "spearman": [0.9, 0.5, 0.1],
                "top10_overlap": [0.8, 0.3, 0.1],
            }
        )

        result = worst_dates(summary, top=1)

        self.assertEqual(result["criterio"].tolist(), ["mayor_mae", "menor_spearman"])
        self.assertEqual(result["fecha"].tolist(), ["2024-01-06", "2024-01-06"])


if __name__ == "__main__":
    unittest.main()
