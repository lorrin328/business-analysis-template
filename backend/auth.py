"""Account authentication and module-level permission checks."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import Depends, Header, HTTPException, Request, status

from db.connection import get_db

ROLE_ADMIN = "admin"
ROLE_SENIOR = "senior"
ROLE_NORMAL = "normal"
ROLES = {ROLE_ADMIN, ROLE_SENIOR, ROLE_NORMAL}

MODULE_KEYS = [
    "kpi",
    "org",
    "platform_trend",
    "product_structure",
    "payment_period",
    "team",
    "team_enhanced",
    "upload",
    "product_config",
    "targets",
    "excel_export",
    "permission_admin",
    "recalculate",
]

ROLE_DEFAULT_PERMISSIONS = {
    ROLE_ADMIN: {key: True for key in MODULE_KEYS},
    ROLE_SENIOR: {key: key != "permission_admin" for key in MODULE_KEYS},
    ROLE_NORMAL: {
        "kpi": True,
        "org": True,
        "platform_trend": True,
        "product_structure": True,
        "payment_period": True,
        "team": True,
        "team_enhanced": True,
        "upload": False,
        "product_config": False,
        "targets": False,
        "excel_export": False,
        "permission_admin": False,
        "recalculate": True,
    },
}

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "Aaaaasynology8888%"
SESSION_DAYS = int(os.getenv("SESSION_DAYS", "7"))
PBKDF2_ITERATIONS = 200_000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return (
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def _verify_password(password: str, salt_b64: str, hash_b64: str) -> bool:
    try:
        salt = base64.b64decode(salt_b64.encode("ascii"))
    except Exception:
        return False
    _, digest = _hash_password(password, salt)
    return hmac.compare_digest(digest, hash_b64)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_role(role: str | None) -> str:
    value = (role or ROLE_NORMAL).strip().lower()
    if value not in ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    return value


def default_permissions_for_role(role: str) -> dict[str, bool]:
    role = normalize_role(role)
    return dict(ROLE_DEFAULT_PERMISSIONS[role])


def ensure_default_admin() -> None:
    """Create the built-in administrator only when no admin user exists."""
    with get_db() as conn:
        row = conn.execute("SELECT id FROM users WHERE role = ? AND is_active = 1 LIMIT 1", (ROLE_ADMIN,)).fetchone()
        if row:
            return
        salt, password_hash = _hash_password(DEFAULT_ADMIN_PASSWORD)
        conn.execute(
            """
            INSERT INTO users (username, password_salt, password_hash, role, is_active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (DEFAULT_ADMIN_USERNAME, salt, password_hash, ROLE_ADMIN),
        )
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        set_user_permissions(conn, user_id, default_permissions_for_role(ROLE_ADMIN))
        conn.commit()


def get_user_permissions(conn, user_id: int, role: str) -> dict[str, bool]:
    permissions = default_permissions_for_role(role)
    rows = conn.execute(
        "SELECT module_key, allowed FROM user_module_permissions WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    for row in rows:
        if row["module_key"] in permissions:
            permissions[row["module_key"]] = bool(row["allowed"])
    if role == ROLE_ADMIN:
        permissions = {key: True for key in MODULE_KEYS}
    return permissions


def set_user_permissions(conn, user_id: int, permissions: dict[str, bool]) -> None:
    for key in MODULE_KEYS:
        allowed = bool(permissions.get(key, False))
        conn.execute(
            """
            INSERT INTO user_module_permissions (user_id, module_key, allowed, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, module_key) DO UPDATE SET
                allowed = excluded.allowed,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, key, 1 if allowed else 0),
        )


def serialize_user(conn, row) -> dict:
    role = row["role"]
    permissions = get_user_permissions(conn, row["id"], role)
    return {
        "id": row["id"],
        "username": row["username"],
        "role": role,
        "roleLabel": {"admin": "管理员组", "senior": "高级用户组", "normal": "普通用户组"}.get(role, role),
        "isActive": bool(row["is_active"]),
        "permissions": permissions,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def create_session(conn, user_id: int) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    expires_at = (_utc_now() + timedelta(days=SESSION_DAYS)).isoformat()
    conn.execute(
        "INSERT INTO user_sessions (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
        (user_id, _hash_token(token), expires_at),
    )
    return token, expires_at


def authenticate_user(username: str, password: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1",
            (username.strip(),),
        ).fetchone()
        if not row or not _verify_password(password, row["password_salt"], row["password_hash"]):
            return None
        token, expires_at = create_session(conn, row["id"])
        conn.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
        conn.commit()
        user = serialize_user(conn, row)
        user["token"] = token
        user["expiresAt"] = expires_at
        return user


def register_user(username: str, password: str) -> dict:
    username = (username or "").strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(password or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    salt, password_hash = _hash_password(password)
    with get_db() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_salt, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, 1)
                """,
                (username, salt, password_hash, ROLE_NORMAL),
            )
        except Exception as exc:
            if "unique" in str(exc).lower():
                raise HTTPException(status_code=409, detail="Username already exists") from exc
            raise
        user_id = cur.lastrowid
        set_user_permissions(conn, user_id, default_permissions_for_role(ROLE_NORMAL))
        token, expires_at = create_session(conn, user_id)
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        user = serialize_user(conn, row)
        user["token"] = token
        user["expiresAt"] = expires_at
        return user


def _test_bypass_enabled() -> bool:
    return os.getenv("AUTH_TEST_BYPASS", "").strip() == "1"


def _system_admin_user() -> dict:
    return {
        "id": 0,
        "username": "pytest-admin",
        "role": ROLE_ADMIN,
        "roleLabel": "管理员组",
        "isActive": True,
        "permissions": {key: True for key in MODULE_KEYS},
    }


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if _test_bypass_enabled():
        return _system_admin_user()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token_hash = _hash_token(token)
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT u.*
            FROM user_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.revoked_at IS NULL AND u.is_active = 1
            """,
            (token_hash,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
        session = conn.execute(
            "SELECT expires_at FROM user_sessions WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
        try:
            expires = datetime.fromisoformat(session["expires_at"])
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc
        if expires < _utc_now():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
        return serialize_user(conn, row)


def revoke_session(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        return
    token_hash = _hash_token(authorization.removeprefix("Bearer ").strip())
    with get_db() as conn:
        conn.execute("UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE token_hash = ?", (token_hash,))
        conn.commit()


def require_permission(module_key: str) -> Callable:
    if module_key not in MODULE_KEYS:
        raise ValueError(f"Unknown module permission: {module_key}")

    def dependency(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] == ROLE_ADMIN or user.get("permissions", {}).get(module_key) is True:
            return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    return dependency


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
