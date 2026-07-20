"""Shared FastAPI query parameter definitions."""
from __future__ import annotations

from typing import Annotated

from fastapi import Query


DashboardYearQuery = Annotated[int, Query(ge=2000, le=2100)]
AsOfQuery = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")]
DateQuery = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")]
RangeTypeQuery = Annotated[str | None, Query(pattern=r"^(ytd|month|day|custom)$")]
