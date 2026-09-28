import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.app.services import rankings


class ParcelAssignmentTransactionsTest(unittest.TestCase):
    @staticmethod
    def _connection(cursor: MagicMock) -> MagicMock:
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value.__enter__.return_value = cursor
        return connection

    def test_bulk_assignment_promotes_and_assigns_in_one_transaction(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"cliente_id": 7},
            {"total": 2},
        ]
        cursor.fetchall.side_effect = [
            [
                {
                    "parcela_id": 10,
                    "cultivo_oficial": "frutales",
                    "cultivo_original": "FRUTALES",
                    "area_m2": 5000.0,
                    "fuente": "idemendoza",
                    "activo": True,
                    "updated_at": None,
                },
                {
                    "parcela_id": 11,
                    "cultivo_oficial": "inculto",
                    "cultivo_original": "INCULTO",
                    "area_m2": 6000.0,
                    "fuente": "idemendoza",
                    "activo": True,
                    "updated_at": None,
                },
            ],
            [],
            [
                {
                    "parcela_id": 10,
                    "cultivo_oficial": "vid",
                    "cultivo_original": "FRUTALES",
                    "area_m2": 5000.0,
                    "fuente": "idemendoza_admin",
                    "activo": True,
                    "updated_at": None,
                },
                {
                    "parcela_id": 11,
                    "cultivo_oficial": "vid",
                    "cultivo_original": "INCULTO",
                    "area_m2": 6000.0,
                    "fuente": "idemendoza_admin",
                    "activo": True,
                    "updated_at": None,
                },
            ],
            [
                {
                    "cliente_id": 7,
                    "parcela_id": 10,
                    "etiqueta": "Finca norte",
                    "created_at": None,
                },
                {
                    "cliente_id": 7,
                    "parcela_id": 11,
                    "etiqueta": "Finca norte",
                    "created_at": None,
                },
            ],
        ]
        connection = self._connection(cursor)

        with (
            patch.object(rankings, "_require_database_url", return_value="postgresql://db"),
            patch("psycopg.connect", return_value=connection),
        ):
            result = rankings.admin_assign_cliente_parcelas(
                cliente_id=7,
                parcela_ids=[11, 10, 10],
                cultivo_oficial="vid",
                etiqueta="Finca norte",
            )

        self.assertEqual(result["count"], 2)
        self.assertEqual(result["total_asignadas"], 2)
        self.assertEqual([item["parcela_id"] for item in result["items"]], [10, 11])
        connection.commit.assert_called_once()
        statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
        self.assertTrue(any("UPDATE parcelas" in statement for statement in statements))
        self.assertTrue(any("INSERT INTO cliente_parcela" in statement for statement in statements))

    def test_available_parcel_activation_reuses_atomic_assignment(self):
        assignment = {
            "source": "postgis",
            "parcelas": [{"parcela_id": 20, "cultivo_oficial": "olivo"}],
            "items": [{"cliente_id": 7, "parcela_id": 20}],
        }
        with patch.object(
            rankings,
            "admin_assign_cliente_parcelas",
            return_value=assignment,
        ) as assign:
            result = rankings.admin_activar_parcela_disponible(
                parcela_id=20,
                cultivo_oficial="olivo",
                cliente_id=7,
                etiqueta="Cuadro este",
            )

        assign.assert_called_once_with(
            cliente_id=7,
            parcela_ids=[20],
            cultivo_oficial="olivo",
            etiqueta="Cuadro este",
        )
        self.assertEqual(result["item"]["cultivo_oficial"], "olivo")
        self.assertEqual(result["cliente_parcela"]["cliente_id"], 7)

    def test_assignment_conflict_stops_before_updates_or_inserts(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"cliente_id": 7}
        cursor.fetchall.side_effect = [
            [
                {
                    "parcela_id": 10,
                    "cultivo_oficial": "vid",
                    "cultivo_original": "VID",
                    "area_m2": 5000.0,
                    "fuente": "idemendoza",
                    "activo": True,
                    "updated_at": None,
                }
            ],
            [{"parcela_id": 10, "cliente_id": 8}],
        ]
        connection = self._connection(cursor)

        with (
            patch.object(rankings, "_require_database_url", return_value="postgresql://db"),
            patch("psycopg.connect", return_value=connection),
        ):
            with self.assertRaises(rankings.ParcelAssignmentConflictError):
                rankings.admin_assign_cliente_parcelas(
                    cliente_id=7,
                    parcela_ids=[10],
                    cultivo_oficial="olivo",
                )

        connection.commit.assert_not_called()
        statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
        self.assertFalse(any("UPDATE parcelas" in statement for statement in statements))
        self.assertFalse(any("INSERT INTO cliente_parcela" in statement for statement in statements))

    def test_bulk_unassignment_requires_every_relation_before_delete(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        cursor.fetchall.return_value = [(10,)]
        connection = self._connection(cursor)

        with (
            patch.object(rankings, "_require_database_url", return_value="postgresql://db"),
            patch("psycopg.connect", return_value=connection),
        ):
            with self.assertRaisesRegex(ValueError, "11"):
                rankings.admin_delete_cliente_parcelas(7, [10, 11])

        connection.commit.assert_not_called()
        statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
        self.assertFalse(any("DELETE FROM cliente_parcela" in statement for statement in statements))

    def test_schema_enforces_one_owner_per_parcel(self):
        schema = Path("backend/sql/schema_postgis.sql").read_text(encoding="utf-8")
        self.assertIn(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_cliente_parcela_parcela",
            schema,
        )


if __name__ == "__main__":
    unittest.main()
