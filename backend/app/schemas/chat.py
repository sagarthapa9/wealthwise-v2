"""Pydantic schemas for chat request/response."""

from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for POST /api/v1/chat."""
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=64)


class ChatMessageResponse(BaseModel):
    """A single message in the conversation."""
    id: int
    role: str
    content: str | None = None
    tool_calls: dict | None = None
    reasoning_content: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""
    session_id: str
    message: str
    reasoning_content: str | None = None
    messages: list[ChatMessageResponse] | None = None


class ChatHistoryResponse(BaseModel):
    """Full conversation history for a session."""
    session_id: str
    title: str
    messages: list[ChatMessageResponse]
