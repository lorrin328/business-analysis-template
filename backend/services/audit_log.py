"""Structured operation audit logging for administrator review."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from db.connection import get_db


LOCAL_TIME_OFFSET = timedelta(hours=8)


def _utc_text_to_local(value: Any) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    text = str(value)
    try:
        utc_dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if utc_dt.tzinfo is not None:
            utc_dt = utc_dt.astimezone().replace(tzinfo=None)
        local_dt = utc_dt + LOCAL_TIME_OFFSET
        return local_dt.strftime("%Y-%m-%d %H:%M:%S"), utc_dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return text, text


def actor_from_user(user: dict | None) -> tuple[int | None, str]:
    if not user:
        return None, "system"
    user_id = user.get("id")
    username = user.get("username") or "system"
    return (int(user_id) if isinstance(user_id, int) and user_id > 0 else None, str(username))


def log_operation(
    action: str,
    *,
    user: dict | None = None,
    target_user_id: int | None = None,
    target_username: str | None = None,
    status: str = "success",
    detail: dict[str, Any] | str | None = None,
) -> None:
    user_id, username = actor_from_user(user)
    if isinstance(detail, str):
        detail_text = detail
    else:
        detail_text = json.dumps(detail or {}, ensure_ascii=False, default=str)
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO operation_logs (
                user_id, username, action, target_user_id, target_username, status, detail
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, action, target_user_id, target_username, status, detail_text),
        )
        conn.commit()


def list_operation_logs(limit: int = 200, action: str | None = None, username: str | None = None) -> list[dict]:
    params: list[Any] = []
    where: list[str] = []
    if action:
        where.append("action = ?")
        params.append(action)
    if username:
        where.append("(username LIKE ? OR target_username LIKE ?)")
        pattern = f"%{username}%"
        params.extend([pattern, pattern])
    sql = """
        SELECT id, user_id, username, action, target_user_id, target_username,
               status, detail, created_at
        FROM operation_logs
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, min(int(limit or 200), 500)))
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            local_time, utc_time = _utc_text_to_local(item.get("created_at"))
            item["created_at"] = local_time
            item["created_at_utc"] = utc_time
            result.append(item)
        return result
