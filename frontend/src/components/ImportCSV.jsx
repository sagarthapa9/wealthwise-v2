import { useState, useRef } from 'react';

/**
 * ImportCSV — file upload → editable preview → bulk import.
 *
 * States: idle → uploading → preview → importing → complete / error
 */
function ImportCSV({ accounts, onComplete, onCancel }) {
  const [state, setState] = useState('idle');        // idle | uploading | preview | importing | complete | error
  const [rows, setRows] = useState([]);               // ImportRowData[]
  const [mappedColumns, setMappedColumns] = useState({});
  const [unmappedColumns, setUnmappedColumns] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [validRows, setValidRows] = useState(0);
  const [invalidRows, setInvalidRows] = useState(0);
  const [selectedAccountId, setSelectedAccountId] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [importResult, setImportResult] = useState(null);  // ImportResponse
  const fileInputRef = useRef(null);

  /** Step 1: Upload CSV for preview */
  async function handleFile(file) {
    if (!file) return;
    setState('uploading');
    setErrorMessage('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/v1/portfolio/import/preview', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to parse CSV');
      }
      const data = await res.json();
      setRows(data.rows);
      setMappedColumns(data.mapped_columns);
      setUnmappedColumns(data.unmapped_columns);
      setTotalRows(data.total_rows);
      setValidRows(data.valid_rows);
      setInvalidRows(data.invalid_rows);
      // Auto-select first account if only one exists
      if (accounts && accounts.length === 1) {
        setSelectedAccountId(String(accounts[0].id));
      }
      setState('preview');
    } catch (err) {
      setErrorMessage(err.message);
      setState('error');
    }
  }

  /** Edit a single cell value in a row */
  function updateCell(rowIndex, field, value) {
    setRows(prev => prev.map((r, i) => {
      if (i !== rowIndex) return r;
      const updated = { ...r, [field]: value };
      // Re-validate on edit
      let errors = [];
      if (!updated.ticker) errors.push('Missing ticker symbol');
      if (!updated.quantity || parseFloat(updated.quantity) <= 0) errors.push('Missing or invalid quantity');
      if (updated.cost_basis_per_share === null || updated.cost_basis_per_share === undefined || parseFloat(updated.cost_basis_per_share) < 0) errors.push('Missing or invalid cost basis');
      updated.errors = errors;
      updated.valid = errors.length === 0;
      return updated;
    }));
  }

  /** Remove a row from the import list */
  function deleteRow(rowIndex) {
    setRows(prev => {
      const next = prev.filter((_, i) => i !== rowIndex);
      // Recalculate counts
      const valid = next.filter(r => r.valid).length;
      const invalid = next.filter(r => !r.valid).length;
      setValidRows(valid);
      setInvalidRows(invalid);
      setTotalRows(next.length);
      return next;
    });
  }

  /** Re-enrich a single row after the user edited the ticker */
  async function reEnrichRow(rowIndex) {
    const row = rows[rowIndex];
    if (!row.ticker) return;

    try {
      const res = await fetch(`/api/v1/ticker/${row.ticker}`);
      if (!res.ok) {
        setRows(prev => prev.map((r, i) =>
          i === rowIndex ? { ...r, enriched: false, enrichment_error: 'Ticker not found' } : r
        ));
        return;
      }
      const data = await res.json();
      setRows(prev => prev.map((r, i) => {
        if (i !== rowIndex) return r;
        return {
          ...r,
          enriched: true,
          enrichment_error: null,
          type: data.type,
          asset_class: data.asset_class,
          sector: data.sector,
          geography: data.geography,
          currency: r.currency || data.currency,
          ocf_pct: data.ocf_pct,
          dividend_yield_pct: data.dividend_yield_pct,
          isin: r.isin || data.isin,
          current_price: data.price || r.current_price,
          name: r.name || data.name,
        };
      }));
    } catch {
      // best-effort
    }
  }

  /** Step 2: Import the edited rows */
  async function handleImport() {
    if (!selectedAccountId) {
      alert('Please select an account for these holdings.');
      return;
    }
    setState('importing');

    try {
      const res = await fetch('/api/v1/portfolio/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_id: parseInt(selectedAccountId, 10),
          rows: rows.filter(r => r.valid),
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Import failed');
      }
      const result = await res.json();
      setImportResult(result);
      setState('complete');
    } catch (err) {
      setErrorMessage(err.message);
      setState('error');
    }
  }

  /** Reset back to idle */
  function handleDone() {
    setState('idle');
    setRows([]);
    setImportResult(null);
    setErrorMessage('');
    onComplete();
  }

  // ── Render helpers ─────────────────────────────────────────────────────

  function enrichmentBadge(row) {
    if (!row.ticker) return <span className="csv-badge csv-badge-none">No ticker</span>;
    if (row.enriched) return <span className="csv-badge csv-badge-enriched">Enriched ✓</span>;
    if (row.enrichment_error) return <span className="csv-badge csv-badge-failed" title={row.enrichment_error}>Not enriched</span>;
    return <span className="csv-badge csv-badge-none">—</span>;
  }

  // ── States ─────────────────────────────────────────────────────────────

  if (state === 'idle') {
    return (
      <div className="csv-import-panel" onClick={() => fileInputRef.current?.click()}>
        <div className="csv-dropzone">
          <span className="csv-dropzone-icon">📥</span>
          <p className="csv-dropzone-text">Click to upload a CSV file from your brokerage</p>
          <p className="csv-dropzone-hint">Supports most broker formats — columns are auto-detected</p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          style={{ display: 'none' }}
          onChange={(e) => {
            if (e.target.files?.[0]) handleFile(e.target.files[0]);
            e.target.value = '';
          }}
        />
      </div>
    );
  }

  if (state === 'uploading') {
    return (
      <div className="csv-import-panel">
        <div className="csv-loading">
          <span className="csv-spinner" />
          <p>Analysing CSV file...</p>
        </div>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div className="csv-import-panel">
        <div className="csv-error">
          <span className="csv-error-icon">⚠️</span>
          <p className="csv-error-text">{errorMessage || 'Something went wrong'}</p>
          <div className="csv-actions">
            <button className="btn-csv-secondary" onClick={onCancel}>Cancel</button>
            <button className="btn-csv-primary" onClick={() => { setState('idle'); setErrorMessage(''); }}>
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (state === 'preview') {
    return (
      <div className="csv-import-panel">
        <div className="csv-preview-header">
          <div>
            <h3 className="csv-preview-title">Preview Import</h3>
            <p className="csv-preview-summary">
              {totalRows} rows · {validRows} valid · {invalidRows} with errors
            </p>
          </div>
          {unmappedColumns.length > 0 && (
            <p className="csv-unmapped-note">
              Unmapped columns: {unmappedColumns.join(', ')}
            </p>
          )}
        </div>

        {/* ── Editable table ──────────────────────────────── */}
        <div className="csv-table-wrap">
          <table className="csv-preview-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Ticker</th>
                <th>Name</th>
                <th>Qty</th>
                <th>Cost/Share</th>
                <th>Price</th>
                <th>Type</th>
                <th>Sector</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className={`csv-row ${!row.valid ? 'csv-row-invalid' : ''}`}>
                  <td className="csv-cell-num">{row.row_number}</td>
                  <td>
                    <input
                      className="csv-cell-input csv-cell-ticker"
                      type="text"
                      value={row.ticker || ''}
                      onChange={(e) => updateCell(i, 'ticker', e.target.value.toUpperCase())}
                    />
                  </td>
                  <td>
                    <input
                      className="csv-cell-input csv-cell-name"
                      type="text"
                      value={row.name || ''}
                      onChange={(e) => updateCell(i, 'name', e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      className="csv-cell-input csv-cell-num-input"
                      type="number"
                      step="any"
                      value={row.quantity || ''}
                      onChange={(e) => updateCell(i, 'quantity', e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      className="csv-cell-input csv-cell-num-input"
                      type="number"
                      step="any"
                      value={row.cost_basis_per_share || ''}
                      onChange={(e) => updateCell(i, 'cost_basis_per_share', e.target.value)}
                    />
                  </td>
                  <td className="csv-cell-readonly">
                    {row.current_price ? `£${parseFloat(row.current_price).toFixed(2)}` : '—'}
                  </td>
                  <td className="csv-cell-readonly">{row.type || '—'}</td>
                  <td className="csv-cell-readonly">{row.sector || '—'}</td>
                  <td>
                    <div className="csv-status-cell">
                      {enrichmentBadge(row)}
                      {row.ticker && (
                        <button
                          className="csv-reenrich-btn"
                          title="Re-fetch ticker data"
                          onClick={() => reEnrichRow(i)}
                        >🔄</button>
                      )}
                    </div>
                  </td>
                  <td>
                    <button
                      className="csv-delete-btn"
                      title="Remove row"
                      onClick={() => deleteRow(i)}
                    >🗑️</button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan="10" className="csv-empty-msg">No rows to show</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* ── Footer ──────────────────────────────────────── */}
        <div className="csv-preview-footer">
          <div className="csv-account-row">
            <label className="csv-account-label">Import into account:</label>
            <select
              className="csv-account-select"
              value={selectedAccountId}
              onChange={(e) => setSelectedAccountId(e.target.value)}
            >
              <option value="">Select account…</option>
              {accounts && accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.provider} ({a.account_type})
                </option>
              ))}
            </select>
          </div>
          <div className="csv-actions">
            <button className="btn-csv-secondary" onClick={onCancel}>Cancel</button>
            <button
              className="btn-csv-primary"
              disabled={validRows === 0 || !selectedAccountId}
              onClick={handleImport}
            >
              Import {validRows} holding{validRows !== 1 ? 's' : ''}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (state === 'importing') {
    return (
      <div className="csv-import-panel">
        <div className="csv-loading">
          <span className="csv-spinner" />
          <p>Creating holdings...</p>
        </div>
      </div>
    );
  }

  if (state === 'complete') {
    const r = importResult;
    return (
      <div className="csv-import-panel">
        <div className="csv-success">
          <span className="csv-success-icon">✅</span>
          <h3>Import complete</h3>
          <p className="csv-success-summary">
            Imported <strong>{r?.imported || 0}</strong> holding{(r?.imported || 0) !== 1 ? 's' : ''}
            {r?.enriched_count > 0 && <> · {r.enriched_count} enriched with live data</>}
            {r?.skipped > 0 && <> · {r.skipped} skipped</>}
          </p>
          {r?.errors && r.errors.length > 0 && (
            <div className="csv-import-errors">
              {r.errors.map((e, i) => (
                <p key={i} className="csv-import-error-row">
                  Row {e.row} ({e.ticker || '?'}): {e.reason}
                </p>
              ))}
            </div>
          )}
          <button className="btn-csv-primary" onClick={handleDone}>Done</button>
        </div>
      </div>
    );
  }

  return null;
}

export default ImportCSV;
