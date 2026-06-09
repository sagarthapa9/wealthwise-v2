"""Async PostgreSQL-backed memory service for conversation persistence.

Replicates the v1 ``MemoryManager`` interface pattern but uses SQLAlchemy
async sessions and PostgreSQL.

Roles:
  - ``get_or_create_session`` — find or create a chat session by session_id
  - ``add_message`` — persist one message to the database
  - ``get_conversation`` — load recent messages for a session (used by sliding window)
  - ``delete_conversation`` — remove a session and all its messages
  - ``list_recent_sessions`` — list sessions for a user
  - ``get_user_memory`` / ``set_user_memory`` — lightweight key-value facts
"""

import uuid
from datetime import datetime

from sqlalchemy import select, update, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession, UserMemory


class SessionRecord:
    """Return type for session lookups."""
    def __init__(self, id: int, session_id: str, title: str,
                 prompt_name: str, created_at: datetime, updated_at: datetime):
        self.id = id
        self.session_id = session_id
        self.title = title
        self.prompt_name = prompt_name
        self.created_at = created_at
        self.updated_at = updated_at


class MemoryService:
    """Async PostgreSQL conversation memory.

    This class handles storage and retrieval. The sliding window (keeping
    only the last N messages in the working prompt) is applied by the
    caller — typically ``ChatService`` — not by this class.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_session(
        self,
        session_id: str | None = None,
        user_id: int | None = None,
        prompt_name: str = "investment_analyst",
    ) -> SessionRecord:
        """Find an existing session or create a new one.

        If *session_id* is provided, looks up that session. Otherwise
        generates a new UUID and creates a fresh session.
        """
        if session_id:
            result = await self.db.execute(
                select(ChatSession).where(ChatSession.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            if session:
                # Touch updated_at
                session.updated_at = datetime.utcnow()
                await self.db.commit()
                return SessionRecord(
                    id=session.id,
                    session_id=session.session_id,
                    title=session.title,
                    prompt_name=session.prompt_name,
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                )

        # Create a new session
        new_id = session_id or str(uuid.uuid4())
        session = ChatSession(
            session_id=new_id,
            user_id=user_id,
            prompt_name=prompt_name,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        return SessionRecord(
            id=session.id,
            session_id=session.session_id,
            title=session.title,
            prompt_name=session.prompt_name,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    async def add_message(
        self,
        session_pk: int,
        role: str,
        content: str | None = None,
        tool_calls: dict | None = None,
        tool_call_id: str | None = None,
        reasoning_content: str | None = None,
    ) -> int:
        """Persist a message to the database. Returns the message id."""
        msg = ChatMessage(
            session_id=session_pk,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            reasoning_content=reasoning_content,
        )
        self.db.add(msg)
        await self.db.commit()
        await self.db.refresh(msg)
        return msg.id

    async def get_conversation(
        self,
        session_pk: int,
        limit: int = 50,
        include_archived: bool = False,
    ) -> list[ChatMessage]:
        """Load the most recent messages for a session, newest first.

        The caller should reverse this list if chronological order is needed.
        Use ``limit`` to bound the result size (sliding window).
        By default, archived (soft-deleted) messages are excluded.
        """
        query = select(ChatMessage).where(ChatMessage.session_id == session_pk)
        if not include_archived:
            query = query.where(
                (ChatMessage.archived == False) | (ChatMessage.archived == None)  # noqa: E712
            )
        query = query.order_by(ChatMessage.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def delete_conversation(self, session_pk: int) -> None:
        """Delete a session and all its messages (CASCADE)."""
        await self.db.execute(
            delete(ChatSession).where(ChatSession.id == session_pk)
        )
        await self.db.commit()

    async def archive_session(self, session_pk: int, summary: str | None) -> None:
        """Store summary on a session and soft-delete its messages."""
        await self.db.execute(
            update(ChatSession)
            .where(ChatSession.id == session_pk)
            .values(summary=summary)
        )
        await self.db.execute(
            update(ChatMessage)
            .where(ChatMessage.session_id == session_pk)
            .values(archived=True)
        )
        await self.db.commit()

    async def get_latest_session(self) -> SessionRecord | None:
        """Return the most recently updated session, or None if no sessions exist."""
        result = await self.db.execute(
            select(ChatSession)
            .order_by(ChatSession.updated_at.desc())
            .limit(1)
        )
        session = result.scalar_one_or_none()
        if session is None:
            return None
        return SessionRecord(
            id=session.id,
            session_id=session.session_id,
            title=session.title,
            prompt_name=session.prompt_name,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    async def list_recent_sessions(
        self,
        user_id: int,
        limit: int = 10,
    ) -> list[SessionRecord]:
        """List the most recent sessions for a user."""
        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
        )
        sessions = result.scalars().all()
        return [
            SessionRecord(
                id=s.id,
                session_id=s.session_id,
                title=s.title,
                prompt_name=s.prompt_name,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in sessions
        ]

    async def get_user_memory(self, user_id: int) -> dict[str, str]:
        """Load all key-value facts for a user."""
        result = await self.db.execute(
            select(UserMemory).where(UserMemory.user_id == user_id)
        )
        rows = result.scalars().all()
        return {row.key: row.value for row in rows}

    async def set_user_memory(
        self,
        user_id: int,
        key: str,
        value: str,
        confidence: float = 1.0,
        source: str | None = None,
    ) -> None:
        """Upsert a user memory fact."""
        result = await self.db.execute(
            select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.key == key,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
            existing.confidence = confidence
            existing.source = source
        else:
            entry = UserMemory(
                user_id=user_id,
                key=key,
                value=value,
                confidence=confidence,
                source=source,
            )
            self.db.add(entry)
        await self.db.commit()
