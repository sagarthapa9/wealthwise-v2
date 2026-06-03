import { useState, useEffect } from 'react';

/**
 * SettingsModal — popup with Profile form + Accounts management.
 *
 * Props:
 *   show     — boolean, whether the modal is visible
 *   onClose  — callback to close the modal
 */
function SettingsModal({ show, onClose }) {
  const [activeTab, setActiveTab] = useState('profile');
  const [profile, setProfile] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  // New account form state
  const [newAccount, setNewAccount] = useState({
    provider: '', account_type: 'ISA', cash_balance: 0,
  });
  const [showNewAccount, setShowNewAccount] = useState(false);

  // Load data when modal opens
  useEffect(() => {
    if (!show) return;
    setLoading(true);
    setMessage(null);
    Promise.all([
      fetch('/api/v1/profile').then(r => r.json()),
      fetch('/api/v1/accounts').then(r => r.json()),
    ])
      .then(([p, accts]) => {
        setProfile(p);
        setAccounts(accts);
        setLoading(false);
      })
      .catch(() => {
        setMessage({ type: 'error', text: 'Failed to load settings' });
        setLoading(false);
      });
  }, [show]);

  // Save profile
  async function handleSaveProfile() {
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch('/api/v1/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      });
      if (!res.ok) throw new Error('Save failed');
      localStorage.setItem('wealthwise_profile_saved', 'true');
      setMessage({ type: 'success', text: 'Profile saved!' });
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setSaving(false);
    }
  }

  // Add account
  async function handleAddAccount() {
    if (!newAccount.provider.trim()) return;
    try {
      const res = await fetch('/api/v1/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newAccount),
      });
      if (!res.ok) throw new Error('Save failed');
      const created = await res.json();
      setAccounts([...accounts, created]);
      setNewAccount({ provider: '', account_type: 'ISA', cash_balance: 0 });
      setShowNewAccount(false);
    } catch (err) {
      alert('Failed to add account: ' + err.message);
    }
  }

  // Delete account
  async function handleDeleteAccount(id) {
    if (!confirm('Remove this account?')) return;
    try {
      await fetch(`/api/v1/accounts/${id}`, { method: 'DELETE' });
      setAccounts(accounts.filter(a => a.id !== id));
    } catch (err) {
      alert('Failed to delete: ' + err.message);
    }
  }

  if (!show) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        {/* ── Modal header ────────────────────────────── */}
        <div className="modal-header">
          <h2>Settings</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        {/* ── Tabs ────────────────────────────────────── */}
        <div className="modal-tabs">
          <button
            className={`modal-tab ${activeTab === 'profile' ? 'active' : ''}`}
            onClick={() => setActiveTab('profile')}
          >
            Profile
          </button>
          <button
            className={`modal-tab ${activeTab === 'accounts' ? 'active' : ''}`}
            onClick={() => setActiveTab('accounts')}
          >
            Accounts
          </button>
        </div>

        {/* ── Loading state ───────────────────────────── */}
        {loading && <p className="modal-status">Loading...</p>}

        {/* ── Profile tab ─────────────────────────────── */}
        {!loading && activeTab === 'profile' && profile && (
          <div className="modal-form">
            <label className="form-field">
              <span className="form-label">Age</span>
              <input
                type="number" className="form-input"
                value={profile.age}
                onChange={e => setProfile({ ...profile, age: parseInt(e.target.value) || 0 })}
              />
            </label>

            <label className="form-field">
              <span className="form-label">Risk Tolerance</span>
              <select
                className="form-input"
                value={profile.risk_tolerance}
                onChange={e => setProfile({ ...profile, risk_tolerance: e.target.value })}
              >
                <option value="low">Low</option>
                <option value="moderate">Moderate</option>
                <option value="high">High</option>
              </select>
            </label>

            <label className="form-field">
              <span className="form-label">Investment Horizon</span>
              <input
                className="form-input"
                value={profile.investment_horizon}
                onChange={e => setProfile({ ...profile, investment_horizon: e.target.value })}
              />
            </label>

            <label className="form-field">
              <span className="form-label">Primary Goal</span>
              <input
                className="form-input"
                value={profile.primary_goal}
                onChange={e => setProfile({ ...profile, primary_goal: e.target.value })}
              />
            </label>

            <label className="form-field">
              <span className="form-label">Income Band</span>
              <select
                className="form-input"
                value={profile.income_band}
                onChange={e => setProfile({ ...profile, income_band: e.target.value })}
              >
                <option value="Under £25k">Under £25k</option>
                <option value="£25k-£50k">£25k-£50k</option>
                <option value="£50k-£100k">£50k-£100k</option>
                <option value="£100k-£150k">£100k-£150k</option>
                <option value="Over £150k">Over £150k</option>
              </select>
            </label>

            <label className="form-field">
              <span className="form-label">Tax Band</span>
              <select
                className="form-input"
                value={profile.tax_band}
                onChange={e => setProfile({ ...profile, tax_band: e.target.value })}
              >
                <option value="basic_rate">Basic Rate</option>
                <option value="higher_rate">Higher Rate</option>
                <option value="additional_rate">Additional Rate</option>
              </select>
            </label>

            <label className="form-field">
              <span className="form-label">Pension (monthly)</span>
              <input
                type="number" className="form-input"
                value={profile.pension_contributions_monthly}
                onChange={e => setProfile({ ...profile, pension_contributions_monthly: parseInt(e.target.value) || 0 })}
              />
            </label>

            <label className="form-field">
              <span className="form-label">ISA (monthly)</span>
              <input
                type="number" className="form-input"
                value={profile.isa_contributions_monthly}
                onChange={e => setProfile({ ...profile, isa_contributions_monthly: parseInt(e.target.value) || 0 })}
              />
            </label>

            {message && (
              <p className={`form-message ${message.type}`}>{message.text}</p>
            )}

            <button
              className="btn-save-profile"
              onClick={handleSaveProfile}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Profile'}
            </button>
          </div>
        )}

        {/* ── Accounts tab ────────────────────────────── */}
        {!loading && activeTab === 'accounts' && (
          <div className="modal-accounts">
            {accounts.length === 0 && !showNewAccount && (
              <p className="modal-status">No accounts yet. Add your first account.</p>
            )}

            {accounts.map(acct => (
              <div key={acct.id} className="account-card">
                <div className="account-info">
                  <span className="account-provider">{acct.provider}</span>
                  <span className="account-type">{acct.account_type}</span>
                  <span className="account-cash">£{acct.cash_balance.toFixed(2)} cash</span>
                </div>
                <button
                  className="btn-remove-account"
                  onClick={() => handleDeleteAccount(acct.id)}
                >
                  ✕
                </button>
              </div>
            ))}

            {showNewAccount ? (
              <div className="new-account-form">
                <input
                  className="form-input"
                  placeholder="Provider name"
                  value={newAccount.provider}
                  onChange={e => setNewAccount({ ...newAccount, provider: e.target.value })}
                />
                <select
                  className="form-input"
                  value={newAccount.account_type}
                  onChange={e => setNewAccount({ ...newAccount, account_type: e.target.value })}
                >
                  <option value="ISA">ISA</option>
                  <option value="SIPP">SIPP</option>
                  <option value="GIA">GIA</option>
                  <option value="LISA">LISA</option>
                </select>
                <input
                  type="number" step="0.01" className="form-input"
                  placeholder="Cash balance"
                  value={newAccount.cash_balance}
                  onChange={e => setNewAccount({ ...newAccount, cash_balance: parseFloat(e.target.value) || 0 })}
                />
                <div className="new-account-actions">
                  <button className="btn-save-profile" onClick={handleAddAccount}>Add</button>
                  <button className="btn-cancel" onClick={() => setShowNewAccount(false)}>Cancel</button>
                </div>
              </div>
            ) : (
              <button
                className="btn-add-account"
                onClick={() => setShowNewAccount(true)}
              >
                + Add Account
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default SettingsModal;
