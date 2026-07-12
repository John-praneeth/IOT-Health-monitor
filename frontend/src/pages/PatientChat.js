import React, { useEffect, useState, useRef, useCallback } from 'react';
import { getPatientChat, sendPatientChat } from '../api';

const ROLE_COLORS = {
  ADMIN:  '#a78bfa',
  DOCTOR: '#60a5fa',
  NURSE:  '#34d399',
};

const ROLE_ICONS = {
  ADMIN:  '🛡️',
  DOCTOR: '👨‍⚕️',
  NURSE:  '👩‍⚕️',
};

export default function PatientChat({ patientId, patientName, onClose }) {
  const [messages, setMessages] = useState([]);
  const [text, setText]         = useState('');
  const [sending, setSending]   = useState(false);
  const [error, setError]       = useState('');
  const messagesEndRef          = useRef(null);
  const inputRef                = useRef(null);

  const currentUser = localStorage.getItem('username');
  const currentRole = localStorage.getItem('role');

  const loadMessages = useCallback(async () => {
    try {
      const res = await getPatientChat(patientId);
      setMessages(res.data);
    } catch (err) {
      setError('Failed to load chat');
    }
  }, [patientId]);

  useEffect(() => {
    loadMessages();
    const interval = setInterval(loadMessages, 4000);
    return () => clearInterval(interval);
  }, [loadMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    setSending(true);
    setError('');
    try {
      await sendPatientChat(patientId, text.trim());
      setText('');
      await loadMessages();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const formatTime = (ts) => {
    if (!ts) return '';
    const d = new Date(ts);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' +
           d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="card" style={{ width: 520, height: '80vh', display: 'flex', flexDirection: 'column' }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="card-header">
          <div style={{ display:'flex', alignItems:'center', gap:10 }}>
            <span style={{ fontSize: 18, fontWeight: 700 }}>💬 Treatment Log</span>
            <span className="badge badge-blue" style={{ background: 'rgba(34, 211, 238, 0.1)' }}>{patientName}</span>
          </div>
          <button onClick={onClose} style={{ background:'none', border:'none', color:'#94a3b8', fontSize:20, cursor:'pointer' }}>✕</button>
        </div>

        {error && <div style={{ background:'rgba(244,63,94,0.1)', color:'#fca5a5', padding:'10px 20px', fontSize:13 }}>⚠️ {error}</div>}

        {/* Messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {messages.length === 0 && (
            <div className="empty-state">
              <span style={{ fontSize: 40, opacity: 0.5 }}>💬</span>
              <p style={{ marginTop: 12 }}>No messages initialized for this patient's treatment session.</p>
            </div>
          )}
          {messages.map((msg) => {
            const isMe = msg.sender_username === currentUser;
            return (
              <div key={msg.message_id} style={{
                display: 'flex', width: '100%',
                justifyContent: isMe ? 'flex-end' : 'flex-start',
              }}>
                <div style={{
                  maxWidth: '85%', padding: '14px 18px', borderRadius: 16,
                  background: isMe ? 'rgba(34, 211, 238, 0.08)' : 'rgba(255,255,255,0.03)',
                  border: `1px solid ${isMe ? 'rgba(34, 211, 238, 0.2)' : 'rgba(255,255,255,0.06)'}`,
                  borderLeft: isMe ? undefined : `4px solid ${ROLE_COLORS[msg.sender_role] || '#64748b'}`,
                  boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={{ color: ROLE_COLORS[msg.sender_role] || '#94a3b8', fontWeight: 800, fontSize: 11, textTransform: 'uppercase' }}>
                      {ROLE_ICONS[msg.sender_role] || '👤'} {msg.sender_username}
                    </span>
                  </div>
                  <div style={{ color: '#f1f5f9', fontSize: 14, lineHeight: 1.5 }}>{msg.message}</div>
                  <div style={{ color: '#475569', fontSize: 10, marginTop: 8, textAlign: 'right', fontWeight: 600 }}>{formatTime(msg.created_at)}</div>
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSend} style={{ padding: 20, background: 'rgba(0,0,0,0.15)', borderTop: '1px solid var(--stroke)' }}>
          <div style={{ display: 'flex', gap: 12 }}>
            <input
              ref={inputRef}
              type="text"
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder="Transmit medical note..."
              style={{ flex: 1, background: 'rgba(0,0,0,0.3)', border: '1px solid var(--stroke)', borderRadius: 12, padding: '12px 16px', color: '#fff', outline: 'none' }}
              disabled={sending}
              maxLength={2000}
            />
            <button
              type="submit"
              className="btn btn-primary"
              style={{ padding: '0 24px', opacity: sending || !text.trim() ? 0.5 : 1 }}
              disabled={sending || !text.trim()}
            >
              {sending ? '⏳' : 'SEND'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    position: 'fixed',
    top: 0, left: 0, right: 0, bottom: 0,
    background: 'rgba(0,0,0,0.6)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    backdropFilter: 'blur(4px)',
  },
  container: {
    width: '100%',
    maxWidth: 520,
    height: '80vh',
    maxHeight: 700,
    background: 'linear-gradient(160deg, rgba(8,31,47,.96), rgba(8,24,38,.96))',
    borderRadius: 16,
    border: '1px solid rgba(148,193,224,.34)',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: '0 28px 60px rgba(0,0,0,0.45)',
    overflow: 'hidden',
    animation: 'chatEnter .28s ease',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 20px',
    borderBottom: '1px solid rgba(148,193,224,.2)',
    background: 'rgba(5,20,32,.7)',
  },
  patientBadge: {
    marginLeft: 10,
    padding: '3px 10px',
    background: 'rgba(45,212,191,.15)',
    borderRadius: 12,
    fontSize: 12,
    color: '#9be8dd',
  },
  closeBtn: {
    background: 'transparent',
    border: 'none',
    color: '#94a3b8',
    fontSize: 20,
    cursor: 'pointer',
    padding: '4px 8px',
    borderRadius: 6,
  },
  error: {
    color: '#f87171',
    padding: '8px 20px',
    fontSize: 13,
    background: 'rgba(239,68,68,0.08)',
  },
  messageArea: {
    flex: 1,
    overflowY: 'auto',
    padding: '16px 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    textAlign: 'center',
    padding: 20,
  },
  messageBubbleRow: {
    display: 'flex',
    width: '100%',
  },
  messageBubble: {
    maxWidth: '80%',
    padding: '10px 14px',
    borderRadius: 12,
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    boxShadow: '0 10px 20px rgba(0,0,0,.18)',
  },
  senderRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  roleBadge: (role) => ({
    fontSize: 9,
    padding: '1px 6px',
    borderRadius: 8,
    background: (ROLE_COLORS[role] || '#64748b') + '22',
    color: ROLE_COLORS[role] || '#64748b',
    fontWeight: 700,
    letterSpacing: 0.5,
  }),
  messageText: {
    color: '#e2e8f0',
    fontSize: 14,
    lineHeight: 1.5,
    wordBreak: 'break-word',
  },
  timestamp: {
    color: '#475569',
    fontSize: 10,
    marginTop: 2,
  },
  inputArea: {
    padding: '12px 20px',
    borderTop: '1px solid rgba(148,193,224,.18)',
    background: 'rgba(5,20,32,.75)',
  },
  inputRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  input: {
    flex: 1,
    padding: '10px 14px',
    borderRadius: 10,
    border: '1px solid rgba(148,193,224,.3)',
    background: 'rgba(8,30,45,.9)',
    color: '#e2e8f0',
    fontSize: 14,
    outline: 'none',
  },
  sendBtn: {
    padding: '10px 18px',
    borderRadius: 10,
    border: 'none',
    background: 'linear-gradient(135deg, #2dd4bf, #0ea5a6)',
    color: '#fff',
    fontWeight: 600,
    fontSize: 13,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
};
