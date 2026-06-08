/**
 * PortfolioTable — displays holdings grouped by account.
 *
 * Each account gets a visual card/section with its holdings listed inside.
 * Accounts with no holdings still show with a £0 placeholder.
 * Holdings without an account appear in an "Ungrouped" section.
 *
 * Props:
 *   holdings  — array of holding objects
 *   accounts  — array of account objects { id, provider, account_type }
 *   loading   — whether data is still loading
 *   onDelete  — called with holding id when user clicks delete
 */
function PortfolioTable({ holdings, accounts, loading, onDelete }) {
  if (loading) {
    return <div className="table-status">Loading portfolio...</div>;
  }

  // Group holdings by account_id
  const byAccount = {};
  const ungrouped = [];
  for (const h of holdings || []) {
    if (h.account_id) {
      if (!byAccount[h.account_id]) byAccount[h.account_id] = [];
      byAccount[h.account_id].push(h);
    } else {
      ungrouped.push(h);
    }
  }

  // Build account sections: merge accounts with their holdings
  const sections = (accounts || []).map(acc => ({
    ...acc,
    holdings: byAccount[acc.id] || [],
  }));

  if (sections.length === 0 && (!holdings || holdings.length === 0)) {
    return (
      <div className="table-status empty">
        No holdings yet. Search a ticker above to add your first holding.
      </div>
    );
  }

  return (
    <div className="account-group-list">
      {sections.map((section) => {
        const sectionValue = section.holdings.reduce(
          (sum, h) => sum + h.quantity * h.current_price, 0
        );
        const sectionCost = section.holdings.reduce(
          (sum, h) => sum + h.quantity * h.cost_basis_per_share, 0
        );
        const sectionGain = sectionValue - sectionCost;
        const sectionGainPct = sectionCost > 0 ? (sectionGain / sectionCost) * 100 : 0;

        return (
          <div key={section.id ?? 'ungrouped'} className="account-group-card">
            {/* ── Account header ───────────────────── */}
            <div className="account-group-header">
              <div className="account-group-title-row">
                <span className={`account-type-badge account-type-${(section.account_type || 'other').toLowerCase()}`}>
                  {section.account_type || '—'}
                </span>
                <span className="account-group-provider">{section.provider}</span>
              </div>
              <div className="account-group-stats">
                <span className="ag-stat">
                  <span className="ag-stat-label">Value</span>
                  <span className="ag-stat-value">£{sectionValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </span>
                <span className={`ag-stat ${sectionGain >= 0 ? 'positive' : 'negative'}`}>
                  <span className="ag-stat-label">Gain/Loss</span>
                  <span className="ag-stat-value">
                    {sectionGain >= 0 ? '+' : ''}£{sectionGain.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    ({sectionGain >= 0 ? '+' : ''}{sectionGainPct.toFixed(1)}%)
                  </span>
                </span>
                <span className="ag-stat">
                  <span className="ag-stat-label">Holdings</span>
                  <span className="ag-stat-value">{section.holdings.length}</span>
                </span>
              </div>
            </div>

            {/* ── Holdings table ───────────────────── */}
            {section.holdings.length > 0 ? (
              <table className="portfolio-table">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Name</th>
                    <th className="num-col">Shares</th>
                    <th className="num-col">Price</th>
                    <th className="num-col">Cost</th>
                    <th className="num-col">Value</th>
                    <th className="num-col">Gain/Loss</th>
                    <th className="num-col">Return</th>
                    <th className="action-col"></th>
                  </tr>
                </thead>
                <tbody>
                  {section.holdings.map((h) => {
                    const totalCost = h.quantity * h.cost_basis_per_share;
                    const currentValue = h.quantity * h.current_price;
                    const gainLoss = currentValue - totalCost;
                    const gainLossPct = totalCost > 0 ? (gainLoss / totalCost) * 100 : 0;
                    const gainClass = gainLoss >= 0 ? 'positive' : 'negative';

                    return (
                      <tr key={h.id}>
                        <td className="ticker-col">{h.ticker}</td>
                        <td className="name-col">{h.name}</td>
                        <td className="num-col">{h.quantity}</td>
                        <td className="num-col">£{h.current_price.toFixed(2)}</td>
                        <td className="num-col">£{totalCost.toFixed(2)}</td>
                        <td className="num-col">£{currentValue.toFixed(2)}</td>
                        <td className={`num-col ${gainClass}`}>
                          {gainLoss >= 0 ? '+' : ''}£{gainLoss.toFixed(2)}
                        </td>
                        <td className={`num-col ${gainClass}`}>
                          {gainLossPct >= 0 ? '+' : ''}{gainLossPct.toFixed(1)}%
                        </td>
                        <td className="action-col">
                          <button className="btn-delete-row" title="Remove holding" onClick={() => onDelete(h.id)}>🗑️</button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <div className="account-group-empty">
                No holdings in this account yet.
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default PortfolioTable;
