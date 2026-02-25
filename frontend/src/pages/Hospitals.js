import React, { useEffect, useState } from 'react';
import { getHospitals, createHospital } from '../api';

const EMPTY = { name: '', location: '', phone: '', email: '' };

export default function Hospitals() {
  const [hospitals, setHospitals] = useState([]);
  const [form,      setForm]      = useState(EMPTY);
  const [showAdd,   setShowAdd]   = useState(false);
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
      await createHospital(form);
      setForm(EMPTY);
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
                <input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="555-1000" />
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
                  <td>{h.phone || '—'}</td>
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
