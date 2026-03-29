"""Job-related API routes."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..services.job_service import get_job_graph, get_job_profile, search_jobs

router = APIRouter()


@router.get("/jobs")
def get_jobs(keyword: str = Query(default=""), page: int = 1, size: int = 10):
    return search_jobs(keyword, page, size)


@router.get("/jobs/{job_id}/profile")
def get_job_profile_api(job_id: int):
    try:
        data = get_job_profile(job_id)
        return JSONResponse(content={"code": 1, "msg": "success", "data": data})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/jobs/{job_id}/graph")
def get_job_graph_api(job_id: int):
    try:
        data = get_job_graph(job_id)
        return JSONResponse(content={"code": 1, "msg": "success", "data": data})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
