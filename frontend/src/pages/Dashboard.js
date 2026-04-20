import React, { useEffect, useState, useCallback } from 'react';
import { getPatients, getAlerts, getDoctors, getDashboardStats, getMyNotifications, markAllNotificationsRead, markNotificationRead, getVitals } from '../api';

// Treat DB timestamps as UTC → convert to local time correctly
const toLocal = (ts) => ts ? new Date(ts.endsWith('Z') ? ts : ts + 'Z') : null;

export default function Dashboard() {
  const [patients,      setPatients]      = useState([]);
  const [alerts,        setAlerts]        = useState([]);
  const [doctors,       setDoctors]       = useState([]);
  const [stats,         setStats]         = useState(null);
  const [liveVitals,    setLiveVitals]    = useState({});
  const [doctorFilter,  setDoctorFilter]  = useState('');
  const [lastRefresh,   setLastRefresh]   = useState(null);
  const [loading,       setLoading]       = useState(true);
  const [notifications, setNotifications] = useState([]);
  const [showNotifs,    setShowNotifs]    = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const params = doctorFilter ? { doctor_id: doctorFilter } : {};
      const [pRes, aRes, dRes, sRes, vRes] = await Promise.all([
        getPatients(params),
        getAlerts(doctorFilter ? { doctor_id: doctorFilter } : {}),
        getDoctors(),
        getDashboardStats(),
        getVitals({ limit: 100, ...(doctorFilter ? { doctor_id: doctorFilter } : {}) }),
      ]);
      setPatients(pRes.data);
      setAlerts(aRes.data);
      setDoctors(dRes.data);
      setStats(sRes.data);
      const latestByPatient = {};
      (vRes.data || []).forEach(v => {
        if (v?.patient_id != null && !latestByPatient[v.patient_id]) {
          latestByPatient[v.patient_id] = v;
        }
      });
      setLiveVitals(prev => ({ ...latestByPatient, ...prev }));

      // Notifications require auth — fetch separately so a 401 doesn't break everything
      try {
        const nRes = await getMyNotifications({ unread_only: false });
        setNotifications(nRes.data);
      } catch { /* auth may have expired */ }
      setLastRefresh(new Date().toLocaleTimeString());
    } catch (err) {
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [doctorFilter]);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 10000);
    return () => clearInterval(id);
  }, [fetchAll]);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) return;

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const base = window.location.port === '3000'
      ? `${proto}://${window.location.hostname}:8000/ws/vitals`
      : `${proto}://${window.location.host}/ws/vitals`;
    const ws = new WebSocket(`${base}?token=${encodeURIComponent(token)}`);

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        if (!Array.isArray(parsed)) return;
        const next = {};
        parsed.forEach((v) => {
          if (v?.patient_id != null) {
            next[v.patient_id] = v;
          }
        });
        if (Object.keys(next).length > 0) {
          setLiveVitals(next);
          setLastRefresh(new Date().toLocaleTimeString());
        }
      } catch {
        // Ignore keepalive/invalid payloads.
      }
    };

    return () => {
      try { ws.close(); } catch { /* no-op */ }
    };
  }, []);

  const unreadCount = notifications.filter(n => !n.is_read).length;

  const handleMarkAllRead = async () => {
    await markAllNotificationsRead();
    fetchAll();
  };

  const handleMarkRead = async (id) => {
    await markNotificationRead(id);
    fetchAll();
  };

  const pendingAlerts   = alerts.filter(a => a.status === 'PENDING');
  const escalatedAlerts = alerts.filter(a => a.status === 'ESCALATED');

  const getStatus = (patientId) => {
    const v = liveVitals[patientId];
    if (!v) return 'no-data';
    if (v.spo2 < 90 || v.heart_rate > 110 || v.heart_rate < 50) return 'critical';
    if (v.temperature > 101 || v.temperature < 96) return 'warning';
    return 'normal';
  };

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>Dashboard</h1>
          <p>
            Real-time patient overview &nbsp;
            <span className="live-tag">
              <span className="live-dot" />
              LIVE {lastRefresh && `· Updated ${lastRefresh}`}
            </span>
          </p>
        </div>
        {/* Notification Bell */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowNotifs(!showNotifs)}
            style={{
              background: unreadCount > 0 ? '#1e3a5f' : '#1e293b', border: '1px solid #334155',
              color: '#e2e8f0', borderRadius: 10, padding: '8px 14px', cursor: 'pointer',
              fontSize: 18, position: 'relative',
            }}>
            🔔
            {unreadCount > 0 && (
              <span style={{
                position: 'absolute', top: -4, right: -4, background: '#ef4444',
                color: '#fff', borderRadius: '50%', width: 20, height: 20,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700,
              }}>{unreadCount}</span>
            )}
          </button>
          {showNotifs && (
            <div style={{
              position: 'absolute', top: 44, right: 0, width: 380, maxHeight: 400,
              background: '#1e293b', border: '1px solid #334155', borderRadius: 12,
              boxShadow: '0 15px 40px rgba(0,0,0,.4)', zIndex: 100, overflow: 'auto',
            }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid #334155', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <strong style={{ color: '#e2e8f0', fontSize: 14 }}>🔔 Notifications</strong>
                {unreadCount > 0 && (
                  <button onClick={handleMarkAllRead} style={{
                    background: '#3b82f6', border: 'none', color: '#fff', borderRadius: 6,
                    padding: '4px 10px', fontSize: 11, cursor: 'pointer',
                  }}>Mark all read</button>
                )}
              </div>
              {notifications.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center', color: '#64748b', fontSize: 13 }}>
                  No notifications yet
                </div>
              ) : (
                notifications.slice(0, 20).map(n => (
                  <div key={n.notification_id}
                    onClick={() => !n.is_read && handleMarkRead(n.notification_id)}
                    style={{
                      padding: '10px 16px', borderBottom: '1px solid #0f172a',
                      background: n.is_read ? 'transparent' : 'rgba(59,130,246,0.08)',
                      cursor: n.is_read ? 'default' : 'pointer',
                    }}>
                    <div style={{ color: '#e2e8f0', fontSize: 12 }}>{n.message}</div>
                    <div style={{ color: '#64748b', fontSize: 10, marginTop: 4 }}>
                      {n.created_at ? toLocal(n.created_at).toLocaleString() : ''}
                      {!n.is_read && <span style={{ color: '#3b82f6', marginLeft: 8 }}>● new</span>}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Doctor filter */}
      <div style={{ display:'flex', gap:12, marginBottom:20 }}>
        <select
          style={{ background:'#1e293b', border:'1px solid #334155', color:'#e2e8f0',
                   borderRadius:8, padding:'8px 12px', fontSize:13 }}
          value={doctorFilter}
          onChange={e => setDoctorFilter(e.target.value)}
        >
          <option value="">All Doctors</option>
          {doctors.map(d => <option key={d.doctor_id} value={d.doctor_id}>{d.name} ({d.specialization || 'N/A'})</option>)}
        </select>
        <button className="btn btn-primary btn-sm" onClick={fetchAll}>⟳ Refresh</button>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card blue">
          <div className="label">Patients</div>
          <div className="value">{stats?.total_patients ?? patients.length}</div>
        </div>
        <div className="stat-card" style={{ background:'linear-gradient(135deg,#1e3a5f,#1e40af)' }}>
          <div className="label">Doctors</div>
          <div className="value">{stats?.total_doctors ?? doctors.length}</div>
        </div>
        <div className="stat-card red">
          <div className="label">Pending Alerts</div>
          <div className="value">{stats?.pending_alerts ?? pendingAlerts.length}</div>
        </div>
        <div className="stat-card amber">
          <div className="label">Escalated</div>
          <div className="value">{stats?.escalated_alerts ?? escalatedAlerts.length}</div>
        </div>
        <div className="stat-card green">
          <div className="label">Stable</div>
          <div className="value">
            {patients.filter(p => getStatus(p.patient_id) === 'normal').length}
          </div>
        </div>
        <div className="stat-card" style={{ background:'linear-gradient(135deg,#4c1d95,#6d28d9)' }}>
          <div className="label">Duplicate Vitals</div>
          <div className="value">{stats?.duplicate_vitals_count ?? 0}</div>
        </div>
        <div className="stat-card" style={{ background:'linear-gradient(135deg,#065f46,#047857)' }}>
          <div className="label">Acknowledged</div>
          <div className="value">{stats?.acknowledged_alerts ?? 0}</div>
        </div>
      </div>

      {/* Patient vitals grid */}
      <div className="card">
        <div className="card-header">
          <h2>Live Patient Vitals</h2>
        </div>
        {loading ? <div className="spinner" /> : (
          <table>
            <thead>
              <tr>
                <th>Patient</th><th>Room</th><th>Hospital</th><th>Doctor</th><th>Nurse</th>
                <th>Heart Rate</th><th>SpO₂</th><th>Temp (°F)</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {patients.length === 0 && (
                <tr><td colSpan={9} className="empty-state">No patients yet. Add patients first.</td></tr>
              )}
              {patients.map(p => {
                const v = liveVitals[p.patient_id];
                const status = getStatus(p.patient_id);
                return (
                  <tr key={p.patient_id}
                    className={status === 'critical' ? 'vital-critical' : status === 'warning' ? 'vital-warning' : ''}>
                    <td><strong>{p.name}</strong></td>
                    <td>{p.room_number}</td>
                    <td>{p.hospital_name || '—'}</td>
                    <td>{p.doctor_name || '—'}</td>
                    <td>{p.nurse_name  || '—'}</td>
                    <td>{v ? `${v.heart_rate} bpm` : '—'}</td>
                    <td>{v ? `${v.spo2}%` : '—'}</td>
                    <td>{v ? `${v.temperature}°F` : '—'}</td>
                    <td>
                      {status === 'critical' && <span className="badge badge-red">Critical</span>}
                      {status === 'warning'  && <span className="badge badge-amber">Warning</span>}
                      {status === 'normal'   && <span className="badge badge-green">Stable</span>}
                      {status === 'no-data'  && <span className="badge badge-blue">No Data</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Recent Alerts */}
      <div className="card">
        <div className="card-header">
          <h2>🚨 Active Alerts (Pending & Escalated)</h2>
        </div>
        <table>
          <thead>
            <tr><th>Alert ID</th><th>Patient</th><th>Type</th><th>Status</th><th>Time</th></tr>
          </thead>
          <tbody>
            {[...pendingAlerts, ...escalatedAlerts].length === 0 && (
              <tr><td colSpan={5} className="empty-state">No active alerts 🎉</td></tr>
            )}
            {[...pendingAlerts, ...escalatedAlerts].slice(0, 15).map(a => {
              const pName = patients.find(p => p.patient_id === a.patient_id)?.name || `Patient ${a.patient_id}`;
              return (
                <tr key={a.alert_id}>
                  <td>#{a.alert_id}</td>
                  <td>{pName}</td>
                  <td><span className={`badge ${a.alert_type.includes('HEART') || a.alert_type.includes('SPO2') ? 'badge-red' : 'badge-amber'}`}>{a.alert_type}</span></td>
                  <td>
                    {a.status === 'ESCALATED'
                      ? <span className="badge badge-red">⬆ ESCALATED</span>
                      : <span className="badge badge-amber">PENDING</span>
                    }
                  </td>
                  <td>{a.created_at ? toLocal(a.created_at).toLocaleTimeString() : '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
