import React, { useEffect, useState } from 'react';
import { getNurses, createNurse, deleteNurse, getNursePatients, getHospitals } from '../api';

const DEPARTMENTS = [
  'ICU', 'Emergency', 'General', 'Cardiology', 'Neurology',
  'Pediatrics', 'Oncology', 'Surgery', 'Orthopedics',
];

const EMPTY = { name: '', department: 'General', phone: '', email: '', hospital_id: '' };

export default function Nurses() {
  const [nurses,    setNurses]    = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [form,      setForm]      = useState(EMPTY);
  const [showAdd,   setShowAdd]   = useState(false);
  const [expanded,  setExpanded]  = useState(null);
  const [patients,  setPatients]  = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState('');

  const role = localStorage.getItem('role');
  const canManage = role === 'ADMIN' || role === 'DOCTOR';

  const load = async () => {
    try {
      const [nRes, hRes] = await Promise.all([getNurses(), getHospitals()]);
      setNurses(nRes.data);
      setHospitals(hRes.data);
    } catch { setError('Failed to load nurses'); }
    finally   { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await createNurse({
        ...form,
        hospital_id: form.hospital_id ? parseInt(form.hospital_id) : null,
      });
      setForm(EMPTY);
      setShowAdd(false);
      load();
    } catch (err) { setError(err.response?.data?.detail || 'Create failed'); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this nurse?')) return;
    try { await deleteNurse(id); load(); }
    catch { setError('Delete failed'); }
  };

  const togglePatients = async (id) => {
    if (expanded === id) { setExpanded(null); setPatients([]); return; }
    try {
      const res = await getNursePatients(id);
      setPatients(res.data);
      setExpanded(id);
    } catch { setError('Failed to load assigned patients'); }
  };

  return (
    <div>
      <div className="page-header">
        <h1>👩‍⚕️ Nurses</h1>
        <p>Manage nurses and view their assigned patients</p>
      </div>

      {error && <div style={{ color:'#f87171', marginBottom:16 }}>⚠️ {error}</div>}

      {canManage && (
        <button className="btn btn-primary" style={{ marginBottom:16 }} onClick={() => setShowAdd(!showAdd)}>
          {showAdd ? '✕ Cancel' : '+ Add Nurse'}
        </button>
      )}

      {canManage && showAdd && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header"><h2>New Nurse</h2></div>
          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              <div className="form-group">
                <label>Full Name</label>
                <input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Jane Doe" />
              </div>
              <div className="form-group">
                <label>Department</label>
                <select value={form.department} onChange={e => setForm({ ...form, department: e.target.value })}>
                  {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Phone</label>
                <input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="+1-555-0200" />
              </div>
              <div className="form-group">
                <label>Email</label>
                <input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} placeholder="jane@hospital.com" />
              </div>
              <div className="form-group">
                <label>Hospital</label>
                <select value={form.hospital_id} onChange={e => setForm({ ...form, hospital_id: e.target.value })}>
                  <option value="">— None —</option>
                  {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
                </select>
              </div>
            </div>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary">Save Nurse</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="card-header"><h2>All Nurses ({nurses.length})</h2></div>
        {loading ? <div className="spinner" /> : (
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Name</th><th>Department</th><th>Hospital</th>
                <th>Phone</th><th>Email</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {nurses.length === 0 && (
                <tr><td colSpan={7} className="empty-state">No nurses yet.</td></tr>
              )}
              {nurses.map(n => (
                <React.Fragment key={n.nurse_id}>
                  <tr>
                    <td>#{n.nurse_id}</td>
                    <td><strong>{n.name}</strong></td>
                    <td>
                      {n.department ? (
                        <span className="badge badge-blue">{n.department}</span>
                      ) : '—'}
                    </td>
                    <td>{n.hospital_name || '—'}</td>
                    <td>{n.phone || '—'}</td>
                    <td>{n.email || '—'}</td>
                    <td style={{ display:'flex', gap:6 }}>
                      <button className="btn btn-primary btn-sm" onClick={() => togglePatients(n.nurse_id)}>
                        {expanded === n.nurse_id ? '▲ Hide' : '▼ Patients'}
                      </button>
                      {canManage && (
                        <button className="btn btn-danger btn-sm" onClick={() => handleDelete(n.nurse_id)}>🗑</button>
                      )}
                    </td>
                  </tr>
                  {expanded === n.nurse_id && (
                    <tr>
                      <td colSpan={7} style={{ background:'#1e293b', padding:16 }}>
                        {patients.length === 0 ? (
                          <em style={{ color:'#94a3b8' }}>No patients assigned to this nurse.</em>
                        ) : (
                          <table style={{ marginBottom:0 }}>
                            <thead><tr><th>Patient</th><th>Age</th><th>Room</th></tr></thead>
                            <tbody>
                              {patients.map(p => (
                                <tr key={p.patient_id}>
                                  <td>{p.name}</td><td>{p.age}</td><td>{p.room_number}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
