import React, { useEffect, useState } from 'react';
import { getHospitals, createHospital, updateHospital } from '../api';

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
  const [editing,     setEditing]     = useState(null);
  const [editForm,    setEditForm]    = useState(EMPTY);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState('');

  const role = (localStorage.getItem('role') || '').toUpperCase();
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

  const openEdit = (hospital) => {
    setEditing(hospital);
    setEditForm({
      name: hospital.name || '',
      location: hospital.location || '',
      phone: hospital.phone || '',
      email: hospital.email || '',
    });
  };

  const saveEdit = async () => {
    if (!editing) return;
    setError('');
    try {
      const cleanPhone = (editForm.phone || '').replace(/[^0-9]/g, '').replace(/^0+/, '');
      await updateHospital(editing.hospital_id, {
        name: editForm.name,
        location: editForm.location,
        phone: cleanPhone || '',
        email: editForm.email || '',
      });
      setEditing(null);
      setEditForm(EMPTY);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Update failed');
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>🏢 Hospitals</h1>
        <p>Manage hospitals in the system</p>
      </div>

      <div className="graphic-banner">
        <div className="banner-title">Hospital Registry Hub</div>
        <div className="banner-subtitle">Maintain institutional nodes feeding your care network.</div>
        <div className="chip-row">
          <span className="status-chip">Facility Mapping</span>
          <span className="status-chip">Contact Matrix</span>
          <span className="status-chip">Network Ready</span>
        </div>
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
                <th>ID</th><th>Name</th><th>Location</th><th>Phone</th><th>Email</th>{canManage && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {hospitals.length === 0 && (
                <tr><td colSpan={canManage ? 6 : 5} className="empty-state">No hospitals yet.</td></tr>
              )}
              {hospitals.map(h => (
                <tr key={h.hospital_id}>
                  <td>#{h.hospital_id}</td>
                  <td><strong>{h.name}</strong></td>
                  <td>{h.location}</td>
                  <td>{formatPhone(h.phone)}</td>
                  <td>{h.email || '—'}</td>
                  {canManage && (
                    <td>
                      <button className="btn btn-success btn-sm" onClick={() => openEdit(h)}>✏️ Edit</button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editing && (
        <div className="modal-backdrop" onClick={() => setEditing(null)}>
          <div className="modal-card" style={{ padding:24, width:520 }} onClick={e => e.stopPropagation()}>
            <h3 style={{ color:'#e2e8f0', marginTop:0 }}>✏️ Edit Hospital</h3>
            <div className="form-grid" style={{ padding:0 }}>
              <div className="form-group"><label>Name</label><input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} /></div>
              <div className="form-group"><label>Location</label><input value={editForm.location} onChange={e => setEditForm({ ...editForm, location: e.target.value })} /></div>
              <div className="form-group"><label>Phone</label><input value={editForm.phone} onChange={e => setEditForm({ ...editForm, phone: e.target.value })} /></div>
              <div className="form-group"><label>Email</label><input type="email" value={editForm.email} onChange={e => setEditForm({ ...editForm, email: e.target.value })} /></div>
            </div>
            <div style={{ display:'flex', gap:10, marginTop:12 }}>
              <button className="btn btn-success" onClick={saveEdit}>Save Changes</button>
              <button className="btn" style={{ background:'#334155', color:'#e2e8f0' }} onClick={() => setEditing(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
