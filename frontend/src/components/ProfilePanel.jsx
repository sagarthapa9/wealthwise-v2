import { useState, useEffect } from 'react';

const RISK_LABELS = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
};

const TAX_LABELS = {
  basic_rate: 'Basic Rate',
  higher_rate: 'Higher Rate',
  additional_rate: 'Additional Rate',
};

function hasSavedProfile(p) {
  if (!p) return false;
  if (localStorage.getItem('wealthwise_profile_saved') === 'true') return true;
  if (p.pension_contributions_monthly > 0 || p.isa_contributions_monthly > 0) return true;
  return false;
}

function ProfilePanel({ onOpenSettings, refreshKey }) {
  const [profile, setProfile] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingProfile, setEditingProfile] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [newAcctForm, setNewAcctForm] = useState(false);
  const [newAcct, setNewAcct] = useState({ provider: '', account_type: 'ISA', cash_balance: 0 });

  useEffect(() => {
    loadData();
  }, [refreshKey]);

  async function loadData() {
    setLoading(true);
    try {
      const [p, accts] = await Promise.all([
        fetch('/api/v1/profile').then(r => r.json()),
        fetch('/api/v1/accounts').then(r => r.json()),
      ]);
      setProfile(p);
      setAccounts(accts);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  // ── Profile save ─────────────────────────────────────

  async function handleSaveProfile() {
    setSaving(true);
    try {
      const res = await fetch('/api/v1/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm),
      });
      if (!res.ok) throw new Error('Save failed');
      localStorage.setItem('wealthwise_profile_saved', 'true');
      setProfile(editForm);
      setEditingProfile(false);
    } catch (err) {
      alert('Failed to save: ' + err.message);
    } finally {
      setSaving(false);
    }
  }

  function startEdit() {
    setEditForm({ ...profile });
    setEditingProfile(true);
  }

  function cancelEdit() {
    setEditingProfile(false);
  }

  // ── Account CRUD ─────────────────────────────────────

  async function handleAddAccount() {
    if (!newAcct.provider.trim()) return;
    try {
      const res = await fetch('/api/v1/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newAcct),
      });
      if (!res.ok) throw new Error('Save failed');
      const created = await res.json();
      setAccounts([...accounts, created]);
      setNewAcct({ provider: '', account_type: 'ISA', cash_balance: 0 });
      setNewAcctForm(false);
    } catch (err) {
      alert('Failed to add account: ' + err.message);
    }
  }

  async function handleDeleteAccount(id) {
    if (!confirm('Remove this account?')) return;
    try {
      await fetch(`/api/v1/accounts/${id}`, { method: 'DELETE' });
      setAccounts(accounts.filter(a => a.id !== id));
    } catch (err) {
      alert('Failed to delete: ' + err.message);
    }
  }

  // ── Render helpers ────────────────────────────────────

  function renderProfileField(label, key, type) {
    if (type === 'select' && key === 'risk_tolerance') {
      return (
        <label className="detail-row">
          <span className="detail-label">{label}</span>
          <select className="detail-edit" value={editForm[key]} onChange={e => setEditForm({ ...editForm, [key]: e.target.value })}>
            <option value="low">Low</option>
            <option value="moderate">Moderate</option>
            <option value="high">High</option>
          </select>
        </label>
      );
    }
    if (type === 'select' && key === 'tax_band') {
      return (
        <label className="detail-row">
          <span className="detail-label">{label}</span>
          <select className="detail-edit" value={editForm[key]} onChange={e => setEditForm({ ...editForm, [key]: e.target.value })}>
            <option value="basic_rate">Basic Rate</option>
            <option value="higher_rate">Higher Rate</option>
            <option value="additional_rate">Additional Rate</option>
          </select>
        </label>
      );
    }
    if (type === 'select' && key === 'income_band') {
      return (
        <label className="detail-row">
          <span className="detail-label">{label}</span>
          <select className="detail-edit" value={editForm[key]} onChange={e => setEditForm({ ...editForm, [key]: e.target.value })}>
            <option value="Under £25k">Under £25k</option>
            <option value="£25k-£50k">£25k-£50k</option>
            <option value="£50k-£100k">£50k-£100k</option>
            <option value="£100k-£150k">£100k-£150k</option>
            <option value="Over £150k">Over £150k</option>
          </select>
        </label>
      );
    }
    return (
      <label className="detail-row">
        <span className="detail-label">{label}</span>
        <input
          className="detail-edit"
          type={type === 'number' ? 'number' : 'text'}
          value={editForm[key]}
          onChange={e => setEditForm({ ...editForm, [key]: type === 'number' ? (parseInt(e.target.value) || 0) : e.target.value })}
        />
      </label>
    );
  }

  if (loading) {
    return <div className="profile-panel"><p className="panel-loading">Loading...</p></div>;
  }

  const needsSetup = !hasSavedProfile(profile);

  return (
    <div className="profile-panel">

      {/* ── Investor Profile ──────────────────────────── */}
      <div className="panel-section">
        <div className="panel-title-row">
          <h3 className="panel-title">Investor Profile</h3>
          {!needsSetup && !editingProfile && (
            <button className="panel-edit-btn" onClick={startEdit} title="Edit profile">✏️</button>
          )}
        </div>

        {needsSetup && !editingProfile ? (
          <div className="panel-cta">
            <p className="cta-text">
              Your profile is not set up yet. Add your age, risk tolerance, and
              tax band for personalised portfolio analysis.
            </p>
            <button className="cta-btn" onClick={startEdit}>Set Up Profile →</button>
          </div>
        ) : editingProfile ? (
          <div className="profile-details">
            {renderProfileField('Age', 'age', 'number')}
            {renderProfileField('Risk Tolerance', 'risk_tolerance', 'select')}
            {renderProfileField('Tax Band', 'tax_band', 'select')}
            {renderProfileField('Income Band', 'income_band', 'select')}
            {renderProfileField('Horizon', 'investment_horizon', 'text')}
            {renderProfileField('Pension /mo', 'pension_contributions_monthly', 'number')}
            {renderProfileField('ISA /mo', 'isa_contributions_monthly', 'number')}
            <div className="detail-actions">
              <button className="cta-btn" onClick={handleSaveProfile} disabled={saving}>
                {saving ? 'Saving...' : 'Save'}
              </button>
              <button className="cta-btn-secondary" onClick={cancelEdit}>Cancel</button>
            </div>
          </div>
        ) : (
          <div className="profile-details">
            <div className="detail-row">
              <span className="detail-label">Age</span>
              <span className="detail-value">{profile.age}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Risk Tolerance</span>
              <span className="detail-value">{RISK_LABELS[profile.risk_tolerance] || profile.risk_tolerance}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Tax Band</span>
              <span className="detail-value">{TAX_LABELS[profile.tax_band] || profile.tax_band}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Income Band</span>
              <span className="detail-value">{profile.income_band}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Horizon</span>
              <span className="detail-value">{profile.investment_horizon}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Pension</span>
              <span className="detail-value">£{profile.pension_contributions_monthly}/mo</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">ISA</span>
              <span className="detail-value">£{profile.isa_contributions_monthly}/mo</span>
            </div>
          </div>
        )}
      </div>

      {/* ── Accounts ────────────────────────────────────── */}
      <div className="panel-section">
        <div className="panel-title-row">
          <h3 className="panel-title">Accounts</h3>
          {!newAcctForm && (
            <button className="panel-edit-btn" onClick={() => setNewAcctForm(true)} title="Add account">+</button>
          )}
        </div>

        {accounts.length > 0 && (
          <div className="account-list">
            {accounts.map(acct => (
              <div key={acct.id} className="panel-account-item">
                <div>
                  <span className="pa-provider">{acct.provider}</span>
                  <span className="pa-type">{acct.account_type}</span>
                </div>
                <button className="pa-delete" onClick={() => handleDeleteAccount(acct.id)} title="Remove">✕</button>
              </div>
            ))}
          </div>
        )}

        {accounts.length === 0 && !newAcctForm && (
          <div className="panel-cta">
            <p className="cta-text">No accounts added yet.</p>
            <button className="cta-btn" onClick={() => setNewAcctForm(true)}>Add Account →</button>
          </div>
        )}

        {newAcctForm && (
          <div className="new-acct-inline">
            <input className="detail-edit" placeholder="Provider" value={newAcct.provider}
              onChange={e => setNewAcct({ ...newAcct, provider: e.target.value })} />
            <select className="detail-edit" value={newAcct.account_type}
              onChange={e => setNewAcct({ ...newAcct, account_type: e.target.value })}>
              <option value="ISA">ISA</option>
              <option value="SIPP">SIPP</option>
              <option value="GIA">GIA</option>
              <option value="LISA">LISA</option>
            </select>
            <div className="detail-actions">
              <button className="cta-btn" onClick={handleAddAccount}>Add</button>
              <button className="cta-btn-secondary" onClick={() => setNewAcctForm(false)}>Cancel</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ProfilePanel;
