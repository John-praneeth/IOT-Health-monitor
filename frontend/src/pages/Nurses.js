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

  const role = localStorage.getItem('role');
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
                <label>Login Username <span style={{ color:'#64748b', fontWeight:400, fontSize:11 }}>(optional — for nurse login access)</span></label>
                <input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} placeholder="e.g. nurse.jane" autoComplete="off" />
              </div>
              <div className="form-group">
                <label>Login Password <span style={{ color:'#64748b', fontWeight:400, fontSize:11 }}>(min 6 chars)</span></label>
                <input type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} placeholder="••••••" autoComplete="new-password" disabled={!form.username} />
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
                    placeholder="9876543210" style={{ flex: 1, minWidth: 0, width: 'auto' }} />
                </div>
                {form.phone.trim() && (
                  <small style={{ color:'#64748b', fontFamily:'monospace' }}>
                    → {countryCode}{form.phone.replace(/^0+/, '')}
                  </small>
                )}
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
                      {canEditNurse(n.nurse_id) && (
                        <button className="btn btn-success btn-sm" onClick={() => openEdit(n)}>✏️ Edit</button>
                      )}
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

      {editing && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.6)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:999 }} onClick={() => setEditing(null)}>
          <div style={{ background:'#1e293b', borderRadius:16, padding:24, width:520, border:'1px solid #334155' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ color:'#e2e8f0', marginTop:0 }}>✏️ Edit Nurse</h3>
            <div className="form-grid" style={{ padding:0 }}>
              <div className="form-group"><label>Name</label><input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} /></div>
              <div className="form-group"><label>Department</label><select value={editForm.department} onChange={e => setEditForm({ ...editForm, department: e.target.value })}>{DEPARTMENTS.map(d => <option key={d}>{d}</option>)}</select></div>
              <div className="form-group"><label>Hospital</label><select value={editForm.hospital_id} onChange={e => setEditForm({ ...editForm, hospital_id: e.target.value })}><option value="">— None —</option>{hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}</select></div>
              <div className="form-group"><label>Phone</label><input value={editForm.phone} onChange={e => setEditForm({ ...editForm, phone: e.target.value })} /></div>
              <div className="form-group"><label>Email</label><input value={editForm.email} onChange={e => setEditForm({ ...editForm, email: e.target.value })} /></div>
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
