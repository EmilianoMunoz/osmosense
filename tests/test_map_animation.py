import unittest

import pandas as pd

from frontend.map import risk_animation_frame


class RiskAnimationFrameTest(unittest.TestCase):
    def test_animation_does_not_improve_risk_under_no_irrigation_scenario(self):
        df = pd.DataFrame(
            [
                {
                    "parcela_id": 1,
                    "riesgo_actual": 46.0,
                    "riesgo_5_dias": 43.0,
                    "riesgo_10_dias": 40.0,
                },
            ]
        )

        result = risk_animation_frame(df)
        parcel = result[result["parcela_id"] == 1].sort_values("dia_proyeccion")

        self.assertTrue((parcel["riesgo_mapa"] >= 46.0).all())
        self.assertEqual(parcel.iloc[0]["riesgo_categoria"], "media")
        self.assertEqual(parcel.iloc[-1]["riesgo_categoria"], "media")

    def test_animation_amplifies_worsening_slightly(self):
        df = pd.DataFrame(
            [
                {
                    "parcela_id": 1,
                    "riesgo_actual": 30.0,
                    "riesgo_5_dias": 40.0,
                    "riesgo_10_dias": 50.0,
                },
            ]
        )

        result = risk_animation_frame(df)
        parcel = result[result["parcela_id"] == 1].sort_values("dia_proyeccion")

        self.assertGreater(parcel.iloc[5]["riesgo_mapa"], 40.0)
        self.assertGreater(parcel.iloc[-1]["riesgo_mapa"], 50.0)
        self.assertTrue(parcel["riesgo_mapa"].is_monotonic_increasing)

    def test_animation_categories_are_absolute_not_relative(self):
        df = pd.DataFrame(
            [
                {
                    "parcela_id": 1,
                    "riesgo_actual": 34.0,
                    "riesgo_5_dias": 34.0,
                    "riesgo_10_dias": 34.0,
                },
                {
                    "parcela_id": 2,
                    "riesgo_actual": 70.0,
                    "riesgo_5_dias": 70.0,
                    "riesgo_10_dias": 70.0,
                },
            ]
        )

        result = risk_animation_frame(df)
        day_0 = result[result["dia_proyeccion"] == 0].set_index("parcela_id")

        self.assertEqual(day_0.loc[1, "riesgo_categoria"], "baja")
        self.assertEqual(day_0.loc[2, "riesgo_categoria"], "critica")

    def test_animation_recalculates_color_even_with_visual_priority(self):
        df = pd.DataFrame(
            [
                {
                    "parcela_id": 1,
                    "ranking_global": 10,
                    "prioridad_visual": "baja",
                    "riesgo_actual": 34.0,
                    "riesgo_5_dias": 38.0,
                    "riesgo_10_dias": 40.0,
                },
            ]
        )

        result = risk_animation_frame(df)
        parcel = result[result["parcela_id"] == 1].set_index("dia_proyeccion")

        self.assertEqual(parcel.loc[0, "riesgo_categoria"], "baja")
        self.assertEqual(parcel.loc[10, "riesgo_categoria"], "media")

    def test_animation_keeps_unranked_parcels_without_category(self):
        df = pd.DataFrame(
            [
                {
                    "parcela_id": 1,
                    "ranking_global": None,
                    "prioridad_visual": "sin ranking",
                    "riesgo_actual": 60.0,
                    "riesgo_5_dias": 65.0,
                    "riesgo_10_dias": 70.0,
                },
            ]
        )

        result = risk_animation_frame(df)

        self.assertEqual(set(result["riesgo_categoria"]), {"sin ranking"})


if __name__ == "__main__":
    unittest.main()
