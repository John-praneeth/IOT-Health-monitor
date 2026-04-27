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

  const role = (localStorage.getItem('role') || '').toUpperCase();
  const userId = parseInt(localStorage.getItem('user_id') || '0', 10);
  const canAcknowledge = role === 'ADMIN' || role === 'DOCTOR' || role === 'NURSE';

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
      getWhatsAppConfig().then(res => setWhatsappStatus(res.data)).catch(err => console.error("Failed to load WhatsApp config:", err));
    }
    return () => clearInterval(id);
  }, [load, role]);

  const handleAck = async (alertId) => {
    const originalAlerts = [...alerts];
    const originalStats = alertStats ? { ...alertStats } : null;

    // Optimistic Update
    setAlerts(prev => prev.map(a => a.alert_id === alertId ? { ...a, status: 'ACKNOWLEDGED' } : a));
    if (alertStats) {
      const target = alerts.find(a => a.alert_id === alertId);
      setAlertStats(prev => ({
        ...prev,
        pending_alerts: Math.max(0, prev.pending_alerts - (target?.status === 'PENDING' ? 1 : 0)),
        escalated_alerts: Math.max(0, prev.escalated_alerts - (target?.status === 'ESCALATED' ? 1 : 0)),
        acknowledged_alerts: prev.acknowledged_alerts + 1
      }));
    }

    try {
      await acknowledgeAlert(alertId, userId || 1);
      // Silence load() here or just let the next poll sync it. 
      // User wants 'immediate' update.
    } catch (err) {
      setAlerts(originalAlerts);
      setAlertStats(originalStats);
      alert('Failed to acknowledge: ' + err.message);
    }
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
    <div style={{ animation: 'reveal 0.4s ease-out' }}>
      <div className="main-topbar">
        <div>
          <div className="main-title">Clinical Alert Monitor</div>
          <div className="main-subtitle">
             {escalated > 0
               ? <span style={{ color:'#f43f5e', fontWeight: 800 }}>⚠️ {escalated} CRITICAL ESCALATIONS ACTIVE</span>
               : <span style={{ color:'#34d399', fontWeight: 700 }}>✓ ALL RESPONSE VECTORS STABLE</span>
             }
          </div>
        </div>
        <div className="topbar-actions">
           <span className="live-tag">
             <span className="live-dot" />
             ACTIVE MONITORING
           </span>
           <button className="btn btn-primary btn-sm" onClick={load}>⟳ Sync Feed</button>
        </div>
      </div>

      <div className="stats-grid" style={{ gridTemplateColumns:'repeat(auto-fit, minmax(180px, 1fr))', marginBottom:24 }}>
        <div className="stat-card red">
          <div className="label">Critical Escalations</div>
          <div className="value">{escalated}</div>
        </div>
        <div className="stat-card amber">
          <div className="label">Pending Triages</div>
          <div className="value">{pending}</div>
        </div>
        <div className="stat-card green">
          <div className="label">Resolved Events</div>
          <div className="value">{acknowledged}</div>
        </div>
        <div className="stat-card blue">
          <div className="label">Total Registry</div>
          <div className="value">{alerts.length}</div>
        </div>
      </div>

      <div className="filter-row" style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 4, background: 'rgba(0,0,0,0.2)', padding: 4, borderRadius: 10, border: '1px solid var(--stroke)' }}>
          {['', 'PENDING', 'ESCALATED', 'ACKNOWLEDGED'].map(s => (
            <button
              key={s}
              className={`btn btn-sm`}
              style={{
                background: filter === s ? 'rgba(255,255,255,0.08)' : 'transparent',
                color: filter === s ? '#fff' : '#64748b',
                padding: '6px 12px', borderRadius: 8, fontSize: 11, fontWeight: 700
              }}
              onClick={() => setFilter(s)}
            >
              {s || 'ALL EVENTS'}
            </button>
          ))}
        </div>
        <select
          style={{ background:'rgba(0,0,0,0.2)', border:'1px solid rgba(255,255,255,0.1)', color:'#e2e8f0',
                   borderRadius:8, padding:'8px 12px', fontSize:13, outline: 'none' }}
          value={doctorFilter} onChange={e => setDoctorFilter(e.target.value)}>
          <option value="">All Physician Groups</option>
          {doctors.map(d => <option key={d.doctor_id} value={d.doctor_id}>{d.name}</option>)}
        </select>
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Active Response Log</h2>
          {whatsappStatus?.enabled && (
             <span className="badge badge-green" style={{ fontSize: 9 }}>📱 WA NOTIFICATIONS ENABLED</span>
          )}
        </div>
        {loading ? <div className="spinner" /> : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Trace ID</th><th>Patient Identity</th><th>Severity Vector</th>
                  <th>Status State</th><th>Time Detected</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {alerts.length === 0 && (
                  <tr><td colSpan={6} className="empty-state">No active clinical alerts detected in this scope.</td></tr>
                )}
                {alerts.map(a => (
                  <tr key={a.alert_id} style={a.status === 'ESCALATED' ? { background:'rgba(244,63,94,0.03)' } : {}}>
                    <td><span style={{ color: '#64748b', fontWeight: 600 }}>#{a.alert_id}</span></td>
                    <td><strong>{patientName(a.patient_id)}</strong></td>
                    <td>
                      <span className={`badge ${badgeForType(a.alert_type)}`} style={{ fontSize: 10 }}>
                        {a.alert_type.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td>{statusBadge(a.status)}</td>
                    <td><span style={{ fontSize: 13, color: '#94a3b8' }}>{a.created_at ? toLocal(a.created_at).toLocaleTimeString() : '—'}</span></td>
                    <td>
                      {canAcknowledge && (a.status === 'PENDING' || a.status === 'ESCALATED') && (
                        <button className="btn btn-primary btn-sm" style={{ padding: '4px 10px', fontSize: 11 }} onClick={() => handleAck(a.alert_id)}>
                          ACKNOWLEDGE
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
