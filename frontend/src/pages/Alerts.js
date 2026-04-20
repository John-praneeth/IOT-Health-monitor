import React, { useEffect, useState, useCallback } from 'react';
import { getAlerts, acknowledgeAlert, getPatients, getDoctors, getWhatsAppConfig, getDashboardStats } from '../api';

// Treat DB timestamps as UTC → convert to local time correctly
const toLocal = (ts) => ts ? new Date(ts.endsWith('Z') ? ts : ts + 'Z') : null;

export default function Alerts() {
  const [alerts,      setAlerts]      = useState([]);
  const [patients,    setPatients]    = useState([]);
  const [doctors,     setDoctors]     = useState([]);
  const [filter,      setFilter]      = useState('');      // '' | 'PENDING' | 'ACKNOWLEDGED' | 'ESCALATED'
  const [doctorFilter, setDoctorFilter] = useState('');    // doctor_id
  const [loading,     setLoading]     = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [whatsappStatus, setWhatsappStatus] = useState(null);
  const [alertStats, setAlertStats] = useState(null);

  const role = localStorage.getItem('role');
  const userId = parseInt(localStorage.getItem('user_id') || '0', 10);
  const canAcknowledge = role === 'ADMIN' || role === 'DOCTOR';

  const load = useCallback(async () => {
    try {
      const params = {};
      if (filter) params.status = filter;
      if (doctorFilter) params.doctor_id = parseInt(doctorFilter);
      const [aRes, pRes, dRes, sRes] = await Promise.all([
        getAlerts(params),
        getPatients(),
        getDoctors(),
        getDashboardStats(),
      ]);
      setAlerts(aRes.data);
      setPatients(pRes.data);
      setDoctors(dRes.data);
      setAlertStats(sRes.data);
      setLastRefresh(new Date().toLocaleTimeString());
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [filter, doctorFilter]);

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    // Load WhatsApp status once
    if (role === 'ADMIN') {
      getWhatsAppConfig().then(res => setWhatsappStatus(res.data)).catch(() => {});
    }
    return () => clearInterval(id);
  }, [load, role]);

  const handleAck = async (alertId) => {
    try {
      await acknowledgeAlert(alertId, userId || 1);
      load();
    } catch (err) { alert('Failed to acknowledge: ' + err.message); }
  };

  const patientName = (id) => patients.find(p => p.patient_id === id)?.name || `Patient ${id}`;

  const badgeForType = (type) => {
    if (type.includes('HEART') || type.includes('SPO2')) return 'badge-red';
    if (type.includes('TEMP'))  return 'badge-amber';
    return 'badge-blue';
  };

  const statusBadge = (status) => {
    if (status === 'PENDING')      return <span className="badge badge-amber">PENDING</span>;
    if (status === 'ESCALATED')    return <span className="badge badge-red">🔺 ESCALATED</span>;
    if (status === 'ACKNOWLEDGED') return <span className="badge badge-green">ACKNOWLEDGED</span>;
    return <span className="badge">{status}</span>;
  };

  const pending = alertStats?.pending_alerts ?? alerts.filter(a => a.status === 'PENDING').length;
  const escalated = alertStats?.escalated_alerts ?? alerts.filter(a => a.status === 'ESCALATED').length;
  const acknowledged = alertStats?.acknowledged_alerts ?? alerts.filter(a => a.status === 'ACKNOWLEDGED').length;

  return (
    <div>
      <div className="page-header">
        <h1>Alerts</h1>
        <p>
          {escalated > 0
            ? <span style={{ color:'#ef4444' }}>🔺 {escalated} escalated alert{escalated > 1 ? 's' : ''}!</span>
            : pending > 0
              ? <span style={{ color:'#f87171' }}>⚠️ {pending} pending alert{pending > 1 ? 's' : ''} require attention</span>
              : <span style={{ color:'#34d399' }}>✅ All alerts handled</span>
          }
          &nbsp;
          <span className="live-tag">
            <span className="live-dot" />
            AUTO-REFRESH {lastRefresh && `· ${lastRefresh}`}
          </span>
          {whatsappStatus && (
            <span style={{
              marginLeft: 12,
              padding: '3px 10px',
              borderRadius: 12,
              fontSize: 11,
              fontWeight: 600,
              background: whatsappStatus.enabled && whatsappStatus.credentials_set
                ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)',
              color: whatsappStatus.enabled && whatsappStatus.credentials_set
                ? '#6ee7b7' : '#fca5a5',
              border: `1px solid ${whatsappStatus.enabled && whatsappStatus.credentials_set
                ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
            }}>
              📱 WhatsApp {whatsappStatus.enabled && whatsappStatus.credentials_set ? 'Active' : 'Inactive'}
            </span>
          )}
        </p>
      </div>

      {/* Stats row */}
      <div className="stats-grid" style={{ gridTemplateColumns:'repeat(4,1fr)', marginBottom:24 }}>
        <div className="stat-card red">
          <div className="label">Escalated</div>
          <div className="value">{escalated}</div>
        </div>
        <div className="stat-card" style={{ background:'linear-gradient(135deg,#78350f,#92400e)' }}>
          <div className="label">Pending</div>
          <div className="value">{pending}</div>
        </div>
        <div className="stat-card green">
          <div className="label">Acknowledged</div>
          <div className="value">{acknowledged}</div>
        </div>
        <div className="stat-card blue">
          <div className="label">Total</div>
          <div className="value">{alerts.length}</div>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display:'flex', gap:10, marginBottom:20, flexWrap:'wrap', alignItems:'center' }}>
        {['', 'PENDING', 'ESCALATED', 'ACKNOWLEDGED'].map(s => (
          <button
            key={s}
            className={`btn btn-sm ${filter === s ? 'btn-primary' : ''}`}
            style={filter !== s ? { background:'#1e293b', border:'1px solid #334155', color:'#94a3b8' } : {}}
            onClick={() => setFilter(s)}
          >
            {s || 'All'}
          </button>
        ))}
        <select
          style={{ background:'#1e293b', border:'1px solid #334155', color:'#e2e8f0',
                   borderRadius:8, padding:'8px 12px', fontSize:13, marginLeft:8 }}
          value={doctorFilter} onChange={e => setDoctorFilter(e.target.value)}>
          <option value="">All Doctors</option>
          {doctors.map(d => <option key={d.doctor_id} value={d.doctor_id}>{d.name}</option>)}
        </select>
        <button className="btn btn-primary btn-sm" onClick={load}>⟳ Refresh</button>
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Alert Log</h2>
          <span style={{ fontSize:12, color:'#64748b' }}>{alerts.length} records</span>
        </div>
        {loading ? <div className="spinner" /> : (
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Patient</th><th>Alert Type</th>
                <th>Status</th><th>Time</th><th>Action</th>
              </tr>
            </thead>
            <tbody>
              {alerts.length === 0 && (
                <tr><td colSpan={6} className="empty-state">No alerts found.</td></tr>
              )}
              {alerts.map(a => (
                <tr key={a.alert_id} style={a.status === 'ESCALATED' ? { background:'rgba(239,68,68,0.08)' } : {}}>
                  <td>#{a.alert_id}</td>
                  <td>{patientName(a.patient_id)}</td>
                  <td><span className={`badge ${badgeForType(a.alert_type)}`}>{a.alert_type}</span></td>
                  <td>{statusBadge(a.status)}</td>
                  <td>{a.created_at ? toLocal(a.created_at).toLocaleString() : '—'}</td>
                  <td>
                    {canAcknowledge && (a.status === 'PENDING' || a.status === 'ESCALATED') && (
                      <button className="btn btn-success btn-sm" onClick={() => handleAck(a.alert_id)}>
                        ✓ Acknowledge
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
