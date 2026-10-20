"""FastAPI route for CareerPulse browser chat through Ant TBox."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from ...auth.dependencies import (
    AuthenticatedRequest,
    require_web_authenticated_request,
    require_web_csrf,
)
from ...auth.identity import external_owner_id, web_owner_id
from .chat_service import TBoxChatException, TBoxChatService
from .schemas import (
    TBoxChatErrorResponse,
    TBoxChatRequest,
    TBoxChatResponse,
    TBoxChatStreamEvent,
)


router = APIRouter(prefix="/api/tbox", tags=["tbox-chat"])

_ERROR_RESPONSES = {
    409: {"model": TBoxChatErrorResponse, "description": "Session conflict"},
    422: {"model": TBoxChatErrorResponse, "description": "Request validation failed"},
    500: {"model": TBoxChatErrorResponse, "description": "Gateway failure"},
    502: {"model": TBoxChatErrorResponse, "description": "TBox response failure"},
    503: {
        "model": TBoxChatErrorResponse,
        "description": "Configuration or persistence unavailable",
    },
    504: {"model": TBoxChatErrorResponse, "description": "TBox timeout"},
}
_CHAT_RESPONSES = {
    200: {
        "description": "JSON response or normalized Server-Sent Events",
        "content": {
            "text/event-stream": {
                "schema": {"type": "string"},
                "example": (
                    "event: delta\n"
                    'data: {"type":"delta","content":"..."}\n\n'
                ),
            }
        },
    },
    **_ERROR_RESPONSES,
}


def _service(request: Request) -> TBoxChatService:
    return request.app.state.tbox_chat_service


def _error_response(exc: TBoxChatException) -> JSONResponse:
    body = TBoxChatErrorResponse(
        code=exc.code,
        message=exc.message,
        request_id=exc.request_id,
        error=exc.detail_model(),
    )
    return JSONResponse(
        status_code=exc.http_status,
        content=body.model_dump(mode="json"),
    )


async def tbox_chat_exception_handler(
    request: Request, exc: TBoxChatException
) -> JSONResponse:
    del request
    return _error_response(exc)


async def tbox_chat_request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    del request, exc
    return _error_response(
        TBoxChatException(
            code=-2,
            http_status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_type="REQUEST_VALIDATION_FAILED",
            message="request validation failed",
            detail="The request does not match the CareerPulse TBox chat schema",
            retryable=False,
            request_id=TBoxChatService._new_request_id(),
        )
    )


async def _encode_stream(
    events: AsyncIterator[TBoxChatStreamEvent],
) -> AsyncIterator[str]:
    async for event in events:
        data = event.model_dump_json(exclude_none=True)
        yield f"event: {event.type}\ndata: {data}\n\n"


@router.post(
    "/chat",
    operation_id="chat_with_tbox_agent",
    response_model=TBoxChatResponse,
    responses=_CHAT_RESPONSES,
    summary="Chat with the configured Ant TBox agent",
)
async def chat_with_tbox_agent(
    payload: TBoxChatRequest,
    request: Request,
    authenticated: AuthenticatedRequest | None = Depends(
        require_web_authenticated_request
    ),
    _csrf: None = Depends(require_web_csrf),
) -> Any:
    if authenticated is not None:
        owner_id = web_owner_id(authenticated.user.id)
    elif payload.user_id:
        owner_id = external_owner_id(payload.user_id)
    else:
        raise TBoxChatException(
            code=-2,
            http_status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_type="REQUEST_VALIDATION_FAILED",
            message="request validation failed",
            detail="user_id is required when Web authentication is disabled",
            retryable=False,
            request_id=TBoxChatService._new_request_id(),
        )
    trusted_payload = payload.model_copy(update={"user_id": owner_id})
    service = _service(request)
    if not trusted_payload.stream:
        return await service.chat(trusted_payload)
    service.ensure_configured()
    return StreamingResponse(
        _encode_stream(service.stream(trusted_payload)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = [
    "router",
    "tbox_chat_exception_handler",
    "tbox_chat_request_validation_exception_handler",
]
