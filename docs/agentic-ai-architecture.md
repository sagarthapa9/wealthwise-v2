# WealthWise Chatbot — Agentic AI Architecture

## Current Status & Roadmap to True ReAct Agent

---

## 1. What We Have Now

The chatbot at `C:\SourceCode\wealthwise\chatBot_dpsk.py` is a
**function-calling chatbot** with persistent memory. It is NOT yet a true
agent, but it has the foundational pieces.

### Current flow (per user message)

```
User: "How is my VWRL performing?"

  1. APPEND  ──► user message → conversation_history + SQLite
  2. SEND    ──► system prompt + full history → DeepSeek API
  3. DECIDE  ──► LLM returns tool_calls OR text response

  ┌── If tool_calls ───────────────────────────────────┐
  │  4. EXECUTE ──► Run each tool (e.g. analyze_ticker)│
  │  5. APPEND  ──► tool result → history + SQLite       │
  │  6. RE-SEND ──► history (with results) → DeepSeek    │
  │  7. REPLY   ──► Return final text to user            │
  └─────────────────────────────────────────────────────┘

  ┌── If text (no tools needed) ───────────────────────┐
  │  4. REPLY   ──► Return text directly                │
  └─────────────────────────────────────────────────────┘
```

### What qualifies as "agent-like"

| Feature | Status | Details |
|---------|--------|---------|
| Tool calling | ✅ | Can call weather, fund analysis, yfinance |
| Persistent memory | ✅ | SQLite — survives restarts across sessions |
| System prompt personas | ✅ | `prompts/` folder with 8+ personalities |
| Portfolio context injection | ✅ | Appends holdings data to system prompt |
| Multi-turn conversation | ✅ | Full history sent each request |

### What's missing for true agency

| Gap | Why it matters |
|-----|----------------|
| **No reasoning loop** | Only 1 round of tool calls per message. Cannot chain tools or iterate. |
| **No scratchpad** | No structured "think → plan → act → observe" instructions in the prompt |
| **No sub-goal decomposition** | Cannot break "analyse my portfolio" into steps (check holdings → check sectors → check market → summarise) |
| **No self-reflection** | Doesn't verify its own outputs or recover from failures |
| **No long-term memory of user preferences** | Profile is static — doesn't learn from past conversations |
| **History keeps growing** | Full history sent every call — eventually hits token limits |

---

## 2. What is ReAct?

**ReAct = Reasoning + Acting**

It's a pattern where the LLM alternates between:

```
  OBSERVE ──► Receive input (user message or tool result)
     │
  THINK   ──► Reason about what to do next
     │
  PLAN    ──► Decide which tools to call and in what order
     │
  ACT     ──► Execute tool calls
     │
  OBSERVE ──► See what the tools returned
     │
     └── Repeat until enough information gathered ──► ANSWER
```

The key difference from the current implementation: **the loop keeps going**
until the LLM explicitly signals it has enough information to answer.

---

## 2b. What "Memory Augmented" Means

A **memory augmented** agent doesn't just rely on its training data or the
current conversation — it actively reads from AND writes to an external memory
store as it works.

Think of it like a doctor who keeps patient files:

| Without memory | With memory (augmented) |
|---------------|------------------------|
| "Hello, I'm Dr AI. What brings you in today?" | "Welcome back, Sagar. Last time we discussed your tech concentration risk. Has anything changed?" |
| Every visit starts from scratch | Remembers your history, preferences, and past advice |

### Three layers of memory

