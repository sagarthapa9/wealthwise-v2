import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * ChatPanel — AI chat interface for portfolio analysis.
 *
 * States:
 *  - Empty: No messages yet, shows placeholder prompt
 *  - Loading: Waiting for LLM response
 *  - Messages: List of user + assistant bubbles
 *  - Reasoning: Collapsible "💭 AI Thinking" section
 *  - Error: API error state
 *
 * Props:
 *  - sessionId: string | null — current chat session
 *  - onSessionChange: (sessionId) => void — called when a new session is created
 *  - initialMessage: string | null — if set, auto-sends this message on mount
 */
function ChatPanel({ sessionId, onSessionChange, initialMessage, filterAutoMessages }) {
  const [showInfoTip, setShowInfoTip] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedReasoning, setExpandedReasoning] = useState(null);
  const [currentSessionId, setCurrentSessionId] = useState(sessionId || null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const initialSent = useRef(false);

  // Always scroll chat container to bottom when messages change
  useEffect(() => {
    const container = document.querySelector('.chat-messages');
    if (container) {
      setTimeout(() => { container.scrollTop = container.scrollHeight; }, 50);
    }
  }, [messages]);

  // Sync sessionId from parent
  useEffect(() => {
    if (sessionId && sessionId !== currentSessionId) {
      setCurrentSessionId(sessionId);
      loadHistory(sessionId);
    }
  }, [sessionId]);

  // Auto-send initial message (e.g. from "Analyze Portfolio" button)
  useEffect(() => {
    if (initialMessage && !initialSent.current) {
      initialSent.current = true;
      sendMessage(initialMessage);
    }
  }, [initialMessage]);

  async function loadHistory(sid) {
    try {
      const res = await fetch(`/api/v1/chat/${sid}/messages`);
      if (res.ok) {
        const data = await res.json();
        const msgs = data.messages || [];
        // Filter out auto-generated analysis messages and their responses
        if (filterAutoMessages && filterAutoMessages.length > 0) {
          const filtered = [];
          let skipNext = false;
          for (const m of msgs) {
            if (m.role === 'user' && filterAutoMessages.some(p => m.content?.startsWith(p))) {
              skipNext = true;  // skip this user message and the next assistant response
              continue;
            }
            if (skipNext && m.role === 'assistant') {
              skipNext = false;
              continue;
            }
            skipNext = false;
            filtered.push(m);
          }
          setMessages(filtered);
        } else {
          setMessages(msgs);
        }
        // Scroll to the latest message after history loads
        setTimeout(() => {
          messagesEndRef.current?.scrollIntoView({ behavior: 'instant' });
        }, 100);
      }
    } catch {
      // best-effort — if history can't load, start fresh
    }
  }

  async function sendMessage(text) {
    const msg = text || input;
    if (!msg.trim() || loading) return;

    // Optimistically add user message to UI
    const userMsg = { role: 'user', content: msg };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: msg,
          session_id: currentSessionId,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Chat request failed');
      }

      const data = await res.json();

      // Update session ID if new
      if (data.session_id && data.session_id !== currentSessionId) {
        setCurrentSessionId(data.session_id);
        if (onSessionChange) onSessionChange(data.session_id);
      }

      // Add assistant message
      const assistantMsg = {
        role: 'assistant',
        content: data.message,
        reasoning_content: data.reasoning_content,
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      setError(err.message);
      // Remove the optimistically added user message on failure
      setMessages(prev => prev.filter(m => m !== userMsg));
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function toggleReasoning(index) {
    setExpandedReasoning(expandedReasoning === index ? null : index);
  }

  async function handleClear() {
    if (!currentSessionId || !confirm('Clear this conversation? It will be archived as a summary.')) return;
    try {
      const res = await fetch(`/api/v1/chat/${currentSessionId}/clear`, { method: 'POST' });
      if (res.ok) {
        setMessages([]);
      }
    } catch {
      // best-effort
    }
  }

  return (
    <div className="chat-panel">
      {/* ── Header ── */}
      <div className="chat-header">
        <span className="chat-badge">
          <svg className="chat-badge-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z"/>
          </svg>
          AI
        </span>
        <h3 className="chat-title">Explore Your Portfolio</h3>
        <div className="chat-info-wrap">
          <div className="chat-info-trigger">
            <svg className="chat-info-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 16v-4"/>
              <path d="M12 8h.01"/>
            </svg>
            <div className="chat-info-tip">
              <strong>Personalised to your portfolio</strong>
              <p>Responses are tailored using your holdings, accounts, and investor profile. Every answer references your actual numbers — no generic advice.</p>
              <p>Ask about diversification, costs, tax efficiency, or any holding in your portfolio.</p>
            </div>
          </div>
        </div>
        {messages.length > 0 && (
          <button className="chat-clear-btn" onClick={handleClear} title="Clear conversation">Clear messages</button>
        )}
      </div>

      {/* ── Messages ── */}
      <div className="chat-messages">
        {messages.length === 0 && !loading && (
          <div className="chat-empty">
            <div className="chat-empty-icon">💬</div>
            <p className="chat-empty-text">
              Ask a follow-up about your portfolio
            </p>
            <p className="chat-empty-hint">
              Try: "How can I reduce my costs?" • "Am I diversified enough?" • "What's my tax efficiency?"
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`chat-bubble ${msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'}`}
          >
            {msg.role === 'assistant' && msg.reasoning_content && (
              <div className="chat-reasoning">
                <button
                  className="chat-reasoning-toggle"
                  onClick={() => toggleReasoning(i)}
                >
                  💭 AI Thinking {expandedReasoning === i ? '▾' : '▸'}
                </button>
                {expandedReasoning === i && (
                  <div className="chat-reasoning-content">
                    {msg.reasoning_content}
                  </div>
                )}
              </div>
            )}
            <div className="chat-bubble-content">
              {msg.role === 'assistant' ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    table({ children }) {
                      return (
                        <div className="md-table-wrap">
                          <table className="md-table">{children}</table>
                        </div>
                      );
                    },
                    th({ children }) {
                      return <th className="md-th">{children}</th>;
                    },
                    td({ children }) {
                      return <td className="md-td">{children}</td>;
                    },
                    code({ className, children, ...props }) {
                      const isInline = !className;
                      return isInline
                        ? <code className="md-code-inline">{children}</code>
                        : <pre className="md-code-block"><code>{children}</code></pre>;
                    },
                    strong({ children }) {
                      return <strong className="md-strong">{children}</strong>;
                    },
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="chat-bubble chat-bubble-assistant">
            <div className="chat-loading">
              <span className="chat-loading-dot">.</span>
              <span className="chat-loading-dot">.</span>
              <span className="chat-loading-dot">.</span>
            </div>
          </div>
        )}

        {error && (
          <div className="chat-error">
            <span className="chat-error-icon">⚠️</span>
            {error}
            <button className="chat-error-retry" onClick={() => setError(null)}>
              Dismiss
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Input ── */}
      <div className="chat-input-row">
        <input
          ref={inputRef}
          className="chat-input"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your portfolio..."
          disabled={loading}
        />
        <button
          className="chat-send-btn"
          onClick={() => sendMessage()}
          disabled={loading || !input.trim()}
        >
          {loading ? '⋯' : 'Send'}
        </button>
      </div>
    </div>
  );
}

export default ChatPanel;
