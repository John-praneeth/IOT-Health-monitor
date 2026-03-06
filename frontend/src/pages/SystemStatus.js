import React, { useState, useEffect, useCallback } from 'react';
import { getDashboardStats, getHealthFull } from '../api';

export default function SystemStatus() {
  const [stats, setStats]       = useState(null);
  const [health, setHealth]     = useState(null);
  const [loading, setLoading]   = useState(true);
  const [lastCheck, setLastCheck] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, healthRes] = await Promise.all([
        getDashboardStats(),
        getHealthFull(),
      ]);
      setStats(statsRes.data);
      setHealth(healthRes.data);
    } catch (err) {
      setHealth({ status: 'error', db: { status: 'error', detail: 'Backend unreachable' }, redis: { status: 'error', detail: 'Backend unreachable' }, whatsapp: { status: 'unknown', detail: 'Backend unreachable' } });
    } finally {
      setLoading(false);
      setLastCheck(new Date().toLocaleTimeString());
    }
  }, []);

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
          <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer" style={{
            padding: '8px 18px', background: '#1d4ed8', borderRadius: 7,
            color: '#fff', textDecoration: 'none', fontSize: 13, fontWeight: 600,
          }}>
            📄 API Docs (Swagger)
          </a>
          <a href="http://localhost:8000/redoc" target="_blank" rel="noopener noreferrer" style={{
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
