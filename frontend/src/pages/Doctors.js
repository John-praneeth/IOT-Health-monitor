import React, { useEffect, useState } from 'react';
import { getDoctors, createDoctor, updateDoctor, deleteDoctor, getDoctorPatients, getHospitals } from '../api';

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

const SPECIALIZATIONS = [
  'Cardiology', 'Neurology', 'Pulmonology', 'Orthopedics',
  'Dermatology', 'Pediatrics', 'Oncology', 'General Medicine',
  'Gastroenterology', 'Endocrinology', 'Nephrology', 'Psychiatry',
];

const EMPTY = { name: '', specialization: 'Cardiology', phone: '', email: '', hospital_id: '', is_freelancer: false, is_available: true, username: '', password: '' };

export default function Doctors() {
  const [doctors,     setDoctors]     = useState([]);
  const [hospitals,   setHospitals]   = useState([]);
  const [form,        setForm]        = useState(EMPTY);
  const [countryCode, setCountryCode] = useState('91');
  const [showAdd,     setShowAdd]     = useState(false);
  const [expanded,    setExpanded]    = useState(null);
  const [patients,    setPatients]    = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState('');
  const [specFilter,  setSpecFilter]  = useState('');
  const [editing,     setEditing]     = useState(null);
  const [editForm,    setEditForm]    = useState(EMPTY);

  const role = (localStorage.getItem('role') || '').toUpperCase();
  const myDoctorId = localStorage.getItem('doctor_id');
  const canManage = role === 'ADMIN';

  const load = async () => {
    try {
      const params = specFilter ? { specialization: specFilter } : {};
      const [dRes, hRes] = await Promise.all([getDoctors(params), getHospitals()]);
      setDoctors(dRes.data);
      setHospitals(hRes.data);
    } catch { setError('Failed to load doctors'); }
    finally   { setLoading(false); }
  };

  useEffect(() => { load(); }, [specFilter]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const cleanPhone = form.phone.replace(/[^0-9]/g, '').replace(/^0+/, '');
      await createDoctor({
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
    if (!window.confirm('Delete this doctor?')) return;
    try { await deleteDoctor(id); load(); }
    catch { setError('Delete failed'); }
  };

  const togglePatients = async (id) => {
    if (expanded === id) { setExpanded(null); setPatients([]); return; }
    try {
      const res = await getDoctorPatients(id);
      setPatients(res.data);
      setExpanded(id);
    } catch { setError('Failed to load assigned patients'); }
  };

  const canEditDoctor = (doctorId) => canManage || (role === 'DOCTOR' && String(myDoctorId) === String(doctorId));

  const openEdit = (d) => {
    setEditing(d);
    setEditForm({
      name: d.name || '',
      specialization: d.specialization || 'General Medicine',
      phone: d.phone || '',
      email: d.email || '',
      hospital_id: d.hospital_id ? String(d.hospital_id) : '',
      is_freelancer: !!d.is_freelancer,
      is_available: d.is_available !== false,
      username: '',
      password: '',
    });
  };

  const saveEdit = async () => {
    if (!editing) return;
    setError('');
    try {
      await updateDoctor(editing.doctor_id, {
        name: editForm.name,
        specialization: editForm.specialization,
        hospital_id: editForm.hospital_id ? Number(editForm.hospital_id) : null,
        phone: editForm.phone || null,
        email: editForm.email || null,
        is_freelancer: !!editForm.is_freelancer,
        is_available: !!editForm.is_available,
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
          <div className="main-title">Physician Registry</div>
          <div className="main-subtitle">Staff management and clinical specializations</div>
        </div>
        <div className="topbar-actions">
           {canManage && (
             <button className="btn btn-primary btn-sm" onClick={() => setShowAdd(!showAdd)}>
               {showAdd ? '✕ Close Portal' : '+ Register Physician'}
             </button>
           )}
        </div>
      </div>

      {error && <div style={{ color:'#fca5a5', background: 'rgba(244,63,94,0.1)', padding: 12, borderRadius: 10, marginBottom:16 }}>⚠️ {error}</div>}

      <div className="filter-row" style={{ display: 'flex', gap: 12, marginBottom: 24, alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: '#64748b', fontWeight: 800 }}>SPECIALIZATION:</span>
        <select
          style={{ background:'rgba(0,0,0,0.2)', border:'1px solid rgba(255,255,255,0.1)', color:'#e2e8f0',
                   borderRadius:8, padding:'6px 12px', fontSize:13, outline: 'none' }}
          value={specFilter}
          onChange={e => setSpecFilter(e.target.value)}>
          <option value="">All Physician Groups</option>
          {SPECIALIZATIONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {canManage && showAdd && (
        <div className="card">
          <div className="card-header"><h2>Register New Physician</h2></div>
          <form onSubmit={handleSubmit} style={{ padding: 24 }}>
            <div className="form-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
              <div className="form-group">
                <label>Legal Name</label>
                <input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Dr. Jane Smith" />
              </div>
              <div className="form-group">
                <label>Medical Specialty</label>
                <select value={form.specialization} onChange={e => setForm({ ...form, specialization: e.target.value })}>
                  {SPECIALIZATIONS.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Access Identifier</label>
                <input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} placeholder="e.g. dr.jane" autoComplete="off" />
              </div>
              <div className="form-group">
                <label>Security Key</label>
                <input type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} placeholder="••••••" autoComplete="new-password" disabled={!form.username} />
              </div>
              <div className="form-group">
                <label>Contact Protocol (Phone)</label>
                <div style={{ display: 'flex', gap: 8 }}>
                  <select value={countryCode} onChange={e => setCountryCode(e.target.value)}
                    style={{ width: 'auto' }}>
                    {COUNTRY_CODES.map(c => <option key={c.code} value={c.code}>{c.label}</option>)}
                  </select>
                  <input value={form.phone}
                    onChange={e => setForm({ ...form, phone: e.target.value.replace(/[^0-9]/g, '') })}
                    placeholder="Phone number" style={{ flex: 1 }} />
                </div>
              </div>
              <div className="form-group">
                <label>Email Address</label>
                <input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} placeholder="jane@hospital.com" />
              </div>
              <div className="form-group">
                <label>Hospital Affiliation</label>
                <select value={form.hospital_id} onChange={e => setForm({ ...form, hospital_id: e.target.value })}>
                  <option value="">— Freelancer / External —</option>
                  {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
                </select>
              </div>
              <div className="form-group" style={{ display: 'flex', alignItems: 'center', height: '100%', paddingTop: 20 }}>
                <label style={{ display:'flex', alignItems:'center', gap:10, cursor: 'pointer' }}>
                  <input type="checkbox" checked={form.is_freelancer}
                    style={{ width: 18, height: 18, accentColor: 'var(--primary)' }}
                    onChange={e => setForm({ ...form, is_freelancer: e.target.checked })} />
                  FREELANCE CONTRACTOR
                </label>
              </div>
            </div>
            <div style={{ marginTop: 24, display: 'flex', gap: 12 }}>
              <button type="submit" className="btn btn-primary">Initialize Terminal</button>
              <button type="button" className="btn" style={{ background: 'rgba(255,255,255,0.05)', color: '#94a3b8' }} onClick={() => setShowAdd(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="card-header"><h2>Physician Roster ({doctors.length})</h2></div>
        {loading ? <div className="spinner" /> : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Identity</th><th>Specialty</th><th>Affiliation</th>
                  <th>Contract</th><th>Availability</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {doctors.length === 0 && (
                  <tr><td colSpan={6} className="empty-state">No medical staff records initialized.</td></tr>
                )}
                {doctors.map(d => (
                  <React.Fragment key={d.doctor_id}>
                    <tr>
                      <td>
                        <strong>{d.name}</strong>
                        <div style={{ fontSize: 10, color: '#64748b' }}>TR-#{d.doctor_id}</div>
                      </td>
                      <td>
                        <span className="badge badge-blue">{d.specialization || 'General'}</span>
                      </td>
                      <td>{d.hospital_name || <span style={{ color: '#64748b' }}>— External</span>}</td>
                      <td>
                        {d.is_freelancer
                          ? <span className="badge badge-green">CONTRACT</span>
                          : <span className="badge" style={{ background:'rgba(255,255,255,0.05)', color:'#94a3b8' }}>STAFF</span>
                        }
                      </td>
                      <td>
                        <span style={{ color: d.is_available ? 'var(--success)' : 'var(--danger)', fontWeight: 800, fontSize: 11 }}>
                          {d.is_available ? '📡 ONLINE' : '🔘 BUSY'}
                        </span>
                      </td>
                      <td>
                        <div style={{ display:'flex', gap:6 }}>
                          <button className="btn btn-primary btn-sm" style={{ padding: '4px 10px', fontSize: 11 }} onClick={() => togglePatients(d.doctor_id)}>
                            {expanded === d.doctor_id ? '▲ HIDE' : '▼ WARD'}
                          </button>
                          {canEditDoctor(d.doctor_id) && (
                            <button className="btn btn-success btn-sm" style={{ padding: '4px 8px' }} onClick={() => openEdit(d)}>✏️</button>
                          )}
                          {canManage && (
                            <button className="btn btn-danger btn-sm" style={{ padding: '4px 8px' }} onClick={() => handleDelete(d.doctor_id)}>🗑</button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {expanded === d.doctor_id && (
                      <tr>
                        <td colSpan={6} style={{ background:'rgba(0,0,0,0.2)', padding: 24 }}>
                          <div className="card" style={{ marginBottom: 0, border: '1px dashed var(--stroke)' }}>
                            <div className="card-header" style={{ padding: '12px 20px' }}><h3 style={{ fontSize: 14, margin: 0 }}>Assigned Clinical Ward</h3></div>
                            {patients.length === 0 ? (
                              <div style={{ padding: 20, textAlign: 'center', color: '#64748b', fontSize: 12 }}>No patients currently assigned to this physician.</div>
                            ) : (
                              <table style={{ marginBottom:0 }}>
                                <thead><tr><th>Patient Identity</th><th>Admitted Ward</th><th>Room</th></tr></thead>
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
              <h2>✏️ Update Physician Profile</h2>
              <button onClick={() => setEditing(null)} style={{ background:'none', border:'none', color:'#94a3b8', fontSize:18, cursor:'pointer' }}>✕</button>
            </div>
            <div className="form-grid" style={{ padding: 24, gap: 16 }}>
              <div className="form-group"><label>Full Name</label><input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} /></div>
              <div className="form-group">
                <label>Specialization</label>
                <select value={editForm.specialization} onChange={e => setEditForm({ ...editForm, specialization: e.target.value })}>
                  {SPECIALIZATIONS.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Hospital Affiliation</label>
                <select value={editForm.hospital_id} onChange={e => setEditForm({ ...editForm, hospital_id: e.target.value })}>
                  <option value="">— External —</option>
                  {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
                </select>
              </div>
              <div className="form-group"><label>Contact Phone</label><input value={editForm.phone} onChange={e => setEditForm({ ...editForm, phone: e.target.value })} /></div>
              <div className="form-group"><label>Email Address</label><input value={editForm.email} onChange={e => setEditForm({ ...editForm, email: e.target.value })} /></div>
              <div className="form-group" style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                 <label style={{ display:'flex', gap:8, alignItems:'center', cursor: 'pointer' }}>
                   <input type="checkbox" checked={editForm.is_freelancer} style={{ width: 18, height: 18 }} onChange={e => setEditForm({ ...editForm, is_freelancer: e.target.checked })} />
                   CONTRACTOR
                 </label>
              </div>
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
