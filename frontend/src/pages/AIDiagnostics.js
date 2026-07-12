import React, { useEffect, useState, useCallback } from 'react';
import { getAllAIDiagnostics, uploadMultimodalData, getEmbeddingSpace, getPatients } from '../api';
import { Scatter, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, BarElement,
  Title, Tooltip, Legend,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, BarElement, Title, Tooltip, Legend);

// ── State color mapping ──────────────────────────────────────────────────────
const STATE_COLORS = {
  AI_STABLE:       { bg: 'rgba(52,211,153,0.15)',  border: '#34d399', glow: '0 0 20px rgba(52,211,153,0.3)' },
  AI_TACHYCARDIA:  { bg: 'rgba(251,146,60,0.15)',  border: '#fb923c', glow: '0 0 20px rgba(251,146,60,0.3)' },
  AI_BRADYCARDIA:  { bg: 'rgba(251,191,36,0.15)',  border: '#fbbf24', glow: '0 0 20px rgba(251,191,36,0.3)' },
  AI_HYPOXIA:      { bg: 'rgba(244,63,94,0.15)',   border: '#f43f5e', glow: '0 0 20px rgba(244,63,94,0.3)' },
  AI_HYPERTHERMIA: { bg: 'rgba(239,68,68,0.15)',   border: '#ef4444', glow: '0 0 20px rgba(239,68,68,0.3)' },
  AI_HYPOTHERMIA:  { bg: 'rgba(96,165,250,0.15)',   border: '#60a5fa', glow: '0 0 20px rgba(96,165,250,0.3)' },
  AI_SEPSIS_RISK:  { bg: 'rgba(168,85,247,0.15)',  border: '#a855f7', glow: '0 0 20px rgba(168,85,247,0.3)' },
  AI_CRITICAL:     { bg: 'rgba(244,63,94,0.2)',    border: '#f43f5e', glow: '0 0 30px rgba(244,63,94,0.5)' },
};

const stateColor = (s) => STATE_COLORS[s] || STATE_COLORS.AI_STABLE;

const MODALITY_ICONS = { vitals: '📡', text: '📝', image: '🖼️', audio: '🎙️', document: '📄' };
const TREND_ARROWS = { IMPROVING: '↗', STABLE: '→', WORSENING: '↘', DETERIORATING: '⬇' };
const TREND_COLORS = { IMPROVING: '#34d399', STABLE: '#94a3b8', WORSENING: '#fbbf24', DETERIORATING: '#f43f5e' };

