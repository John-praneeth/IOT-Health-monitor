import React, { useState, useEffect, useCallback } from 'react';
import {
  getDashboardStats,
  getHealthFull,
  getVitalsSourceConfig,
  updateVitalsSourceConfig,
} from '../api';
import { getDocsUrl, getRedocUrl } from '../config';

export default function SystemStatus() {
  const [stats, setStats]       = useState(null);
  const [health, setHealth]     = useState(null);
  const [loading, setLoading]   = useState(true);
  const [lastCheck, setLastCheck] = useState(null);
  const [sourceConfig, setSourceConfig] = useState(null);
  const [sourceForm, setSourceForm] = useState({
    source: 'fake',
    thingspeak_channel_id: '',
    thingspeak_read_api_key: '',
    thingspeak_temp_unit: 'F',
    thingspeak_stale_seconds: 120,
  });
  const [savingSource, setSavingSource] = useState(false);
  const [sourceMessage, setSourceMessage] = useState('');
  const role = (localStorage.getItem('role') || '').toUpperCase();
  const isAdmin = role === 'ADMIN';

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const requests = [
        getDashboardStats(),
        getHealthFull(),
      ];
      if (isAdmin) requests.push(getVitalsSourceConfig());
      const responses = await Promise.all(requests);
      const [statsRes, healthRes, sourceRes] = responses;
      setStats(statsRes.data);
      setHealth(healthRes.data);
      if (isAdmin && sourceRes?.data) {
        setSourceConfig(sourceRes.data);
        setSourceForm({
          source: sourceRes.data.source,
          thingspeak_channel_id: sourceRes.data.thingspeak_channel_id || '',
          thingspeak_read_api_key: '',
          thingspeak_temp_unit: sourceRes.data.thingspeak_temp_unit || 'F',
          thingspeak_stale_seconds: sourceRes.data.thingspeak_stale_seconds || 120,
        });
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
    background: '#1e293b',
    borderRadius: 10,
    padding: '18px 20px',
    border: '1px solid #334155',
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
      const payload = {
        source: sourceForm.source,
        thingspeak_temp_unit: sourceForm.thingspeak_temp_unit,
        thingspeak_stale_seconds: Number(sourceForm.thingspeak_stale_seconds),
      };
      if (sourceForm.thingspeak_channel_id.trim()) {
        payload.thingspeak_channel_id = sourceForm.thingspeak_channel_id.trim();
      }
      if (sourceForm.thingspeak_read_api_key.trim()) {
        payload.thingspeak_read_api_key = sourceForm.thingspeak_read_api_key.trim();
      }
      const res = await updateVitalsSourceConfig(payload);
      setSourceConfig(res.data);
      setSourceForm((prev) => ({ ...prev, thingspeak_read_api_key: '' }));
      setSourceMessage('Vitals source updated.');
    } catch (err) {
      setSourceMessage(err?.response?.data?.detail || 'Failed to update vitals source.');
    } finally {
      setSavingSource(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <h1>🖥️ System Status</h1>
        <p>Live overview of services, database health, and alert activity</p>
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 28 }}>
        <ServiceCard title="PostgreSQL"          icon="🐘" data={health?.db} />
        <ServiceCard title="Redis"               icon="🔴" data={health?.redis} />
        <ServiceCard title="WhatsApp (GREEN-API)" icon="📱" data={health?.whatsapp} />
      </div>

      {/* Stats — from DB */}
      <h3 style={{ color: '#94a3b8', fontSize: 13, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
        Database Summary
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 28 }}>
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 28 }}>
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
          <h3 style={{ color: '#e2e8f0', fontSize: 15, marginBottom: 14 }}>🧪 Vitals Data Source</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(240px, 1fr))', gap: 12 }}>
            <div>
              <label style={{ color: '#94a3b8', fontSize: 12 }}>Source</label>
              <select
                value={sourceForm.source}
                onChange={(e) => setSourceForm((prev) => ({ ...prev, source: e.target.value }))}
                style={{ width: '100%', marginTop: 5, padding: '8px 10px', borderRadius: 6, background: '#0f172a', color: '#e2e8f0', border: '1px solid #334155' }}
              >
                <option value="fake">Fake vitals (demo)</option>
                <option value="thingspeak">ThingSpeak (real hardware)</option>
              </select>
            </div>
            <div>
              <label style={{ color: '#94a3b8', fontSize: 12 }}>ThingSpeak Channel ID</label>
              <input
                value={sourceForm.thingspeak_channel_id}
                onChange={(e) => setSourceForm((prev) => ({ ...prev, thingspeak_channel_id: e.target.value }))}
                style={{ width: '100%', marginTop: 5, padding: '8px 10px', borderRadius: 6, background: '#0f172a', color: '#e2e8f0', border: '1px solid #334155' }}
              />
            </div>
            <div>
              <label style={{ color: '#94a3b8', fontSize: 12 }}>ThingSpeak Read API Key (optional)</label>
              <input
                value={sourceForm.thingspeak_read_api_key}
                onChange={(e) => setSourceForm((prev) => ({ ...prev, thingspeak_read_api_key: e.target.value }))}
                placeholder={sourceConfig?.thingspeak_read_api_key_set ? 'Configured (leave blank to keep)' : ''}
                style={{ width: '100%', marginTop: 5, padding: '8px 10px', borderRadius: 6, background: '#0f172a', color: '#e2e8f0', border: '1px solid #334155' }}
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={{ color: '#94a3b8', fontSize: 12 }}>Temperature Unit</label>
                <select
                  value={sourceForm.thingspeak_temp_unit}
                  onChange={(e) => setSourceForm((prev) => ({ ...prev, thingspeak_temp_unit: e.target.value }))}
                  style={{ width: '100%', marginTop: 5, padding: '8px 10px', borderRadius: 6, background: '#0f172a', color: '#e2e8f0', border: '1px solid #334155' }}
                >
                  <option value="F">Fahrenheit</option>
                  <option value="C">Celsius</option>
                </select>
              </div>
              <div>
                <label style={{ color: '#94a3b8', fontSize: 12 }}>Stale Threshold (sec)</label>
                <input
                  type="number"
                  min={10}
                  max={3600}
                  value={sourceForm.thingspeak_stale_seconds}
                  onChange={(e) => setSourceForm((prev) => ({ ...prev, thingspeak_stale_seconds: e.target.value }))}
                  style={{ width: '100%', marginTop: 5, padding: '8px 10px', borderRadius: 6, background: '#0f172a', color: '#e2e8f0', border: '1px solid #334155' }}
                />
              </div>
            </div>
          </div>
          <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
            <button
              onClick={saveSourceConfig}
              disabled={savingSource}
              style={{ padding: '8px 16px', borderRadius: 7, border: '1px solid #475569', background: '#1d4ed8', color: '#fff', fontWeight: 600, cursor: savingSource ? 'not-allowed' : 'pointer', opacity: savingSource ? 0.6 : 1 }}
            >
              {savingSource ? 'Saving…' : 'Save Source Settings'}
            </button>
            {sourceMessage && <span style={{ color: sourceMessage.includes('Failed') ? '#f87171' : '#4ade80', fontSize: 12 }}>{sourceMessage}</span>}
          </div>
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
