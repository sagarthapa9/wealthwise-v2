"""Chat API endpoint — LLM-powered portfolio analysis.

Endpoints:
  - ``POST /api/v1/chat`` — Send a message and get an LLM response
  - ``GET /api/v1/chat/{session_id}/messages`` — Load conversation history
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatHistoryResponse,
    ChatMessageResponse,
)
from app.services.chat_service import ChatService

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get an LLM-powered portfolio analysis response.

    The endpoint:
    1. Builds a full portfolio context from the database
    2. Injects it into the system prompt
    3. Sends the conversation to DeepSeek
    4. Returns the response with optional reasoning content

    A new session is created if ``session_id`` is not provided.
    """
    service = ChatService(db)
    result = await service.chat(
        message=body.message,
        session_id=body.session_id,
    )

    return ChatResponse(
        session_id=result["session_id"],
        message=result["message"],
        reasoning_content=result.get("reasoning_content"),
    )


@router.get("/chat/{session_id}/messages", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Load the full conversation history for a session."""
    service = ChatService(db)
    history = await service.get_history(session_id)

    if history is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return ChatHistoryResponse(
        session_id=history["session_id"],
        title=history["title"],
        messages=[
            ChatMessageResponse(**m) for m in history["messages"]
        ],
    )
