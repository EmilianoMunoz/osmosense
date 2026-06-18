import argparse
import tempfile
import unittest
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from backend.scripts.experiments import generar_dataset_clasificacion_multiclase as multi
from backend.scripts.experiments.entrenar_clasificador_tensorflow import (
    add_temporal_features,
    binary_threshold_metrics,
    classification_feature_columns,
    prepare_dataset,
    split_train_validation_test,
)


class TensorFlowClassifierExperimentTest(unittest.TestCase):
    def test_multiclass_crop_normalization_keeps_requested_classes(self):
        self.assertEqual(multi.normalizar_cultivo_multiclase("VID"), "vid")
        self.assertEqual(multi.normalizar_cultivo_multiclase("OLIVOS"), "olivo")
        self.assertEqual(multi.normalizar_cultivo_multiclase("FRUTALES"), "frutales")
        self.assertEqual(multi.normalizar_cultivo_multiclase("INCULTOS"), "incultos")
        self.assertEqual(multi.normalizar_cultivo_multiclase("ANUALES"), "anuales")
        self.assertIsNone(multi.normalizar_cultivo_multiclase(""))

    def test_prepare_multiclass_sample_balances_classes(self):
        gdf = gpd.GeoDataFrame(
            {
                "fid": list(range(10)),
                "tipo_culti": [
                    "VID",
                    "VID",
                    "OLIVOS",
                    "OLIVOS",
                    "FRUTALES",
                    "FRUTALES",
                    "INCULTOS",
                    "INCULTOS",
                    "ANUALES",
                    "ANUALES",
                ],
                "area_m2": [5000.0] * 10,
            },
            geometry=[Point(float(i), float(i)) for i in range(10)],
            crs="EPSG:4326",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            args = argparse.Namespace(
                input="unused.geojson",
                output_sample=str(Path(tmpdir) / "sample.geojson"),
                reuse_sample=False,
                classes=["vid", "olivo", "frutales", "incultos", "anuales"],
                area_minima_m2=4000,
                samples_per_class=1,
            )
            original_read_file = multi.gpd.read_file
            try:
                multi.gpd.read_file = lambda _: gdf.copy()
                sample = multi.preparar_muestra_multiclase(args)
            finally:
                multi.gpd.read_file = original_read_file

        self.assertEqual(len(sample), 5)
        self.assertEqual(
            sample["cultivo"].value_counts().to_dict(),
            {"vid": 1, "olivo": 1, "frutales": 1, "incultos": 1, "anuales": 1},
        )

    def test_feature_columns_exclude_ids_and_use_spectral_temporal_features(self):
        df = pd.DataFrame(
            {
                "parcela_id": [1],
                "cultivo": ["vid"],
                "month": [1],
                "day_of_year": [15],
                "ndvi_mean": [0.5],
                "ndvi_stddev": [0.1],
                "b11_max": [1000.0],
                "scl_mean": [4.0],
                "area_m2": [5000.0],
            }
        )
        df = add_temporal_features(df)

        features = classification_feature_columns(df, "cultivo", "mean-std")

        self.assertIn("ndvi_mean", features)
        self.assertIn("ndvi_stddev", features)
        self.assertIn("month_sin", features)
        self.assertIn("doy_cos", features)
        self.assertNotIn("parcela_id", features)
        self.assertNotIn("b11_max", features)
        self.assertNotIn("scl_mean", features)
        self.assertNotIn("area_m2", features)

    def test_wide_spectral_features_exclude_counts_and_date_columns(self):
        df = pd.DataFrame(
            {
                "parcela_id": ["1"],
                "cultivo": ["vid"],
                "day_of_year_2024_01": [1],
                "window_days_2024_01": [15],
                "ndvi_count_2024_01": [20],
                "ndvi_mean_2024_01": [0.5],
                "ndvi_stddev_2024_01": [0.1],
                "ndvi_amp_year": [0.4],
            }
        )

        features = classification_feature_columns(df, "cultivo", "wide-spectral")

        self.assertEqual(
            features,
            ["ndvi_mean_2024_01", "ndvi_stddev_2024_01", "ndvi_amp_year"],
        )

    def test_split_by_group_keeps_parcels_disjoint(self):
        rows = []
        for parcela_id in range(30):
            cultivo = "vid" if parcela_id % 2 == 0 else "olivo"
            for month in [1, 2, 3]:
                rows.append(
                    {
                        "parcela_id": parcela_id,
                        "cultivo": cultivo,
                        "month": month,
                        "ndvi_mean": 0.1 * month,
                    }
                )
        df = pd.DataFrame(rows)

        train_idx, val_idx, test_idx, split_mode = split_train_validation_test(
            df,
            target="cultivo",
            group_col="parcela_id",
            test_size=0.2,
            validation_size=0.2,
            random_state=42,
        )

        train_groups = set(df.iloc[train_idx]["parcela_id"])
        val_groups = set(df.iloc[val_idx]["parcela_id"])
        test_groups = set(df.iloc[test_idx]["parcela_id"])

        self.assertEqual(split_mode, "group")
        self.assertTrue(train_groups.isdisjoint(val_groups))
        self.assertTrue(train_groups.isdisjoint(test_groups))
        self.assertTrue(val_groups.isdisjoint(test_groups))

    def test_prepare_dataset_filters_requested_classes(self):
        args = argparse.Namespace(
            input="unused.csv",
            target="cultivo",
            classes=["vid", "olivo"],
            group_col="parcela_id",
            max_rows=None,
            random_state=42,
            feature_set="mean",
            features=None,
            include_area=False,
        )
        df = pd.DataFrame(
            {
                "parcela_id": [1, 2, 3],
                "cultivo": ["vid", "olivo", "frutales"],
                "month": [1, 1, 1],
                "ndvi_mean": [0.5, 0.4, 0.3],
            }
        )

        original_read_csv = pd.read_csv
        try:
            pd.read_csv = lambda _: df.copy()
            result, features, label_encoder = prepare_dataset(args)
        finally:
            pd.read_csv = original_read_csv

        self.assertEqual(set(result["cultivo"]), {"vid", "olivo"})
        self.assertIn("ndvi_mean", features)
        self.assertIn("month_sin", features)
        self.assertIn("month_cos", features)
        self.assertEqual(label_encoder.classes_.tolist(), ["olivo", "vid"])

    def test_binary_threshold_metrics_selects_best_validation_threshold(self):
        y_val = pd.Series([0, 0, 1, 1]).to_numpy()
        val_probabilities = pd.DataFrame(
            {
                0: [0.90, 0.70, 0.55, 0.20],
                1: [0.10, 0.30, 0.45, 0.80],
            }
        ).to_numpy()
        y_test = pd.Series([0, 1]).to_numpy()
        test_probabilities = pd.DataFrame({0: [0.80, 0.30], 1: [0.20, 0.70]}).to_numpy()

        result = binary_threshold_metrics(
            y_val,
            val_probabilities,
            y_test,
            test_probabilities,
            ["olivo", "vid"],
        )

        self.assertIsNotNone(result)
        self.assertGreaterEqual(result["macro_f1"], 0.9)
        self.assertIn("threshold", result)


if __name__ == "__main__":
    unittest.main()
