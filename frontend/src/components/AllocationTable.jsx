/**
 * AllocationTable — a simple list showing category names and percentages.
 *
 * Props:
 *   data — array of { label, value_gbp, percentage, color }
 *
 * Rows with >20% get a grey background highlight.
 */
function AllocationTable({ data }) {
  if (!data || data.length === 0) {
    return <p className="table-empty">No allocation data to display.</p>;
  }

  // Sort descending by percentage
  const sorted = [...data].sort((a, b) => b.percentage - a.percentage);

  return (
    <div className="allocation-table-wrap">
      <table className="allocation-table">
        <thead>
          <tr>
            <th>Category</th>
            <th className="num-col">Value</th>
            <th className="num-col">Allocation</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => {
            const isConcentrated = row.percentage > 20;
            return (
              <tr
                key={row.label}
                className={isConcentrated ? 'row-concentrated' : ''}
              >
                <td>
                  <span className="dot-indicator" style={{ background: row.color }} />
                  {row.label}
                </td>
                <td className="num-col">
                  £{row.value_gbp.toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                  })}
                </td>
                <td className={`num-col ${isConcentrated ? 'bold' : ''}`}>
                  {row.percentage.toFixed(1)}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default AllocationTable;
