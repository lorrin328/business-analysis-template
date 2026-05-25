from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from config.business_lines import DEFAULT_YEAR
from services.excel_exporter import build_dashboard_export_workbook

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/export/excel")
def export_excel(year: int = Query(DEFAULT_YEAR, ge=2000, le=2100)):
    content = build_dashboard_export_workbook(year)
    filename = quote(f"经营分析看板数据_{year}.xlsx")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
