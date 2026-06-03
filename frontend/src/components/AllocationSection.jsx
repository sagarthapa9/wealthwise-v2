import { useState, useEffect } from 'react';
import AllocationDonut from './AllocationDonut';
import AllocationTable from './AllocationTable';
import HookInsightCard from './HookInsightCard';

const TABS = ['asset_class', 'sector', 'geographic'];
const TAB_LABELS = {
  asset_class: 'Asset Class',
  sector: 'Sector',
  geographic: 'Geographic',
};

/**
 * AllocationSection — fetches allocation data and renders tabbed view
 * with donut chart, table, and insight card.
 *
 * Props:
 *   hasHoldings — boolean, whether the portfolio has any holdings
 */
function AllocationSection({ hasHoldings }) {
  const [activeTab, setActiveTab] = useState('asset_class');
  const [allocData, setAllocData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!hasHoldings) {
      setAllocData(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch(`/api/v1/portfolio/allocations?tab=${activeTab}`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load');
        return res.json();
      })
      .then((data) => {
        if (!cancelled) {
          setAllocData(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [activeTab, hasHoldings]);

  // Don't render at all if no holdings
  if (!hasHoldings) return null;

  // Determine which allocation list to show
  const currentAlloc = allocData ? allocData[activeTab] : [];
  const hook = allocData?.hook || null;

  return (
    <div className="allocation-section">

      {/* ── Tabs ──────────────────────────────────────────── */}
      <div className="alloc-tabs">
        {TABS.map((tab) => (
          <button
            key={tab}
            className={`alloc-tab ${tab === activeTab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {TAB_LABELS[tab]}
          </button>
        ))}
      </div>

      {/* ── Content ────────────────────────────────────────── */}
      <div className="alloc-content">
        {loading && (
          <p className="alloc-status">Loading allocations...</p>
        )}
        {error && (
          <p className="alloc-status error">Error: {error}</p>
        )}
        {!loading && !error && allocData && (
          <>
            <AllocationDonut data={currentAlloc} />
            <AllocationTable data={currentAlloc} />
            <HookInsightCard hook={hook} />
          </>
        )}
      </div>
    </div>
  );
}

export default AllocationSection;
