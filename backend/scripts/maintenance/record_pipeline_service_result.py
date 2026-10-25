from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


PIPELINE_STATE_PATH = Path("backend/data/state/pipeline_hidrico_state.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def record_service_result(
    environment: Mapping[str, str] | None = None,
    state_path: Path = PIPELINE_STATE_PATH,
) -> bool:
    env = environment or os.environ
    service_result = env.get("SERVICE_RESULT", "").strip().lower()
    if service_result in {"", "success"} or not state_path.exists():
        return False

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(state, dict) or state.get("status") != "processing":
        return False

    state.update(
        {
            "status": "failed",
            "failed": True,
            "skipped": False,
            "completed_at_utc": utc_now(),
            "reason": "service_terminated",
            "error_type": "SystemdServiceFailure",
            "error": (
                "El servicio del pipeline terminó de forma externa; "
                "consultar journalctl para conocer la causa."
            ),
            "service_result": service_result,
            "service_exit_code": env.get("EXIT_CODE"),
            "service_exit_status": env.get("EXIT_STATUS"),
        }
    )
    temporary = state_path.with_name(f".{state_path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temporary.replace(state_path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main() -> None:
    if record_service_result():
        print("Estado fallido del pipeline persistido desde systemd.", flush=True)


if __name__ == "__main__":
    main()
