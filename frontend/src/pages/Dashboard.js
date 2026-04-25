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
            setLiveVitals(next);
            setLastRefresh(new Date().toLocaleTimeString());
          }
        } catch {}
      };
      ws.onclose = () => { if (isMounted) reconnectTimer = setTimeout(connect, 3000); };
      ws.onerror = () => { if (ws.readyState === 1) ws.close(); };
    };
    connect();
    return () => { isMounted = false; clearTimeout(reconnectTimer); if (ws) ws.close(); };
  }, []);

  const getStatus = (pId) => {
    const v = liveVitals[pId];
    if (!v) return 'no-data';
    if (v.spo2 < 90 || v.heart_rate > 110 || v.heart_rate < 50) return 'critical';
    if (v.temperature > 101 || v.temperature < 96) return 'warning';
    return 'normal';
  };

  const counts = patients.reduce((acc, p) => {
    const s = getStatus(p.patient_id);
    acc[s] = (acc[s] || 0) + 1;
    return acc;
  }, { critical: 0, warning: 0, normal: 0, 'no-data': 0 });

  const barSeries = [
    { key: 'critical', label: 'Critical', value: counts.critical, color: '#f43f5e' },
    { key: 'warning', label: 'Warning', value: counts.warning, color: '#fbbf24' },
    { key: 'normal', label: 'Stable', value: counts.normal, color: '#34d399' },
    { key: 'no-data', label: 'No Data', value: counts['no-data'], color: '#22d3ee' },
  ];

  const totalA = Math.max(1, alerts.length);
  const pndA = alerts.filter(a => a.status === 'PENDING').length;
  const escA = alerts.filter(a => a.status === 'ESCALATED').length;
  const ackA = alerts.filter(a => a.status === 'ACKNOWLEDGED').length;
  
  const pndPct = Math.round((pndA / totalA) * 100);
  const escPct = Math.round((escA / totalA) * 100);
  const ackPct = Math.max(0, 100 - pndPct - escPct);

  return (
    <div style={{ animation: 'reveal 0.5s ease-out' }}>
      <div className="main-topbar">
        <div>
          <div className="main-title">Clinical Dashboard</div>
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
        <div className="topbar-actions">
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
          <div className="label">Pending Alerts</div>
          <div className="value">{pndA}</div>
        </div>
        <div className="stat-card green">
          <div className="label">Stable Ward</div>
          <div className="value">{counts.normal}</div>
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
                        <span className={`badge ${s==='critical'?'badge-red':s==='warning'?'badge-amber':'badge-green'}`}>
                          {s.toUpperCase()}
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
