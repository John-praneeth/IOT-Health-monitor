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
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.container} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={styles.header}>
          <div>
            <span style={{ fontSize: 18, fontWeight: 700 }}>💬 Treatment Chat</span>
            <span style={styles.patientBadge}>🛏️ {patientName}</span>
          </div>
          <button onClick={onClose} style={styles.closeBtn}>✕</button>
        </div>

        {error && <div style={styles.error}>⚠️ {error}</div>}

        {/* Messages */}
        <div style={styles.messageArea}>
          {messages.length === 0 && (
            <div style={styles.emptyState}>
              <span style={{ fontSize: 40 }}>💬</span>
              <p style={{ color: '#94a3b8', marginTop: 8 }}>No messages yet. Start the conversation about this patient's treatment.</p>
            </div>
          )}
          {messages.map((msg) => {
            const isMe = msg.sender_username === currentUser;
            return (
              <div key={msg.message_id} style={{
                ...styles.messageBubbleRow,
                justifyContent: isMe ? 'flex-end' : 'flex-start',
              }}>
                <div style={{
                  ...styles.messageBubble,
                  background: isMe ? '#1e3a5f' : '#1e293b',
                  borderLeft: isMe ? 'none' : `3px solid ${ROLE_COLORS[msg.sender_role] || '#64748b'}`,
                  borderRight: isMe ? `3px solid ${ROLE_COLORS[msg.sender_role] || '#64748b'}` : 'none',
                  alignItems: isMe ? 'flex-end' : 'flex-start',
                }}>
                  <div style={styles.senderRow}>
                    <span style={{ color: ROLE_COLORS[msg.sender_role] || '#94a3b8', fontWeight: 600, fontSize: 12 }}>
                      {ROLE_ICONS[msg.sender_role] || '👤'} {msg.sender_username}
                    </span>
                    <span style={styles.roleBadge(msg.sender_role)}>
                      {msg.sender_role}
                    </span>
                  </div>
                  <div style={styles.messageText}>{msg.message}</div>
                  <div style={styles.timestamp}>{formatTime(msg.created_at)}</div>
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSend} style={styles.inputArea}>
          <div style={styles.inputRow}>
            <span style={{ color: ROLE_COLORS[currentRole] || '#94a3b8', fontSize: 12, marginRight: 8 }}>
              {ROLE_ICONS[currentRole] || '👤'} {currentUser}
            </span>
          </div>
          <div style={styles.inputRow}>
            <input
              ref={inputRef}
              type="text"
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder="Type your message about treatment..."
              style={styles.input}
              disabled={sending}
              maxLength={2000}
            />
            <button
              type="submit"
              style={{
                ...styles.sendBtn,
                opacity: sending || !text.trim() ? 0.5 : 1,
              }}
              disabled={sending || !text.trim()}
            >
              {sending ? '⏳' : '📤'} Send
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
    background: '#0f172a',
    borderRadius: 16,
    border: '1px solid #334155',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: '0 25px 50px rgba(0,0,0,0.5)',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 20px',
    borderBottom: '1px solid #1e293b',
    background: '#0f172a',
  },
  patientBadge: {
    marginLeft: 10,
    padding: '3px 10px',
    background: '#1e293b',
    borderRadius: 12,
    fontSize: 12,
    color: '#94a3b8',
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
    borderTop: '1px solid #1e293b',
    background: '#0f172a',
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
    border: '1px solid #334155',
    background: '#1e293b',
    color: '#e2e8f0',
    fontSize: 14,
    outline: 'none',
  },
  sendBtn: {
    padding: '10px 18px',
    borderRadius: 10,
    border: 'none',
    background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
    color: '#fff',
    fontWeight: 600,
    fontSize: 13,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
};