export default function AIDiagnostics() {
  const [diagnostics, setDiagnostics] = useState([]);
  const [patients, setPatients] = useState([]);
  const [embeddingSpace, setEmbeddingSpace] = useState(null);
  const [selectedPatient, setSelectedPatient] = useState('');
  const [uploadData, setUploadData] = useState({ clinical_text: '', document_text: '' });
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [activeSection, setActiveSection] = useState('overview'); // overview | upload | embedding

  const load = useCallback(async () => {
    try {
      const results = await Promise.allSettled([
        getAllAIDiagnostics(),
        getPatients(),
        getEmbeddingSpace(),
      ]);
      if (results[0].status === 'fulfilled') setDiagnostics(results[0].value.data || []);
      if (results[1].status === 'fulfilled') setPatients(results[1].value.data || []);
      if (results[2].status === 'fulfilled') setEmbeddingSpace(results[2].value.data || null);
      setLastRefresh(new Date().toLocaleTimeString());
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 12000);
    return () => clearInterval(id);
  }, [load]);

  // ── Upload Handler ──
  const handleUpload = async () => {
    if (!selectedPatient) return;
    setUploading(true);
    setUploadResult(null);
    try {
      const res = await uploadMultimodalData(parseInt(selectedPatient), uploadData);
      setUploadResult(res.data);
      setUploadData({ clinical_text: '', document_text: '' });
      load(); // refresh
    } catch (err) {
      setUploadResult({ error: err.response?.data?.detail || err.message });
    } finally {
      setUploading(false);
    }
  };

  const handleFileUpload = (field) => (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const b64 = reader.result.split(',')[1]; // Strip data:xxx;base64, prefix
      setUploadData(prev => ({ ...prev, [field]: b64 }));
    };
    reader.readAsDataURL(file);
  };

  // ── Stats ──
  const totalPatients = diagnostics.length;
  const flagged = diagnostics.filter(d => d.classification !== 'AI_STABLE').length;
  const critical = diagnostics.filter(d => d.classification === 'AI_CRITICAL').length;
  const avgRisk = totalPatients > 0 ? Math.round(diagnostics.reduce((s, d) => s + d.risk_severity, 0) / totalPatients) : 0;

  // ── Embedding Space Chart Data ──
  const scatterData = {
    datasets: [
      // Centroids
      ...(embeddingSpace?.centroids ? Object.entries(embeddingSpace.centroids).map(([label, coords]) => ({
        label: label.replace('AI_', ''),
        data: [{ x: coords[0], y: coords[1] }],
        backgroundColor: stateColor(label).border,
        borderColor: stateColor(label).border,
        pointRadius: 12,
        pointStyle: 'star',
        pointBorderWidth: 2,
      })) : []),
      // Patients
      {
        label: 'Patients',
        data: (embeddingSpace?.patients || []).map(p => ({
          x: p.embedding[0],
          y: p.embedding[1],
          label: p.name,
        })),
        backgroundColor: (embeddingSpace?.patients || []).map(p => stateColor(p.classification).border + '99'),
        borderColor: (embeddingSpace?.patients || []).map(p => stateColor(p.classification).border),
        pointRadius: 7,
        pointBorderWidth: 2,
      },
    ],
  };

  const scatterOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            if (ctx.dataset.label === 'Patients') {
              const p = embeddingSpace?.patients?.[ctx.dataIndex];
              return p ? `${p.name} — ${p.classification.replace('AI_', '')} (Risk: ${p.risk_severity})` : '';
            }
            return ctx.dataset.label;
          }
        }
      }
    },
    scales: {
      x: { title: { display: true, text: 'Embedding Axis 1', color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#64748b' } },
      y: { title: { display: true, text: 'Embedding Axis 2', color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#64748b' } },
    },
  };

  // ── Confidence chart for selected diagnostic ──
  const selectedDiag = uploadResult || (selectedPatient ? diagnostics.find(d => String(d.patient_id) === selectedPatient) : null);

  const confData = selectedDiag?.confidence ? {
    labels: Object.keys(selectedDiag.confidence).map(k => k.replace('AI_', '')),
    datasets: [{
      data: Object.values(selectedDiag.confidence).map(v => (v * 100).toFixed(1)),
      backgroundColor: Object.keys(selectedDiag.confidence).map(k => stateColor(k).border + '44'),
      borderColor: Object.keys(selectedDiag.confidence).map(k => stateColor(k).border),
      borderWidth: 1,
    }],
  } : null;

  const confOptions = {
    responsive: true,
    indexAxis: 'y',
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${c.raw}%` } } },
    scales: {
      x: { max: 100, grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#64748b', callback: v => v + '%' } },
      y: { grid: { display: false }, ticks: { color: '#e2e8f0', font: { weight: '700', size: 11 } } },
    },
  };

  // ── Architecture Flow Diagram (CSS) ──
  const ArchFlow = () => (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0, padding: '20px 0' }}>
      {/* Modality Inputs Row */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center', marginBottom: 4 }}>
        {[
          { icon: '📡', label: 'IoT Vitals', sub: 'HR, SpO₂, Temp' },
          { icon: '📝', label: 'Clinical Notes', sub: 'Text Input' },
          { icon: '🖼️', label: 'Medical Images', sub: 'X-ray, Scan' },
          { icon: '🎙️', label: 'Audio Data', sub: 'Heart/Lung' },
          { icon: '📄', label: 'Lab Reports', sub: 'Documents' },
        ].map((m, i) => (
          <div key={i} style={{
            background: 'rgba(34,211,238,0.06)', border: '1px solid rgba(34,211,238,0.15)',
            borderRadius: 12, padding: '12px 16px', textAlign: 'center', minWidth: 100,
            transition: 'all 0.3s', cursor: 'default',
          }}>
            <div style={{ fontSize: 24 }}>{m.icon}</div>
            <div style={{ fontSize: 10, fontWeight: 800, color: '#22d3ee', marginTop: 4 }}>{m.label}</div>
            <div style={{ fontSize: 8, color: '#64748b' }}>{m.sub}</div>
          </div>
        ))}
      </div>

      {/* Arrow Down */}
      <div style={{ fontSize: 20, color: '#64748b', lineHeight: 1 }}>▼ ▼ ▼ ▼ ▼</div>

      {/* Encoder Row */}
      <div style={{
        background: 'rgba(168,85,247,0.06)', border: '1px solid rgba(168,85,247,0.2)',
        borderRadius: 12, padding: '12px 24px', margin: '4px 0', textAlign: 'center',
      }}>
        <div style={{ fontSize: 11, fontWeight: 800, color: '#a855f7' }}>MODALITY ENCODERS</div>
        <div style={{ fontSize: 9, color: '#94a3b8' }}>Each encoder → ℝ⁸ embedding vector</div>
      </div>

      <div style={{ fontSize: 20, color: '#64748b', lineHeight: 1 }}>▼</div>

      {/* Fusion Layer */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(34,211,238,0.08), rgba(168,85,247,0.08))',
        border: '1px solid rgba(34,211,238,0.2)', borderRadius: 16,
        padding: '14px 32px', textAlign: 'center',
        boxShadow: '0 0 30px rgba(34,211,238,0.05)',
      }}>
        <div style={{ fontSize: 12, fontWeight: 800, color: '#22d3ee' }}>MULTIMODAL FUSION LAYER</div>
        <div style={{ fontSize: 9, color: '#94a3b8' }}>Weighted Concatenation + Linear Projection → ℝ¹⁶</div>
      </div>

      <div style={{ fontSize: 20, color: '#64748b', lineHeight: 1 }}>▼</div>

      {/* Unified Space */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(52,211,153,0.08), rgba(34,211,238,0.08))',
        border: '2px solid rgba(52,211,153,0.3)', borderRadius: 20,
        padding: '16px 40px', textAlign: 'center',
        boxShadow: '0 0 40px rgba(52,211,153,0.08)',
      }}>
        <div style={{ fontSize: 14, fontWeight: 800, color: '#34d399', letterSpacing: '0.05em' }}>UNIFIED EMBEDDING SPACE</div>
        <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 2 }}>Nearest-Centroid + Softmax Classifier (ℝ¹⁶)</div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 8, flexWrap: 'wrap' }}>
          {['STABLE', 'TACHYCARDIA', 'HYPOXIA', 'CRITICAL', 'SEPSIS'].map(s => (
            <span key={s} style={{
              fontSize: 8, padding: '2px 6px', borderRadius: 4, fontWeight: 800,
              background: stateColor('AI_' + s).bg, color: stateColor('AI_' + s).border || '#94a3b8',
              border: `1px solid ${(stateColor('AI_' + s).border || '#94a3b8')}33`,
            }}>{s}</span>
          ))}
        </div>
      </div>

      <div style={{ fontSize: 20, color: '#64748b', lineHeight: 1 }}>▼</div>

      {/* Output */}
      <div style={{
        background: 'rgba(244,63,94,0.06)', border: '1px solid rgba(244,63,94,0.2)',
        borderRadius: 12, padding: '12px 24px', textAlign: 'center',
      }}>
        <div style={{ fontSize: 11, fontWeight: 800, color: '#f43f5e' }}>🚨 CLASSIFICATION → DOCTOR ALERT</div>
        <div style={{ fontSize: 9, color: '#94a3b8' }}>Risk Score + Trend Analysis + Auto-Escalation</div>
      </div>
    </div>
  );

  // ── Risk Gauge SVG ──
  const RiskGauge = ({ value }) => {
    const angle = (value / 100) * 180;
    const color = value > 70 ? '#f43f5e' : value > 40 ? '#fbbf24' : '#34d399';
    const rad = (angle - 90) * (Math.PI / 180);
    const x = 50 + 40 * Math.cos(rad);
    const y = 50 + 40 * Math.sin(rad);
    return (
      <svg viewBox="0 0 100 60" style={{ width: 160, height: 100 }}>
        <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" strokeLinecap="round" />
        <path d={`M 10 50 A 40 40 0 ${angle > 90 ? 1 : 0} 1 ${x} ${y}`} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round" />
        <text x="50" y="48" textAnchor="middle" fill={color} fontSize="18" fontWeight="800" fontFamily="Space Grotesk">{value}</text>
        <text x="50" y="57" textAnchor="middle" fill="#64748b" fontSize="6" fontWeight="700">RISK SCORE</text>
      </svg>
    );
  };

  return (
    <div style={{ animation: 'reveal 0.4s ease-out' }}>
      <div className="main-topbar">
        <div>
          <div className="main-title">🧠 AI Diagnostic Engine</div>
          <div className="main-subtitle">
            <span className="live-tag">
              <span className="live-dot" />
              MULTIMODAL UNIFIED EMBEDDING SPACE {lastRefresh && `· ${lastRefresh}`}
            </span>
          </div>
        </div>
        <div className="topbar-actions">
          <button className="btn btn-primary btn-sm" onClick={load}>⟳ Refresh AI</button>
        </div>
      </div>

      {/* ── Stats Grid ── */}
      <div className="stats-grid">
        <div className="stat-card"><div className="label">AI Analysed</div><div className="value">{totalPatients}</div></div>
        <div className="stat-card red"><div className="label">AI Flagged</div><div className="value">{flagged}</div></div>
        <div className="stat-card red"><div className="label">Critical (AI)</div><div className="value">{critical}</div></div>
        <div className="stat-card amber"><div className="label">Avg Risk Score</div><div className="value">{avgRisk}</div></div>
      </div>

      {/* ── Section Tabs ── */}
      <div style={{ display: 'flex', gap: 4, background: 'rgba(0,0,0,0.2)', padding: 4, borderRadius: 10, border: '1px solid var(--stroke)', marginBottom: 24, width: 'fit-content' }}>
        {[
          { key: 'overview', label: '📊 AI OVERVIEW' },
          { key: 'upload', label: '📤 MULTIMODAL UPLOAD' },
          { key: 'embedding', label: '🌐 EMBEDDING SPACE' },
        ].map(t => (
          <button key={t.key} className="btn btn-sm" onClick={() => setActiveSection(t.key)}
            style={{ background: activeSection === t.key ? 'rgba(255,255,255,0.08)' : 'transparent', color: activeSection === t.key ? '#fff' : '#64748b', padding: '8px 16px', borderRadius: 8, fontSize: 11, fontWeight: 700 }}
          >{t.label}</button>
        ))}
      </div>

      {/* ═══ ARCHITECTURE FLOW ═══ */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header"><h2>Multimodal AI Pipeline Architecture</h2></div>
        <ArchFlow />
      </div>

      {/* ═══ OVERVIEW SECTION ═══ */}
      {activeSection === 'overview' && (
        <div className="card">
          <div className="card-header">
            <h2>Real-Time AI Classification</h2>
            <span style={{ fontSize: 11, color: '#64748b', fontWeight: 800 }}>{diagnostics.length} PATIENTS ANALYSED</span>
          </div>
          {loading ? <div className="spinner" /> : (
            <div style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Patient</th><th>Room</th><th>AI State</th><th>Confidence</th>
                    <th>Risk</th><th>Trend</th><th>Modalities</th>
                  </tr>
                </thead>
                <tbody>
                  {diagnostics.length === 0 && (
                    <tr><td colSpan={7} className="empty-state">No AI diagnostics available. Ensure patients have vitals data.</td></tr>
                  )}
                  {diagnostics.map(d => {
                    const sc = stateColor(d.classification);
                    const topConf = d.confidence ? Math.max(...Object.values(d.confidence)) : 0;
                    return (
                      <tr key={d.patient_id} style={d.classification === 'AI_CRITICAL' ? { background: 'rgba(244,63,94,0.03)' } : {}}>
                        <td><strong>{d.patient_name || `Patient ${d.patient_id}`}</strong></td>
                        <td>{d.room_number || '—'}</td>
                        <td>
                          <span style={{
                            display: 'inline-block', padding: '3px 10px', borderRadius: 6,
                            fontSize: 10, fontWeight: 800, background: sc.bg, color: sc.border,
                            border: `1px solid ${sc.border}33`, boxShadow: sc.glow,
                            animation: d.classification !== 'AI_STABLE' ? 'pulse 2s infinite' : 'none',
                          }}>
                            {d.classification.replace('AI_', '')}
                          </span>
                        </td>
                        <td>
                          <span style={{ fontWeight: 800, color: topConf > 0.5 ? '#f1f5f9' : '#94a3b8' }}>
                            {(topConf * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td>
                          <span style={{
                            fontWeight: 800, fontSize: 14,
                            color: d.risk_severity > 70 ? '#f43f5e' : d.risk_severity > 40 ? '#fbbf24' : '#34d399'
                          }}>
                            {d.risk_severity}
                          </span>
                        </td>
                        <td>
                          <span style={{ fontWeight: 800, fontSize: 16, color: TREND_COLORS[d.trend] || '#94a3b8' }}>
                            {TREND_ARROWS[d.trend] || '→'}
                          </span>
                          <span style={{ fontSize: 9, color: TREND_COLORS[d.trend] || '#94a3b8', marginLeft: 4, fontWeight: 700 }}>
                            {d.trend}
                          </span>
                        </td>
                        <td>
                          {(d.modalities_used || []).map(m => (
                            <span key={m} title={m} style={{ marginRight: 4, fontSize: 14 }}>
                              {MODALITY_ICONS[m] || '❓'}
                            </span>
                          ))}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ═══ UPLOAD SECTION ═══ */}
      {activeSection === 'upload' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 24 }}>
          {/* Upload Panel */}
          <div className="card">
            <div className="card-header"><h2>Multimodal Data Upload</h2></div>
            <div style={{ padding: 24 }}>
              <div className="form-group" style={{ marginBottom: 16 }}>
                <label>Select Patient</label>
                <select value={selectedPatient} onChange={e => setSelectedPatient(e.target.value)}
                  style={{ width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--stroke)', color: '#e2e8f0', borderRadius: 8, padding: '10px 12px', fontSize: 13 }}>
                  <option value="">— Choose Patient —</option>
                  {patients.map(p => <option key={p.patient_id} value={p.patient_id}>{p.name} (Room {p.room_number})</option>)}
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: 16 }}>
                <label>📝 Clinical Notes</label>
                <textarea value={uploadData.clinical_text}
                  onChange={e => setUploadData(prev => ({ ...prev, clinical_text: e.target.value }))}
                  placeholder="Enter clinical observations... e.g., Patient shows signs of tachycardia with elevated heart rate"
                  rows={3}
                  style={{ width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--stroke)', color: '#e2e8f0', borderRadius: 8, padding: '10px 12px', fontSize: 13, resize: 'vertical', fontFamily: 'inherit' }}
                />
              </div>

              <div className="form-group" style={{ marginBottom: 16 }}>
                <label>🖼️ Medical Image</label>
                <input type="file" accept="image/*" onChange={handleFileUpload('image_b64')}
                  style={{ width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--stroke)', color: '#e2e8f0', borderRadius: 8, padding: '8px 12px', fontSize: 12 }}
                />
              </div>

              <div className="form-group" style={{ marginBottom: 16 }}>
                <label>🎙️ Audio Waveform</label>
                <input type="file" accept="audio/*" onChange={handleFileUpload('audio_b64')}
                  style={{ width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--stroke)', color: '#e2e8f0', borderRadius: 8, padding: '8px 12px', fontSize: 12 }}
                />
              </div>

              <div className="form-group" style={{ marginBottom: 16 }}>
                <label>📄 Lab Report / Document</label>
                <textarea value={uploadData.document_text}
                  onChange={e => setUploadData(prev => ({ ...prev, document_text: e.target.value }))}
                  placeholder="Paste lab results... e.g., WBC: 15000, CRP: elevated, Glucose: 280 mg/dL"
                  rows={3}
                  style={{ width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--stroke)', color: '#e2e8f0', borderRadius: 8, padding: '10px 12px', fontSize: 13, resize: 'vertical', fontFamily: 'inherit' }}
                />
              </div>

              <button className="btn btn-primary" onClick={handleUpload} disabled={!selectedPatient || uploading}
                style={{ width: '100%', padding: '12px', fontWeight: 800, fontSize: 13, borderRadius: 10, border: 'none', cursor: selectedPatient ? 'pointer' : 'not-allowed', opacity: selectedPatient ? 1 : 0.5 }}
              >
                {uploading ? '⏳ Processing through Unified Embedding Space...' : '🧠 Run AI Diagnosis'}
              </button>
            </div>
          </div>

          {/* Results Panel */}
          <div className="card">
            <div className="card-header"><h2>AI Classification Result</h2></div>
            <div style={{ padding: 24 }}>
              {!selectedDiag ? (
                <div className="empty-state">Select a patient and upload data to see AI classification results.</div>
              ) : selectedDiag.error ? (
                <div style={{ color: '#f43f5e', fontWeight: 700, textAlign: 'center', padding: 20 }}>❌ {selectedDiag.error}</div>
              ) : (
                <>
                  {/* State Badge */}
                  <div style={{ textAlign: 'center', marginBottom: 20 }}>
                    <div style={{
                      display: 'inline-block', padding: '8px 24px', borderRadius: 12,
                      fontSize: 18, fontWeight: 800, letterSpacing: '0.05em',
                      background: stateColor(selectedDiag.classification).bg,
                      color: stateColor(selectedDiag.classification).border,
                      border: `2px solid ${stateColor(selectedDiag.classification).border}33`,
                      boxShadow: stateColor(selectedDiag.classification).glow,
                      animation: selectedDiag.classification !== 'AI_STABLE' ? 'pulse 2s infinite' : 'none',
                    }}>
                      {selectedDiag.classification.replace('AI_', '')}
                    </div>
                  </div>

                  {/* Risk Gauge + Trend */}
                  <div style={{ display: 'flex', justifyContent: 'center', gap: 40, marginBottom: 20 }}>
                    <RiskGauge value={selectedDiag.risk_severity} />
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 36, color: TREND_COLORS[selectedDiag.trend] }}>
                        {TREND_ARROWS[selectedDiag.trend]}
                      </div>
                      <div style={{ fontSize: 11, fontWeight: 800, color: TREND_COLORS[selectedDiag.trend] }}>
                        {selectedDiag.trend}
                      </div>
                      <div style={{ fontSize: 9, color: '#64748b', marginTop: 2 }}>
                        Velocity: {selectedDiag.trend_velocity}
                      </div>
                    </div>
                  </div>

                  {/* Modalities Used */}
                  <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginBottom: 20 }}>
                    {['vitals', 'text', 'image', 'audio', 'document'].map(m => (
                      <div key={m} style={{
                        padding: '6px 10px', borderRadius: 8, fontSize: 10, fontWeight: 700, textAlign: 'center',
                        background: (selectedDiag.modalities_used || []).includes(m) ? 'rgba(34,211,238,0.1)' : 'rgba(255,255,255,0.02)',
                        color: (selectedDiag.modalities_used || []).includes(m) ? '#22d3ee' : '#475569',
                        border: `1px solid ${(selectedDiag.modalities_used || []).includes(m) ? 'rgba(34,211,238,0.2)' : 'var(--stroke)'}`,
                      }}>
                        <div style={{ fontSize: 16 }}>{MODALITY_ICONS[m]}</div>
                        <div style={{ marginTop: 2 }}>{m.toUpperCase()}</div>
                      </div>
                    ))}
                  </div>

                  {/* Confidence Distribution */}
                  {confData && (
                    <div style={{ height: 200 }}>
                      <div style={{ fontSize: 10, fontWeight: 800, color: '#94a3b8', marginBottom: 8, textTransform: 'uppercase' }}>Softmax Confidence Distribution</div>
                      <Bar data={confData} options={confOptions} />
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══ EMBEDDING SPACE SECTION ═══ */}
      {activeSection === 'embedding' && (
        <div className="card">
          <div className="card-header">
            <h2>Unified Embedding Space Visualization</h2>
            <span style={{ fontSize: 10, color: '#64748b', fontWeight: 800 }}>ℝ¹⁶ → 2D PROJECTION</span>
          </div>
          <div style={{ padding: 24 }}>
            {/* Legend */}
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
              {Object.entries(STATE_COLORS).map(([label, sc]) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <div style={{ width: 10, height: 10, borderRadius: '50%', background: sc.border }} />
                  <span style={{ fontSize: 9, color: '#94a3b8', fontWeight: 700 }}>{label.replace('AI_', '')}</span>
                </div>
              ))}
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <div style={{ width: 10, height: 10, background: '#64748b', clipPath: 'polygon(50% 0%, 100% 100%, 0% 100%)' }} />
                <span style={{ fontSize: 9, color: '#94a3b8', fontWeight: 700 }}>★ = Centroid</span>
              </div>
            </div>

            <div style={{ height: 400 }}>
              {embeddingSpace ? (
                <Scatter data={scatterData} options={scatterOptions} />
              ) : (
                <div className="empty-state">Loading embedding space data...</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
