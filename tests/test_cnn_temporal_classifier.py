import unittest

import numpy as np
import pandas as pd

from backend.scripts.experiments.entrenar_cnn_temporal_clasificacion import (
    build_temporal_sequences,
    temporal_feature_columns,
)


class TemporalCnnClassifierTest(unittest.TestCase):
    def test_temporal_feature_columns_keep_spectral_stats(self):
        df = pd.DataFrame(
            {
                "parcela_id": ["1"],
                "cultivo": ["vid"],
                "fecha": ["2024-01-01"],
                "year": [2024],
                "month": [1],
                "ndvi_mean": [0.5],
                "ndvi_stddev": [0.1],
                "ndvi_count": [20],
                "b11_max": [1200.0],
                "scl_mean": [4.0],
                "area_m2": [5000.0],
            }
        )

        features = temporal_feature_columns(
            df,
            target="cultivo",
            id_col="parcela_id",
            date_col="fecha",
            feature_set="mean-std",
        )

        self.assertEqual(features, ["ndvi_mean", "ndvi_stddev"])

    def test_build_temporal_sequences_returns_parcel_date_feature_tensor(self):
        rows = []
        for parcela_id, cultivo in [("1", "vid"), ("2", "olivo")]:
            for fecha, ndvi in [
                ("2024-01-01", 0.2),
                ("2024-03-01", 0.4),
                ("2024-06-01", 0.6),
            ]:
                rows.append(
                    {
                        "parcela_id": parcela_id,
                        "cultivo": cultivo,
                        "fecha": fecha,
                        "ndvi_mean": ndvi + int(parcela_id) * 0.01,
                        "msi_mean": 1.0 - ndvi,
                    }
                )
        df = pd.DataFrame(rows)

        x, y, parcel_ids, dates, class_names = build_temporal_sequences(
            df,
            id_col="parcela_id",
            date_col="fecha",
            target="cultivo",
            features=["ndvi_mean", "msi_mean"],
            classes=["vid", "olivo"],
            min_timesteps=3,
        )

        self.assertEqual(x.shape, (2, 3, 2))
        self.assertEqual(parcel_ids.tolist(), ["1", "2"])
        self.assertEqual(dates, ["2024-01-01", "2024-03-01", "2024-06-01"])
        self.assertEqual(class_names, ["olivo", "vid"])
        self.assertTrue(np.array_equal(y, np.array([1, 0])))


if __name__ == "__main__":
    unittest.main()
