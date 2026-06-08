import { useState, useEffect, useCallback, useRef } from 'react';
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
  const [accounts, setAccounts] = useState([]);
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
  const [analysisStale, setAnalysisStale] = useState(false);
  const summaryRef = useRef(null);

  // On mount, scroll to summary metrics if analysis exists, otherwise focus ticker search
  useEffect(() => {
    if (!loading) {
      if (aiAnalysis) {
        setTimeout(() => summaryRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300);
      } else {
        document.querySelector('.ticker-search-input')?.focus();
      }
    }
  }, [loading, aiAnalysis]);
  const [newAccountProvider, setNewAccountProvider] = useState('');
  const [newAccountType, setNewAccountType] = useState('ISA');

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

  const loadAccounts = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/accounts');
      if (res.ok) {
        setAccounts(await res.json());
      }
    } catch {
      // best-effort
    }
  }, []);

  // Check if any holding was added after the analysis — marks stale across refreshes
  function checkStale(holdingsData, generatedAt) {
    if (!generatedAt || !holdingsData || holdingsData.length === 0) return;
    const analysisTime = new Date(generatedAt).getTime();
    const newestHolding = Math.max(...holdingsData.map(h => new Date(h.created_at).getTime()));
    if (newestHolding > analysisTime) {
      setAnalysisStale(true);
    }
  }

  useEffect(() => {
    loadHoldings();
    loadAccounts();
    // Restore the last chat session from the database on mount
    fetch('/api/v1/chat/latest')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data && data.session_id) {
          setChatSessionId(data.session_id);
          setShowAnalysis(true);
          if (data.message) {
            const analysisData = {
              message: data.message,
              reasoning_content: data.reasoning_content,
              generated_at: data.generated_at,
            };
            setAiAnalysis(analysisData);
          }
        }
      })
      .catch(() => {});
  }, [loadHoldings, loadAccounts]);

  // Check stale status whenever holdings finish loading after analysis restore
  useEffect(() => {
    if (aiAnalysis?.generated_at && holdings.length > 0) {
      checkStale(holdings, aiAnalysis.generated_at);
    }
  }, [holdings, aiAnalysis?.generated_at]);

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
          account_id: holding.account_id || null,
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
      if (aiAnalysis) setAnalysisStale(true);
    } catch (err) {
      alert('Failed to add holding: ' + err.message);
    }
  }

  /** Create a new account via inline form */
  async function handleCreateAccount() {
    if (!newAccountProvider.trim()) {
      alert('Please enter a provider name.');
      return;
    }
    try {
      const res = await fetch('/api/v1/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: newAccountProvider.trim(), account_type: newAccountType }),
      });
      if (!res.ok) throw new Error('Failed to create account');
      setNewAccountProvider('');
      await loadAccounts();
    } catch (err) {
      alert('Error creating account: ' + err.message);
    }
  }

  /** Delete a holding */
  async function handleDelete(id) {
    if (!confirm('Remove this holding?')) return;
    try {
      await fetch(`/api/v1/portfolio/holdings/${id}`, { method: 'DELETE' });
      await loadHoldings();
      if (aiAnalysis) setAnalysisStale(true);
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
    setAnalysisStale(false);

    // Use existing chat session so conversation stays continuous
    const sessionId = chatSessionId;

    setAiLoading(true);
    try {
      const res = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: ANALYSIS_PROMPT,
          session_id: sessionId,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setAiAnalysis({
          message: data.message,
          reasoning_content: data.reasoning_content,
          generated_at: new Date().toISOString(),
        });
        // Set the session so ChatPanel can load the conversation history
        if (data.session_id) {
          setChatSessionId(data.session_id);
        }
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
        holdings={holdings}
        accounts={accounts}
        onAccountChange={() => { loadHoldings(); loadAccounts(); }}
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

        {/* ── Account-first flow ──────────────────── */}
        {accounts.length === 0 ? (
          <div className="no-account-prompt">
            <div className="no-account-icon">🏦</div>
            <p className="no-account-text">Set up your first account to start tracking your portfolio</p>
            <div className="no-account-form">
              <input
                className="no-account-input"
                type="text"
                value={newAccountProvider}
                onChange={(e) => setNewAccountProvider(e.target.value)}
                placeholder="Provider name (e.g. Vanguard, AJ Bell)"
                onKeyDown={(e) => e.key === 'Enter' && handleCreateAccount()}
              />
              <select
                className="no-account-select"
                value={newAccountType}
                onChange={(e) => setNewAccountType(e.target.value)}
              >
                <option value="ISA">ISA</option>
                <option value="SIPP">SIPP</option>
                <option value="GIA">GIA</option>
                <option value="LISA">LISA</option>
              </select>
              <button className="btn-add-ticker" onClick={handleCreateAccount}>+</button>
            </div>
            <button className="btn-settings-link" onClick={() => setShowSettings(true)}>
              Add cash balance & more details in Settings ⚙️
            </button>
          </div>
        ) : (
          <TickerSearch onAdd={handleAddHolding} accounts={accounts} />
        )}

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
          accounts={accounts}
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
              className={`btn-analyze${analysisStale ? ' btn-analyze-stale' : ''}`}
              disabled={holdings.length === 0}
              onClick={handleAnalyze}
            >
              {analysisStale ? '↻ Analyse again' : 'Analyze Portfolio'}
            </button>
          </div>
        </div>

        {/* ── Analysis Section (after clicking Analyze) ──── */}
        {showAnalysis && (
          <>
            {/* Summary Metrics */}
            {summary && summary.holding_count > 0 && (
              <div className="summary-strip" ref={summaryRef}>
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
            {aiLoading ? (
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
            ) : aiAnalysis ? (
              <div className="ai-hero">
                <div className="ai-hero-header">
                  <span className="ai-hero-icon">✨</span>
                  <span className="ai-hero-title">Portfolio Overview</span>
                </div>
                {analysisStale && (
                  <div className="ai-stale-banner">
                    <span className="ai-stale-icon">📊</span>
                    <span className="ai-stale-text">Portfolio updated since this analysis</span>
                  </div>
                )}

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
            ) : null}
            {/* Allocation Breakdown — hidden while re-analysing */}
            {!aiLoading && (
              <AllocationSection
                hasHoldings={holdings.length > 0}
                onAsk={handleAsk}
              />
            )}
          </>
        )}

        {/* ── Chat Panel (follow-up questions) ── */}
        <ChatPanel
          sessionId={chatSessionId}
          onSessionChange={setChatSessionId}
          initialMessage={chatInitialMessage}
          filterAutoMessages={[ANALYSIS_PROMPT]}
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
