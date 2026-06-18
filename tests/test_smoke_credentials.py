import sys
import unittest
from unittest.mock import patch

from backend.scripts.postgis import smoke_test_crud_productor
from backend.scripts.postgis import smoke_test_operativo
from backend.scripts.postgis import smoke_test_productor
from backend.scripts.postgis import smoke_test_regional


class SmokeCredentialsTest(unittest.TestCase):
    def parse_with_clean_argv(self, module):
        with patch.object(sys, "argv", ["smoke"]):
            return module.parse_args()

    def test_operativo_reads_admin_credentials_from_env(self):
        with patch.dict(
            "os.environ",
            {
                "OSMOSENSE_ADMIN_EMAIL": "admin-cloud@osmosense.local",
                "OSMOSENSE_ADMIN_PASSWORD": "password-cloud",
            },
            clear=False,
        ):
            args = self.parse_with_clean_argv(smoke_test_operativo)

        self.assertEqual(args.admin_email, "admin-cloud@osmosense.local")
        self.assertEqual(args.admin_password, "password-cloud")

    def test_productor_reads_credentials_from_env(self):
        with patch.dict(
            "os.environ",
            {
                "OSMOSENSE_ADMIN_EMAIL": "admin-cloud@osmosense.local",
                "OSMOSENSE_ADMIN_PASSWORD": "admin-password",
                "OSMOSENSE_PRODUCTOR_EMAIL": "productor-cloud@osmosense.local",
                "OSMOSENSE_PRODUCTOR_PASSWORD": "productor-password",
            },
            clear=False,
        ):
            args = self.parse_with_clean_argv(smoke_test_productor)

        self.assertEqual(args.admin_email, "admin-cloud@osmosense.local")
        self.assertEqual(args.admin_password, "admin-password")
        self.assertEqual(args.productor_email, "productor-cloud@osmosense.local")
        self.assertEqual(args.productor_password, "productor-password")

    def test_regional_reads_credentials_from_env(self):
        with patch.dict(
            "os.environ",
            {
                "OSMOSENSE_REGIONAL_EMAIL": "regional-cloud@osmosense.local",
                "OSMOSENSE_REGIONAL_PASSWORD": "regional-password",
            },
            clear=False,
        ):
            args = self.parse_with_clean_argv(smoke_test_regional)

        self.assertEqual(args.regional_email, "regional-cloud@osmosense.local")
        self.assertEqual(args.regional_password, "regional-password")

    def test_crud_reads_credentials_from_env(self):
        with patch.dict(
            "os.environ",
            {
                "OSMOSENSE_ADMIN_EMAIL": "admin-cloud@osmosense.local",
                "OSMOSENSE_ADMIN_PASSWORD": "admin-password",
                "OSMOSENSE_PRODUCTOR_EMAIL": "productor-cloud@osmosense.local",
                "OSMOSENSE_PRODUCTOR_PASSWORD": "productor-password",
            },
            clear=False,
        ):
            args = self.parse_with_clean_argv(smoke_test_crud_productor)

        self.assertEqual(args.admin_email, "admin-cloud@osmosense.local")
        self.assertEqual(args.admin_password, "admin-password")
        self.assertEqual(args.productor_email, "productor-cloud@osmosense.local")
        self.assertEqual(args.productor_password, "productor-password")


if __name__ == "__main__":
    unittest.main()