```
┌─────────────────────────────────────────────────────────────┐
│                   MEMORY AUGMENTED AGENT                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  WORKING MEMORY    │   EPISODIC MEMORY    │   SEMANTIC MEMORY │
│  (current chat)    │   (past sessions)    │   (user profile)  │
│                     │                       │                   │
│  "What's my VWRL  │  "Last week they     │  "Age: 40         │
│   price?"          │   asked about        │   Risk: moderate  │
│  "Analyse my       │   rebalancing"       │   Tax: higher     │
│   portfolio"       │  "They worried about │   Prefers ESG     │
│                     │   tech in March"    │   Knows basic     │
│                     │                       │   investing"     │
│                     │                       │                   │
│  ─── lost when     │  ─── stored in       │  ─── stored in    │
│  session ends      │  SQLite/Postgres     │  profile table    │
│                     │  (raw messages)      │  (structured)     │
└─────────────────────────────────────────────────────────────┘
```

### How the current chatbot uses memory

```python
# Current code — BASIC persistence only
self.conversation_history = []  # Working memory: only current session

# On each message:
self.conversation_history.append(user_msg)
self.memory.add_message(self.session_id, user_msg)  # Save to SQLite

# On next session:
saved = self.memory.get_conversation(self.session_id)
self.conversation_history = saved  # Restore from SQLite
```

**What it does:** Saves and restores raw chat messages. That's it.

**What it does NOT do:**
| Missing capability | Why it matters |
|--------------------|----------------|
| Extract facts from conversations | Never learns "user mentioned they're 40" |
| Build a user profile over time | Static — doesn't get smarter with use |
| Retrieve relevant past advice | Can't connect "this is like what we discussed in March" |
| Summarise old conversations | Context window grows unbounded until it breaks |
| Learn preferences | "user always asks about fees first" — never noticed |

### How a memory-augmented version works

```
                  USER MESSAGE
                       │
                       ▼
            ┌─────────────────────┐
            │  WORKING MEMORY     │  ← Current conversation
            │  (last N messages) │
            └────────┬────────────┘
                     │
            ┌────────▼────────────┐
            │  REASONING LOOP     │  ← Think → act → observe → repeat
            │  (with ReAct)       │
            └────────┬────────────┘
                     │
       ┌─────────────┼─────────────┐
       │             │             │
       ▼             ▼             ▼
┌──────────┐ ┌──────────────┐ ┌──────────┐
│ EPISODIC  │ │  SEMANTIC    │ │  TOOLS   │
│ MEMORY   │ │  MEMORY      │ │  (API)   │
│           │ │              │ │          │
│ SQLite/   │ │  Profile     │ │ yfinance │
│ Postgres  │ │  table       │ │ portfolio│
│           │ │              │ │ holdings │
│ Past      │ │ Age, risk,   │ │          │
│ messages  │ │ tax band,    │ │          │
│ per       │ │ preferences  │ │          │
│ session   │ │ (learned)    │ │          │
└──────────┘ └──────────────┘ └──────────┘
```

### Code sketch — memory-augmented `chat()`

```python
def chat(self, user_message: str) -> str:
    # ── 1. RETRIEVE relevant memory ─────────────────────
    # Instead of full history, build context from:
    #   a) User profile (semantic memory)
    #   b) Summary of past conversations (episodic memory)
    #   c) Recent N messages (working memory)

    profile = self.memory.get_profile(self.user_id)
    summary = self.memory.get_session_summary(self.user_id)
    recent = self.conversation_history[-10:]

    context = self._build_augmented_context(profile, summary, recent)

    # ── 2. RUN ReAct LOOP ───────────────────────────────
    for iteration in range(MAX_ITERATIONS):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=context,
            tools=self.tools,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            # Done — extract and store what we learned
            self._extract_and_store_facts(msg.content)
            return msg.content

        # Execute tools and continue loop
        ...

    # ── 3. EXTRACT & STORE (write to memory) ─────────────
    def _extract_and_store_facts(self, response: str):
        """After each chat, extract user facts for long-term memory."""
        facts = self._extract_preferences(response)
        # facts = {"concern": "tech concentration",
        #          "mentioned_goal": "retire in 15 years"}
        self.memory.update_profile(self.user_id, facts)

    def _build_augmented_context(self, profile, summary, recent):
        """Inject all memory layers into the LLM context."""
        messages = [
            {"role": "system", "content": self._system_prompt()},
        ]
        if profile:
            messages.append({
                "role": "system",
                "content": f"## About this user:\n{json.dumps(profile)}"
            })
        if summary:
            messages.append({
                "role": "system",
                "content": f"## Earlier conversation summary:\n{summary}"
            })
        messages.extend(recent)
        return messages
```

