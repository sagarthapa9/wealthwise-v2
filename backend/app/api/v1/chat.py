"""Chat API endpoint — LLM-powered portfolio analysis.

Endpoints:
  - ``POST /api/v1/chat`` — Send a message and get an LLM response
  - ``GET /api/v1/chat/{session_id}/messages`` — Load conversation history
  - ``GET /api/v1/chat/latest`` — Get the most recent session for restoration
  - ``POST /api/v1/chat/{session_id}/clear`` — Clear messages with smart archiving
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
from app.services.memory_service import MemoryService

router = APIRouter(tags=["chat"])


@router.get("/chat/latest")
async def get_latest_session(
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent chat session with its last assistant message.

    Used to restore the hero card and chat panel when the user returns.
    Returns null if no sessions exist yet.
    """
    service = ChatService(db)
    session = await service.get_latest_session()
    if session is None:
        return {"session_id": None, "message": None, "reasoning_content": None}

    # Get the last assistant message for the hero card
    messages = await service.memory.get_conversation(session.id, limit=5)
    last_assistant = None
    for msg in messages:
        if msg.role == "assistant" and msg.content:
            last_assistant = msg

    return {
        "session_id": session.session_id,
        "message": last_assistant.content if last_assistant else None,
        "reasoning_content": last_assistant.reasoning_content if last_assistant else None,
        "generated_at": last_assistant.created_at.isoformat() if last_assistant else None,
    }


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


@router.post("/chat/{session_id}/clear")
async def clear_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Clear messages for a session and archive a summary.

    Before deleting, the conversation is summarised via LLM and stored
    on the session record for future reference.
    """
    service = ChatService(db)
    summary = await service.clear_and_summarize(session_id)
    return {"session_id": session_id, "summary": summary}
