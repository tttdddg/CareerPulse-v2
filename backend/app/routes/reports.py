"""Report API routes."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from ..schemas import ReportGenerateRequest, ReportPolishRequest
from ..services.report_service import export_report, generate_report, get_report, polish_report

router = APIRouter()


@router.post("/reports/generate")
def generate_report_api(payload: ReportGenerateRequest):
    try:
        data = generate_report(
            payload.student_id,
            payload.job_id,
            payload.custom_instructions,
            payload.user_id or "default",
        )
        return JSONResponse(content={"code": 1, "msg": "success", "data": data})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/reports/{report_id}")
def get_report_api(report_id: int):
    try:
        data = get_report(report_id)
        return JSONResponse(content={"code": 1, "msg": "success", "data": data})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/reports/{report_id}/polish")
def polish_report_api(report_id: int, payload: ReportPolishRequest):
    try:
        data = polish_report(report_id, payload.paragraph_index, payload.text)
        return JSONResponse(content={"code": 1, "msg": "success", "data": data})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/reports/{report_id}/export")
def export_report_api(report_id: int, format: str = Query("pdf")):
    try:
        filename, content, mime = export_report(report_id, format)
        return Response(
            content=content,
            media_type=mime,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
