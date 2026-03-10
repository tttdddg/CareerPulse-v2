"""Matching API routes."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..schemas import MatchingAnalyzeRequest
from ..services.matching_service import analyze_matching

router = APIRouter()


@router.post("/matching/analyze")
def matching_analyze_api(payload: MatchingAnalyzeRequest):
    try:
        data = analyze_matching(payload.student_id, payload.job_id, payload.user_id or "default")
        return JSONResponse(content={"code": 1, "msg": "success", "data": data})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
