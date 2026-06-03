import { useState, useRef, useEffect } from 'react';

/**
 * TickerSearch — search input with autocomplete dropdown + shares field.
 *
 * Flow:
 *   User types ticker → autocomplete shows matching results
 *   User clicks result → fills name and price
 *   User enters shares → clicks "+" to add
 */
function TickerSearch({ onAdd }) {
  const [query, setQuery] = useState('');
  const [shares, setShares] = useState('');
  const [results, setResults] = useState(null);   // null = no search yet
  const [loading, setLoading] = useState(false);
  const [selectedResult, setSelectedResult] = useState(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);

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

  /** Search for ticker */
  async function handleSearch(val) {
    const q = val.trim().toUpperCase();
    setQuery(val);
    setSelectedResult(null);

    if (!q) {
      setResults(null);
      setShowDropdown(false);
      return;
    }

    setLoading(true);
    setShowDropdown(true);

    try {
      const res = await fetch(`/api/v1/ticker/${q}`);
      if (res.ok) {
        const data = await res.json();
        // Show as a single result (yfinance lookup is exact-match)
        setResults([{
          ticker: data.ticker,
          name: data.name,
          price: data.price,
          currency: data.currency,
        }]);
      } else {
        setResults([]);
      }
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  /** User selected a result from the dropdown */
  function selectResult(r) {
    setSelectedResult(r);
    setQuery(r.ticker);
    setShowDropdown(false);
    // Focus shares field
    setTimeout(() => {
      const sharesInput = document.querySelector('.shares-input');
      sharesInput?.focus();
    }, 100);
  }

  /** Add the holding */
  function handleAdd() {
    if (!selectedResult) return;
    if (!shares || parseFloat(shares) <= 0) {
      alert('Please enter a valid number of shares.');
      return;
    }
    onAdd(
      selectedResult.ticker,
      selectedResult.name,
      selectedResult.price,
      parseFloat(shares),
    );
    // Reset form
    setQuery('');
    setShares('');
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

        {/* Add button */}
        <button
          className="btn-add-ticker"
          onClick={handleAdd}
          disabled={!selectedResult || !shares || parseFloat(shares) <= 0}
        >
          +
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
              key={r.ticker}
              className="dropdown-item"
              onClick={() => selectResult(r)}
            >
              <span className="result-badge">ETF</span>
              <div className="result-details">
                <span className="result-name">{r.name}</span>
                <span className="result-subtitle">
                  {r.ticker} · {r.currency === 'GBP' ? 'LSE' : 'NYSE'}
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
