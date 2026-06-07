import { useState, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import PortfolioTable from './components/PortfolioTable';
import TickerSearch from './components/TickerSearch';
import AllocationSection from './components/AllocationSection';
import SettingsModal from './components/SettingsModal';
import ProfilePanel from './components/ProfilePanel';
import ChatPanel from './components/ChatPanel';

function App() {
  const [holdings, setHoldings] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currency, setCurrency] = useState('GBP');
  const [showSettings, setShowSettings] = useState(false);
  const [profileRefreshKey, setProfileRefreshKey] = useState(0);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [chatSessionId, setChatSessionId] = useState(null);
  const [chatInitialMessage, setChatInitialMessage] = useState(null);
  const [aiAnalysis, setAiAnalysis] = useState(null);          // hero card response
  const [aiLoading, setAiLoading] = useState(false);           // hero card loading
  const [showFullAnalysis, setShowFullAnalysis] = useState(false);

  const loadHoldings = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/portfolio/holdings');
      if (res.ok) {
        const data = await res.json();
        setHoldings(data);
        await fetchSummary();
      }
    } catch {
      // handled by empty state
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchSummary = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/portfolio/summary');
      if (res.ok) {
        setSummary(await res.json());
      }
    } catch {
      // best-effort
    }
  }, []);

  useEffect(() => {
    loadHoldings();
  }, [loadHoldings]);

  /** Add a holding (called by TickerSearch after user confirms) */
  async function handleAddHolding(holding) {
    try {
      const res = await fetch('/api/v1/portfolio/holdings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: holding.ticker.trim().toUpperCase(),
          name: holding.name,
          quantity: holding.quantity || 0,
          cost_basis_per_share: holding.cost_basis_per_share || 0,
          current_price: holding.current_price || 0,
          // Classification fields (auto-populated from ticker lookup)
          type: holding.type || null,
          asset_class: holding.asset_class || null,
          sector: holding.sector || null,
          geography: holding.geography || null,
          currency: holding.currency || null,
          ocf_pct: holding.ocf_pct || null,
          dividend_yield_pct: holding.dividend_yield_pct || null,
          isin: holding.isin || null,
        }),
      });
      if (!res.ok) throw new Error('Save failed');
      await loadHoldings();
    } catch (err) {
      alert('Failed to add holding: ' + err.message);
    }
  }

  /** Delete a holding */
  async function handleDelete(id) {
    if (!confirm('Remove this holding?')) return;
    try {
      await fetch(`/api/v1/portfolio/holdings/${id}`, { method: 'DELETE' });
      await loadHoldings();
    } catch (err) {
      alert('Failed to delete: ' + err.message);
    }
  }

  /** Extract health grade from LLM response text — looks for patterns like "Health Grade: C" or "Grade: B+" */
  function extractGrade(text) {
    const match = text.match(/(?:Health\s*)?[Gg]rade\s*[:：]\s*([A-E][+-]?)/);
    return match ? match[1] : '—';
  }

  /** Show first N lines of text as a preview */
  function truncateText(text, lines) {
    const parts = text.split('\n');
    const preview = parts.slice(0, lines).join('\n');
    return parts.length > lines ? preview + '\n\n*…*' : preview;
  }

  /** Send an insight question to the chat panel */
  function handleAsk(question) {
    setChatInitialMessage(question);
  }

  const ANALYSIS_PROMPT = "Here is an analysis of the portfolio, providing a brief summary of its total value, overall health grade, and the most important issue that needs to be addressed.";

  /** Analyze Portfolio button — shows charts + fetches AI analysis hero card */
  async function handleAnalyze() {
    setShowAnalysis(true);

    // Don't re-fetch if we already have analysis data
    if (aiAnalysis) return;

    setAiLoading(true);
    try {
      const res = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: ANALYSIS_PROMPT,
          // No session_id — hero card uses its own orphan session
          // so it doesn't pollute the chat panel's conversation history
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setAiAnalysis({
          message: data.message,
          reasoning_content: data.reasoning_content,
        });
        // Don't set chatSessionId from hero card — keep chat panel independent
      }
    } catch {
      // ChatPanel will show the error state for follow-ups; hero card just
      // doesn't appear — user can type in the chat manually.
    } finally {
      setAiLoading(false);
    }
  }

  return (
    <div className="app">
      <div className="main-layout">
      {/* ── Profile Sidebar ───────────────────── */}
      <ProfilePanel
        refreshKey={profileRefreshKey}
        onOpenSettings={() => setShowSettings(true)}
      />

      {/* ── Portfolio Card ──────────────────── */}
      <div className="portfolio-card">
        {/* ── Header ─────────────────────────────── */}
        <div className="portfolio-header">
          <h2>Portfolio</h2>
          <button
            className="btn-settings"
            onClick={() => setShowSettings(true)}
            title="Settings"
          >
            ⚙️
          </button>
        </div>

        {/* ── Ticker Entry Row ────────────────────── */}
        <TickerSearch onAdd={handleAddHolding} />

        {/* ── Divider: "or import CSV" ────────────── */}
        <div className="entry-divider">
          <span className="divider-line"></span>
          <span className="divider-text">or import from CSV</span>
          <span className="divider-line"></span>
        </div>

        {/* ── Import CSV ──────────────────────────── */}
        <button className="btn-import-csv">
          <span className="btn-icon">📥</span>
          Import CSV File
        </button>

        {/* ── Portfolio Table ──────────────────────── */}
        <PortfolioTable
          holdings={holdings}
          loading={loading}
          onDelete={handleDelete}
        />

        {/* ── Action Bar ──────────────────────────── */}
        <div className="action-bar">
          <div className="action-bar-left"></div>
          <div className="action-bar-right">
            <select
              className="currency-select"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
            >
              <option value="GBP">£ GBP</option>
              <option value="USD">$ USD</option>
              <option value="EUR">€ EUR</option>
            </select>

            <button
              className="btn-analyze"
              disabled={holdings.length === 0}
              onClick={handleAnalyze}
            >
              Analyze Portfolio
            </button>
          </div>
        </div>

        {/* ── Analysis Section (after clicking Analyze) ──── */}
        {showAnalysis && (
          <>
            {/* Summary Metrics */}
            {summary && summary.holding_count > 0 && (
              <div className="summary-strip">
                <div className="summary-item">
                  <span className="summary-label">Holdings</span>
                  <span className="summary-value">{summary.holding_count}</span>
                </div>
                <div className="summary-item">
                  <span className="summary-label">Total Cost</span>
                  <span className="summary-value">
                    £{summary.total_cost.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="summary-item">
                  <span className="summary-label">Current Value</span>
                  <span className="summary-value">
                    £{summary.total_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className={`summary-item ${summary.total_gain_loss >= 0 ? 'positive' : 'negative'}`}>
                  <span className="summary-label">Gain / Loss</span>
                  <span className="summary-value">
                    {summary.total_gain_loss >= 0 ? '+' : ''}
                    £{summary.total_gain_loss.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    ({summary.total_gain_loss >= 0 ? '+' : ''}
                    {summary.total_gain_loss_pct.toFixed(1)}%)
                  </span>
                </div>
              </div>
            )}

            {/* ── Loading Skeleton ──────────────────── */}
            {aiLoading && (
              <div className="ai-hero ai-hero-loading">
                <div className="ai-hero-header">
                  <span className="ai-hero-icon">✨</span>
                  <span className="ai-hero-title">Analysing your portfolio...</span>
                </div>
                <div className="ai-skeleton-row">
                  <div className="ai-skeleton-card" />
                  <div className="ai-skeleton-card" />
                  <div className="ai-skeleton-card" />
                </div>
                <div className="ai-skeleton-line" />
                <div className="ai-skeleton-line" style={{ width: '70%' }} />
                <div className="ai-skeleton-line" style={{ width: '85%' }} />
              </div>
            )}

            {/* ── AI Portfolio Analysis Hero Card ────── */}
            {aiAnalysis && (
              <div className="ai-hero">
                <div className="ai-hero-header">
                  <span className="ai-hero-icon">✨</span>
                  <span className="ai-hero-title">AI Portfolio Analysis</span>
                </div>

                {/* Stat cards — key metrics at a glance */}
                <div className="ai-stat-row">
                  <div className="ai-stat-card">
                    <span className="ai-stat-value">
                      £{summary ? summary.total_value.toLocaleString(undefined, { minimumFractionDigits: 0 }) : '—'}
                    </span>
                    <span className="ai-stat-label">Portfolio Value</span>
                  </div>
                  <div className="ai-stat-card">
                    <span className="ai-stat-value ai-stat-grade">
                      {extractGrade(aiAnalysis.message)}
                    </span>
                    <span className="ai-stat-label">Health Grade</span>
                  </div>
                  <div className="ai-stat-card">
                    <span className="ai-stat-value">
                      {summary ? summary.holding_count : '—'}
                    </span>
                    <span className="ai-stat-label">Holdings</span>
                  </div>
                </div>

                {/* Preview text + Read more */}
                <div className="ai-hero-collapse">
                  {showFullAnalysis ? (
                    <>
                      <div className="ai-hero-body">
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
                          {aiAnalysis.message}
                        </ReactMarkdown>
                      </div>
                      <button
                        className="ai-hero-more-btn"
                        onClick={() => setShowFullAnalysis(false)}
                      >
                        Show less ▴
                      </button>
                    </>
                  ) : (
                    <>
                      <div className="ai-hero-body ai-hero-preview">
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
                          {truncateText(aiAnalysis.message, 10)}
                        </ReactMarkdown>
                      </div>
                      <button
                        className="ai-hero-more-btn"
                        onClick={() => setShowFullAnalysis(true)}
                      >
                        Read more ▾
                      </button>
                    </>
                  )}
                </div>

                {/* Reasoning toggle */}
                {aiAnalysis.reasoning_content && (
                  <details className="ai-hero-reasoning">
                    <summary className="ai-hero-reasoning-summary">💭 AI Thinking</summary>
                    <div className="ai-hero-reasoning-content">{aiAnalysis.reasoning_content}</div>
                  </details>
                )}
              </div>
            )}
            {/* Allocation Breakdown */}
            <AllocationSection
              hasHoldings={holdings.length > 0}
              onAsk={handleAsk}
            />
          </>
        )}

        {/* ── Chat Panel (follow-up questions) ── */}
        <ChatPanel
          sessionId={chatSessionId}
          onSessionChange={setChatSessionId}
          initialMessage={chatInitialMessage}
        />
      </div>
    </div>

      {/* ── Settings Modal ──────────────────────── */}
      <SettingsModal
        show={showSettings}
        onClose={() => {
          setShowSettings(false);
          setProfileRefreshKey(k => k + 1); // triggers panel reload
        }}
      />
    </div>
  );
}

export default App;
