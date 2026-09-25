import os

import ee
import google.auth
from dotenv import load_dotenv

load_dotenv()

GEE_SCOPES = (
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/drive",
)


def _gee_credentials():
    auth_mode = os.getenv("GEE_AUTH_MODE", "persistent").strip().lower()
    if auth_mode == "persistent":
        return "persistent"
    if auth_mode == "appdefault":
        credentials, _ = google.auth.default(scopes=GEE_SCOPES)
        return credentials
    raise RuntimeError(
        "GEE_AUTH_MODE inválido; usar 'persistent' o 'appdefault'."
    )


def inicializar_gee() -> None:
    try:
        credentials = _gee_credentials()
        ee.Initialize(
            credentials=credentials,
            project=os.getenv("GEE_PROJECT_ID"),
        )
        print("GEE inicializado correctamente")
    except Exception as exc:
        print(f"Error inicializando GEE: {exc}")
        raise
