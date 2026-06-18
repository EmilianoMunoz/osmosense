from __future__ import annotations

import os

from dotenv import load_dotenv


PRODUCTION_ENV_VALUES = {"prod", "production"}


def app_env() -> str:
    load_dotenv()
    return (
        os.getenv("APP_ENV")
        or os.getenv("OSMOSENSE_ENV")
        or os.getenv("ENVIRONMENT")
        or "development"
    ).strip().lower()


def is_production() -> bool:
    return app_env() in PRODUCTION_ENV_VALUES