### Concrete example across visits

```python
FIRST VISIT:
  User: "I'm 40, moderate risk, worried about tech stocks"
  Agent: *responds normally*
  After: Stores {age: 40, risk: moderate, concerns: ["tech"]} in profile

SECOND VISIT (next day):
  User: "Is my portfolio okay?"
  Context injected: "About this user: 40, moderate risk, worried about tech"
  Agent: "I see you were concerned about tech yesterday. Your current
          portfolio has 30% tech — within moderate risk guidelines."
  → Remembers WITHOUT the user repeating themselves

THIRD VISIT (a month later):
  User: "I'm thinking of increasing my pension contributions"
  Context: same profile + conversation summary
  Agent: "We've discussed your tech exposure before. Since you're
          moderate risk at 40, increasing pension makes sense..."
  → Coherent long-term relationship, not starting from scratch
```

### Summary — current vs memory augmented

| Concept | Current chatbot | Memory augmented |
|---------|----------------|------------------|
| Working memory | ✅ Full chat history | ✅ Recent N messages only |
| Episodic memory | ❌ Raw SQLite dump | ✅ Summarised past sessions |
| Semantic memory | ❌ Static portfolio context | ✅ Learned profile (age, goals, concerns) |
| Self-improving | ❌ Never learns | ✅ Extracts facts after each chat |
| Context window | ❌ Grows unbounded | ✅ Managed — summary + recent only |

**The key insight:** Memory augmentation is what makes the chatbot feel like
it **knows you** over time, rather than treating every conversation as a fresh
start. The v2 profile table we built is the **semantic memory** layer — we
just need to add the extraction and injection logic to make it come alive.

---

## 3. How to Make It Truly Agentic

### Change 1: Add a reasoning loop

The single biggest change. Instead of two LLM calls per message, loop until
the model signals completion:

```python
def chat(self, user_message: str) -> str:
    self.conversation_history.append({"role": "user", "content": user_message})

    MAX_ITERATIONS = 10  # Safety limit to prevent infinite loops

    for iteration in range(MAX_ITERATIONS):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                *self.conversation_history
            ],
            tools=self.tools,
            tool_choice="auto",
        )

        msg = response.choices[0].message

        # ── LLM signals completion: no tool calls ──────────
        if not msg.tool_calls:
            self.conversation_history.append({
                "role": "assistant", "content": msg.content
            })
            self.memory.add_message(self.session_id, "assistant", msg.content)
            return msg.content

        # ── LLM wants more data — execute and continue ─────
        # Store the assistant's reasoning + tool calls
        self.conversation_history.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": msg.tool_calls,
        })
        self.memory.add_message(...)

        for tool_call in msg.tool_calls:
            result = self._execute_tool(tool_call)
            self.conversation_history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })
            self.memory.add_message(...)

        # Loop continues — LLM sees tool results and decides
        # whether it needs more data or can answer now

    # Safety: break out if max iterations hit
    return "I need more information to fully answer that. Could you be more specific?"
```

### Change 2: Add agentic instructions to the system prompt

The prompt needs a **scratchpad** section. Currently prompts just describe the
persona — they don't tell the model *how* to reason:

