"""Structured operation audit logging for administrator review."""
from __future__ import annotations

import json
from typing import Any

from db.connection import get_db


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
        return [dict(row) for row in rows]
