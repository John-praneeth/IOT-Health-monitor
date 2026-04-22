import React, { useState, useEffect, useCallback } from 'react';
import {
  getDashboardStats,
  getHealthFull,
  getVitalsSourceConfig,
  updateVitalsSourceConfig,
  getFakeVitalsStatus,
  forceStartFakeVitals,
  forceStopFakeVitals,
  cleanupVitalsByTime,
  freshResetDomainData,
} from '../api';
import { getDocsUrl, getRedocUrl } from '../config';

export default function SystemStatus() {
  const [stats, setStats]       = useState(null);
  const [health, setHealth]     = useState(null);
  const [loading, setLoading]   = useState(true);
  const [lastCheck, setLastCheck] = useState(null);
  const [sourceConfig, setSourceConfig] = useState(null);
  const [fakeVitalsStatus, setFakeVitalsStatus] = useState(null);
  const [sourceForm, setSourceForm] = useState({
    source: 'fake',
  });
  const [savingSource, setSavingSource] = useState(false);
  const [sourceMessage, setSourceMessage] = useState('');
  const [runtimeMessage, setRuntimeMessage] = useState('');
  const [cleanupMessage, setCleanupMessage] = useState('');
  const [resetMessage, setResetMessage] = useState('');
  const [runtimeBusy, setRuntimeBusy] = useState(false);
  const [cleanupBusy, setCleanupBusy] = useState(false);
  const [resetBusy, setResetBusy] = useState(false);
  const [cleanupForm, setCleanupForm] = useState({
    mode: 'last_24h',
    before_datetime: '',
    source: 'all',
  });
  const role = (localStorage.getItem('role') || '').toUpperCase();
  const isAdmin = role === 'ADMIN';

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const requests = [
        getDashboardStats(),
        getHealthFull(),
      ];
      if (isAdmin) {
        requests.push(getVitalsSourceConfig());
        requests.push(getFakeVitalsStatus());
      }
      const responses = await Promise.allSettled(requests);
      const [statsRes, healthRes, sourceRes, fakeVitalsRes] = responses;

      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value.data);
      }
      if (healthRes.status === 'fulfilled') {
        setHealth(healthRes.value.data);
      } else {
        setHealth({ status: 'error', db: { status: 'error', detail: 'Backend unreachable' }, redis: { status: 'error', detail: 'Backend unreachable' }, whatsapp: { status: 'unknown', detail: 'Backend unreachable' } });
      }
      if (isAdmin && sourceRes?.status === 'fulfilled' && sourceRes.value?.data) {
        setSourceConfig(sourceRes.value.data);
        setSourceForm({
          source: sourceRes.value.data.source,
        });
      }
      if (isAdmin && fakeVitalsRes?.status === 'fulfilled' && fakeVitalsRes.value?.data) {
        setFakeVitalsStatus(fakeVitalsRes.value.data);
      }
    } catch (err) {
      setHealth({ status: 'error', db: { status: 'error', detail: 'Backend unreachable' }, redis: { status: 'error', detail: 'Backend unreachable' }, whatsapp: { status: 'unknown', detail: 'Backend unreachable' } });
    } finally {
      setLoading(false);
      setLastCheck(new Date().toLocaleTimeString());
    }
  }, [isAdmin]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Auto-refresh every 30s
  useEffect(() => {
    const t = setInterval(fetchAll, 30000);
    return () => clearInterval(t);
  }, [fetchAll]);

  // ── helpers ──────────────────────────────────────────────────────────────
  const svcColor = (s) => ({ ok: '#4ade80', degraded: '#fbbf24', disabled: '#94a3b8', error: '#f87171', unknown: '#f87171' }[s] || '#94a3b8');
  const svcIcon  = (s) => ({ ok: '🟢', degraded: '🟡', disabled: '⚪', error: '🔴', unknown: '🔴' }[s] || '⚪');
  const svcLabel = (s) => ({ ok: 'Healthy', degraded: 'Degraded', disabled: 'Disabled', error: 'Error', unknown: 'Unknown' }[s] || s || 'Unknown');

  const overallStatus = health?.status || 'unknown';
  const overallColor  = svcColor(overallStatus);

  // ── styles ───────────────────────────────────────────────────────────────
  const card = {
    background: 'linear-gradient(165deg, rgba(7, 30, 45, 0.86), rgba(8, 23, 36, 0.92))',
    borderRadius: 10,
    padding: '18px 20px',
    border: '1px solid rgba(140, 190, 221, 0.22)',
  };

  const statCard = (color) => ({
    ...card,
    borderTop: `3px solid ${color}`,
    textAlign: 'center',
  });

  const ServiceCard = ({ title, icon, data }) => {
    const s = data?.status || 'unknown';
    const c = svcColor(s);
    return (
      <div style={{ ...card, borderLeft: `4px solid ${c}` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <span style={{ fontSize: 16, color: '#e2e8f0', fontWeight: 600 }}>
            {icon} {title}
          </span>
          <span style={{ fontSize: 18 }}>{data ? svcIcon(s) : '⏳'}</span>
        </div>
        <div style={{
          padding: '8px 12px', borderRadius: 6,
          background: s === 'ok' ? 'rgba(20,83,45,0.2)' : s === 'disabled' ? 'rgba(30,41,59,0.5)' : 'rgba(127,29,29,0.2)',
        }}>
          <div style={{ color: c, fontWeight: 700, fontSize: 13, marginBottom: 3 }}>
            {data ? svcLabel(s).toUpperCase() : 'CHECKING…'}
          </div>
          <div style={{ color: '#94a3b8', fontSize: 12 }}>
            {data?.detail || 'Waiting for health check…'}
          </div>
        </div>
      </div>
    );
  };

  const saveSourceConfig = async () => {
    setSavingSource(true);
    setSourceMessage('');
    try {
      const res = await updateVitalsSourceConfig({ source: sourceForm.source });
      setSourceConfig(res.data);
      setSourceMessage('Vitals source updated.');
    } catch (err) {
      setSourceMessage(err?.response?.data?.detail || 'Failed to update vitals source.');
    } finally {
      setSavingSource(false);
    }
  };

  const handleForceStart = async () => {
    setRuntimeBusy(true);
    setRuntimeMessage('');
    try {
      const res = await forceStartFakeVitals();
      setFakeVitalsStatus({ enabled: res.data.enabled });
      setRuntimeMessage(res.data.detail || 'Fake vitals started.');
      fetchAll();
    } catch (err) {
      setRuntimeMessage(err?.response?.data?.detail || 'Failed to start fake vitals.');
    } finally {
      setRuntimeBusy(false);
    }
  };

  const handleForceStop = async () => {
    setRuntimeBusy(true);
    setRuntimeMessage('');
    try {
      const res = await forceStopFakeVitals();
      setFakeVitalsStatus({ enabled: res.data.enabled });
      setRuntimeMessage(res.data.detail || 'Fake vitals stopped.');
      fetchAll();
    } catch (err) {
      setRuntimeMessage(err?.response?.data?.detail || 'Failed to stop fake vitals.');
    } finally {
      setRuntimeBusy(false);
    }
  };

  const handleCleanupVitals = async () => {
    setCleanupBusy(true);
    setCleanupMessage('');
    try {
      const payload = {
        mode: cleanupForm.mode,
        source: cleanupForm.source,
      };
      if (cleanupForm.mode === 'before_datetime') {
        if (!cleanupForm.before_datetime) {
          setCleanupMessage('Please select a date/time for custom cleanup.');
          setCleanupBusy(false);
          return;
        }
        payload.before_datetime = new Date(cleanupForm.before_datetime).toISOString();
      }
      const res = await cleanupVitalsByTime(payload);
      setCleanupMessage(`${res.data.detail} Deleted vitals: ${res.data.deleted_vitals}`);
      fetchAll();
    } catch (err) {
      setCleanupMessage(err?.response?.data?.detail || 'Vitals cleanup failed.');
    } finally {
      setCleanupBusy(false);
    }
  };

  const handleFreshReset = async () => {
    const confirmValue = window.prompt('Type RESET to confirm full data reset. Admin users will be preserved.');
    if (confirmValue !== 'RESET') {
      setResetMessage('Reset cancelled. Type RESET exactly to continue.');
      return;
    }
    setResetBusy(true);
    setResetMessage('');
    try {
      const res = await freshResetDomainData();
      setResetMessage(`${res.data.detail} Deleted patients: ${res.data.deleted_patients}, vitals: ${res.data.deleted_vitals}`);
      fetchAll();
    } catch (err) {
      setResetMessage(err?.response?.data?.detail || 'Fresh reset failed.');
    } finally {
      setResetBusy(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <h1>🖥️ System Status</h1>
        <p>Live overview of services, database health, and alert activity</p>
      </div>

      <div className="graphic-banner">
        <div className="banner-title">Platform Reliability Matrix</div>
        <div className="banner-subtitle">Real-time operational health of core infrastructure and message delivery.</div>
        <div className="chip-row">
          <span className="status-chip">DB Health</span>
          <span className="status-chip">Redis Signal</span>
          <span className="status-chip">WhatsApp Pipeline</span>
        </div>
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        {lastCheck && <span style={{ color: '#64748b', fontSize: 12 }}>Last updated: {lastCheck}</span>}
        <button
          onClick={fetchAll}
          disabled={loading}
          style={{
            padding: '7px 18px', borderRadius: 7, border: '1px solid #475569',
            background: '#1e293b', color: '#60a5fa', fontSize: 13,
            cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 600,
            opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? '⏳ Checking…' : '🔄 Refresh'}
        </button>
      </div>

      {/* Overall Banner */}
      <div style={{
        ...card,
        marginBottom: 24,
        display: 'flex', alignItems: 'center', gap: 16,
        borderColor: overallColor,
        background: overallStatus === 'ok'
          ? 'rgba(20,83,45,0.15)'
          : overallStatus === 'degraded'
            ? 'rgba(120,85,10,0.15)'
            : 'rgba(127,29,29,0.15)',
      }}>
        <span style={{ fontSize: 36 }}>{svcIcon(overallStatus)}</span>
        <div>
          <div style={{ color: overallColor, fontWeight: 700, fontSize: 20 }}>
            {overallStatus === 'ok'
              ? 'All Systems Operational'
              : overallStatus === 'degraded'
                ? 'System Degraded'
                : loading ? 'Checking Systems…' : 'System Error'}
          </div>
          <div style={{ color: '#94a3b8', fontSize: 13, marginTop: 3 }}>
            {overallStatus === 'ok'
              ? 'Backend, database, and all services are running normally.'
              : overallStatus === 'degraded'
                ? 'One or more services need attention. Check details below.'
                : loading ? 'Fetching service status…' : 'Unable to reach backend — is the server running?'}
          </div>
        </div>
      </div>

      {/* Service Health */}
      <h3 style={{ color: '#94a3b8', fontSize: 13, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
        Service Health
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14, marginBottom: 28 }}>
        <ServiceCard title="PostgreSQL"          icon="🐘" data={health?.db} />
        <ServiceCard title="Redis"               icon="🔴" data={health?.redis} />
        <ServiceCard title="WhatsApp (GREEN-API)" icon="📱" data={health?.whatsapp} />
      </div>

      {/* Stats — from DB */}
      <h3 style={{ color: '#94a3b8', fontSize: 13, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
        Database Summary
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 14, marginBottom: 28 }}>
        {[
          { label: 'Patients',    value: stats?.total_patients   ?? '—', color: '#60a5fa', icon: '🛏️' },
          { label: 'Doctors',     value: stats?.total_doctors    ?? '—', color: '#34d399', icon: '👨‍⚕️' },
          { label: 'Nurses',      value: stats?.total_nurses     ?? '—', color: '#a78bfa', icon: '👩‍⚕️' },
          { label: 'Hospitals',   value: stats?.total_hospitals  ?? '—', color: '#fbbf24', icon: '🏢' },
        ].map(s => (
          <div key={s.label} style={statCard(s.color)}>
            <div style={{ fontSize: 22, marginBottom: 4 }}>{s.icon}</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: s.color }}>{s.value}</div>
            <div style={{ color: '#94a3b8', fontSize: 13, marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Alert Activity */}
      <h3 style={{ color: '#94a3b8', fontSize: 13, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
        Alert Activity
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14, marginBottom: 28 }}>
        {[
          { label: 'Pending Alerts',      value: stats?.pending_alerts      ?? '—', color: '#f87171', icon: '🚨' },
          { label: 'Escalated Alerts',    value: stats?.escalated_alerts    ?? '—', color: '#fb923c', icon: '⚠️' },
          { label: 'Acknowledged Alerts', value: stats?.acknowledged_alerts ?? '—', color: '#4ade80', icon: '✅' },
        ].map(s => (
          <div key={s.label} style={statCard(s.color)}>
            <div style={{ fontSize: 22, marginBottom: 4 }}>{s.icon}</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: s.color }}>{s.value}</div>
            <div style={{ color: '#94a3b8', fontSize: 13, marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {isAdmin && (
        <div style={{ ...card, marginBottom: 28 }}>
          <h3 style={{ color: '#e2e8f0', fontSize: 15, marginBottom: 12 }}>🛠️ Admin Runtime Controls</h3>
          <div className="ops-grid" style={{ marginBottom: 8 }}>
            <section className="ops-card">
              <h3 style={{ color: '#e2e8f0', fontSize: 15, marginBottom: 10 }}>🧪 Vitals Data Source</h3>
              <p style={{ color: '#94a3b8', fontSize: 12, marginBottom: 10 }}>
                Current source: <strong style={{ color: '#e2e8f0' }}>{sourceConfig?.source || sourceForm.source}</strong>
              </p>
              <p style={{ color: '#64748b', fontSize: 12, marginTop: 0, marginBottom: 12 }}>
                ThingSpeak connection details are configured in backend environment variables.
              </p>
              <div className="ops-actions">
                <button
                  onClick={() => setSourceForm((prev) => ({ ...prev, source: prev.source === 'fake' ? 'thingspeak' : 'fake' }))}
                  disabled={savingSource}
                  style={{ padding: '8px 16px', borderRadius: 7, border: '1px solid #475569', background: '#0f172a', color: '#93c5fd', fontWeight: 600, cursor: savingSource ? 'not-allowed' : 'pointer', opacity: savingSource ? 0.6 : 1 }}
                >
                  Switch to {sourceForm.source === 'fake' ? 'ThingSpeak' : 'Fake'}
                </button>
                <button
                  onClick={saveSourceConfig}
                  disabled={savingSource}
                  style={{ padding: '8px 16px', borderRadius: 7, border: '1px solid #475569', background: '#1d4ed8', color: '#fff', fontWeight: 600, cursor: savingSource ? 'not-allowed' : 'pointer', opacity: savingSource ? 0.6 : 1 }}
                >
                  {savingSource ? 'Saving…' : 'Apply Source'}
                </button>
              </div>
              <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
                {sourceMessage && <span className={`ops-msg ${sourceMessage.includes('Failed') ? 'ops-msg-error' : 'ops-msg-success'}`}>{sourceMessage}</span>}
              </div>
            </section>

            <section className="ops-card">
              <h3 style={{ color: '#e2e8f0', fontSize: 15, marginBottom: 10 }}>⚙️ Fake Vitals Runtime</h3>
              <p style={{ color: '#94a3b8', fontSize: 12, marginTop: 0, marginBottom: 10 }}>
                Current state: <strong style={{ color: fakeVitalsStatus?.enabled ? '#4ade80' : '#f87171' }}>{fakeVitalsStatus?.enabled ? 'RUNNING' : 'STOPPED'}</strong>
              </p>
              <div className="ops-actions">
                <button
                  onClick={handleForceStart}
                  disabled={runtimeBusy}
                  style={{ padding: '8px 14px', borderRadius: 7, border: '1px solid #166534', background: '#14532d', color: '#dcfce7', fontWeight: 600, cursor: runtimeBusy ? 'not-allowed' : 'pointer', opacity: runtimeBusy ? 0.6 : 1 }}
                >
                  ▶ Force Start
                </button>
                <button
                  onClick={handleForceStop}
                  disabled={runtimeBusy}
                  style={{ padding: '8px 14px', borderRadius: 7, border: '1px solid #7f1d1d', background: '#7f1d1d', color: '#fee2e2', fontWeight: 600, cursor: runtimeBusy ? 'not-allowed' : 'pointer', opacity: runtimeBusy ? 0.6 : 1 }}
                >
                  ⏹ Force Stop
                </button>
              </div>
              <div style={{ marginTop: 10 }}>
                {runtimeMessage && <span className={`ops-msg ${runtimeMessage.toLowerCase().includes('failed') ? 'ops-msg-error' : 'ops-msg-success'}`}>{runtimeMessage}</span>}
              </div>
            </section>

            <section className="ops-card">
              <h3 style={{ color: '#e2e8f0', fontSize: 15, marginBottom: 10 }}>🧹 Vitals History Cleanup</h3>
              <p style={{ color: '#94a3b8', fontSize: 12, marginTop: 0, marginBottom: 10 }}>
                Delete vitals by time window and optionally by source.
              </p>
              <div className="ops-form-grid">
            <select
              value={cleanupForm.mode}
              onChange={(e) => setCleanupForm((prev) => ({ ...prev, mode: e.target.value }))}
              style={{ padding: '8px 10px', borderRadius: 7, background: '#0b1620', color: '#e2e8f0', border: '1px solid #334155' }}
            >
              <option value="last_24h">Older than 24 hours</option>
              <option value="last_7d">Older than 7 days</option>
              <option value="last_30d">Older than 30 days</option>
              <option value="before_datetime">Before custom date/time</option>
              <option value="all">Delete all vitals</option>
            </select>
            <select
              value={cleanupForm.source}
              onChange={(e) => setCleanupForm((prev) => ({ ...prev, source: e.target.value }))}
              style={{ padding: '8px 10px', borderRadius: 7, background: '#0b1620', color: '#e2e8f0', border: '1px solid #334155' }}
            >
              <option value="all">All Sources</option>
              <option value="fake">Fake Only</option>
              <option value="thingspeak">ThingSpeak Only</option>
            </select>
            <input
              type="datetime-local"
              value={cleanupForm.before_datetime}
              onChange={(e) => setCleanupForm((prev) => ({ ...prev, before_datetime: e.target.value }))}
              disabled={cleanupForm.mode !== 'before_datetime'}
              style={{ padding: '8px 10px', borderRadius: 7, background: '#0b1620', color: '#e2e8f0', border: '1px solid #334155', opacity: cleanupForm.mode !== 'before_datetime' ? 0.5 : 1 }}
            />
              </div>
              <div className="ops-actions" style={{ marginTop: 10 }}>
                <button
                  onClick={handleCleanupVitals}
                  disabled={cleanupBusy}
                  style={{ padding: '8px 14px', borderRadius: 7, border: '1px solid #0f766e', background: '#115e59', color: '#ccfbf1', fontWeight: 600, cursor: cleanupBusy ? 'not-allowed' : 'pointer', opacity: cleanupBusy ? 0.6 : 1 }}
                >
                  {cleanupBusy ? 'Cleaning…' : 'Run Cleanup'}
                </button>
              </div>
              <div style={{ marginTop: 10 }}>
                {cleanupMessage && <span className={`ops-msg ${cleanupMessage.toLowerCase().includes('failed') ? 'ops-msg-error' : 'ops-msg-success'}`}>{cleanupMessage}</span>}
              </div>
            </section>
          </div>

          <section className="ops-card ops-card-danger">
            <h3 style={{ color: '#fee2e2', fontSize: 15, marginBottom: 10 }}>🗑 Fresh Reset</h3>
            <p style={{ color: '#fecaca', fontSize: 12, marginTop: 0, marginBottom: 10 }}>
              Deletes doctors, nurses, patients, vitals, alerts, and hospitals. Admin account is preserved.
            </p>
            <p style={{ color: '#fda4af', fontSize: 12, marginTop: 0, marginBottom: 12 }}>
              Safety check enabled: you must type <strong>RESET</strong> to confirm.
            </p>
            <div className="ops-actions">
              <button
                onClick={handleFreshReset}
                disabled={resetBusy}
                style={{ padding: '8px 14px', borderRadius: 7, border: '1px solid #b91c1c', background: '#991b1b', color: '#fee2e2', fontWeight: 700, cursor: resetBusy ? 'not-allowed' : 'pointer', opacity: resetBusy ? 0.6 : 1 }}
              >
                {resetBusy ? 'Resetting…' : 'Run Fresh Reset'}
              </button>
              {resetMessage && <span className={`ops-msg ${resetMessage.toLowerCase().includes('failed') || resetMessage.toLowerCase().includes('cancelled') ? 'ops-msg-error' : 'ops-msg-success'}`}>{resetMessage}</span>}
            </div>
          </section>
        </div>
      )}

      {/* Redis note */}
      {health?.redis?.status === 'disabled' && (
        <div style={{ ...card, marginBottom: 20, padding: '12px 16px', borderColor: '#475569' }}>
          <span style={{ color: '#94a3b8', fontSize: 13 }}>
            ℹ️ <strong style={{ color: '#fbbf24' }}>Redis not running</strong> — The app works without Redis in development mode using the direct scheduler. Run{' '}
            <code style={{ background: '#374151', padding: '2px 6px', borderRadius: 4 }}>docker compose up --build</code> to start all services.
          </span>
        </div>
      )}

      {/* Quick links */}
      <div style={{ ...card, padding: '16px 20px' }}>
        <h3 style={{ color: '#e2e8f0', fontSize: 14, marginBottom: 12 }}>🔗 Quick Links</h3>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <a href={getDocsUrl()} target="_blank" rel="noopener noreferrer" style={{
            padding: '8px 18px', background: '#1d4ed8', borderRadius: 7,
            color: '#fff', textDecoration: 'none', fontSize: 13, fontWeight: 600,
          }}>
            📄 API Docs (Swagger)
          </a>
          <a href={getRedocUrl()} target="_blank" rel="noopener noreferrer" style={{
            padding: '8px 18px', background: '#0f766e', borderRadius: 7,
            color: '#fff', textDecoration: 'none', fontSize: 13, fontWeight: 600,
          }}>
            📘 API Docs (ReDoc)
          </a>
        </div>
        <p style={{ color: '#475569', fontSize: 11, marginTop: 10, marginBottom: 0 }}>
          Auto-refreshes every 30 seconds.
        </p>
      </div>
    </div>
  );
}
