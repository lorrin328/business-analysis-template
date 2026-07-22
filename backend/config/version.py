"""Single source for the application version."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = ROOT / "VERSION"
DEFAULT_VERSION = "v1.0.107"


def get_app_version() -> str:
    try:
        value = VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return DEFAULT_VERSION
    return value or DEFAULT_VERSION


def get_semver() -> str:
    return get_app_version().removeprefix("v")
