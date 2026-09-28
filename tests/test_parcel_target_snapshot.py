import tempfile
import unittest
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

from backend.app.services.parcel_targets import write_target_snapshot
from backend.scripts.pipeline.generar_ranking_hidrico import cargar_parcelas_objetivo
from backend.scripts.zonificacion.cruzar_parcelas_zonificacion_um import read_inputs


class ParcelTargetSnapshotTest(unittest.TestCase):
    def test_reclassified_parcel_is_shared_by_ranking_and_zoning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            snapshot_path = root / "parcelas_objetivo.geojson"
            zones_path = root / "zonas.geojson"
            ranking_path = root / "ranking.csv"

            parcels = gpd.GeoDataFrame(
                {
                    "parcela_id": [99001],
                    "id": ["99001"],
                    "cultivo": ["vid"],
                    "area_m2": [10000.0],
                },
                geometry=[
                    Polygon(
                        [
                            (-68.40, -34.60),
                            (-68.39, -34.60),
                            (-68.39, -34.59),
                            (-68.40, -34.59),
                        ]
                    )
                ],
                crs="EPSG:4326",
            )
            write_target_snapshot(parcels, snapshot_path)

            zones = gpd.GeoDataFrame(
                {
                    "fid": [1],
                    "tipo": ["UM"],
                    "nombre": ["UM prueba"],
                    "cuenca": ["Prueba"],
                },
                geometry=[
                    Polygon(
                        [
                            (-68.41, -34.61),
                            (-68.38, -34.61),
                            (-68.38, -34.58),
                            (-68.41, -34.58),
                        ]
                    )
                ],
                crs="EPSG:4326",
            )
            zones.to_file(zones_path, driver="GeoJSON")
            pd.DataFrame([{"parcela_id": 99001}]).to_csv(ranking_path, index=False)

            ranking_ids = cargar_parcelas_objetivo(snapshot_path)
            _, zoning_parcels, _ = read_inputs(
                zones_path,
                snapshot_path,
                ranking_path,
            )

        self.assertEqual(ranking_ids, {99001})
        self.assertEqual(zoning_parcels["parcela_id"].tolist(), [99001])
        self.assertEqual(zoning_parcels["cultivo"].tolist(), ["vid"])

    def test_missing_snapshot_fails_instead_of_disabling_target_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.geojson"
            with self.assertRaisesRegex(FileNotFoundError, "universo de parcelas"):
                cargar_parcelas_objetivo(missing)


if __name__ == "__main__":
    unittest.main()
