from datetime import datetime
from typing import Any


def response_meta(
    *,
    metric: str,
    unit: str | None = None,
    data_source: str | None = None,
    definitions: dict | None = None,
    **extra: Any,
) -> dict:
    meta = {"metric": metric}
    if unit is not None:
        meta["unit"] = unit
    if data_source is not None:
        meta["dataSource"] = data_source
    if definitions is not None:
        meta["definitions"] = definitions
    meta.update(extra)
    return meta


def batch_meta(
    *,
    batch_id: Any,
    rule_version: str | None = None,
    data_source_mode: str | None = None,
    **extra: Any,
) -> dict:
    meta = {"batchId": batch_id}
    if rule_version is not None:
        meta["ruleVersion"] = rule_version
    if data_source_mode is not None:
        meta["dataSourceMode"] = data_source_mode
    meta.update(extra)
    return meta


def success_response(data: Any, message: str = "", meta: dict | None = None) -> dict:
    base_meta = {
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    }
    if meta:
        base_meta.update(meta)
    return {"success": True, "data": data, "message": message, "meta": base_meta}


def error_response(message: str, error_code: str = "ERROR", data: Any = None) -> dict:
    return {"success": False, "data": data, "message": message, "errorCode": error_code}
