import { useState, useRef, useEffect } from 'react';

/**
 * TickerSearch — search input with autocomplete dropdown + shares + purchase price + account selector.
 *
 * Flow:
 *   User types ticker → autocomplete shows matching results via /api/v1/ticker/search
 *   User clicks result → fetches full details via /api/v1/ticker/{code}
 *   User selects account, enters shares + optional purchase price → clicks "+" to add
 */
function TickerSearch({ onAdd, accounts }) {
  const [query, setQuery] = useState('');
  const [shares, setShares] = useState('');
  const [purchasePrice, setPurchasePrice] = useState('');
  const [selectedAccountId, setSelectedAccountId] = useState('');
  const [results, setResults] = useState(null);   // null = no search yet
  const [loading, setLoading] = useState(false);
  const [fetchingDetails, setFetchingDetails] = useState(false);
  const [selectedResult, setSelectedResult] = useState(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);
  const debounceRef = useRef(null);

  // Close dropdown when user clicks outside
  useEffect(() => {
    function handleClick(e) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target) &&
        !inputRef.current?.contains(e.target)
      ) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  /** Search for tickers via EODHD search endpoint */
  async function handleSearch(val) {
    const q = val.trim();
    setQuery(val);
    setSelectedResult(null);
    setPurchasePrice('');
    setSearchError(null);

    if (!q || q.length < 1) {
      setResults(null);
      setShowDropdown(false);
      return;
    }

    // Debounce: wait 200ms after user stops typing
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      setShowDropdown(true);

      try {
        const res = await fetch(`/api/v1/ticker/search?q=${encodeURIComponent(q)}&limit=8`);
        if (res.status === 501) {
          setSearchError('Search requires EODHD_API_KEY');
          setResults([]);
          return;
        }
        if (res.ok) {
          const data = await res.json();
          console.log('[TickerSearch] search results:', data);
          setResults(data || []);
        } else {
          setResults([]);
        }
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 200);
  }

  /** User selected a result from the dropdown — fetch full details */
  async function selectResult(r) {
    setSelectedResult(r);
    setQuery(r.code);
    setShowDropdown(false);
    setSearchError(null);
    setFetchingDetails(true);

    try {
      const symbol = r.exchange ? `${r.code}.${r.exchange}` : r.code;
      const res = await fetch(`/api/v1/ticker/${symbol}`);
      if (res.ok) {
        const data = await res.json();
        console.log('[TickerSearch] ticker detail:', data);
        // Merge full details into the selected result
        setSelectedResult({
          ticker: data.ticker,
          name: data.name,
          price: data.price,
          currency: data.currency,
          type: data.type,
          asset_class: data.asset_class,
          sector: data.sector,
          geography: data.geography,
          ocf_pct: data.ocf_pct,
          dividend_yield_pct: data.dividend_yield_pct,
          isin: data.isin,
          exchange: r.exchange,
        });
        // Pre-fill purchase price with current price (user can override)
        if (data.price > 0) {
          setPurchasePrice(String(data.price));
        }
      }
      // If detail fetch fails, still keep the search result as selected
    } catch {
      // best-effort
    } finally {
      setFetchingDetails(false);
      // Focus shares field
      setTimeout(() => {
        const sharesInput = document.querySelector('.shares-input');
        sharesInput?.focus();
      }, 100);
    }
  }

  /** Add the holding */
  function handleAdd() {
    if (!selectedResult) return;
    if (!shares || parseFloat(shares) <= 0) {
      alert('Please enter a valid number of shares.');
      return;
    }
    if (!selectedAccountId) {
      alert('Please select an account for this holding.');
      return;
    }
    const pp = purchasePrice ? parseFloat(purchasePrice) : selectedResult.price;
    const aid = parseInt(selectedAccountId, 10);
    onAdd({
      ticker: selectedResult.ticker || selectedResult.code,
      name: selectedResult.name,
      current_price: selectedResult.price || 0,
      cost_basis_per_share: pp,
      quantity: parseFloat(shares),
      account_id: aid,
      type: selectedResult.type,
      asset_class: selectedResult.asset_class,
      sector: selectedResult.sector,
      geography: selectedResult.geography,
      currency: selectedResult.currency,
      ocf_pct: selectedResult.ocf_pct,
      dividend_yield_pct: selectedResult.dividend_yield_pct,
      isin: selectedResult.isin,
    });
    // Reset form
    setQuery('');
    setShares('');
    setPurchasePrice('');
    setSelectedResult(null);
    setResults(null);
    setShowDropdown(false);
    inputRef.current?.focus();
  }

  /** Handle Enter key in either field */
  function handleKeyDown(e) {
    if (e.key === 'Enter') {
      if (selectedResult) {
        handleAdd();
      } else if (results && results.length > 0) {
        selectResult(results[0]);
      }
    }
  }

  return (
    <div className="ticker-entry-wrapper">
      <div className="ticker-entry-row">
        {/* Ticker input */}
        <div className="ticker-input-wrap">
          <span className="search-icon">🔍</span>
          <input
            ref={inputRef}
            className="ticker-search-input"
            type="text"
            value={query}
            onChange={(e) => handleSearch(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => results !== null && setShowDropdown(true)}
            placeholder="Search ticker symbol..."
            autoComplete="off"
          />
        </div>

        {/* Shares input */}
        <input
          className="shares-input"
          type="number"
          step="any"
          value={shares}
          onChange={(e) => setShares(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Shares"
          disabled={!selectedResult}
        />

        {/* Purchase Price input — separate from live price */}
        <input
          className="purchase-price-input"
          type="number"
          step="any"
          value={purchasePrice}
          onChange={(e) => setPurchasePrice(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Price you paid"
          disabled={!selectedResult}
          title="Leave blank to use current market price as cost basis"
        />

        {/* Account selector */}
        <select
          className="account-select-input"
          value={selectedAccountId}
          onChange={(e) => setSelectedAccountId(e.target.value)}
          disabled={!selectedResult}
          title="Required: select an account"
        >
          <option value="">Select account…</option>
          {accounts && accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.provider} ({a.account_type})
            </option>
          ))}
        </select>

        {/* Add button */}
        <button
          className="btn-add-ticker"
          onClick={handleAdd}
          disabled={!selectedResult || !shares || parseFloat(shares) <= 0 || !selectedAccountId || fetchingDetails}
        >
          {fetchingDetails ? '⋯' : '+'}
        </button>
      </div>

      {/* ── Autocomplete dropdown ─────────────────────────────── */}
      {showDropdown && (
        <div className="autocomplete-dropdown" ref={dropdownRef}>
          {loading && (
            <div className="dropdown-item loading-state">
              Searching...
            </div>
          )}

          {!loading && results === null && (
            <div className="dropdown-item loading-state">
              Type a ticker to search
            </div>
          )}

          {!loading && results !== null && results.length === 0 && (
            <div className="dropdown-item no-results">
              No results found for "{query}"
            </div>
          )}

          {!loading && results && results.length > 0 && results.map((r, i) => (
            <div
              key={`${r.code}-${r.exchange || i}`}
              className="dropdown-item"
              onClick={() => selectResult(r)}
            >
              <span className="result-badge">{r.type || 'ETF'}</span>
              <div className="result-details">
                <span className="result-name">{r.name}</span>
                <span className="result-subtitle">
                  {r.code} · {r.exchange || 'N/A'}
                  {r.match_score ? ` · ${Math.round(r.match_score * 100)}%` : ''}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default TickerSearch;
