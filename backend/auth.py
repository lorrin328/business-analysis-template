"""Simple admin-token protection for mutating operations."""
import os
from secrets import compare_digest

from fastapi import Header, HTTPException, status


def require_admin(x_admin_token: str | None = Header(default=None)):
    """Require X-Admin-Token when ADMIN_TOKEN is configured.

    In production, missing ADMIN_TOKEN is treated as a deployment error and
    mutating endpoints are blocked. Development remains frictionless unless
    ADMIN_TOKEN is explicitly set.
    """
    expected = os.getenv("ADMIN_TOKEN", "").strip()
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if not expected:
        if app_env == "production":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ADMIN_TOKEN is not configured",
            )
        return True
    if not x_admin_token or not compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")
    return True
