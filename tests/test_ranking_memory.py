import unittest
import warnings

import pandas as pd
from pandas.errors import PerformanceWarning

from backend.scripts.pipeline.generar_ranking_hidrico import (
    preparar_observaciones_latest,
    seleccionar_fecha,
)
from backend.scripts.pipeline.generar_targets_hidricos_regresion import (
    BASE_FEATURES,
    preparar_observaciones,
)


class RankingMemoryTest(unittest.TestCase):
    def test_latest_only_features_match_full_historical_preparation(self):
        rows = []
        dates = pd.date_range("2026-09-01", periods=6, freq="5D")
        parcels = [(1, "vid"), (2, "vid"), (3, "olivo"), (4, "olivo")]
        for date_index, current_date in enumerate(dates):
            for parcel_id, crop in parcels:
                row = {
                    "parcela_id": parcel_id,
                    "cultivo": crop,
                    "fecha": current_date.strftime("%Y-%m-%d"),
                    "fecha_fin": (current_date + pd.Timedelta(days=5)).strftime(
                        "%Y-%m-%d"
                    ),
                    "area_m2": 5000 + parcel_id,
                    "window_days": 5,
                    "month": current_date.month,
                    "day_of_year": current_date.dayofyear,
                }
                for feature_index, feature in enumerate(BASE_FEATURES):
                    row[feature] = (
                        1.0
                        + feature_index * 0.05
                        + parcel_id * 0.1
                        + date_index * 0.2
                    )
                rows.append(row)

        source = pd.DataFrame(rows)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", PerformanceWarning)
            full = preparar_observaciones(source)
        expected, expected_date = seleccionar_fecha(full, None, 15)
        result, result_date = preparar_observaciones_latest(source, None, 15)

        self.assertEqual(result_date, expected_date)
        self.assertEqual(set(result.columns), set(expected.columns))
        columns = sorted(expected.columns)
        expected = expected.sort_values("parcela_id")[columns].reset_index(drop=True)
        result = result.sort_values("parcela_id")[columns].reset_index(drop=True)
        pd.testing.assert_frame_equal(
            result,
            expected,
            check_dtype=False,
            check_exact=False,
            rtol=1e-12,
            atol=1e-12,
        )


if __name__ == "__main__":
    unittest.main()
