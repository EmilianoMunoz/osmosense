import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import backend.app.services.rankings as rankings
from backend.scripts.pipeline import run_pipeline_hidrico as pipeline
from frontend.components import tables


class PipelineResilienceTest(unittest.TestCase):
    def test_review_table_supports_missing_noise_severity(self):
        frame = pd.DataFrame(
            [
                {
                    "parcela_id": 10,
                    "ranking_global": 1,
                    "confianza_lectura": "baja",
                    "riesgo_actual": 70.0,
                }
            ]
        )

        with patch.object(tables.st, "dataframe") as dataframe:
            tables.render_review_cases(frame)

        dataframe.assert_called_once()

    def test_quality_contract_is_stable_without_optional_audits(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = str(Path(tmpdir) / "missing.csv")
            data = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [0, 0]},
                        "properties": {
                            "parcela_id": 10,
                            "ranking_global": 1,
                            "prioridad": "alta",
                            "prioridad_score": 60.0,
                            "riesgo_actual": 80.0,
                        },
                    }
                ],
            }

            with (
                patch.object(rankings, "AUDIT_VECINOS_CSV", missing),
                patch.object(rankings, "AUDIT_TEMPORAL_CSV", missing),
                patch.object(rankings, "AUDIT_RUIDO_CSV", missing),
                patch.object(rankings, "AUDIT_HISTORICAL_METRICS_CSV", missing),
            ):
                result = rankings._enrich_feature_collection_quality(data)

        props = result["features"][0]["properties"]
        self.assertIn("severidad_ruido", props)
        self.assertIsNone(props["severidad_ruido"])
        self.assertIn("accion_recomendada", props)
        self.assertFalse(props["outlier_espacial"])

    def test_pipeline_log_redacts_database_password(self):
        command = [
            "python",
            "script.py",
            "--database-url",
            "postgresql://user:secret@db/estres",
            "--dry-run",
        ]

        logged = pipeline.command_for_log(command)

        self.assertNotIn("secret", logged)
        self.assertIn("--database-url <redacted>", logged)

    def test_failed_pipeline_updates_state_without_exposing_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            args = Namespace(
                mode="cloud",
                logs_dir=str(root / "logs"),
                state_dir=str(root / "state"),
                input="dataset.csv",
                update_sentinel=True,
                load_postgis=True,
                dry_run=False,
            )

            with (
                patch.object(pipeline, "parse_args", return_value=args),
                patch.object(
                    pipeline,
                    "ejecutar_pipeline",
                    side_effect=RuntimeError("postgresql://user:secret@db/estres"),
                ),
            ):
                with self.assertRaises(RuntimeError):
                    pipeline.main()

            state = json.loads(
                (root / "state" / "pipeline_hidrico_state.json").read_text()
            )

        self.assertTrue(state["failed"])
        self.assertEqual(state["reason"], "error")
        self.assertEqual(state["error_type"], "RuntimeError")
        self.assertNotIn("secret", json.dumps(state))


if __name__ == "__main__":
    unittest.main()
