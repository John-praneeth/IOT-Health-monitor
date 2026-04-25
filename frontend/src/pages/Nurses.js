import React, { useEffect, useState } from 'react';
import { getNurses, createNurse, updateNurse, deleteNurse, getNursePatients, getHospitals } from '../api';

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

const DEPARTMENTS = [
  'ICU', 'Emergency', 'General', 'Cardiology', 'Neurology',
  'Pediatrics', 'Oncology', 'Surgery', 'Orthopedics',
];

const EMPTY = { name: '', department: 'General', phone: '', email: '', hospital_id: '', username: '', password: '' };

export default function Nurses() {
  const [nurses,      setNurses]      = useState([]);
  const [hospitals,   setHospitals]   = useState([]);
  const [form,        setForm]        = useState(EMPTY);
  const [countryCode, setCountryCode] = useState('91');
  const [showAdd,     setShowAdd]     = useState(false);
  const [expanded,  setExpanded]  = useState(null);
  const [patients,  setPatients]  = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState('');
  const [editing,   setEditing]   = useState(null);
  const [editForm,  setEditForm]  = useState(EMPTY);

  const role = (localStorage.getItem('role') || '').toUpperCase();
  const myNurseId = localStorage.getItem('nurse_id');
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
      const cleanPhone = form.phone.replace(/[^0-9]/g, '').replace(/^0+/, '');
      await createNurse({
        ...form,
        phone: cleanPhone ? countryCode + cleanPhone : '',
        hospital_id: form.hospital_id ? parseInt(form.hospital_id) : null,
      });
      setForm(EMPTY);
      setCountryCode('91');
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

  const canEditNurse = (nurseId) => canManage || (role === 'NURSE' && String(myNurseId) === String(nurseId));

  const openEdit = (n) => {
    setEditing(n);
    setEditForm({
      name: n.name || '',
      department: n.department || 'General',
      phone: n.phone || '',
      email: n.email || '',
      hospital_id: n.hospital_id ? String(n.hospital_id) : '',
      username: '',
      password: '',
    });
  };

  const saveEdit = async () => {
    if (!editing) return;
    setError('');
    try {
      await updateNurse(editing.nurse_id, {
        name: editForm.name,
        department: editForm.department,
        hospital_id: editForm.hospital_id ? Number(editForm.hospital_id) : null,
        phone: editForm.phone || null,
        email: editForm.email || null,
      });
      setEditing(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Update failed');
    }
  };

  return (
    <div style={{ animation: 'reveal 0.4s ease-out' }}>
      <div className="main-topbar">
        <div>
          <div className="main-title">Nursing Staff Registry</div>
          <div className="main-subtitle">Care unit assignments and shift management</div>
        </div>
        <div className="topbar-actions">
           {canManage && (
             <button className="btn btn-primary btn-sm" onClick={() => setShowAdd(!showAdd)}>
               {showAdd ? '✕ Close Portal' : '+ Register Nurse'}
             </button>
           )}
        </div>
      </div>

      {error && <div style={{ color:'#fca5a5', background: 'rgba(244,63,94,0.1)', padding: 12, borderRadius: 10, marginBottom:16 }}>⚠️ {error}</div>}

      {canManage && showAdd && (
        <div className="card">
          <div className="card-header"><h2>Register New Nursing Staff</h2></div>
          <form onSubmit={handleSubmit} style={{ padding: 24 }}>
            <div className="form-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
              <div className="form-group">
                <label>Full Legal Name</label>
                <input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Jane Doe" />
              </div>
              <div className="form-group">
                <label>Assigned Department</label>
                <select value={form.department} onChange={e => setForm({ ...form, department: e.target.value })}>
                  {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Access Identifier</label>
                <input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} placeholder="e.g. nurse.jane" autoComplete="off" />
              </div>
              <div className="form-group">
                <label>Security Key</label>
                <input type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} placeholder="••••••" autoComplete="new-password" disabled={!form.username} />
              </div>
              <div className="form-group">
                <label>Primary Phone</label>
                <div style={{ display: 'flex', gap: 8 }}>
                  <select value={countryCode} onChange={e => setCountryCode(e.target.value)} style={{ width: 'auto' }}>
                    {COUNTRY_CODES.map(c => <option key={c.code} value={c.code}>{c.label}</option>)}
                  </select>
                  <input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value.replace(/[^0-9]/g, '') })} placeholder="Phone number" style={{ flex: 1 }} />
                </div>
              </div>
              <div className="form-group">
                <label>Work Email</label>
                <input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} placeholder="jane@hospital.com" />
              </div>
              <div className="form-group">
                <label>Facility Affiliation</label>
                <select value={form.hospital_id} onChange={e => setForm({ ...form, hospital_id: e.target.value })}>
                  <option value="">— Select Site —</option>
                  {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
                </select>
              </div>
            </div>
            <div style={{ marginTop: 24, display: 'flex', gap: 12 }}>
              <button type="submit" className="btn btn-primary">Save Staff Member</button>
              <button type="button" className="btn" style={{ background: 'rgba(255,255,255,0.05)', color: '#94a3b8' }} onClick={() => setShowAdd(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="card-header"><h2>Care Team Roster ({nurses.length})</h2></div>
        {loading ? <div className="spinner" /> : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Identity</th><th>Care Unit</th><th>Assigned Site</th>
                  <th>Contact Registry</th><th>Status</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {nurses.length === 0 && (
                  <tr><td colSpan={6} className="empty-state">No nursing staff records initialized.</td></tr>
                )}
                {nurses.map(n => (
                  <React.Fragment key={n.nurse_id}>
                    <tr>
                      <td>
                        <strong>{n.name}</strong>
                        <div style={{ fontSize: 10, color: '#64748b' }}>ST-#{n.nurse_id}</div>
                      </td>
                      <td>
                        <span className="badge badge-blue">{n.department || 'General'}</span>
                      </td>
                      <td>{n.hospital_name || <span style={{ color: '#64748b' }}>— External</span>}</td>
                      <td>
                         <div style={{ fontSize: 13 }}>{n.phone || '—'}</div>
                         <div style={{ fontSize: 11, color: '#64748b' }}>{n.email || ''}</div>
                      </td>
                      <td>
                        <span style={{ color: 'var(--success)', fontWeight: 800, fontSize: 11 }}>📡 ON-CALL</span>
                      </td>
                      <td>
                        <div style={{ display:'flex', gap:6 }}>
                          <button className="btn btn-primary btn-sm" style={{ padding: '4px 10px', fontSize: 11 }} onClick={() => togglePatients(n.nurse_id)}>
                            {expanded === n.nurse_id ? '▲ HIDE' : '▼ WARD'}
                          </button>
                          {canEditNurse(n.nurse_id) && (
                            <button className="btn btn-success btn-sm" style={{ padding: '4px 8px' }} onClick={() => openEdit(n)}>✏️</button>
                          )}
                          {canManage && (
                            <button className="btn btn-danger btn-sm" style={{ padding: '4px 8px' }} onClick={() => handleDelete(n.nurse_id)}>🗑</button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {expanded === n.nurse_id && (
                      <tr>
                        <td colSpan={6} style={{ background:'rgba(0,0,0,0.2)', padding: 24 }}>
                          <div className="card" style={{ marginBottom: 0, border: '1px dashed var(--stroke)' }}>
                            <div className="card-header" style={{ padding: '12px 20px' }}><h3 style={{ fontSize: 14, margin: 0 }}>Active Care Ward</h3></div>
                            {patients.length === 0 ? (
                              <div style={{ padding: 20, textAlign: 'center', color: '#64748b', fontSize: 12 }}>No patients currently assigned to this staff member.</div>
                            ) : (
                              <table style={{ marginBottom:0 }}>
                                <thead><tr><th>Patient Identity</th><th>Admitted Site</th><th>Room</th></tr></thead>
                                <tbody>
                                  {patients.map(p => (
                                    <tr key={p.patient_id}>
                                      <td>{p.name}</td><td>{p.hospital_name || '—'}</td><td>{p.room_number}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
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
              <h2>✏️ Update Staff Profile</h2>
              <button onClick={() => setEditing(null)} style={{ background:'none', border:'none', color:'#94a3b8', fontSize:18, cursor:'pointer' }}>✕</button>
            </div>
            <div className="form-grid" style={{ padding: 24, gap: 16 }}>
              <div className="form-group"><label>Full Legal Name</label><input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} /></div>
              <div className="form-group">
                <label>Assigned Unit</label>
                <select value={editForm.department} onChange={e => setEditForm({ ...editForm, department: e.target.value })}>
                  {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Facility Affiliation</label>
                <select value={editForm.hospital_id} onChange={e => setEditForm({ ...editForm, hospital_id: e.target.value })}>
                  <option value="">— Select Site —</option>
                  {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
                </select>
              </div>
              <div className="form-group"><label>Primary Phone</label><input value={editForm.phone} onChange={e => setEditForm({ ...editForm, phone: e.target.value })} /></div>
              <div className="form-group"><label>Work Email</label><input value={editForm.email} onChange={e => setEditForm({ ...editForm, email: e.target.value })} /></div>
            </div>
            <div style={{ padding: '0 24px 24px', display: 'flex', gap: 12 }}>
              <button className="btn btn-primary" onClick={saveEdit}>Save Profile</button>
              <button className="btn" style={{ background: 'rgba(255,255,255,0.05)', color: '#94a3b8' }} onClick={() => setEditing(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
