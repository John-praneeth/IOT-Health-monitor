import React, { useEffect, useState, useCallback } from 'react';
import { getVitals, getPatients, getDoctors } from '../api';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

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
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  const patientName = (id) => patients.find(p => p.patient_id === id)?.name || `Patient ${id}`;

  const rowClass = (v) => {
    if (v.spo2 < 90 || v.heart_rate > 110 || v.heart_rate < 50) return 'vital-critical';
    if (v.temperature > 101 || v.temperature < 96) return 'vital-warning';
    return '';
  };

  // ── Chart data (reversed so oldest is left) ────────────────────────────
  const chartVitals = [...vitals].reverse();
  const labels = chartVitals.map(v => v.timestamp ? new Date(v.timestamp).toLocaleTimeString() : '');

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Heart Rate (bpm)',
        data: chartVitals.map(v => v.heart_rate),
        borderColor: '#f87171',
        backgroundColor: 'rgba(248,113,113,0.1)',
        tension: 0.3, fill: true,
      },
      {
        label: 'SpO₂ (%)',
        data: chartVitals.map(v => v.spo2),
        borderColor: '#34d399',
        backgroundColor: 'rgba(52,211,153,0.1)',
        tension: 0.3, fill: true,
      },
      {
        label: 'Temperature (°F)',
        data: chartVitals.map(v => v.temperature),
        borderColor: '#fbbf24',
        backgroundColor: 'rgba(251,191,36,0.1)',
        tension: 0.3, fill: true,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: '#e2e8f0' } },
      title: {
        display: true,
        text: filter ? `Trend: ${patientName(parseInt(filter))}` : 'Vitals Trend (All Patients)',
        color: '#e2e8f0',
      },
    },
    scales: {
      x: { ticks: { color: '#64748b', maxTicksLimit: 15 }, grid: { color: '#1e293b' } },
      y: { ticks: { color: '#64748b' }, grid: { color: '#1e293b' } },
    },
  };

  return (
    <div>
      <div className="page-header">
        <h1>Vitals</h1>
        <p>
          Most recent 100 readings &nbsp;
          <span className="live-tag">
            <span className="live-dot" />
            AUTO-REFRESH {lastRefresh && `· ${lastRefresh}`}
          </span>
        </p>
      </div>

      <div style={{ display:'flex', gap:12, marginBottom:20, flexWrap:'wrap' }}>
        <select
          style={{ background:'#1e293b', border:'1px solid #334155', color:'#e2e8f0',
                   borderRadius:8, padding:'8px 12px', fontSize:13 }}
          value={filter}
          onChange={e => setFilter(e.target.value)}
        >
          <option value="">All Patients</option>
          {patients.map(p => <option key={p.patient_id} value={p.patient_id}>{p.name}</option>)}
        </select>
        <select
          style={{ background:'#1e293b', border:'1px solid #334155', color:'#e2e8f0',
                   borderRadius:8, padding:'8px 12px', fontSize:13 }}
          value={doctorFilter}
          onChange={e => setDoctorFilter(e.target.value)}
        >
          <option value="">All Doctors</option>
          {doctors.map(d => <option key={d.doctor_id} value={d.doctor_id}>{d.name}</option>)}
        </select>
        <button className="btn btn-primary btn-sm" onClick={load}>⟳ Refresh</button>
        <button
          className={`btn btn-sm ${showChart ? 'btn-primary' : ''}`}
          style={{ background: showChart ? '#3b82f6' : '#1e293b', color: '#e2e8f0',
                   border: '1px solid #334155', borderRadius: 8, padding: '8px 14px',
                   cursor: 'pointer', fontSize: 13 }}
          onClick={() => setShowChart(!showChart)}
        >
          📈 {showChart ? 'Hide' : 'View'} Trends
        </button>
      </div>

      {/* ── Chart ────────────────────────────────────────────────── */}
      {showChart && vitals.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header"><h2>📈 Vitals Trend</h2></div>
          <div style={{ height: 320, padding: '0 16px 16px' }}>
            <Line data={chartData} options={chartOptions} />
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <h2>Vitals Log</h2>
          <span style={{ fontSize:12, color:'#64748b' }}>{vitals.length} records</span>
        </div>
        {loading ? <div className="spinner" /> : (
          <table>
            <thead>
              <tr>
                <th>Time</th><th>Patient</th><th>Heart Rate</th>
                <th>SpO₂</th><th>Temp (°F)</th><th>Blood Pressure</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {vitals.length === 0 && (
                <tr><td colSpan={7} className="empty-state">No vitals yet. Start the scheduler.</td></tr>
              )}
              {vitals.map(v => (
                <tr key={v.vital_id} className={rowClass(v)}>
                  <td>{v.timestamp ? new Date(v.timestamp).toLocaleTimeString() : '—'}</td>
                  <td>{patientName(v.patient_id)}</td>
                  <td style={{ color: (v.heart_rate > 110 || v.heart_rate < 50) ? '#f87171' : '#34d399' }}>
                    {v.heart_rate} bpm
                  </td>
                  <td style={{ color: v.spo2 < 90 ? '#f87171' : '#34d399' }}>
                    {v.spo2}%
                  </td>
                  <td style={{ color: (v.temperature > 101 || v.temperature < 96) ? '#fbbf24' : '#e2e8f0' }}>
                    {v.temperature}°F
                  </td>
                  <td>{v.blood_pressure}</td>
                  <td>
                    {rowClass(v) === 'vital-critical' && <span className="badge badge-red">Critical</span>}
                    {rowClass(v) === 'vital-warning'  && <span className="badge badge-amber">Warning</span>}
                    {rowClass(v) === ''               && <span className="badge badge-green">Normal</span>}
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
