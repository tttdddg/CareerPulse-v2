"""Public and internal schemas for the Ant TBox chat gateway."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class TBoxSchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TBoxChatRequest(TBoxSchemaModel):
    """One browser message sent through the server-side TBox gateway."""

    session_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    user_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    message: str = Field(min_length=1, max_length=20_000)
    stream: bool = False


class TBoxChatData(TBoxSchemaModel):
    session_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    conversation_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    message_id: str | None = Field(default=None, max_length=256)
    upstream_request_id: str | None = Field(default=None, max_length=256)
    content: str = Field(min_length=1, max_length=100_000)


class TBoxChatResponse(TBoxSchemaModel):
    code: Literal[0] = 0
    message: Literal["success"] = "success"
    request_id: str = Field(
        min_length=1, max_length=64, pattern=_IDENTIFIER_PATTERN
    )
    data: TBoxChatData
    error: None = None


class TBoxChatErrorDetail(TBoxSchemaModel):
    type: str = Field(min_length=1, max_length=128)
    detail: str = Field(min_length=1, max_length=500)
    retryable: bool


class TBoxChatErrorResponse(TBoxSchemaModel):
    code: int = Field(le=-1)
    message: str = Field(min_length=1, max_length=200)
    request_id: str = Field(
        min_length=1, max_length=64, pattern=_IDENTIFIER_PATTERN
    )
    data: None = None
    error: TBoxChatErrorDetail


StreamEventType = Literal["session", "delta", "done", "error"]


class TBoxChatStreamEvent(TBoxSchemaModel):
    """Normalized SSE payload; the SSE event name equals ``type``."""

    type: StreamEventType
    request_id: str = Field(
        min_length=1, max_length=64, pattern=_IDENTIFIER_PATTERN
    )
    session_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    conversation_id: str | None = Field(
        default=None, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    message_id: str | None = Field(default=None, max_length=256)
    upstream_request_id: str | None = Field(default=None, max_length=256)
    content: str | None = Field(default=None, max_length=100_000)
    error: TBoxChatErrorDetail | None = None

    @model_validator(mode="after")
    def validate_event_shape(self) -> "TBoxChatStreamEvent":
        if self.type == "delta" and self.content is None:
            raise ValueError("delta event requires content")
        if self.type == "error" and self.error is None:
            raise ValueError("error event requires error detail")
        if self.type != "error" and self.error is not None:
            raise ValueError("only error events may contain error detail")
        return self


class TBoxUpstreamReply(TBoxSchemaModel):
    """Normalized non-stream response returned by ``TBoxClient``."""

    conversation_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    message_id: str | None = Field(default=None, max_length=256)
    request_id: str | None = Field(default=None, max_length=256)
    content: str = Field(min_length=1, max_length=100_000)


class TBoxUpstreamStreamFrame(TBoxSchemaModel):
    """Small, privacy-safe projection of one upstream SSE event."""

    kind: Literal["header", "chunk", "end"]
    conversation_id: str | None = Field(
        default=None, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    message_id: str | None = Field(default=None, max_length=256)
    request_id: str | None = Field(default=None, max_length=256)
    text: str | None = Field(default=None, max_length=100_000)


__all__ = [
    "TBoxChatData",
    "TBoxChatErrorDetail",
    "TBoxChatErrorResponse",
    "TBoxChatRequest",
    "TBoxChatResponse",
    "TBoxChatStreamEvent",
    "TBoxUpstreamReply",
    "TBoxUpstreamStreamFrame",
]
