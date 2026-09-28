import json
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import backend.app.services.rankings as rankings
from backend.app.services.pipeline_state import _processing_health
from backend.scripts.pipeline import run_pipeline_hidrico as pipeline
from frontend.components import tables
from frontend.data import ranking_items_to_feature_collection
from frontend.views.dashboard import admin_requires_detailed_data


class PipelineResilienceTest(unittest.TestCase):
    def test_pipeline_lock_rejects_a_concurrent_run_and_releases_afterwards(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            with pipeline.pipeline_lock(state_dir, "run-1"):
                with self.assertRaises(pipeline.PipelineAlreadyRunning) as raised:
                    with pipeline.pipeline_lock(state_dir, "run-2"):
                        self.fail("La segunda corrida no debía adquirir el lock")

            with pipeline.pipeline_lock(state_dir, "run-3"):
                pass

        self.assertEqual(raised.exception.owner["run_id"], "run-1")

    def test_processing_state_is_marked_stale_after_configured_window(self):
        now = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
        state = {
            "status": "processing",
            "started_at_utc": (now - timedelta(hours=7)).isoformat(),
        }

        result = _processing_health(state, now=now)

        self.assertTrue(result["processing_stale"])
        self.assertEqual(result["processing_elapsed_seconds"], 7 * 3600)

    def test_recent_processing_state_is_not_marked_stale(self):
        now = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
        state = {
            "status": "processing",
            "started_at_utc": (now - timedelta(hours=2)).isoformat(),
        }

        result = _processing_health(state, now=now)

        self.assertFalse(result["processing_stale"])

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

    def test_generated_ranking_rejects_duplicate_parcels(self):
        frame = pd.DataFrame(
            {
                "fecha_actual": ["2026-09-20", "2026-09-20"],
                "parcela_id": [10, 10],
                "cultivo": ["vid", "vid"],
                "ranking_global": [1, 2],
                "prioridad": ["alta", "media"],
            }
        )

        with self.assertRaisesRegex(RuntimeError, "duplicadas"):
            pipeline.validar_ranking_generado(frame)

    def test_latest_is_promoted_atomically_only_when_requested(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            candidate = root / "ranking_2026-09-20.csv"
            latest = root / "ranking_latest.csv"
            candidate.write_text("new", encoding="utf-8")
            latest.write_text("old", encoding="utf-8")
            args = Namespace(dry_run=False)
            state = {
                "ranking_candidate": str(candidate),
                "ranking_latest": str(latest),
            }

            pipeline.promover_ranking_latest(args, state, root / "pipeline.log")

            self.assertEqual(latest.read_text(encoding="utf-8"), "new")
            self.assertTrue(state["ranking_latest_promoted"])
            self.assertFalse(any(root.glob("*.tmp")))

    def test_postgis_target_snapshot_is_refreshed_without_sentinel_update(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            snapshot = root / "parcelas_objetivo.geojson"
            args = Namespace(
                parcel_source="postgis",
                parcelas="parcelas_historicas.geojson",
                extract_output_sample=str(snapshot),
                update_sentinel=False,
                dry_run=False,
                database_url="postgresql://user:secret@db/estres",
            )
            target_rows = [1, 2]

            def write_snapshot(_parcels, output):
                Path(output).touch()

            with (
                patch.object(
                    pipeline,
                    "require_database_url",
                    return_value=args.database_url,
                ),
                patch.object(
                    pipeline,
                    "load_target_parcels_from_postgis",
                    return_value=target_rows,
                ) as load,
                patch.object(
                    pipeline,
                    "write_target_snapshot",
                    side_effect=write_snapshot,
                ) as write,
            ):
                result = pipeline.preparar_universo_objetivo(
                    args, root / "pipeline.log"
                )

        self.assertEqual(result, snapshot)
        load.assert_called_once_with(args.database_url)
        write.assert_called_once_with(target_rows, snapshot)

    def test_postgis_publication_prepares_zoning_before_ranking(self):
        events = []
        args = Namespace(
            mode="cloud",
            parcel_source="geojson",
            parcelas="parcelas.geojson",
            extract_output_sample="snapshot.geojson",
            database_url=None,
            run_quality_audits=False,
            backfill_outlier_history=False,
            update_zonificacion_um=True,
            load_postgis=True,
            update_sentinel=False,
            input="dataset.csv",
            dry_run=True,
            state_dir="state",
        )
        state = {
            "ranking_candidate": "candidate.csv",
            "ranking_latest": "latest.csv",
        }

        def prepare_zoning(_args, current_state, _log_path, _parcelas_path):
            events.append("prepare_zoning")
            return current_state

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "pipeline.log"
            with (
                patch.object(pipeline, "ultima_fecha_dataset", return_value="2026-09-20"),
                patch.object(pipeline, "ejecutar_ranking", return_value=state.copy()),
                patch.object(
                    pipeline,
                    "ejecutar_zonificacion_um",
                    side_effect=prepare_zoning,
                ),
                patch.object(
                    pipeline,
                    "cargar_zonificacion_postgis",
                    side_effect=lambda *_: events.append("zoning_postgis"),
                ),
                patch.object(
                    pipeline,
                    "cargar_ranking_postgis",
                    side_effect=lambda *_: events.append("ranking_postgis"),
                ),
                patch.object(
                    pipeline,
                    "promover_ranking_latest",
                    side_effect=lambda *_: events.append("promote_latest"),
                ),
            ):
                pipeline.ejecutar_pipeline(args, log_path)

        self.assertEqual(
            events,
            [
                "prepare_zoning",
                "zoning_postgis",
                "ranking_postgis",
                "promote_latest",
            ],
        )

    def test_compact_ranking_keeps_dataframe_contract_without_geometry(self):
        result = ranking_items_to_feature_collection(
            {
                "source": "postgis",
                "count": 1,
                "items": [
                    {
                        "parcela_id": 10,
                        "ranking_global": 1,
                        "cultivo": "vid",
                    }
                ],
            }
        )

        self.assertEqual(result["source"], "postgis")
        self.assertEqual(result["features"][0]["properties"]["parcela_id"], 10)
        self.assertIsNone(result["features"][0]["geometry"])

    def test_admin_only_requires_full_payload_for_map_or_review(self):
        self.assertFalse(admin_requires_detailed_data("Estado", "Operación"))
        self.assertFalse(admin_requires_detailed_data("Ranking", "Operación"))
        self.assertTrue(admin_requires_detailed_data("Mapa", "Operación"))
        self.assertTrue(admin_requires_detailed_data("Estado", "Revisión técnica"))

    def test_full_geojson_cache_reuses_same_data_version(self):
        rankings._cached_latest_geojson_from_postgis.cache_clear()
        expected = {"type": "FeatureCollection", "features": []}
        with (
            patch.object(
                rankings,
                "_postgis_latest_geojson_version",
                return_value=("2026-09-20", "10"),
            ),
            patch.object(rankings, "_quality_files_signature", return_value=()),
            patch.object(
                rankings,
                "_build_latest_geojson_from_postgis",
                return_value=expected,
            ) as build,
        ):
            first = rankings.latest_geojson_from_postgis(2)
            second = rankings.latest_geojson_from_postgis(2)

        self.assertIs(first, second)
        build.assert_called_once_with(2.0)

if __name__ == "__main__":
    unittest.main()
