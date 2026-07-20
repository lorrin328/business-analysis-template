from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.params import AsOfQuery, DashboardYearQuery, DateQuery, RangeTypeQuery
from auth import require_permission
from config.business_lines import DEFAULT_YEAR
from services.audit_log import log_operation
from services.excel_exporter import build_dashboard_export_workbook

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/export/excel")
def export_excel(
    year: DashboardYearQuery = DEFAULT_YEAR,
    asOf: AsOfQuery = None,
    rangeType: RangeTypeQuery = None,
    startDate: DateQuery = None,
    endDate: DateQuery = None,
    _user=Depends(require_permission("excel_export")),
):
    content = build_dashboard_export_workbook(
        year,
        as_of=asOf,
        range_type=rangeType,
        start_date=startDate,
        end_date=endDate,
    )
    detail = {
        "year": year,
        "rangeType": rangeType or "ytd",
        "startDate": startDate,
        "endDate": endDate or asOf,
        "bytes": len(content),
    }
    log_operation("excel_export", user=_user, detail=detail)
    filename = quote(f"经营分析看板数据_{year}_{rangeType or 'ytd'}.xlsx")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
