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
    <div>
      <div className="page-header">
        <h1>👨‍⚕️ Doctors</h1>
        <p>Manage doctors — freelancer & hospital-based</p>
      </div>

      <div className="graphic-banner">
        <div className="banner-title">Doctor Network Control</div>
        <div className="banner-subtitle">Specialization matrix, coverage, and assignment visibility in one place.</div>
        <div className="chip-row">
          <span className="status-chip">Specialty Pool</span>
          <span className="status-chip">Freelancer Mix</span>
          <span className="status-chip">Availability</span>
        </div>
      </div>

      {error && <div style={{ color:'#f87171', marginBottom:16 }}>⚠️ {error}</div>}

      <div className="filter-row">
        {canManage && (
          <button className="btn btn-primary" onClick={() => setShowAdd(!showAdd)}>
            {showAdd ? '✕ Cancel' : '+ Add Doctor'}
          </button>
        )}
        <select
          style={{ background:'#1e293b', border:'1px solid #334155', color:'#e2e8f0',
                   borderRadius:8, padding:'8px 12px', fontSize:13 }}
          value={specFilter}
          onChange={e => setSpecFilter(e.target.value)}>
          <option value="">All Specializations</option>
          {SPECIALIZATIONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {canManage && showAdd && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header"><h2>New Doctor</h2></div>
          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              <div className="form-group">
                <label>Full Name</label>
                <input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Dr. Jane Smith" />
              </div>
              <div className="form-group">
                <label>Specialization</label>
                <select value={form.specialization} onChange={e => setForm({ ...form, specialization: e.target.value })}>
                  {SPECIALIZATIONS.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Login Username <span style={{ color:'#64748b', fontWeight:400, fontSize:11 }}>(optional — for doctor login access)</span></label>
                <input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} placeholder="e.g. dr.jane" autoComplete="off" />
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
                  <option value="">— None (Freelancer) —</option>
                  {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label style={{ display:'flex', alignItems:'center', gap:8 }}>
                  <input type="checkbox" checked={form.is_freelancer}
                    onChange={e => setForm({ ...form, is_freelancer: e.target.checked })} />
                  Freelancer
                </label>
              </div>
            </div>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary">Save Doctor</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="card-header"><h2>All Doctors ({doctors.length})</h2></div>
        {loading ? <div className="spinner" /> : (
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Name</th><th>Specialization</th><th>Hospital</th>
                <th>Type</th><th>Status</th><th>Phone</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {doctors.length === 0 && (
                <tr><td colSpan={8} className="empty-state">No doctors found.</td></tr>
              )}
              {doctors.map(d => (
                <React.Fragment key={d.doctor_id}>
                  <tr>
                    <td>#{d.doctor_id}</td>
                    <td><strong>{d.name}</strong></td>
                    <td>
                      {d.specialization ? (
                        <span className="badge badge-blue">{d.specialization}</span>
                      ) : '—'}
                    </td>
                    <td>{d.hospital_name || '—'}</td>
                    <td>
                      {d.is_freelancer
                        ? <span className="badge badge-green">🟢 Freelancer</span>
                        : <span className="badge" style={{ background:'#334155', color:'#94a3b8' }}>Hospital</span>
                      }
                    </td>
                    <td>
                      {d.is_available
                        ? <span style={{ color:'#34d399' }}>Available</span>
                        : <span style={{ color:'#f87171' }}>Unavailable</span>
                      }
                    </td>
                    <td>{d.phone || '—'}</td>
                    <td style={{ display:'flex', gap:6 }}>
                      <button className="btn btn-primary btn-sm" onClick={() => togglePatients(d.doctor_id)}>
                        {expanded === d.doctor_id ? '▲ Hide' : '▼ Patients'}
                      </button>
                      {canEditDoctor(d.doctor_id) && (
                        <button className="btn btn-success btn-sm" onClick={() => openEdit(d)}>✏️ Edit</button>
                      )}
                      {canManage && (
                        <button className="btn btn-danger btn-sm" onClick={() => handleDelete(d.doctor_id)}>🗑</button>
                      )}
                    </td>
                  </tr>
                  {expanded === d.doctor_id && (
                    <tr>
                      <td colSpan={8} style={{ background:'#1e293b', padding:16 }}>
                        {patients.length === 0 ? (
                          <em style={{ color:'#94a3b8' }}>No patients assigned to this doctor.</em>
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
        <div className="modal-backdrop" onClick={() => setEditing(null)}>
          <div className="modal-card" style={{ padding:24, width:520 }} onClick={e => e.stopPropagation()}>
            <h3 style={{ color:'#e2e8f0', marginTop:0 }}>✏️ Edit Doctor</h3>
            <div className="form-grid" style={{ padding:0 }}>
              <div className="form-group"><label>Name</label><input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} /></div>
              <div className="form-group"><label>Specialization</label><select value={editForm.specialization} onChange={e => setEditForm({ ...editForm, specialization: e.target.value })}>{SPECIALIZATIONS.map(s => <option key={s}>{s}</option>)}</select></div>
              <div className="form-group"><label>Hospital</label><select value={editForm.hospital_id} onChange={e => setEditForm({ ...editForm, hospital_id: e.target.value })}><option value="">— None —</option>{hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}</select></div>
              <div className="form-group"><label>Phone</label><input value={editForm.phone} onChange={e => setEditForm({ ...editForm, phone: e.target.value })} /></div>
              <div className="form-group"><label>Email</label><input value={editForm.email} onChange={e => setEditForm({ ...editForm, email: e.target.value })} /></div>
              <div className="form-group"><label style={{ display:'flex', gap:8, alignItems:'center' }}><input type="checkbox" checked={editForm.is_freelancer} onChange={e => setEditForm({ ...editForm, is_freelancer: e.target.checked })} />Freelancer</label></div>
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
