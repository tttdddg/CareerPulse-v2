"""History API routes."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..services.history_service import get_history_snapshot, get_user_histories

router = APIRouter()


@router.get("/users/{user_id}/histories")
def get_user_histories_api(user_id: str):
    data = get_user_histories(user_id)
    return JSONResponse(content={"code": 1, "msg": "success", "data": data})


@router.get("/histories/{history_id}/snapshot")
def get_history_snapshot_api(history_id: int):
    try:
        data = get_history_snapshot(history_id)
        return JSONResponse(content={"code": 1, "msg": "success", "data": data})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
