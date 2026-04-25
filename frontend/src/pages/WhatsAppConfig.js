import React, { useEffect, useState, useCallback } from 'react';
import {
  getWhatsAppConfig,
  pauseWhatsAppAlerts,
  resumeWhatsAppAlerts,
  addWhatsAppRecipient,
  removeWhatsAppRecipient,
  getDoctors,
  getNurses,
  updateDoctor,
  updateNurse,
} from '../api';

export default function WhatsAppConfig() {
  const [config, setConfig]           = useState(null);
  const [doctors, setDoctors]         = useState([]);
  const [nurses, setNurses]           = useState([]);
  const [loading, setLoading]         = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError]             = useState('');
  const [recipientInput, setRecipientInput] = useState('');

  const role = localStorage.getItem('role');

  const load = useCallback(async () => {
    try {
      const [cfgRes, docRes, nurRes] = await Promise.all([
        getWhatsAppConfig(),
        getDoctors(),
        getNurses(),
      ]);
      setConfig(cfgRes.data);
      setDoctors(docRes.data || []);
      setNurses(nurRes.data || []);
      setError('');
    } catch (err) {
      if (err.response?.status === 403) {
        setError('Only admins can access WhatsApp configuration.');
      } else {
        setError('Failed to load WhatsApp configuration.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Combine all registered doctors + nurses who have a phone number
  const registeredRecipients = [
    ...doctors.filter(d => d.phone).map(d => ({
      id: d.doctor_id,
      name: d.name,
      phone: d.phone,
      role: 'Doctor',
      dept: d.specialization || '',
      roleIcon: '👨‍⚕️',
      original: d
    })),
    ...nurses.filter(n => n.phone).map(n => ({
      id: n.nurse_id,
      name: n.name,
      phone: n.phone,
      role: 'Nurse',
      dept: n.department || '',
      roleIcon: '👩‍⚕️',
      original: n
    })),
  ];

  const handleRemoveAutoRecipient = async (r) => {
    if (!window.confirm(`Remove ${r.name}'s phone number to stop WhatsApp alerts for them?`)) return;
    setActionLoading(true);
    try {
      if (r.role === 'Doctor') {
        await updateDoctor(r.id, {
          name: r.original.name,
          specialization: r.original.specialization,
          hospital_id: r.original.hospital_id,
          phone: null,
          email: r.original.email,
          is_freelancer: r.original.is_freelancer,
        });
      } else {
        await updateNurse(r.id, {
          name: r.original.name,
          department: r.original.department,
          hospital_id: r.original.hospital_id,
          phone: null,
          email: r.original.email,
          shift_time: r.original.shift_time,
        });
      }
      await load();
    } catch (err) {
      setError('Failed to remove phone: ' + (err.response?.data?.detail || err.message));
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggleAlerts = async () => {
    setActionLoading(true);
    try {
      const res = config?.alerts_paused
        ? await resumeWhatsAppAlerts()
        : await pauseWhatsAppAlerts();
      setConfig(res.data);
      setError('');
    } catch (err) {
      setError('Failed to toggle alerts: ' + (err.response?.data?.detail || err.message));
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddRecipient = async (e) => {
    e.preventDefault();
    const phone = recipientInput.replace(/\D/g, '');
    if (!phone) return;
    setActionLoading(true);
    try {
      const res = await addWhatsAppRecipient(phone);
      setConfig(res.data);
      setRecipientInput('');
      setError('');
    } catch (err) {
      setError('Failed to add recipient: ' + (err.response?.data?.detail || err.message));
    } finally {
      setActionLoading(false);
    }
  };

  const handleRemoveRecipient = async (phone) => {
    setActionLoading(true);
    try {
      const res = await removeWhatsAppRecipient(phone);
      setConfig(res.data);
      setError('');
    } catch (err) {
      setError('Failed to remove recipient: ' + (err.response?.data?.detail || err.message));
    } finally {
      setActionLoading(false);
    }
  };

  if (role !== 'ADMIN') {
    return (
      <div style={{ animation: 'reveal 0.4s ease-out' }}>
        <div className="main-topbar">
          <div>
            <div className="main-title">Communication Settings</div>
            <div className="main-subtitle" style={{ color: '#ef4444' }}>⛔ Administrative Access Required</div>
          </div>
        </div>
      </div>
    );
  }

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: '#94a3b8' }}>Loading…</div>;

  return (
    <div style={{ animation: 'reveal 0.4s ease-out' }}>
      <div className="main-topbar">
        <div>
          <div className="main-title">Communication Settings</div>
          <div className="main-subtitle">Manage automated WhatsApp clinical alerts and recipient registry</div>
        </div>
        <div className="topbar-actions">
           <button className="btn btn-primary btn-sm" onClick={load}>⟳ Refresh Config</button>
        </div>
      </div>

      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.15)',
          border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 8,
          padding: '12px 16px',
          marginBottom: 20,
          color: '#fca5a5',
        }}>
          ❌ {error}
        </div>
      )}

      {/* Status Cards */}
      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: 24 }}>
        <div className={`stat-card ${config?.enabled ? 'green' : 'red'}`}>
          <div className="label">Status</div>
          <div className="value" style={{ fontSize: 18 }}>{config?.enabled ? '✅ Enabled' : '❌ Disabled'}</div>
        </div>
        <div className={`stat-card ${config?.credentials_set ? 'green' : 'red'}`}>
          <div className="label">GREEN-API</div>
          <div className="value" style={{ fontSize: 16 }}>{config?.credentials_set ? '🔑 Connected' : '⚠️ Not Configured'}</div>
        </div>
        <div className="stat-card blue">
          <div className="label">Alert Recipients</div>
          <div className="value">{registeredRecipients.length}</div>
        </div>
      </div>

      {/* 🔴🟢 Force Stop / Start WhatsApp Alerts */}
      <div style={{
        background: config?.alerts_paused
          ? 'rgba(239,68,68,0.1)'
          : 'rgba(16,185,129,0.1)',
        border: `2px solid ${config?.alerts_paused ? 'rgba(239,68,68,0.4)' : 'rgba(16,185,129,0.4)'}`,
        borderRadius: 12,
        padding: 20,
        marginBottom: 24,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 12,
      }}>
        <div>
          <h3 style={{ color: config?.alerts_paused ? '#fca5a5' : '#6ee7b7', margin: 0, fontSize: 16 }}>
            {config?.alerts_paused ? '⏸️ WhatsApp Alerts are PAUSED' : '▶️ WhatsApp Alerts are ACTIVE'}
          </h3>
          <p style={{ color: '#94a3b8', fontSize: 13, margin: '6px 0 0' }}>
            {config?.alerts_paused
              ? 'No WhatsApp messages will be sent for new alerts. In-app alerts still work.'
              : 'WhatsApp messages are being sent to assigned doctors when alerts trigger.'}
          </p>
        </div>
        <button
          onClick={handleToggleAlerts}
          disabled={actionLoading}
          style={{
            padding: '12px 28px',
            borderRadius: 10,
            border: 'none',
            background: config?.alerts_paused
              ? 'linear-gradient(135deg, #10b981, #059669)'
              : 'linear-gradient(135deg, #ef4444, #dc2626)',
            color: 'white',
            fontWeight: 700,
            cursor: 'pointer',
            opacity: actionLoading ? 0.5 : 1,
            fontSize: 15,
            whiteSpace: 'nowrap',
            minWidth: 180,
            boxShadow: config?.alerts_paused
              ? '0 4px 15px rgba(16,185,129,0.3)'
              : '0 4px 15px rgba(239,68,68,0.3)',
            transition: 'all 0.2s ease',
          }}
        >
          {actionLoading
            ? '⏳ Processing…'
            : config?.alerts_paused
              ? '▶️ Start Alerts'
              : '⏹️ Force Stop Alerts'}
        </button>
      </div>

      {!config?.credentials_set && (
        <div style={{
          background: 'rgba(251,191,36,0.1)',
          border: '1px solid rgba(251,191,36,0.3)',
          borderRadius: 8,
          padding: '12px 16px',
          marginBottom: 20,
          color: '#fcd34d',
        }}>
          ⚠️ <strong>GREEN-API credentials not set.</strong> Add <code>GREEN_API_ID</code> and <code>GREEN_API_TOKEN</code> to your backend <code>.env</code> file and restart the server.
        </div>
      )}

      {/* Recipients — auto-populated from registered doctors & nurses */}
      <div className="card" style={{
        borderRadius: 12,
        padding: 20,
        marginBottom: 24,
      }}>
        <h3 style={{ color: '#e2e8f0', marginBottom: 4, fontSize: 15 }}>📋 Alert Recipients</h3>
        <p style={{ color: '#64748b', fontSize: 12, marginBottom: 16 }}>
          Auto-populated from registered doctors &amp; nurses. To add or remove a recipient, register or delete them from the <strong style={{ color: '#93c5fd' }}>Doctors</strong> / <strong style={{ color: '#93c5fd' }}>Nurses</strong> pages.
        </p>

        {registeredRecipients.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {registeredRecipients.map((r, i) => (
              <div key={i} style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '12px 14px',
                background: 'rgba(0,0,0,0.2)',
                borderRadius: 8,
                border: '1px solid rgba(255,255,255,0.08)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontSize: 22 }}>{r.roleIcon}</span>
                  <div>
                    <div style={{ color: '#e2e8f0', fontSize: 14, fontWeight: 600 }}>{r.name}</div>
                    <div style={{ color: '#64748b', fontSize: 12, marginTop: 2 }}>
                      {r.role}{r.dept ? ` · ${r.dept}` : ''}
                    </div>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, justifyContent: 'flex-end' }}>
                    <div>
                      <div style={{ color: '#67e8f9', fontFamily: 'monospace', fontSize: 13 }}>+{r.phone}</div>
                      <div style={{ color: '#10b981', fontSize: 11, marginTop: 2 }}>✓ via GREEN-API</div>
                    </div>
                    <button
                      className="btn btn-danger btn-sm"
                      disabled={actionLoading}
                      onClick={() => handleRemoveAutoRecipient(r)}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: '#64748b', textAlign: 'center', padding: 30 }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>📭</div>
            <div>No recipients yet.</div>
            <div style={{ fontSize: 12, marginTop: 6 }}>
              Register doctors or nurses with phone numbers and they will appear here automatically.
            </div>
          </div>
        )}
      </div>

      <div className="card" style={{
        borderRadius: 12,
        padding: 20,
        marginBottom: 24,
      }}>
        <h3 style={{ color: '#e2e8f0', marginBottom: 8, fontSize: 15 }}>🛠️ Manual Recipients</h3>
        <p style={{ color: '#64748b', fontSize: 12, marginBottom: 14 }}>
          Add/remove test recipients used by WhatsApp config and manual testing.
        </p>
        <form onSubmit={handleAddRecipient} style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <input
            value={recipientInput}
            onChange={(e) => setRecipientInput(e.target.value)}
            placeholder="e.g. 919876543210"
            style={{
              flex: 1,
              background: '#0f172a',
              border: '1px solid #334155',
              borderRadius: 8,
              color: '#e2e8f0',
              padding: '10px 12px',
            }}
          />
          <button type="submit" className="btn btn-primary btn-sm" disabled={actionLoading}>
            + Add
          </button>
        </form>
        {(config?.recipients || []).length === 0 ? (
          <div style={{ color: '#64748b', fontSize: 12 }}>No manual recipients configured.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {config.recipients.map((phone) => (
              <div key={phone} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 8, padding: '8px 12px',
              }}>
                <span style={{ color: '#67e8f9', fontFamily: 'monospace', fontSize: 13 }}>+{phone}</span>
                <button
                  className="btn btn-danger btn-sm"
                  disabled={actionLoading}
                  onClick={() => handleRemoveRecipient(phone)}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
}
