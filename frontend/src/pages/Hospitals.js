import React, { useEffect, useState } from 'react';
import { getHospitals, createHospital } from '../api';

const COUNTRY_CODES = [
  { code: '91',  label: '🇮🇳 +91' },
  { code: '1',   label: '🇺🇸 +1' },
  { code: '44',  label: '🇬🇧 +44' },
  { code: '971', label: '🇦🇪 +971' },
  { code: '966', label: '🇸🇦 +966' },
  { code: '61',  label: '🇦🇺 +61' },
  { code: '49',  label: '🇩🇪 +49' },
  { code: '33',  label: '🇫🇷 +33' },
  { code: '81',  label: '🇯🇵 +81' },
  { code: '86',  label: '🇨🇳 +86' },
  { code: '65',  label: '🇸🇬 +65' },
  { code: '60',  label: '🇲🇾 +60' },
  { code: '92',  label: '🇵🇰 +92' },
  { code: '880', label: '🇧🇩 +880' },
  { code: '94',  label: '🇱🇰 +94' },
  { code: '977', label: '🇳🇵 +977' },
];

const EMPTY = { name: '', location: '', phone: '', email: '' };

const formatPhone = (raw) => {
  if (!raw) return '—';
  const digits = String(raw).replace(/\D/g, '');
  if (!digits) return '—';
  return `+${digits}`;
};

export default function Hospitals() {
  const [hospitals,   setHospitals]   = useState([]);
  const [form,        setForm]        = useState(EMPTY);
  const [countryCode, setCountryCode] = useState('91');
  const [showAdd,     setShowAdd]     = useState(false);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState('');

  const role = localStorage.getItem('role');
  const canManage = role === 'ADMIN';

  const load = async () => {
    try {
      const res = await getHospitals();
      setHospitals(res.data);
    } catch { setError('Failed to load hospitals'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const cleanPhone = form.phone.replace(/[^0-9]/g, '').replace(/^0+/, '');
      await createHospital({
        ...form,
        phone: cleanPhone ? countryCode + cleanPhone : '',
      });
      setForm(EMPTY);
      setCountryCode('91');
      setShowAdd(false);
      load();
    } catch (err) { setError(err.response?.data?.detail || 'Create failed'); }
  };

  return (
    <div>
      <div className="page-header">
        <h1>🏢 Hospitals</h1>
        <p>Manage hospitals in the system</p>
      </div>

      {error && <div style={{ color:'#f87171', marginBottom:16 }}>⚠️ {error}</div>}

      {canManage && (
        <button className="btn btn-primary" style={{ marginBottom:16 }} onClick={() => setShowAdd(!showAdd)}>
          {showAdd ? '✕ Cancel' : '+ Add Hospital'}
        </button>
      )}

      {canManage && showAdd && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header"><h2>New Hospital</h2></div>
          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              <div className="form-group">
                <label>Hospital Name</label>
                <input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="City General Hospital" />
              </div>
              <div className="form-group">
                <label>Location</label>
                <input required value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} placeholder="Downtown" />
              </div>
              <div className="form-group">
                <label>Phone</label>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <select value={countryCode} onChange={e => setCountryCode(e.target.value)}
                    style={{ width: 'auto', flexShrink: 0 }}>
                    {COUNTRY_CODES.map(c => <option key={c.code} value={c.code}>{c.label}</option>)}
                  </select>
                  <input value={form.phone}
                    onChange={e => setForm({ ...form, phone: e.target.value.replace(/[^0-9]/g, '') })}
                    placeholder="4023607777" style={{ flex: 1, minWidth: 0, width: 'auto' }} />
                </div>
                {form.phone.trim() && (
                  <small style={{ color:'#64748b', fontFamily:'monospace' }}>
                    → +{countryCode}{form.phone.replace(/^0+/, '')}
                  </small>
                )}
              </div>
              <div className="form-group">
                <label>Email</label>
                <input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} placeholder="info@hospital.com" />
              </div>
            </div>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary">Save Hospital</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="card-header"><h2>All Hospitals ({hospitals.length})</h2></div>
        {loading ? <div className="spinner" /> : (
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Name</th><th>Location</th><th>Phone</th><th>Email</th>
              </tr>
            </thead>
            <tbody>
              {hospitals.length === 0 && (
                <tr><td colSpan={5} className="empty-state">No hospitals yet.</td></tr>
              )}
              {hospitals.map(h => (
                <tr key={h.hospital_id}>
                  <td>#{h.hospital_id}</td>
                  <td><strong>{h.name}</strong></td>
                  <td>{h.location}</td>
                  <td>{formatPhone(h.phone)}</td>
                  <td>{h.email || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
