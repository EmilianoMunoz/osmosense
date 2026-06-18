import unittest
from argparse import Namespace

from backend.scripts.maintenance import rotar_credenciales_cloud as rotate


class CloudCredentialRotationTest(unittest.TestCase):
    def test_parse_explicit_passwords(self):
        parsed = rotate.parse_explicit_passwords(
            ["ADMIN@OSMOSENSE.LOCAL=password-segura"]
        )

        self.assertEqual(
            parsed,
            {"admin@osmosense.local": "password-segura"},
        )

    def test_parse_explicit_passwords_rejects_short_password(self):
        with self.assertRaisesRegex(ValueError, "al menos"):
            rotate.parse_explicit_passwords(["admin@osmosense.local=corta"])

    def test_target_users_includes_explicit_users(self):
        args = Namespace(user=["admin@osmosense.local"], password_length=20)
        users = rotate.target_users(
            args,
            {"regional@osmosense.local": "password-segura"},
        )

        self.assertEqual(
            users,
            ["admin@osmosense.local", "regional@osmosense.local"],
        )

    def test_generate_password_length(self):
        password = rotate.generate_password(24)

        self.assertEqual(len(password), 24)

    def test_generate_password_rejects_short_length(self):
        with self.assertRaisesRegex(ValueError, ">= 12"):
            rotate.generate_password(8)

    def test_detects_generated_passwords(self):
        users = ["admin@osmosense.local", "regional@osmosense.local"]

        self.assertTrue(
            rotate.has_generated_passwords(
                users,
                {"admin@osmosense.local": "password-segura"},
            )
        )
        self.assertFalse(
            rotate.has_generated_passwords(
                users,
                {
                    "admin@osmosense.local": "password-segura",
                    "regional@osmosense.local": "password-segura",
                },
            )
        )


if __name__ == "__main__":
    unittest.main()
