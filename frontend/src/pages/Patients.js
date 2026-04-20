import React, { useEffect, useState } from 'react';
import { getPatients, createPatient, deletePatient, getHospitals, getDoctors, getNurses, assignDoctor, assignNurse, getLatestVital } from '../api';
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

  const role = localStorage.getItem('role');
  const canManage = role === 'ADMIN' || role === 'DOCTOR' || role === 'NURSE';
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

  return (
    <div>
      <div className="page-header">
        <h1>Patients</h1>
        <p>Manage patients, assign specialist doctors & nurses</p>
      </div>

      {error && <div style={{ color:'#f87171', marginBottom:16 }}>⚠️ {error}</div>}

      <div style={{ marginBottom: 16, display:'flex', gap:10, flexWrap:'wrap' }}>
        {canManage && (
          <button className="btn btn-primary" onClick={() => setShowAdd(!showAdd)}>
            {showAdd ? '✕ Cancel' : '+ Add Patient'}
          </button>
        )}
      </div>

      {/* Add Patient Form */}
      {canManage && showAdd && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header"><h2>New Patient</h2></div>
          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              {[
                { key:'name',        label:'Full Name',   type:'text',   required:true },
                { key:'age',         label:'Age',         type:'number', required:true },
                { key:'room_number', label:'Room Number', type:'text',   required:true },
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
                  <option value="">— None —</option>
                  {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Assign Doctor {form.hospital_id && <span style={{ color:'#64748b', fontWeight:400, fontSize:11 }}>(filtered by hospital)</span>}</label>
                <select value={form.assigned_doctor} onChange={e => setForm({ ...form, assigned_doctor: e.target.value })}>
                  <option value="">— None —</option>
                  {formDoctors.map(d => <option key={d.doctor_id} value={d.doctor_id}>{d.name} ({d.specialization || 'N/A'})</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Assign Nurse {form.hospital_id && <span style={{ color:'#64748b', fontWeight:400, fontSize:11 }}>(filtered by hospital)</span>}</label>
                <select value={form.assigned_nurse} onChange={e => setForm({ ...form, assigned_nurse: e.target.value })}>
                  <option value="">— None —</option>
                  {formNurses.map(n => <option key={n.nurse_id} value={n.nurse_id}>{n.name}</option>)}
                </select>
              </div>
            </div>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary">Save Patient</button>
            </div>
          </form>
        </div>
      )}

      {/* Specialization filter for doctor assignment */}
      <div style={{ marginBottom: 16, display:'flex', gap:10, alignItems:'center' }}>
        <span style={{ color: '#94a3b8', fontSize: 13 }}>Filter doctors by specialization:</span>
        <select
          style={{ background:'#1e293b', border:'1px solid #334155', color:'#e2e8f0',
                   borderRadius:8, padding:'6px 10px', fontSize:13 }}
          value={specFilter}
          onChange={e => setSpecFilter(e.target.value)}>
          <option value="">All Specializations</option>
          {specializations.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {/* Table */}
      <div className="card">
        <div className="card-header">
          <h2>All Patients ({patients.length})</h2>
        </div>
        {loading ? <div className="spinner" /> : (
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Name</th><th>Age</th><th>Room</th>
                <th>Hospital</th><th>Doctor</th><th>Nurse</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {patients.length === 0 && (
                <tr><td colSpan={8} className="empty-state">No patients yet. Add one above.</td></tr>
              )}
              {patients.map(p => (
                <tr key={p.patient_id}>
                  <td>#{p.patient_id}</td>
                  <td><strong>{p.name}</strong></td>
                  <td>{p.age}</td>
                  <td>{p.room_number}</td>
                  <td>{p.hospital_name || '—'}</td>
                  <td>
                    {canManage ? (
                      <select className="inline-select" value={p.assigned_doctor || ''}
                        onChange={e => handleAssignDoctor(p.patient_id, e.target.value)}>
                        <option value="">— None —</option>
                        {filteredDoctors.map(d => (
                          <option key={d.doctor_id} value={d.doctor_id}>
                            {d.name} ({d.specialization || 'N/A'}) {d.is_freelancer ? '🟢' : ''}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span>{p.doctor_name || '—'}</span>
                    )}
                  </td>
                  <td>
                    {canManage ? (
                      <select className="inline-select" value={p.assigned_nurse || ''}
                        onChange={e => handleAssignNurse(p.patient_id, e.target.value)}>
                        <option value="">— None —</option>
                        {nurses.map(n => <option key={n.nurse_id} value={n.nurse_id}>{n.name}</option>)}
                      </select>
                    ) : (
                      <span>{p.nurse_name || '—'}</span>
                    )}
                  </td>
                  <td style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
                    <button className="btn btn-primary btn-sm"
                      onClick={() => showVitals(p)} title="View latest vitals">
                      💓 Vitals
                    </button>
                    <button className="btn btn-primary btn-sm"
                      onClick={() => setChatPatient({ patient_id: p.patient_id, name: p.name })}
                      title="Open treatment chat">
                      💬 Chat
                    </button>
                    {canDelete && (
                      <button className="btn btn-danger btn-sm" onClick={() => handleDelete(p.patient_id)}>
                        🗑
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Vitals Modal */}
      {vitalsModal && (
        <div style={{
          position:'fixed', top:0, left:0, right:0, bottom:0,
          background:'rgba(0,0,0,0.6)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:999,
        }} onClick={() => setVitalsModal(null)}>
          <div style={{
            background:'#1e293b', borderRadius:16, padding:24, width:380,
            border:'1px solid #334155', boxShadow:'0 15px 40px rgba(0,0,0,.4)',
          }} onClick={e => e.stopPropagation()}>
            <div style={{ display:'flex', justifyContent:'space-between', marginBottom:16 }}>
              <h3 style={{ color:'#e2e8f0', margin:0 }}>💓 {vitalsModal.patient.name}</h3>
              <button onClick={() => setVitalsModal(null)} style={{ background:'none', border:'none', color:'#94a3b8', fontSize:18, cursor:'pointer' }}>✕</button>
            </div>
            {vitalsModal.vitals ? (
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:12 }}>
                <div style={{ background:'#0f172a', borderRadius:10, padding:14, textAlign:'center' }}>
                  <div style={{ fontSize:12, color:'#94a3b8' }}>Heart Rate</div>
                  <div style={{ fontSize:24, fontWeight:700, color: vitalsModal.vitals.heart_rate > 110 || vitalsModal.vitals.heart_rate < 50 ? '#f87171' : '#34d399' }}>
                    {vitalsModal.vitals.heart_rate} <span style={{ fontSize:12 }}>bpm</span>
                  </div>
                </div>
                <div style={{ background:'#0f172a', borderRadius:10, padding:14, textAlign:'center' }}>
                  <div style={{ fontSize:12, color:'#94a3b8' }}>SpO₂</div>
                  <div style={{ fontSize:24, fontWeight:700, color: vitalsModal.vitals.spo2 < 90 ? '#f87171' : '#34d399' }}>
                    {vitalsModal.vitals.spo2}<span style={{ fontSize:12 }}>%</span>
                  </div>
                </div>
                <div style={{ background:'#0f172a', borderRadius:10, padding:14, textAlign:'center' }}>
                  <div style={{ fontSize:12, color:'#94a3b8' }}>Temperature</div>
                  <div style={{ fontSize:24, fontWeight:700, color: vitalsModal.vitals.temperature > 101 ? '#fbbf24' : '#e2e8f0' }}>
                    {vitalsModal.vitals.temperature}<span style={{ fontSize:12 }}>°F</span>
                  </div>
                </div>
              </div>
            ) : (
              <p style={{ color:'#64748b', textAlign:'center' }}>No vitals recorded yet</p>
            )}
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
    </div>
  );
}
