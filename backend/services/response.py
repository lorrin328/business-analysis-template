from datetime import datetime
from typing import Any


def success_response(data: Any, message: str = "", meta: dict | None = None) -> dict:
    base_meta = {
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    }
    if meta:
        base_meta.update(meta)
    return {"success": True, "data": data, "message": message, "meta": base_meta}


def error_response(message: str, error_code: str = "ERROR", data: Any = None) -> dict:
    return {"success": False, "data": data, "message": message, "errorCode": error_code}
