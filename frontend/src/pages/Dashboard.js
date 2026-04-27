import React, { useEffect, useState, useCallback } from 'react';
import { getPatients, getAlerts, getDoctors, getDashboardStats, getMyNotifications, markAllNotificationsRead, markNotificationRead, getVitals, getVitalsSourceConfig } from '../api';
import { buildVitalsWsUrl } from '../config';

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
  const [sourceConfig,  setSourceConfig]  = useState(null);
  const role = (localStorage.getItem('role') || '').toUpperCase();

  const fetchAll = useCallback(async () => {
    try {
      const params = doctorFilter ? { doctor_id: doctorFilter } : {};
      const results = await Promise.allSettled([
        getPatients(params),
        getAlerts(doctorFilter ? { doctor_id: doctorFilter } : {}),
        getDoctors(),
        getDashboardStats(),
        getVitals({ limit: 100, ...(doctorFilter ? { doctor_id: doctorFilter } : {}) }),
      ]);

      const [pRes, aRes, dRes, sRes, vRes] = results;

      if (pRes.status === 'fulfilled') setPatients(pRes.value.data);
      if (aRes.status === 'fulfilled') setAlerts(aRes.value.data);
      if (dRes.status === 'fulfilled') setDoctors(dRes.value.data);
      if (sRes.status === 'fulfilled') setStats(sRes.value.data);
      
      if (vRes.status === 'fulfilled') {
        const latestByPatient = {};
        (vRes.value.data || []).forEach(v => {
          if (v?.patient_id != null && !latestByPatient[v.patient_id]) {
            latestByPatient[v.patient_id] = v;
          }
        });
        setLiveVitals(prev => ({ ...latestByPatient, ...prev }));
      }

      if (role === 'ADMIN') {
        getVitalsSourceConfig().then(res => setSourceConfig(res.data)).catch(() => setSourceConfig(null));
      }

      getMyNotifications({ unread_only: false }).then(res => setNotifications(res.data)).catch(() => {});
      setLastRefresh(new Date().toLocaleTimeString());
    } catch (err) {
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [doctorFilter, role]);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 10000);
    return () => clearInterval(id);
  }, [fetchAll]);

  const patientsRef = React.useRef(patients);
  useEffect(() => { patientsRef.current = patients; }, [patients]);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) return;
    let ws = null;
    let reconnectTimer = null;
    let isMounted = true;

    const connect = () => {
      if (!isMounted) return;
      ws = new WebSocket(buildVitalsWsUrl(token));
      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          if (!Array.isArray(parsed)) return;
          const next = {};
          parsed.forEach((v) => { if (v?.patient_id != null) next[v.patient_id] = v; });
          if (Object.keys(next).length > 0) {
            setLiveVitals(prev => ({ ...prev, ...next }));
            setLastRefresh(new Date().toLocaleTimeString());
          }
        } catch {}
      };
      ws.onclose = () => { if (isMounted) reconnectTimer = setTimeout(connect, 3000); };
      ws.onerror = () => { if (ws.readyState === 1) ws.close(); };
    };
    connect();
    return () => { isMounted = false; clearTimeout(reconnectTimer); if (ws) ws.close(); };
  }, [role]); // Only restart if role/session fundamentally changes

  const getStatus = (pId) => {
    const v = liveVitals[pId];
    if (!v) return 'new-admission';
    
    // Signal Loss Detection (5 minute threshold)
    const ts = toLocal(v.timestamp);
    if (ts && (new Date() - ts > 5 * 60 * 1000)) return 'signal-loss';

    if (v.spo2 < 90 || v.heart_rate > 110 || v.heart_rate < 50) return 'critical';
    if (v.temperature > 101 || v.temperature < 96) return 'warning';
    return 'normal';
  };

  const counts = patients.reduce((acc, p) => {
    const s = getStatus(p.patient_id);
    acc[s] = (acc[s] || 0) + 1;
    return acc;
  }, { critical: 0, warning: 0, normal: 0, 'new-admission': 0, 'signal-loss': 0 });

  const barSeries = [
    { key: 'critical',        label: 'Critical',      value: counts.critical,        color: '#f43f5e' },
    { key: 'signal-loss',     label: 'Signal Loss',   value: counts['signal-loss'],  color: '#fbbf24' },
    { key: 'warning',         label: 'Stable (Obs)',  value: counts.warning,         color: '#fcd34d' },
    { key: 'normal',          label: 'Healthy',       value: counts.normal,          color: '#34d399' },
    { key: 'new-admission',   label: 'Incoming',      value: counts['new-admission'],color: '#22d3ee' },
  ];

  const totalA = Math.max(1, alerts.length);
  const pndA = alerts.filter(a => a.status === 'PENDING').length;
  const escA = alerts.filter(a => a.status === 'ESCALATED').length;
  const ackA = alerts.filter(a => a.status === 'ACKNOWLEDGED').length;
  
  const pndPct = Math.round((pndA / totalA) * 100);
  const escPct = Math.round((escA / totalA) * 100);
  const ackPct = Math.max(0, 100 - pndPct - escPct);

  const unreadCount = notifications.filter(n => !n.is_read).length;

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsRead();
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    } catch {}
  };

  const handleMarkOneRead = async (id) => {
    try {
      await markNotificationRead(id);
      setNotifications(prev => prev.map(n => n.notification_id === id ? { ...n, is_read: true } : n));
    } catch {}
  };

  return (
    <div style={{ animation: 'reveal 0.5s ease-out' }}>
      <div className="main-topbar">
        <div>
          <div className="main-title">Medical Command Center</div>
          <div className="main-subtitle">
            <span className="live-tag">
              <span className="live-dot" />
              LIVE {lastRefresh && `· Updated ${lastRefresh}`}
            </span>
            {sourceConfig && (
              <span style={{ marginLeft: 12, fontSize: 10, color: sourceConfig.source === 'thingspeak' ? '#22d3ee' : '#34d399', fontWeight: 800 }}>
                {sourceConfig.source === 'thingspeak' ? '📡 IOT HARDWARE' : '🎲 SIMULATED'}
              </span>
            )}
          </div>
        </div>
        <div className="topbar-actions" style={{ position: 'relative' }}>
           <button
             className="btn"
             style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid var(--stroke)', padding: '8px 12px', position: 'relative', fontSize: 18 }}
             onClick={() => setShowNotifs(!showNotifs)}
             title="System Notifications"
           >
             🔔
             {unreadCount > 0 && (
               <span style={{
                 position: 'absolute', top: -4, right: -4, background: 'var(--danger)',
                 color: '#fff', borderRadius: '50%', width: 18, height: 18,
                 fontSize: 10, fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center',
                 boxShadow: '0 0 10px var(--danger-glow)'
               }}>
                 {unreadCount}
               </span>
             )}
           </button>

           {showNotifs && (
             <div className="card" style={{
               position: 'absolute', top: 50, right: 0, width: 320, zIndex: 100,
               maxHeight: 400, overflowY: 'auto', boxShadow: '0 20px 50px rgba(0,0,0,0.5)'
             }}>
               <div className="card-header" style={{ padding: '12px 20px' }}>
                 <h3 style={{ fontSize: 12, margin: 0 }}>NOTIFICATIONS</h3>
                 {unreadCount > 0 && (
                   <button onClick={handleMarkAllRead} style={{ background:'none', border:'none', color:'var(--primary)', fontSize:10, fontWeight:800, cursor:'pointer' }}>MARK ALL READ</button>
                 )}
               </div>
               {notifications.length === 0 ? (
                 <div style={{ padding: 20, textAlign: 'center', color: '#64748b', fontSize: 12 }}>No system notifications.</div>
               ) : (
                 notifications.map(n => (
                   <div key={n.notification_id} onClick={() => handleMarkOneRead(n.notification_id)} style={{
                     padding: '12px 20px', borderBottom: '1px solid var(--stroke)',
                     background: n.is_read ? 'transparent' : 'rgba(34, 211, 238, 0.05)',
                     cursor: 'pointer', transition: 'background 0.2s'
                   }}>
                     <div style={{ fontSize: 12, color: n.is_read ? '#94a3b8' : '#f1f5f9', fontWeight: n.is_read ? 400 : 700 }}>{n.message}</div>
                     <div style={{ fontSize: 9, color: '#64748b', marginTop: 4 }}>{n.created_at ? toLocal(n.created_at).toLocaleTimeString() : ''}</div>
                   </div>
                 ))
               )}
             </div>
           )}

           <button className="btn btn-primary btn-sm" onClick={fetchAll}>Refresh Data</button>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="label">Total Patients</div>
          <div className="value">{patients.length}</div>
        </div>
        <div className="stat-card red">
          <div className="label">Critical Issues</div>
          <div className="value">{counts.critical}</div>
        </div>
        <div className="stat-card amber">
          <div className="label">Avg Triage Time</div>
          <div className="value">
            {stats?.avg_response_time_seconds ? (stats.avg_response_time_seconds < 60 ? `${Math.round(stats.avg_response_time_seconds)}s` : `${Math.round(stats.avg_response_time_seconds/60)}m`) : '—'}
          </div>
        </div>
        <div className="stat-card red">
          <div className="label">SLA Breaches</div>
          <div className="value" style={{ color: (stats?.sla_breach_count > 0) ? '#f43f5e' : 'inherit' }}>
            {stats?.sla_breach_count ?? 0}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 24, marginBottom: 24 }}>
        <div className="card">
          <div className="card-header"><h2>Stability Index</h2></div>
          <div style={{ padding: 20, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {barSeries.map(s => (
              <div key={s.key} style={{ padding: 12, borderRadius: 12, background: 'rgba(255,255,255,0.03)', border: `1px solid ${s.color}22` }}>
                <div style={{ fontSize: 10, color: '#94a3b8', fontWeight: 800 }}>{s.label}</div>
                <div style={{ fontSize: 20, fontWeight: 800, color: s.color, marginTop: 2 }}>{s.value}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <div className="card-header"><h2>Alert Response</h2></div>
          <div style={{ padding: 20 }}>
            <div style={{ height: 12, width: '100%', background: 'rgba(255,255,255,0.05)', borderRadius: 6, overflow: 'hidden', display: 'flex' }}>
              <div style={{ width: `${escPct}%`, background: '#f43f5e' }} />
              <div style={{ width: `${pndPct}%`, background: '#fbbf24' }} />
              <div style={{ width: `${ackPct}%`, background: '#34d399' }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16 }}>
               <div style={{ textAlign:'center' }}><div style={{color:'#f43f5e', fontWeight:800}}>{escPct}%</div><div style={{fontSize:9, color:'#64748b'}}>ESC</div></div>
               <div style={{ textAlign:'center' }}><div style={{color:'#fbbf24', fontWeight:800}}>{pndPct}%</div><div style={{fontSize:9, color:'#64748b'}}>PND</div></div>
               <div style={{ textAlign:'center' }}><div style={{color:'#34d399', fontWeight:800}}>{ackPct}%</div><div style={{fontSize:9, color:'#64748b'}}>ACK</div></div>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h2>Live Vitals Telemetry</h2></div>
        {loading ? <div className="spinner" /> : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Patient</th><th>Room</th><th>Doctor</th><th>Heart Rate</th><th>SpO₂</th><th>Temp</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {patients.map(p => {
                  const v = liveVitals[p.patient_id];
                  const s = getStatus(p.patient_id);
                  return (
                    <tr key={p.patient_id}>
                      <td><strong>{p.name}</strong></td>
                      <td>{p.room_number}</td>
                      <td>{p.doctor_name || '—'}</td>
                      <td style={{color: s === 'critical' && v?.heart_rate > 110 ? '#f43f5e' : 'inherit'}}>{v ? `${v.heart_rate} bpm` : '—'}</td>
                      <td style={{color: s === 'critical' && v?.spo2 < 90 ? '#f43f5e' : 'inherit'}}>{v ? `${v.spo2}%` : '—'}</td>
                      <td>{v ? `${v.temperature}°F` : '—'}</td>
                      <td>
                        <span className={`badge ${
                          s === 'critical' ? 'badge-red' : 
                          s === 'signal-loss' ? 'badge-amber' : 
                          s === 'new-admission' ? 'badge-blue' : 
                          s === 'warning' ? 'badge-amber' : 'badge-green'
                        }`}>
                          {s === 'signal-loss' ? 'SIGNAL LOSS' : 
                           s === 'new-admission' ? 'NEW ADMIT' : 
                           s.toUpperCase()}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
