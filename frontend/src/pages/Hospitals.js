import React, { useEffect, useState } from 'react';
import { getHospitals, createHospital, updateHospital, deleteHospital } from '../api';

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

  const handleDelete = async (id) => {
    if (!window.confirm('Permanently remove this medical center? Staff and patients will be unassigned.')) return;
    setError('');
    try {
      await deleteHospital(id);
      load();
    } catch (err) { setError(err.response?.data?.detail || 'Delete failed'); }
  };

  return (
    <div style={{ animation: 'reveal 0.4s ease-out' }}>
      <div className="main-topbar">
        <div>
          <div className="main-title">Medical Center Directory</div>
          <div className="main-subtitle">Management of affiliated healthcare facilities and sites</div>
        </div>
        <div className="topbar-actions">
           {canManage && (
             <button className="btn btn-primary btn-sm" onClick={() => setShowAdd(!showAdd)}>
               {showAdd ? '✕ Close Portal' : '+ Register Hospital'}
             </button>
           )}
        </div>
      </div>

      {error && (
        <div className="card" style={{ background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.2)', padding: 12, marginBottom: 20, borderRadius: 12, color: '#fda4af', fontSize: 13 }}>
          ⚠️ {error}
        </div>
      )}

      {canManage && showAdd && (
        <div className="card">
          <div className="card-header"><h2>New Hospital Registration</h2></div>
          <form onSubmit={handleSubmit} style={{ padding: 24 }}>
            <div className="form-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
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
              </div>
              <div className="form-group">
                <label>Email</label>
                <input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} placeholder="info@hospital.com" />
              </div>
            </div>
            <div style={{ marginTop: 24, display: 'flex', gap: 12 }}>
              <button type="submit" className="btn btn-primary">Save Hospital</button>
              <button type="button" className="btn" style={{ background: 'rgba(255,255,255,0.05)', color: '#94a3b8' }} onClick={() => setShowAdd(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="card-header"><h2>All Hospitals ({hospitals.length})</h2></div>
        {loading ? <div className="spinner" /> : (
          <div style={{ overflowX: 'auto' }}>
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
                        <div style={{ display:'flex', gap:6 }}>
                          <button className="btn btn-success btn-sm" style={{ padding: '4px 8px' }} onClick={() => openEdit(h)}>✏️</button>
                          <button className="btn btn-danger btn-sm" style={{ padding: '4px 8px' }} onClick={() => handleDelete(h.hospital_id)}>🗑</button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {editing && (
        <div className="modal-backdrop" onClick={() => setEditing(null)}>
          <div className="card" style={{ width: 500, maxWidth: '95vw' }} onClick={e => e.stopPropagation()}>
            <div className="card-header">
              <h2>✏️ Edit Hospital</h2>
              <button onClick={() => setEditing(null)} style={{ background:'none', border:'none', color:'#94a3b8', fontSize:18, cursor:'pointer' }}>✕</button>
            </div>
            <div className="form-grid" style={{ padding: 24, gap: 16 }}>
              <div className="form-group"><label>Name</label><input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} /></div>
              <div className="form-group"><label>Location</label><input value={editForm.location} onChange={e => setEditForm({ ...editForm, location: e.target.value })} /></div>
              <div className="form-group"><label>Phone</label><input value={editForm.phone} onChange={e => setEditForm({ ...editForm, phone: e.target.value })} /></div>
              <div className="form-group"><label>Email</label><input type="email" value={editForm.email} onChange={e => setEditForm({ ...editForm, email: e.target.value })} /></div>
            </div>
            <div style={{ display:'flex', gap:10, padding: '0 24px 24px' }}>
              <button className="btn btn-primary" onClick={saveEdit}>Save Changes</button>
              <button className="btn" style={{ background:'rgba(255,255,255,0.05)', color:'#e2e8f0' }} onClick={() => setEditing(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
