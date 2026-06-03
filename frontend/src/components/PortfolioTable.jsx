/**
 * PortfolioTable — displays existing holdings in a clean table.
 *
 * Props:
 *   holdings  — array of holding objects
 *   loading   — whether data is still loading
 *   onDelete  — called with holding id when user clicks delete
 */
function PortfolioTable({ holdings, loading, onDelete }) {
  if (loading) {
    return <div className="table-status">Loading portfolio...</div>;
  }

  if (!holdings || holdings.length === 0) {
    return (
      <div className="table-status empty">
        No holdings yet. Search a ticker above to add your first holding.
      </div>
    );
  }

  return (
    <div className="portfolio-table-wrap">
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
          {holdings.map((h) => {
            const totalCost = h.quantity * h.cost_basis_per_share;
            const currentValue = h.quantity * h.current_price;
            const gainLoss = currentValue - totalCost;
            const gainLossPct = totalCost > 0
              ? (gainLoss / totalCost) * 100
              : 0;
            const gainClass = gainLoss >= 0 ? 'positive' : 'negative';

            return (
              <tr key={h.id}>
                <td className="ticker-col">{h.ticker}</td>
                <td className="name-col">{h.name}</td>
                <td className="num-col">{h.quantity}</td>
                <td className="num-col">
                  £{h.current_price.toFixed(2)}
                </td>
                <td className="num-col">
                  £{totalCost.toFixed(2)}
                </td>
                <td className="num-col">
                  £{currentValue.toFixed(2)}
                </td>
                <td className={`num-col ${gainClass}`}>
                  {gainLoss >= 0 ? '+' : ''}£{gainLoss.toFixed(2)}
                </td>
                <td className={`num-col ${gainClass}`}>
                  {gainLossPct >= 0 ? '+' : ''}{gainLossPct.toFixed(1)}%
                </td>
                <td className="action-col">
                  <button
                    className="btn-delete-row"
                    title="Remove holding"
                    onClick={() => onDelete(h.id)}
                  >
                    🗑️
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default PortfolioTable;
