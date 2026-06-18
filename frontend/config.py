from __future__ import annotations

import os

from dotenv import load_dotenv


PRODUCTION_ENV_VALUES = {"prod", "production"}
FALSE_VALUES = {"0", "false", "no", "off"}


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


def env_flag(name: str, default: bool) -> bool:
    load_dotenv()
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in FALSE_VALUES


def local_fallback_enabled() -> bool:
    return (not is_production()) and env_flag("ENABLE_LOCAL_FALLBACK", True)


def quick_login_enabled() -> bool:
    return (not is_production()) and env_flag("ENABLE_QUICK_LOGIN", True)
