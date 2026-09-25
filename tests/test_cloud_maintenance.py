import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from backend.scripts.maintenance import rotar_credenciales_cloud as rotate
from backend.scripts.maintenance import preflight_cloud as preflight


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


class CloudPreflightGeeTest(unittest.TestCase):
    def base_config(self) -> dict[str, str]:
        return {
            "APP_ENV": "production",
            "ENABLE_LOCAL_FALLBACK": "false",
            "ENABLE_QUICK_LOGIN": "false",
            "DATABASE_URL": "postgresql://user:password@db/estres",
            "API_BASE_URL": "http://api:8000",
            "AUTH_SECRET": "a" * 40,
            "GEE_PROJECT_ID": "test-project",
        }

    def test_warns_when_cloud_still_uses_personal_oauth(self):
        findings = []

        with patch.object(preflight, "CONFIG", self.base_config()):
            preflight.check_required_env(findings)

        self.assertTrue(
            any(
                item.level == "WARN" and "OAuth personal" in item.message
                for item in findings
            )
        )

    def test_accepts_restricted_gcloud_adc_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            credentials_path = Path(tmpdir) / "application_default_credentials.json"
            credentials_path.write_text(json.dumps({"type": "authorized_user"}))
            credentials_path.chmod(0o600)
            config = {
                **self.base_config(),
                "GEE_AUTH_MODE": "appdefault",
                "GOOGLE_APPLICATION_CREDENTIALS": str(credentials_path),
            }
            findings = []

            with patch.object(preflight, "CONFIG", config):
                preflight.check_required_env(findings)

        self.assertTrue(
            any(
                item.level == "OK" and "ADC de gcloud" in item.message
                for item in findings
            )
        )
        self.assertFalse(
            any(
                item.level == "FAIL" and "configuración ADC" in item.message
                for item in findings
            )
        )


if __name__ == "__main__":
    unittest.main()
