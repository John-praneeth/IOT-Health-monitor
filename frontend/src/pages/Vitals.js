import React, { useEffect, useState, useCallback } from 'react';
import { getVitals, getPatients, getDoctors } from '../api';
import { buildVitalsWsUrl } from '../config';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

// Treat DB timestamps as UTC (they have no tz info) → convert to local time correctly
const toLocal = (ts) => ts ? new Date(ts.endsWith('Z') ? ts : ts + 'Z') : null;

export default function Vitals() {
  const [vitals,       setVitals]       = useState([]);
  const [patients,     setPatients]     = useState([]);
  const [doctors,      setDoctors]      = useState([]);
  const [filter,       setFilter]       = useState('');
  const [doctorFilter, setDoctorFilter] = useState('');
  const [loading,      setLoading]      = useState(true);
  const [lastRefresh,  setLastRefresh]  = useState(null);
  const [showChart,    setShowChart]    = useState(false);

  const load = useCallback(async () => {
    try {
      const params = { limit: 100 };
      if (filter)       params.patient_id = parseInt(filter);
      if (doctorFilter) params.doctor_id  = parseInt(doctorFilter);
      const [vRes, pRes, dRes] = await Promise.all([
        getVitals(params),
        getPatients(),
        getDoctors(),
      ]);
      setVitals(vRes.data);
      setPatients(pRes.data);
      setDoctors(dRes.data);
      setLastRefresh(new Date().toLocaleTimeString());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [filter, doctorFilter]);

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);

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
          if (!Array.isArray(parsed) || parsed.length === 0) return;

          const incoming = parsed
            .filter(v => v?.patient_id != null)
            .filter(v => !filter || String(v.patient_id) === String(filter))
            .filter(v => {
              if (!doctorFilter) return true;
              const patient = patients.find(p => p.patient_id === v.patient_id);
              return patient && String(patient.assigned_doctor) === String(doctorFilter);
            })
            .map(v => ({
              ...v,
              vital_id: v.vital_id ?? `ws-${v.patient_id}-${v.timestamp}`,
            }));

          if (incoming.length === 0) return;

          setVitals(prev => {
            const merged = [...incoming, ...prev];
            const seen = new Set();
            const deduped = [];
            for (const row of merged) {
              const key = `${row.patient_id}-${row.timestamp}`;
              if (!seen.has(key)) {
                seen.add(key);
                deduped.push(row);
              }
              if (deduped.length >= 100) break;
            }
            return deduped;
          });
          setLastRefresh(new Date().toLocaleTimeString());
        } catch {
          // Ignore keepalive/invalid payloads.
        }
      };

      ws.onclose = () => {
        if (isMounted) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => {
        if (ws.readyState === 1) ws.close();
      };
    };

    connect();

    return () => {
      isMounted = false;
      clearTimeout(reconnectTimer);
      if (ws) {
        try { ws.close(); } catch { /* no-op */ }
      }
    };
  }, [filter, doctorFilter, patients]);

  const patientName = (id) => patients.find(p => p.patient_id === id)?.name || `Patient ${id}`;

  const rowClass = (v) => {
    if (v.spo2 < 90 || v.heart_rate > 110 || v.heart_rate < 50) return 'vital-critical';
    if (v.temperature > 101 || v.temperature < 96) return 'vital-warning';
    return '';
  };

  // ── Chart data (reversed so oldest is left) ────────────────────────────
  const chartVitals = [...vitals].reverse();
  const labels = chartVitals.map(v => v.timestamp ? toLocal(v.timestamp).toLocaleTimeString() : '');

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Heart Rate (bpm)',
        data: chartVitals.map(v => v.heart_rate),
        borderColor: '#f43f5e',
        backgroundColor: 'rgba(244,63,94,0.1)',
        tension: 0.4, fill: true,
        pointRadius: 2,
      },
      {
        label: 'SpO₂ (%)',
        data: chartVitals.map(v => v.spo2),
        borderColor: '#34d399',
        backgroundColor: 'rgba(52,211,153,0.1)',
        tension: 0.4, fill: true,
        pointRadius: 2,
      },
      {
        label: 'Temperature (°F)',
        data: chartVitals.map(v => v.temperature),
        borderColor: '#fbbf24',
        backgroundColor: 'rgba(251,191,36,0.1)',
        tension: 0.4, fill: true,
        pointRadius: 2,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { weight: '600' } } },
      title: {
        display: true,
        text: filter ? `Telemetry Feed: ${patientName(parseInt(filter))}` : 'Global Vitals Telemetry',
        color: '#f1f5f9',
        font: { size: 16, weight: '700', family: "'Space Grotesk', sans-serif" }
      },
    },
    scales: {
      x: { ticks: { color: '#64748b', maxTicksLimit: 15 }, grid: { color: 'rgba(255,255,255,0.03)' } },
      y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.03)' } },
    },
  };

  return (
    <div style={{ animation: 'reveal 0.4s ease-out' }}>
      <div className="main-topbar">
        <div>
          <div className="main-title">Clinical Telemetry Feed</div>
          <div className="main-subtitle">
             <span className="live-tag">
               <span className="live-dot" />
               RECEIVING {lastRefresh && `· ${lastRefresh}`}
             </span>
          </div>
        </div>
        <div className="topbar-actions">
           <button
             className={`btn btn-sm ${showChart ? 'btn-primary' : ''}`}
             style={{ background: showChart ? 'var(--primary)' : 'rgba(255,255,255,0.05)', color: showChart ? '#000' : '#e2e8f0', border: '1px solid var(--stroke)' }}
             onClick={() => setShowChart(!showChart)}
           >
             {showChart ? '📊 Hide Analytics' : '📈 Show Analytics'}
           </button>
           <button className="btn btn-primary btn-sm" onClick={load}>⟳ Refresh Feed</button>
        </div>
      </div>

      <div className="filter-row" style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: '#64748b', fontWeight: 800 }}>SOURCE FILTER:</span>
        <select
          style={{ background:'rgba(0,0,0,0.2)', border:'1px solid rgba(255,255,255,0.1)', color:'#e2e8f0',
                   borderRadius:8, padding:'6px 12px', fontSize:13, outline: 'none' }}
          value={filter}
          onChange={e => setFilter(e.target.value)}
        >
          <option value="">All Active Patients</option>
          {patients.map(p => <option key={p.patient_id} value={p.patient_id}>{p.name}</option>)}
        </select>
        <select
          style={{ background:'rgba(0,0,0,0.2)', border:'1px solid rgba(255,255,255,0.1)', color:'#e2e8f0',
                   borderRadius:8, padding:'6px 12px', fontSize:13, outline: 'none' }}
          value={doctorFilter}
          onChange={e => setDoctorFilter(e.target.value)}
        >
          <option value="">All Physician Groups</option>
          {doctors.map(d => <option key={d.doctor_id} value={d.doctor_id}>{d.name}</option>)}
        </select>
      </div>

      {/* ── Chart ────────────────────────────────────────────────── */}
      {showChart && vitals.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header"><h2>Live Vitals Trend Analysis</h2></div>
          <div style={{ height: 320, padding: '16px 24px 24px' }}>
            <Line data={chartData} options={chartOptions} />
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <h2>Telemetry Log</h2>
          <span style={{ fontSize:11, color:'#64748b', fontWeight: 800 }}>{vitals.length} SEQUENTIAL RECORDS</span>
        </div>
        {loading ? <div className="spinner" /> : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th><th>Patient Identity</th><th>Pulse (BPM)</th>
                  <th>SpO₂ (%)</th><th>Temp (°F)</th><th>Diagnostic State</th>
                </tr>
              </thead>
              <tbody>
                {vitals.length === 0 && (
                  <tr><td colSpan={6} className="empty-state">No real-time telemetry received yet.</td></tr>
                )}
                {vitals.map(v => (
                  <tr key={v.vital_id}>
                    <td><span style={{ color: '#64748b', fontWeight: 600 }}>{v.timestamp ? toLocal(v.timestamp).toLocaleTimeString() : '—'}</span></td>
                    <td>
                      <strong>{patientName(v.patient_id)}</strong>
                      {v.source === 'thingspeak' && !v.is_fallback && (
                        <span style={{ marginLeft: 8, fontSize: 8, padding: '2px 4px', borderRadius: 4, background: 'rgba(34, 211, 238, 0.1)', color: '#22d3ee', border: '1px solid rgba(34, 211, 238, 0.2)' }}>IOT</span>
                      )}
                    </td>
                    <td style={{ fontWeight: 800, color: (v.heart_rate > 110 || v.heart_rate < 50) ? '#f43f5e' : '#34d399' }}>
                      {v.heart_rate}
                    </td>
                    <td style={{ fontWeight: 800, color: v.spo2 < 90 ? '#f43f5e' : '#34d399' }}>
                      {v.spo2}%
                    </td>
                    <td style={{ fontWeight: 800, color: (v.temperature > 101 || v.temperature < 96) ? '#fbbf24' : 'inherit' }}>
                      {v.temperature}°
                    </td>
                    <td>
                      <span className={`badge ${rowClass(v)==='vital-critical'?'badge-red':rowClass(v)==='vital-warning'?'badge-amber':'badge-green'}`}>
                        {rowClass(v) === 'vital-critical' ? 'CRITICAL' : rowClass(v) === 'vital-warning' ? 'WARNING' : 'STABLE'}
                      </span>
                      {v.source === 'thingspeak' && !v.is_fallback && (
                        <span style={{ fontSize: 9, color: '#22d3ee', marginLeft: 8, fontWeight: 700 }}>✓ HW</span>
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
