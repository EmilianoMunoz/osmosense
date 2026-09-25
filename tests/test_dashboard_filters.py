import unittest

import pandas as pd

from frontend.views.dashboard_filters import (
    filter_admin_dataframe,
    view_mode_for_role,
)


class DashboardRoleRoutingTest(unittest.TestCase):
    def test_view_is_derived_from_authenticated_role(self):
        self.assertEqual(view_mode_for_role("admin"), "Admin")
        self.assertEqual(view_mode_for_role("regional"), "Regional")
        self.assertEqual(view_mode_for_role("productor"), "Productor")

    def test_unknown_role_has_no_view(self):
        self.assertIsNone(view_mode_for_role(None))
        self.assertIsNone(view_mode_for_role("desconocido"))


class AdminSidebarFilterTest(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            {
                "parcela_id": [1, 2, 3],
                "cultivo": ["vid", "olivo", "vid"],
                "prioridad_visual": ["critica", "baja", "alta"],
                "confianza_lectura": ["alta", "baja", "media"],
                "ranking_global": [1, 2, 3],
                "accion_recomendada": [
                    None,
                    "bajar_confianza_y_revisar_geometria",
                    None,
                ],
            }
        )

    def test_operational_mode_applies_all_filters(self):
        result = filter_admin_dataframe(
            self.df,
            cultivos=["vid", "olivo"],
            prioridades=["critica"],
            confianza=["alta", "baja", "media"],
            rank_range=(1, 3),
            review_only=False,
        )

        self.assertEqual(result["parcela_id"].tolist(), [1])

    def test_review_mode_ignores_priority_and_keeps_review_cases(self):
        result = filter_admin_dataframe(
            self.df,
            cultivos=["vid", "olivo"],
            prioridades=["critica"],
            confianza=["alta", "baja", "media"],
            rank_range=(1, 3),
            review_only=True,
        )

        self.assertEqual(result["parcela_id"].tolist(), [2])

    def test_rank_filter_keeps_unranked_reviewable_rows(self):
        frame = self.df.copy()
        frame.loc[1, "ranking_global"] = None

        result = filter_admin_dataframe(
            frame,
            cultivos=["vid", "olivo"],
            prioridades=["critica", "alta", "baja"],
            confianza=["alta", "baja", "media"],
            rank_range=(1, 1),
            review_only=True,
        )

        self.assertEqual(result["parcela_id"].tolist(), [2])


if __name__ == "__main__":
    unittest.main()
