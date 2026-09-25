import os
import unittest
from unittest.mock import patch

from backend.app.core import gee


class GeeAuthenticationTest(unittest.TestCase):
    def test_initializes_with_persistent_oauth_by_default(self):
        with (
            patch.dict(
                os.environ,
                {"GEE_PROJECT_ID": "test-project"},
                clear=True,
            ),
            patch.object(gee.ee, "Initialize") as initialize,
        ):
            gee.inicializar_gee()

        initialize.assert_called_once_with(
            credentials="persistent",
            project="test-project",
        )

    def test_appdefault_uses_adc_credentials(self):
        credentials = object()
        with (
            patch.dict(
                os.environ,
                {
                    "GEE_PROJECT_ID": "test-project",
                    "GEE_AUTH_MODE": "appdefault",
                },
                clear=True,
            ),
            patch.object(
                gee.google.auth,
                "default",
                return_value=(credentials, "adc-project"),
            ) as auth_default,
            patch.object(gee.ee, "Initialize") as initialize,
        ):
            gee.inicializar_gee()

        auth_default.assert_called_once_with(scopes=gee.GEE_SCOPES)
        initialize.assert_called_once_with(
            credentials=credentials,
            project="test-project",
        )

    def test_invalid_auth_mode_fails_clearly(self):
        with (
            patch.dict(
                os.environ,
                {
                    "GEE_PROJECT_ID": "test-project",
                    "GEE_AUTH_MODE": "invalid",
                },
                clear=True,
            ),
            patch.object(gee.ee, "Initialize") as initialize,
        ):
            with self.assertRaisesRegex(RuntimeError, "GEE_AUTH_MODE"):
                gee.inicializar_gee()

        initialize.assert_not_called()


if __name__ == "__main__":
    unittest.main()
