"""Chat service — orchestrates the LLM interaction with context injection.

Pattern (matches v1's ``chatBot_dpsk.py`` but async + PostgreSQL):

1. Load conversation history (sliding window, last 20 messages)
2. Build portfolio context from DB
3. Check guardrails
4. Build system prompt with context injected
5. Call DeepSeek via OpenAI-compatible client
6. Handle optional tool_calls (analyze_ticker only)
7. Persist messages
8. Return response
"""

import json
from datetime import datetime, timezone

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.context_builder import build_llm_context
from app.services.system_prompt import build_system_prompt
from app.services.guardrails import check_input
from app.services.memory_service import MemoryService, SessionRecord

# ── Constants ────────────────────────────────────────────────────────────

MAX_HISTORY_MESSAGES = 20

# ── OpenAI-compatible client (points at DeepSeek) ───────────────────────

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    return _client


# ── Tool definitions ────────────────────────────────────────────────────

ANALYZE_TICKER_TOOL = {
    "type": "function",
    "function": {
        "name": "analyze_ticker",
        "description": "Fetch current price and metadata for a ticker symbol. "
                       "Use when the user asks about a specific holding's current price, "
                       "performance, or when you need up-to-date market data.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Ticker symbol, e.g. VWRL, VUSA, AAPL",
                },
            },
            "required": ["symbol"],
        },
    },
}

TOOLS = [ANALYZE_TICKER_TOOL]


# ── Chat service ────────────────────────────────────────────────────────