```markdown
# Current prompt (describes WHO you are)
You are a financial advisor. Help users with their investments.
Be conservative and risk-aware.

# Agentic prompt (describes HOW you think)
You are a financial advisor with access to market data tools.

## Your reasoning process
For every request, follow these steps:

1. **THINK** — What does the user actually need?
   - What data do I already have?
   - What's missing?
   - Which tools can fill the gaps?

2. **PLAN** — What sequence of tool calls will get the answer?
   - Group independent calls together (they run in parallel)
   - Order dependent calls sequentially

3. **ACT** — Execute your planned tool calls
   - Call multiple tools in one response when possible

4. **OBSERVE** — What did the tools return?
   - Does the data make sense?
   - Is anything unexpected?

5. **REPEAT or ANSWER**
   - If you have enough information → provide your final answer
   - If not → return to step 1 with what you now know

## Guidelines
- You can make multiple tool calls in a single turn
- If a tool fails, explain the limitation to the user
- Do NOT guess data — call the right tool
- Signal completion by returning a response with no tool_calls
```

### Change 3: Enable multi-tool chaining

A true agent chains tools naturally. Example:

```
User: "Is my portfolio too concentrated in tech?"

  Iteration 1:
    THINK:  "I need portfolio holdings first"
    ACT:    get_user_data()
    OBSERVES: {holdings: [VWRL(global), VUAG(US tech), ...]}

  Iteration 2:
    THINK:  "VUAG is US large-cap — need to check sector exposure"
    ACT:    analyze_ticker("VUAG")
    OBSERVES: {sector: "technology", weight: 40%}

  Iteration 3:
    THINK:  "40% tech is concentrated. Let me check the others too"
    ACT:    analyze_ticker("VWRL"), analyze_ticker("VUSA")
    OBSERVES: {sector: "diversified"}, {sector: "technology"}

  Iteration 4:
    THINK:  "Combined tech exposure is ~55% — that's concentrated"
    ACT:    (none — has enough to answer)

  FINAL:   "Your portfolio has ~55% tech exposure..."
```

### Change 4: Implement memory augmentation

