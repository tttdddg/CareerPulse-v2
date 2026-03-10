"""Recommendation API route."""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from ..services.recommendation_service import get_recommendations

router = APIRouter()


@router.get("/recommendations")
def get_recommendations_api(gap: str = Query("")):
    data = get_recommendations(gap)
    return JSONResponse(content={"code": 1, "msg": "success", "data": data})
