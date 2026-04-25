import React, { useEffect, useState } from 'react';
import { getPatients, createPatient, updatePatient, deletePatient, getHospitals, getDoctors, getNurses, assignDoctor, assignNurse, getLatestVital } from '../api';
import PatientChat from './PatientChat';

const EMPTY_FORM = { name: '', age: '', room_number: '', hospital_id: '', assigned_doctor: '', assigned_nurse: '' };

export default function Patients() {
  const [patients,  setPatients]  = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [doctors,   setDoctors]   = useState([]);
  const [nurses,    setNurses]    = useState([]);
  const [form,      setForm]      = useState(EMPTY_FORM);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState('');
  const [showAdd,   setShowAdd]   = useState(false);
  const [chatPatient, setChatPatient] = useState(null);
  const [vitalsModal, setVitalsModal] = useState(null); // { patient, vitals }
  const [specFilter, setSpecFilter] = useState('');
  const [editingPatient, setEditingPatient] = useState(null);
  const [editForm, setEditForm] = useState(EMPTY_FORM);

  const role = (localStorage.getItem('role') || '').toUpperCase();
  const canCreate = role === 'ADMIN' || role === 'DOCTOR';
  const canEdit = role === 'ADMIN' || role === 'DOCTOR' || role === 'NURSE';
  const canAssignDoctor = role === 'ADMIN' || role === 'DOCTOR';
  const canAssignNurse = role === 'ADMIN' || role === 'DOCTOR' || role === 'NURSE';
  const canDelete = role === 'ADMIN' || role === 'DOCTOR';

  const load = async () => {
    try {
      const [pRes, hRes, dRes, nRes] = await Promise.all([
        getPatients(), getHospitals(), getDoctors(), getNurses()
      ]);
      setPatients(pRes.data);
      setHospitals(hRes.data);
      setDoctors(dRes.data);
      setNurses(nRes.data);
    } catch { setError('Failed to load data. Is the backend running?'); }
    finally   { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  // Filter doctors/nurses by selected hospital in the Add Patient form
  const formDoctors = form.hospital_id
    ? doctors.filter(d => String(d.hospital_id) === String(form.hospital_id) || d.is_freelancer)
    : doctors;
  const formNurses = form.hospital_id
    ? nurses.filter(n => String(n.hospital_id) === String(form.hospital_id))
    : nurses;

  // Filter doctors by specialization for the assign dropdown
  const filteredDoctors = specFilter
    ? doctors.filter(d => d.specialization === specFilter)
    : doctors;

  // Get unique specializations
  const specializations = [...new Set(doctors.map(d => d.specialization).filter(Boolean))];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await createPatient({
        ...form,
        age:             parseInt(form.age),
        hospital_id:     form.hospital_id     ? parseInt(form.hospital_id)     : null,
        assigned_doctor: form.assigned_doctor ? parseInt(form.assigned_doctor) : null,
        assigned_nurse:  form.assigned_nurse  ? parseInt(form.assigned_nurse)  : null,
      });
      setForm(EMPTY_FORM);
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create patient');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this patient?')) return;
    try {
      await deletePatient(id);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Delete failed');
    }
  };

  const handleAssignDoctor = async (patientId, doctorId) => {
    try {
      const parsedDoctorId = doctorId ? parseInt(doctorId, 10) : null;
      await assignDoctor(patientId, parsedDoctorId);
      load();
    } catch (err) { setError('Failed to assign doctor'); }
  };

  const handleAssignNurse = async (patientId, nurseId) => {
    try {
      const parsedNurseId = nurseId ? parseInt(nurseId, 10) : null;
      await assignNurse(patientId, parsedNurseId);
      load();
    } catch (err) { setError('Failed to assign nurse'); }
  };

  const showVitals = async (patient) => {
    try {
      const res = await getLatestVital(patient.patient_id);
      setVitalsModal({ patient, vitals: res.data });
    } catch {
      setVitalsModal({ patient, vitals: null });
    }
  };

  const openEdit = (patient) => {
    setEditingPatient(patient);
    setEditForm({
      name: patient.name || '',
      age: String(patient.age ?? ''),
      room_number: patient.room_number || '',
      hospital_id: patient.hospital_id ? String(patient.hospital_id) : '',
      assigned_doctor: patient.assigned_doctor ? String(patient.assigned_doctor) : '',
      assigned_nurse: patient.assigned_nurse ? String(patient.assigned_nurse) : '',
    });
  };

  const saveEdit = async () => {
    if (!editingPatient) return;
    setError('');
    try {
      await updatePatient(editingPatient.patient_id, {
        name: editForm.name,
        age: Number(editForm.age),
        room_number: editForm.room_number,
        hospital_id: editForm.hospital_id === '' ? null : Number(editForm.hospital_id),
        assigned_doctor: editForm.assigned_doctor === '' ? null : Number(editForm.assigned_doctor),
        assigned_nurse: editForm.assigned_nurse === '' ? null : Number(editForm.assigned_nurse),
      });
      setEditingPatient(null);
      setEditForm(EMPTY_FORM);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update patient');
    }
  };

  return (
    <div style={{ animation: 'reveal 0.4s ease-out' }}>
      <div className="main-topbar">
        <div>
          <div className="main-title">Patient Directory</div>
          <div className="main-subtitle">Directory of clinical admissions and assignments</div>
        </div>
        <div className="topbar-actions">
           {canCreate && (
             <button className="btn btn-primary btn-sm" onClick={() => setShowAdd(!showAdd)}>
               {showAdd ? '✕ Close Portal' : '+ Register Patient'}
             </button>
           )}
        </div>
      </div>

      {error && (
        <div className="card" style={{ background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.2)', padding: 12, marginBottom: 20, borderRadius: 12, color: '#fda4af', fontSize: 13 }}>
          ⚠️ {error}
        </div>
      )}

      {/* Add Patient Form */}
      {canCreate && showAdd && (
        <div className="card">
          <div className="card-header"><h2>New Patient Registration</h2></div>
          <form onSubmit={handleSubmit}>
            <div className="form-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, padding: 24 }}>
              {[
                { key:'name',        label:'Full Name',   type:'text',   required:true },
                { key:'age',         label:'Age',         type:'number', required:true },
                { key:'room_number', label:'Room No.',    type:'text',   required:true },
              ].map(f => (
                <div className="form-group" key={f.key}>
                  <label>{f.label}</label>
                  <input type={f.type} required={!!f.required} value={form[f.key]}
                    onChange={e => setForm({ ...form, [f.key]: e.target.value })} placeholder={f.label} />
                </div>
              ))}
              <div className="form-group">
                <label>Hospital</label>
                <select value={form.hospital_id} onChange={e => setForm({ ...form, hospital_id: e.target.value, assigned_doctor: '', assigned_nurse: '' })}>
                  <option value="">— Select Site —</option>
                  {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Assign Doctor</label>
                <select value={form.assigned_doctor} onChange={e => setForm({ ...form, assigned_doctor: e.target.value })}>
                  <option value="">— Not Assigned —</option>
                  {formDoctors.map(d => <option key={d.doctor_id} value={d.doctor_id}>{d.name} ({d.specialization || 'N/A'})</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Assign Nurse</label>
                <select value={form.assigned_nurse} onChange={e => setForm({ ...form, assigned_nurse: e.target.value })}>
                  <option value="">— Not Assigned —</option>
                  {formNurses.map(n => <option key={n.nurse_id} value={n.nurse_id}>{n.name}</option>)}
                </select>
              </div>
            </div>
            <div style={{ padding: '0 24px 24px', display: 'flex', gap: 12 }}>
              <button type="submit" className="btn btn-primary">Initialize Patient Record</button>
              <button type="button" className="btn" style={{ background: 'rgba(255,255,255,0.05)', color: '#94a3b8' }} onClick={() => setShowAdd(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Table */}
      <div className="card">
        <div className="card-header">
          <h2>Clinical Directory ({patients.length})</h2>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ fontSize: 11, color: '#64748b', fontWeight: 800 }}>FILTER:</span>
            <select
              style={{ background:'rgba(0,0,0,0.2)', border:'1px solid rgba(255,255,255,0.1)', color:'#e2e8f0',
                       borderRadius:8, padding:'4px 10px', fontSize:12, outline: 'none' }}
              value={specFilter}
              onChange={e => setSpecFilter(e.target.value)}>
              <option value="">All Specializations</option>
              {specializations.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>
        {loading ? <div className="spinner" /> : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>ID</th><th>Name</th><th>Age</th><th>Room</th>
                  <th>Hospital</th><th>Primary Physician</th><th>Assigned Nurse</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {patients.length === 0 && (
                  <tr><td colSpan={8} className="empty-state">No active patient records found.</td></tr>
                )}
                {patients.map(p => (
                  <tr key={p.patient_id}>
                    <td><span style={{ color: '#64748b', fontWeight: 700 }}>#{p.patient_id}</span></td>
                    <td><strong>{p.name}</strong></td>
                    <td>{p.age}</td>
                    <td><span className="badge badge-blue" style={{ background: 'rgba(34, 211, 238, 0.05)' }}>{p.room_number}</span></td>
                    <td>{p.hospital_name || '—'}</td>
                    <td>
                      {canAssignDoctor ? (
                        <select className="inline-select" style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.05)', color: '#fff', fontSize: 12, padding: '4px 8px' }}
                          value={p.assigned_doctor || ''}
                          onChange={e => handleAssignDoctor(p.patient_id, e.target.value)}>
                          <option value="">— Unassigned —</option>
                          {doctors
                            .filter(d => !specFilter || d.specialization === specFilter || String(d.doctor_id) === String(p.assigned_doctor))
                            .map(d => (
                            <option key={d.doctor_id} value={d.doctor_id}>
                              {d.name} ({d.specialization || 'N/A'})
                            </option>
                          ))}
                        </select>
                      ) : (
                        <span>{p.doctor_name || '—'}</span>
                      )}
                    </td>
                    <td>
                      {canAssignNurse ? (
                        <select className="inline-select" style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.05)', color: '#fff', fontSize: 12, padding: '4px 8px' }}
                          value={p.assigned_nurse || ''}
                          onChange={e => handleAssignNurse(p.patient_id, e.target.value)}>
                          <option value="">— Unassigned —</option>
                          {nurses.map(n => <option key={n.nurse_id} value={n.nurse_id}>{n.name}</option>)}
                        </select>
                      ) : (
                        <span>{p.nurse_name || '—'}</span>
                      )}
                    </td>
                    <td>
                      <div style={{ display:'flex', gap:6 }}>
                        <button className="btn btn-primary btn-sm" style={{ padding: '4px 8px', fontSize: 11 }}
                          onClick={() => showVitals(p)} title="Latest Vitals">💓</button>
                        <button className="btn btn-primary btn-sm" style={{ padding: '4px 8px', fontSize: 11 }}
                          onClick={() => setChatPatient({ patient_id: p.patient_id, name: p.name })} title="Patient Chat">💬</button>
                        {canEdit && (
                          <button className="btn btn-success btn-sm" style={{ padding: '4px 8px', fontSize: 11 }} onClick={() => openEdit(p)}>✏️</button>
                        )}
                        {canDelete && (
                          <button className="btn btn-danger btn-sm" style={{ padding: '4px 8px', fontSize: 11 }} onClick={() => handleDelete(p.patient_id)}>🗑</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Vitals Modal */}
      {vitalsModal && (
        <div className="modal-backdrop" onClick={() => setVitalsModal(null)}>
          <div className="card" style={{ width: 400, maxWidth: '90vw' }} onClick={e => e.stopPropagation()}>
            <div className="card-header">
              <h2>💓 {vitalsModal.patient.name}</h2>
              <button onClick={() => setVitalsModal(null)} style={{ background:'none', border:'none', color:'#94a3b8', fontSize:18, cursor:'pointer' }}>✕</button>
            </div>
            <div style={{ padding: 24 }}>
              {vitalsModal.vitals ? (
                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12 }}>
                  <div style={{ background:'rgba(0,0,0,0.2)', borderRadius:12, padding:16, textAlign:'center', border: '1px solid rgba(255,255,255,0.05)' }}>
                    <div style={{ fontSize:10, color:'#94a3b8', fontWeight: 800 }}>HEART RATE</div>
                    <div style={{ fontSize:24, fontWeight:800, color: vitalsModal.vitals.heart_rate > 110 || vitalsModal.vitals.heart_rate < 50 ? '#f43f5e' : '#34d399', marginTop: 4 }}>
                      {vitalsModal.vitals.heart_rate} <span style={{ fontSize:11, opacity: 0.6 }}>BPM</span>
                    </div>
                  </div>
                  <div style={{ background:'rgba(0,0,0,0.2)', borderRadius:12, padding:16, textAlign:'center', border: '1px solid rgba(255,255,255,0.05)' }}>
                    <div style={{ fontSize:10, color:'#94a3b8', fontWeight: 800 }}>SPO₂</div>
                    <div style={{ fontSize:24, fontWeight:800, color: vitalsModal.vitals.spo2 < 90 ? '#f43f5e' : '#34d399', marginTop: 4 }}>
                      {vitalsModal.vitals.spo2}<span style={{ fontSize:11, opacity: 0.6 }}>%</span>
                    </div>
                  </div>
                  <div style={{ background:'rgba(0,0,0,0.2)', borderRadius:12, padding:16, textAlign:'center', border: '1px solid rgba(255,255,255,0.05)', gridColumn: 'span 2' }}>
                    <div style={{ fontSize:10, color:'#94a3b8', fontWeight: 800 }}>BODY TEMPERATURE</div>
                    <div style={{ fontSize:24, fontWeight:800, color: vitalsModal.vitals.temperature > 101 ? '#fbbf24' : '#f1f5f9', marginTop: 4 }}>
                      {vitalsModal.vitals.temperature}<span style={{ fontSize:11, opacity: 0.6 }}>°F</span>
                    </div>
                  </div>
                </div>
              ) : (
                <p style={{ color:'#64748b', textAlign:'center', padding: 20 }}>No clinical data available for this session.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Chat Modal */}
      {chatPatient && (
        <PatientChat
          patientId={chatPatient.patient_id}
          patientName={chatPatient.name}
          onClose={() => setChatPatient(null)}
        />
      )}

      {/* Edit Modal */}
      {editingPatient && (
        <div className="modal-backdrop" onClick={() => setEditingPatient(null)}>
          <div className="card" style={{ width: 500, maxWidth: '95vw' }} onClick={e => e.stopPropagation()}>
            <div className="card-header">
              <h2>✏️ Update Patient Record</h2>
              <button onClick={() => setEditingPatient(null)} style={{ background:'none', border:'none', color:'#94a3b8', fontSize:18, cursor:'pointer' }}>✕</button>
            </div>
            <div className="form-grid" style={{ padding: 24, gap: 16 }}>
              <div className="form-group"><label>Full Name</label><input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} /></div>
              <div className="form-group"><label>Age</label><input type="number" value={editForm.age} onChange={e => setEditForm({ ...editForm, age: e.target.value })} /></div>
              <div className="form-group"><label>Room Number</label><input value={editForm.room_number} onChange={e => setEditForm({ ...editForm, room_number: e.target.value })} /></div>
              <div className="form-group">
                <label>Hospital Site</label>
                <select value={editForm.hospital_id} onChange={e => setEditForm({ ...editForm, hospital_id: e.target.value, assigned_doctor: '', assigned_nurse: '' })}>
                  <option value="">— None —</option>
                  {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Primary Doctor</label>
                <select value={editForm.assigned_doctor} onChange={e => setEditForm({ ...editForm, assigned_doctor: e.target.value })}>
                  <option value="">— Not Assigned —</option>
                  {(editForm.hospital_id ? doctors.filter(d => String(d.hospital_id) === String(editForm.hospital_id) || d.is_freelancer || String(d.doctor_id) === editForm.assigned_doctor) : doctors)
                    .map(d => <option key={d.doctor_id} value={d.doctor_id}>{d.name}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>On-Call Nurse</label>
                <select value={editForm.assigned_nurse} onChange={e => setEditForm({ ...editForm, assigned_nurse: e.target.value })}>
                  <option value="">— Not Assigned —</option>
                  {(editForm.hospital_id ? nurses.filter(n => String(n.hospital_id) === String(editForm.hospital_id) || String(n.nurse_id) === editForm.assigned_nurse) : nurses)
                    .map(n => <option key={n.nurse_id} value={n.nurse_id}>{n.name}</option>)}
                </select>
              </div>
            </div>
            <div style={{ padding: '0 24px 24px', display: 'flex', gap: 12 }}>
              <button className="btn btn-primary" onClick={saveEdit}>Commit Changes</button>
              <button className="btn" style={{ background: 'rgba(255,255,255,0.05)', color: '#94a3b8' }} onClick={() => setEditingPatient(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
