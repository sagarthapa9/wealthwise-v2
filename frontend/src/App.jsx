import { useState, useEffect, useCallback } from 'react';
import PortfolioTable from './components/PortfolioTable';
import TickerSearch from './components/TickerSearch';
import AllocationSection from './components/AllocationSection';
import SettingsModal from './components/SettingsModal';
import ProfilePanel from './components/ProfilePanel';

function App() {
  const [holdings, setHoldings] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currency, setCurrency] = useState('GBP');
  const [showSettings, setShowSettings] = useState(false);
  const [profileRefreshKey, setProfileRefreshKey] = useState(0);
  const [showAnalysis, setShowAnalysis] = useState(false);

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
  async function handleAddHolding(ticker, name, price, quantity) {
    try {
      const res = await fetch('/api/v1/portfolio/holdings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: ticker.trim().toUpperCase(),
          name,
          quantity: parseFloat(quantity) || 0,
          cost_basis_per_share: parseFloat(price) || 0,
          current_price: parseFloat(price) || 0,
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
              onClick={() => setShowAnalysis(true)}
            >
              Analyze Portfolio
            </button>
          </div>
        </div>

        {/* ── Analysis Section (shown after clicking Analyze) ──── */}
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

            {/* Allocation Breakdown */}
            <AllocationSection hasHoldings={holdings.length > 0} />
          </>
        )}
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
