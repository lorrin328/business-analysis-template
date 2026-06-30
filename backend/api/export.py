from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.params import DashboardYearQuery
from auth import require_permission
from config.business_lines import DEFAULT_YEAR
from services.audit_log import log_operation
from services.excel_exporter import build_dashboard_export_workbook

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/export/excel")
def export_excel(year: DashboardYearQuery = DEFAULT_YEAR, _user=Depends(require_permission("excel_export"))):
    content = build_dashboard_export_workbook(year)
    log_operation("excel_export", user=_user, detail={"year": year, "bytes": len(content)})
    filename = quote(f"经营分析看板数据_{year}.xlsx")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
