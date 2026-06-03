import unittest
from unittest.mock import patch

from fastapi import HTTPException

import backend.app.services.auth as auth
from backend.app import main


class AuthServiceTest(unittest.TestCase):
    def test_password_hash_verification(self):
        password_hash = auth.hash_password("admin123", salt=b"fixed-test-salt1")

        self.assertTrue(auth.verify_password("admin123", password_hash))
        self.assertFalse(auth.verify_password("otro", password_hash))
        self.assertFalse(auth.verify_password("admin123", "hash-invalido"))

    def test_access_token_roundtrip(self):
        user = {
            "usuario_id": 1,
            "email": "admin",
            "nombre": "Administrador",
            "rol": "admin",
            "cliente_id": None,
            "view_mode": "Admin",
        }
        with patch.object(auth, "auth_secret", return_value="test-secret"):
            token = auth.create_access_token(user)
            payload = auth.verify_access_token(token)

        self.assertEqual(payload["usuario_id"], 1)
        self.assertEqual(payload["rol"], "admin")
        self.assertEqual(payload["view_mode"], "Admin")


class AuthApiDependencyTest(unittest.TestCase):
    def test_current_user_requires_token(self):
        with self.assertRaises(HTTPException) as context:
            main.current_user(None)

        self.assertEqual(context.exception.status_code, 401)

    def test_current_user_rejects_invalid_token(self):
        with self.assertRaises(HTTPException) as context:
            main.current_user("Bearer token-invalido")

        self.assertEqual(context.exception.status_code, 401)

    def test_current_user_accepts_valid_token(self):
        user = {
            "usuario_id": 1,
            "email": "admin",
            "nombre": "Administrador",
            "rol": "admin",
            "cliente_id": None,
            "view_mode": "Admin",
        }
        with patch.object(auth, "auth_secret", return_value="test-secret"):
            token = auth.create_access_token(user)
            result = main.current_user(f"Bearer {token}")

        self.assertEqual(result["rol"], "admin")
        self.assertEqual(result["email"], "admin")

    def test_require_roles_allows_expected_role(self):
        dependency = main.require_roles("admin")
        user = {"rol": "admin"}

        self.assertEqual(dependency(user), user)

    def test_require_roles_rejects_wrong_role(self):
        dependency = main.require_roles("admin")
        with self.assertRaises(HTTPException) as context:
            dependency({"rol": "productor"})

        self.assertEqual(context.exception.status_code, 403)

    def test_cliente_can_access_own_cliente_data(self):
        user = {"rol": "productor", "cliente_id": 7}

        self.assertEqual(main.require_cliente_or_admin(7, user), user)

    def test_cliente_cannot_access_other_cliente_data(self):
        user = {"rol": "productor", "cliente_id": 7}
        with self.assertRaises(HTTPException) as context:
            main.require_cliente_or_admin(8, user)

        self.assertEqual(context.exception.status_code, 403)

    def test_admin_can_access_any_cliente_data(self):
        user = {"rol": "admin", "cliente_id": None}

        self.assertEqual(main.require_cliente_or_admin(8, user), user)

    def test_regional_cannot_access_cliente_data(self):
        user = {"rol": "regional", "cliente_id": None}
        with self.assertRaises(HTTPException) as context:
            main.require_cliente_or_admin(8, user)

        self.assertEqual(context.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
