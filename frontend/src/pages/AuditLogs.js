import React, { useEffect, useState } from 'react';
import { getAuditLogs } from '../api';

const toLocal = (ts) => ts ? new Date(ts.endsWith('Z') ? ts : ts + 'Z') : null;

export default function AuditLogs() {
  const [logs,       setLogs]       = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState('');
  const [entityFilter, setEntityFilter] = useState('');

  const load = async () => {
    try {
      const params = {};
      if (entityFilter) params.entity = entityFilter;
      const res = await getAuditLogs(params);
      setLogs(res.data);
    } catch { setError('Failed to load audit logs'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [entityFilter]);

  const entities = [...new Set(logs.map(l => l.entity))];

  return (
    <div>
      <div className="page-header">
        <h1>📋 Audit Logs</h1>
        <p>System activity log — admin only</p>
      </div>



      {error && <div style={{ color:'#f87171', marginBottom:16 }}>⚠️ {error}</div>}

      <div className="filter-row">
        <select
          style={{ background:'#1e293b', border:'1px solid #334155', color:'#e2e8f0',
                   borderRadius:8, padding:'8px 12px', fontSize:13 }}
          value={entityFilter}
          onChange={e => setEntityFilter(e.target.value)}>
          <option value="">All Entities</option>
          {entities.map(e => <option key={e} value={e}>{e}</option>)}
        </select>
        <button className="btn btn-primary btn-sm" onClick={load}>⟳ Refresh</button>
        <span style={{ color:'#64748b', fontSize:12 }}>{logs.length} records</span>
      </div>

      <div className="card">
        <div className="card-header"><h2>Activity Log</h2></div>
        {loading ? <div className="spinner" /> : (
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Action</th><th>Entity</th><th>Entity ID</th>
                <th>User ID</th><th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 && (
                <tr><td colSpan={6} className="empty-state">No audit logs found.</td></tr>
              )}
              {logs.map(l => (
                <tr key={l.log_id}>
                  <td>#{l.log_id}</td>
                  <td>
                    <span className={`badge ${
                      l.action.includes('DELETE') ? 'badge-red' :
                      l.action.includes('CREATE') || l.action.includes('REGISTER') ? 'badge-green' :
                      l.action.includes('LOGIN') ? 'badge-blue' : 'badge-amber'
                    }`}>{l.action}</span>
                  </td>
                  <td>{l.entity}</td>
                  <td>{l.entity_id || '—'}</td>
                  <td>{l.user_id || '—'}</td>
                  <td>{l.timestamp ? toLocal(l.timestamp).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
