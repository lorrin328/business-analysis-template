from fastapi import APIRouter, Body, Header, HTTPException, Depends, Query

from auth import (
    MODULE_KEYS,
    ROLE_ADMIN,
    ROLE_NORMAL,
    default_permissions_for_role,
    authenticate_user,
    get_current_user,
    normalize_role,
    public_registration_enabled,
    register_user,
    require_admin,
    revoke_session,
    serialize_user,
    set_user_permissions,
    validate_username,
)
from db import get_db
from services.audit_log import list_operation_logs, log_operation
from services.response import success_response

router = APIRouter(prefix="/api/auth", tags=["auth"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


def _active_admin_count(conn) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM users WHERE role = ? AND is_active = 1",
        (ROLE_ADMIN,),
    ).fetchone()
    return int(row["count"] if row else 0)


@router.post("/login")
def login(payload: dict = Body(...)):
    user = authenticate_user(payload.get("username", ""), payload.get("password", ""))
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = user.pop("token")
    expires_at = user.pop("expiresAt")
    return success_response({"token": token, "expiresAt": expires_at, "user": user})


@router.post("/register")
def register(payload: dict = Body(...)):
    user = register_user(payload.get("username", ""), payload.get("password", ""))
    token = user.pop("token")
    expires_at = user.pop("expiresAt")
    return success_response({"token": token, "expiresAt": expires_at, "user": user})


@router.get("/config")
def auth_config():
    return success_response({"allowPublicRegistration": public_registration_enabled()})


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)):
    revoke_session(authorization)
    return success_response({"ok": True})


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return success_response(user)


@admin_router.get("/users")
def list_users(_admin=Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY CASE role WHEN 'admin' THEN 1 WHEN 'senior' THEN 2 ELSE 3 END, username"
        ).fetchall()
        return success_response(
            {
                "moduleKeys": MODULE_KEYS,
                "roleDefaults": {
                    "admin": default_permissions_for_role("admin"),
                    "senior": default_permissions_for_role("senior"),
                    "normal": default_permissions_for_role("normal"),
                },
                "users": [serialize_user(conn, row) for row in rows],
            }
        )


@admin_router.get("/operation-logs")
def operation_logs(
    limit: int = Query(200, ge=1, le=500),
    action: str | None = None,
    username: str | None = None,
    _admin=Depends(require_admin),
):
    return success_response(
        {
            "logs": list_operation_logs(limit=limit, action=action, username=username),
            "actions": [
                "register",
                "login",
                "password_reset",
                "import_report",
                "target_save",
                "excel_export",
                "product_config",
                "permission_admin",
                "honor_field_audit",
                "honor_recalculate",
                "honor_export",
                "honor_view_batch",
                "scheme_upload",
            ],
        }
    )


@admin_router.post("/users")
def create_user(payload: dict = Body(...), admin=Depends(require_admin)):
    username = validate_username(payload.get("username"))
    password = payload.get("password") or ""
    role = normalize_role(payload.get("role") or ROLE_NORMAL)
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="密码至少需要8个字符")

    from auth import _hash_password

    salt, password_hash = _hash_password(password)
    permissions = default_permissions_for_role(role)
    permissions.update(payload.get("permissions") or {})
    if role == ROLE_ADMIN:
        permissions = default_permissions_for_role(ROLE_ADMIN)
    with get_db() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_salt, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, 1)
                """,
                (username, salt, password_hash, role),
            )
        except Exception as exc:
            if "unique" in str(exc).lower():
                raise HTTPException(status_code=409, detail="用户名已存在") from exc
            raise
        set_user_permissions(conn, cur.lastrowid, permissions)
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
        data = serialize_user(conn, row)
    log_operation(
        "permission_admin",
        user=admin,
        target_user_id=data["id"],
        target_username=data["username"],
        detail={"operation": "create_user", "role": data["role"]},
    )
    return success_response(data)


@admin_router.patch("/users/{user_id}")
def update_user(user_id: int, payload: dict = Body(...), admin=Depends(require_admin)):
    password_changed = False
    password_target_username = None
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        if row["role"] == ROLE_ADMIN and row["id"] == admin["id"]:
            requested_role = payload.get("role")
            if requested_role and normalize_role(requested_role) != ROLE_ADMIN:
                raise HTTPException(status_code=400, detail="不能降低当前管理员账号权限")

        username = payload.get("username")
        role = normalize_role(payload.get("role") or row["role"])
        is_active = payload.get("isActive")
        projected_active = bool(row["is_active"]) if is_active is None else bool(is_active)
        removing_active_admin = row["role"] == ROLE_ADMIN and bool(row["is_active"]) and (
            role != ROLE_ADMIN or not projected_active
        )
        if removing_active_admin and _active_admin_count(conn) <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last active administrator")
        if role == ROLE_ADMIN:
            permissions = default_permissions_for_role(ROLE_ADMIN)
        elif row["role"] == ROLE_ADMIN:
            permissions = default_permissions_for_role(role)
        else:
            permissions = default_permissions_for_role(role)
            permissions.update(payload.get("permissions") or {})
            permissions["permission_admin"] = False

        if username is not None:
            username = validate_username(username)
            conn.execute("UPDATE users SET username = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (username, user_id))
        conn.execute("UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (role, user_id))
        if is_active is not None:
            if row["role"] == ROLE_ADMIN and row["id"] == admin["id"] and not bool(is_active):
                raise HTTPException(status_code=400, detail="不能停用当前管理员账号")
            conn.execute("UPDATE users SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (1 if is_active else 0, user_id))

        new_password = payload.get("password")
        if new_password:
            if len(new_password) < 8:
                raise HTTPException(status_code=400, detail="密码至少需要8个字符")
            from auth import _hash_password
            salt, password_hash = _hash_password(new_password)
            conn.execute(
                "UPDATE users SET password_salt = ?, password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (salt, password_hash, user_id),
            )
            password_changed = True
            password_target_username = username or row["username"]

        set_user_permissions(conn, user_id, permissions)
        conn.commit()
        updated = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        data = serialize_user(conn, updated)
    if password_changed:
        log_operation(
            "password_reset",
            user=admin,
            target_user_id=user_id,
            target_username=password_target_username or data["username"],
        )
    log_operation(
        "permission_admin",
        user=admin,
        target_user_id=data["id"],
        target_username=data["username"],
        detail={"operation": "update_user", "role": data["role"], "isActive": data["isActive"]},
    )
    return success_response(data)


@admin_router.delete("/users/{user_id}")
def delete_user(user_id: int, admin=Depends(require_admin)):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        if row["id"] == admin["id"]:
            raise HTTPException(status_code=400, detail="不能删除当前登录管理员账号")
        if row["role"] == ROLE_ADMIN and bool(row["is_active"]) and _active_admin_count(conn) <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last active administrator")
        conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_module_permissions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    log_operation(
        "permission_admin",
        user=admin,
        target_user_id=user_id,
        target_username=row["username"],
        detail={"operation": "delete_user", "role": row["role"]},
    )
    return success_response({"deleted": True, "id": user_id})