class ChatService:
    """Orchestrates the LLM interaction.

    Usage::

        service = ChatService(db)
        result = await service.chat("How diversified am I?", session_id="abc")
        # => {"message": "...", "session_id": "abc", "reasoning_content": "..."}
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.memory = MemoryService(db)

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
        user_id: int | None = None,
    ) -> dict:
        """Process a chat message and return the LLM response.

        Args:
            message: The user's message.
            session_id: Optional existing session ID. If None, a new session is created.
            user_id: Optional user ID for memory persistence.

        Returns:
            A dict with keys: ``message``, ``session_id``, ``reasoning_content``,
            and optionally ``messages`` (full conversation list).
        """
        # ── 1. Guardrails check ───────────────────────────────────────
        refusal = check_input(message)
        if refusal:
            # Create a session to return, even for blocked messages
            session = await self.memory.get_or_create_session(
                session_id=session_id,
                user_id=user_id,
            )
            await self.memory.add_message(
                session_pk=session.id,
                role="user",
                content=message,
            )
            await self.memory.add_message(
                session_pk=session.id,
                role="assistant",
                content=refusal,
            )
            return {
                "message": refusal,
                "session_id": session.session_id,
                "reasoning_content": None,
            }

        # ── 2. Get or create session ──────────────────────────────────
        session = await self.memory.get_or_create_session(
            session_id=session_id,
            user_id=user_id,
        )

        # ── 3. Build portfolio context ────────────────────────────────
        context = await build_llm_context(self.db)
        system_prompt = build_system_prompt(context)

        # ── 4. Load conversation history (sliding window) ─────────────
        raw_history = await self.memory.get_conversation(
            session_pk=session.id,
            limit=MAX_HISTORY_MESSAGES,
        )

        # Convert to OpenAI message format (reversed to chronological)
        history_messages = []
        for msg in reversed(raw_history):
            entry = {"role": msg.role, "content": msg.content or ""}
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            history_messages.append(entry)

        # ── 5. Build the full message list for the LLM call ───────────
        llm_messages = [
            {"role": "system", "content": system_prompt},
            *history_messages,
            {"role": "user", "content": message},
        ]

        # ── 6. Persist user message ───────────────────────────────────
        await self.memory.add_message(
            session_pk=session.id,
            role="user",
            content=message,
        )

        # ── 7. Call DeepSeek ──────────────────────────────────────────
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.deepseek_model,
            messages=llm_messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        response_message = choice.message
        reasoning_content = getattr(choice.message, "reasoning_content", None)

        # ── 8. Handle tool calls ──────────────────────────────────────
        if response_message.tool_calls:
            tool_result = await self._handle_tool_calls(response_message.tool_calls)

            # Persist assistant response with tool calls
            tool_calls_data = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in response_message.tool_calls
            ]
            await self.memory.add_message(
                session_pk=session.id,
                role="assistant",
                content=response_message.content or "",
                tool_calls=tool_calls_data,
                reasoning_content=reasoning_content,
            )

            # Persist tool results
            for tr in tool_result:
                await self.memory.add_message(
                    session_pk=session.id,
                    role="tool",
                    content=json.dumps(tr["result"]),
                    tool_call_id=tr["tool_call_id"],
                )

            # Second LLM call with tool results
            llm_messages.append({
                "role": "assistant",
                "content": response_message.content or "",
                "tool_calls": tool_calls_data,
            })
            for tr in tool_result:
                llm_messages.append({
                    "role": "tool",
                    "tool_call_id": tr["tool_call_id"],
                    "content": json.dumps(tr["result"]),
                })

            second_response = await client.chat.completions.create(
                model=settings.deepseek_model,
                messages=llm_messages,
            )

            final_content = second_response.choices[0].message.content or ""
            final_reasoning = getattr(
                second_response.choices[0].message, "reasoning_content", None
            )

            # Persist final assistant response
            await self.memory.add_message(
                session_pk=session.id,
                role="assistant",
                content=final_content,
                reasoning_content=final_reasoning,
            )

            return {
                "message": final_content,
                "session_id": session.session_id,
                "reasoning_content": final_reasoning,
            }

        # ── 9. No tool calls — persist and return ─────────────────────
        content = response_message.content or ""
        await self.memory.add_message(
            session_pk=session.id,
            role="assistant",
            content=content,
            reasoning_content=reasoning_content,
        )

        return {
            "message": content,
            "session_id": session.session_id,
            "reasoning_content": reasoning_content,
        }

    # ── Tool handler ──────────────────────────────────────────────────

    async def _handle_tool_calls(self, tool_calls) -> list[dict]:
        """Execute tool calls. Currently only supports ``analyze_ticker``."""
        results = []
        for tc in tool_calls:
            if tc.function.name == "analyze_ticker":
                try:
                    args = json.loads(tc.function.arguments)
                    symbol = args.get("symbol", "")
                    result = await self._analyze_ticker(symbol)
                    results.append({
                        "tool_call_id": tc.id,
                        "result": result,
                    })
                except Exception as e:
                    results.append({
                        "tool_call_id": tc.id,
                        "result": {"error": str(e)},
                    })
        return results

    async def _analyze_ticker(self, symbol: str) -> dict:
        """Fetch current data for a ticker using the provider abstraction."""
        from app.services.ticker_provider import get_ticker_provider, TickerNotFoundError

        provider = get_ticker_provider()
        try:
            data = await provider.lookup(symbol)
            return {
                "ticker": data.ticker,
                "name": data.name,
                "price": data.price,
                "currency": data.currency,
                "type": data.type,
                "asset_class": data.asset_class,
                "sector": data.sector,
                "geography": data.geography,
                "ocf_pct": data.ocf_pct,
                "dividend_yield_pct": data.dividend_yield_pct,
            }
        except TickerNotFoundError as e:
            return {"error": str(e)}

    # ── Session history ───────────────────────────────────────────────

    async def get_latest_session(self) -> SessionRecord | None:
        """Return the most recently updated session."""
        return await self.memory.get_latest_session()

    async def get_history(self, session_id: str) -> dict | None:
        """Load full conversation history for a session."""
        session = await self.memory.get_or_create_session(session_id=session_id)
        messages = await self.memory.get_conversation(session_pk=session.id, limit=200)

        msg_list = []
        for msg in reversed(messages):
            msg_list.append({
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "tool_calls": msg.tool_calls,
                "reasoning_content": msg.reasoning_content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            })

        return {
            "session_id": session.session_id,
            "title": session.title,
            "messages": msg_list,
        }