This is the full memory augmentation pattern described in
[Section 2b](#2b-what-memory-augmented-means). In short:

- Add a **`_extract_and_store_facts()`** method that runs after each chat
  to pull user preferences, concerns, and goals from the conversation
- Add a **`_build_augmented_context()`** method that injects profile data
  + past conversation summaries alongside the system prompt
- Store extracted facts in the v2 profile table (add a `preferences` JSONB
  column for unstructured learned data)

### Change 5: History management (context window)

The current implementation sends the **entire** conversation history every
time. A production agent needs:

```python
def _build_context(self) -> list[dict]:
    """Smart context builder — keeps relevant messages, drops noise."""
    messages = []

    # Always include system prompt
    messages.append({"role": "system", "content": self._system_prompt()})

    # Include learned user preferences
    if self.user_memory:
        messages.append({
            "role": "system",
            "content": f"## What you know about this user:\n{self.user_memory}"
        })

    # Include recent conversation (last N turns)
    messages.extend(self.conversation_history[-20:])

    # Include a summary of older conversations
    if len(self.conversation_history) > 20:
        messages.insert(1, {
            "role": "system",
            "content": f"## Summary of earlier conversation:\n{self.summary}"
        })

    return messages
```

---

## 3b. How Memory Augmentation Saves Token Cost

This is one of the main practical benefits — keeping the context window small.

### Token comparison: before vs after

| Scenario | Turns | Full history (current) | Memory augmented | Saving |
|----------|-------|----------------------|-----------------|--------|
| Quick chat | 5 | ~1,500 tokens | ~1,500 tokens | 0% |
| Active session | 20 | ~6,000 tokens | ~2,000 tokens | **67%** |
| Long session | 50 | ~15,000 tokens | ~2,000 tokens | **87%** |
| Power user (daily) | 200 | ~60,000 tokens | ~2,000 tokens | **97%** |

### Why the savings work

The LLM doesn't need the exact wording of every past message. It only needs:

```python
# Expensive: sends every word of every message every time
*self.conversation_history  # 15,000 tokens at turn 50

# Efficient: sends only what matters
context = [
    system_prompt + scratchpad,          # ~600 tokens
    user_profile + learned_facts,        # ~150 tokens  (semantic)
    past_conversation_summary,           # ~200 tokens  (episodic)
    last_10_messages_raw,                # ~3,000 tokens (working)
    new_user_message,                    # ~100 tokens
]
# Total: ~4,050 tokens — stays flat regardless of session length
```

**The context stays the same size whether the user has exchanged 10 messages
or 200.** That's where the cost saving comes from.

---

## 3c. Implementation Design — Modifying `chatBot_dpsk.py`

This section describes the exact code changes needed to make the original
chatbot at `C:\SourceCode\wealthwise\chatBot_dpsk.py` memory-augmented.

### Files changed

| File | Change |
|------|--------|
| `memory_manager.py` | Add `user_memory` table + 4 new abstract methods + SQLite implementation |
| `chatBot_dpsk.py` | Add `user_id`, `_build_context()`, `_extract_and_store_facts()`, `_summarize_if_needed()` |

### Step 1 — New database table

Add to `SQLiteMemoryManager._init_db()` in `memory_manager.py`:

```sql
CREATE TABLE IF NOT EXISTS user_memory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    key         TEXT NOT NULL,    -- e.g. "concerns", "goals", "preferences"
    value       TEXT NOT NULL,    -- e.g. "tech_concentration"
    confidence  REAL DEFAULT 1.0, -- how sure we are (0-1)
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
    UNIQUE(user_id, key, value)
);
```

Also add a `summary` TEXT column to the existing `conversations` table.

### Step 2 — New abstract methods on `MemoryManager`

```python
@abstractmethod
def get_user_memory(self, user_id: str) -> list[dict]:
    """Return all stored facts about a user."""

@abstractmethod
def upsert_user_memory(self, user_id: str, key: str, value: str) -> None:
    """Store or update a fact about the user."""

@abstractmethod
def get_conversation_summary(self, session_id: str) -> str | None:
    """Return a previously stored summary of this conversation."""

@abstractmethod
def save_conversation_summary(self, session_id: str, summary: str) -> None:
    """Store a summary of this conversation."""
```

### Step 3 — Modify `ChatBot_Dpsk.__init__`

```python
def __init__(self, ..., user_id: str | None = None):
    self.user_id = user_id or session_id  # Default: session IS the user
    # Load stored memory on init
    self.user_memory = self.memory.get_user_memory(self.user_id)
```

### Step 4 — Add `_build_augmented_context()`

This replaces `*self.conversation_history` in the LLM call. Instead of
dumping every message, it builds three memory layers:

```python
def _build_context(self) -> list[dict]:
    """Build LLM context from three memory layers instead of full history."""
    messages = [{"role": "system", "content": self._system_prompt()}]

    # ── Layer 1: Semantic memory (learned facts about user) ──
    if self.user_memory:
        messages.append({
            "role": "system",
            "content": f"## What you know about this user:\n{json.dumps(self.user_memory, indent=2)}"
        })

    # ── Layer 2: Episodic memory (past conversation summary) ──
    summary = self.memory.get_conversation_summary(self.session_id)
    if summary:
        messages.append({
            "role": "system",
            "content": f"## Earlier conversation summary:\n{summary}"
        })

    # ── Layer 3: Working memory (last 10 messages only) ──
    recent = self.conversation_history[-10:]
    messages.extend(recent)

    return messages
```

### Step 5 — Add `_extract_and_store_facts()`

Runs after each chat to pull facts from the exchange using a cheap LLM call:

```python
def _extract_and_store_facts(self, user_message: str, response: str):
    """Use a small LLM call to extract facts from this exchange."""

    extract_prompt = f"""
    From this conversation exchange, extract facts about the user.
    Return a JSON object with keys like: concerns, goals, preferences, knowledge_level.

    User: {user_message}
    Assistant: {response}

    Return ONLY a JSON object with extracted facts, or {{}} if nothing to learn.
    """

    extraction = self.client.chat.completions.create(
        model="deepseek-chat",  # cheaper model for extraction
        messages=[{"role": "user", "content": extract_prompt}],
        response_format={"type": "json_object"},
    )

    try:
        facts = json.loads(extraction.choices[0].message.content)
        for key, values in facts.items():
            if isinstance(values, list):
                for v in values:
                    self.memory.upsert_user_memory(self.user_id, key, str(v))
            else:
                self.memory.upsert_user_memory(self.user_id, key, str(values))
    except (json.JSONDecodeError, AttributeError):
        pass  # extraction failed silently — no harm done
```

### Step 6 — Modify `chat()` to use augmented context

**Important:** Memory retrieval happens **once at session start**, not every
iteration of the ReAct loop. The loop itself is pure in-memory — no DB reads
between iterations.

```
SESSION START ──► 1 DB read (profile + summary)
                    │
                    ▼
              ┌── ReAct LOOP ──────────────────┐
              │  Iteration 1: LLM → tools      │
              │  Iteration 2: LLM → more tools │  ← No DB reads
              │  Iteration 3: LLM → answer     │
              └────────────────────────────────┘
                    │
                    ▼
SESSION END   ──► 1 DB write (extract facts)
```

Total per user message: **2 DB calls** regardless of how many iterations
the ReAct loop runs.

```python
def chat(self, user_message: str) -> str:
    self.conversation_history.append({"role": "user", "content": user_message})
    self.memory.add_message(self.session_id, "user", user_message)

    # ── Use augmented context instead of full history ──
    response = self.client.chat.completions.create(
        model=self.model,
        messages=self._build_context(),  # ← THE key change
        tools=self.tools,
        tool_choice="auto"
    )

    assistant_message = response.choices[0].message

    if assistant_message.tool_calls:
        return self._handle_function_calls(assistant_message)

    response_text = assistant_message.content or ""
    self.conversation_history.append({
        "role": "assistant", "content": response_text
    })
    self.memory.add_message(self.session_id, "assistant", response_text)

    # ── Extract facts in background (fire and forget) ──
    import threading
    threading.Thread(
        target=self._extract_and_store_facts,
        args=(user_message, response_text)
    ).start()

    return response_text
```

### Step 7 — Periodic conversation summarisation

```python
def _summarize_if_needed(self):
    """When conversation gets long, summarise older messages to save context."""
    if len(self.conversation_history) < 20:
        return  # Not long enough to summarise

    older = self.conversation_history[:-5]
    recent = self.conversation_history[-5:]

    summary_prompt = f"""
    Summarise this financial conversation in 3-5 sentences.
    Focus on: user questions, advice given, decisions made.

    {json.dumps(older, indent=2)}

    Summary:
    """

    summary = self.client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": summary_prompt}],
    ).choices[0].message.content

    # Store summary, drop old messages from working memory
    self.memory.save_conversation_summary(self.session_id, summary)
    self.conversation_history = recent  # Keep only recent 5
```

Call `_summarize_if_needed()` at the end of each `chat()` turn.

---

## 3d. Production-Grade Agentic Memory — Future Reference

> **Note:** This section describes what enterprise/production systems do
> differently. It's here for when **scalability and maintainability** become
> priorities — for a personal tool, the design in Section 3c is sufficient.

### What production systems do differently

#### 1. Retrieval-Augmented Generation (RAG) instead of key-value

Our design stores facts as flat `(key, value)` pairs. Production systems use
**vector embeddings** to search across past conversations by meaning:

```python
# Our approach — key-value lookup
if key == "concerns":
    return ["tech_concentration"]

# Production approach — semantic search
query = "What does this user worry about?"
results = vector_db.similarity_search(query, k=5)
# Returns: "user mentioned tech risk in March",
#          "user asked about volatility in Jan"
```

This lets the agent find relevant memories without knowing the exact key.

#### 2. Importance-scored memory (not all facts are equal)

Production systems score memories to avoid wasting context on trivia:

```python
memory.score = importance * recency / (1 + retrieval_count)
# importance: 1-10 how significant
# recency: how recently mentioned
# retrieval_count: how often surfaced already
```

Low-scoring memories get archived. High-scoring ones stay in context.

#### 3. Agent frameworks (LangGraph, CrewAI) instead of raw loops

Production agents use state machines, not raw `for` loops:

```python
graph = StateGraph(AgentState)
graph.add_node("retrieve_memory", load_profile_and_history)
graph.add_node("reason", call_llm)
graph.add_node("execute_tools", run_tool_calls)
graph.add_node("reflect", extract_facts_from_response)
graph.add_conditional_edges(
    "reason", has_tool_calls,
    {True: "execute_tools", False: "store_memory"}
)
```

Benefits: observability, error recovery, parallel execution, persistence.

#### 4. Multi-modal memory stores

| Data type | Store | Why |
|-----------|-------|-----|
| Current conversation | In-memory | Fast, lost on restart |
| User preferences | PostgreSQL / SQLite | Structured, queryable |
| Past conversations | Vector DB (Pinecone, Qdrant) | Semantic search |
| Long-term summaries | LLM-generated + stored | Compression |
| Chat session logs | S3 / Cloud Storage | Audit, debugging |

#### 5. Consolidation jobs (nightly)

A background process runs daily to:
1. Review all conversations from the day
2. Extract important facts
3. Merge duplicates
4. Drop low-importance facts
5. Update user profile with consolidated view

Prevents memory bloat over months of use.

### When to revisit this

| Trigger | Action |
|---------|--------|
| Memory table grows beyond 10,000 rows per user | Add vector search |
| Context quality degrades over weeks | Add importance scoring |
| Need observability into agent decisions | Switch to LangGraph |
| Multiple users with shared data | Add multi-tenant memory isolation |
| Compliance requirements (GDPR, audits) | Add S3 logging + data retention policies |

---

## 4. What This Changes in the v2 Architecture

The v2 backend already has most of the data infrastructure an agent needs:

| v2 Service | How an agent would use it |
|------------|--------------------------|
| `GET /api/v1/portfolio/holdings` | "What do I own?" |
| `GET /api/v1/portfolio/summary` | "What's my total position?" |
| `GET /api/v1/portfolio/allocations` | "How am I diversified?" |
| `GET /api/v1/ticker/{symbol}` | "What's the current price?" |
| `Profile table` | "What do I know about this user?" |

The new chat endpoint would look like:

```
POST /api/v1/chat

Request:  {"message": "How risky is my portfolio?"}
Response: {"response": "Your portfolio is 70% equities...",
           "tool_calls": [...],
           "iterations": 3}

It internally:
  1. Fetches profile + holdings from PostgreSQL
  2. Injects them as context
  3. Runs the ReAct loop (up to N iterations)
  4. Returns the final answer + metadata
```

---

## 5. Summary — Upgrade Path

| Priority | Change | Effort | Impact |
|----------|--------|--------|--------|
| P0 | Add reasoning loop (iterate until no tool_calls) | 1 day | Biggest impact — enables chaining |
| P1 | Update system prompts with scratchpad instructions | 0.5 day | Guides LLM to plan and reflect |
| P2 | Add context window management (summary/trim) | 1 day | Prevents token limit issues |
| P3 | Long-term user memory (preferences from chat) | 2 days | Personalises over time |
| P4 | Build v2 chat endpoint with full ReAct support | 3 days | Production-ready agent API |

### Quick win

The fastest path to a true agent is **Change 1** (reasoning loop) combined with
**Change 2** (scratchpad prompt). These two changes alone would let the chatbot:

- Chain multiple tool calls (look up portfolio → analyse tickers → compare)
- Iterate when data is incomplete
- Self-correct based on tool results

Without adding a single new tool or database table.
