import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Patients from './pages/Patients';
import Vitals from './pages/Vitals';
import Alerts from './pages/Alerts';
import Doctors from './pages/Doctors';
import Nurses from './pages/Nurses';
import Hospitals from './pages/Hospitals';
import AuditLogs from './pages/AuditLogs';
import WhatsAppConfig from './pages/WhatsAppConfig';
import SystemStatus from './pages/SystemStatus';
import Login from './pages/Login';
import { getMe, logout } from './api';
import { API_BASE_LABEL } from './config';
import './App.css';

export default function App() {
  const [user, setUser] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [serverOffline, setServerOffline] = useState(false);

  useEffect(() => {
    const handleOffline = () => setServerOffline(true);
    window.addEventListener('server-offline', handleOffline);
    return () => window.removeEventListener('server-offline', handleOffline);
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const role = (localStorage.getItem('role') || '').toUpperCase();
    const username = localStorage.getItem('username');
    const doctor_id = localStorage.getItem('doctor_id');
    const nurse_id = localStorage.getItem('nurse_id');
    const user_id = localStorage.getItem('user_id');
    if (token && role && username) {
      setUser({ token, role, username, doctor_id, nurse_id, user_id });
    }
  }, []);

  const handleLogin = async (data) => {
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('role', (data.role || '').toUpperCase());
    localStorage.setItem('username', data.username);
    if (data.doctor_id) localStorage.setItem('doctor_id', data.doctor_id);
    if (data.nurse_id) localStorage.setItem('nurse_id', data.nurse_id);
    // Fetch user_id from /auth/me
    try {
      const meRes = await getMe();
      localStorage.setItem('user_id', meRes.data.user_id);
    } catch { /* ignore */ }
    setUser({
      token: data.access_token, role: (data.role || '').toUpperCase(), username: data.username,
      doctor_id: data.doctor_id, nurse_id: data.nurse_id,
    });
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch (e) {
      // ignore
    }
    localStorage.clear();
    setUser(null);
  };

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <Router>
      <div className="app-layout">
        <div className="bg-orb orb-a" />
        <div className="bg-orb orb-b" />
        <div className="bg-orb orb-c" />

        {serverOffline && (
          <div className="server-offline-banner">
            ⚠️ Connection Lost: The server is currently offline. Some features may be limited. 
            <button onClick={() => setServerOffline(false)} style={{ marginLeft: 12, background:'rgba(255,255,255,0.1)', border:'1px solid #fff', color:'#fff', padding:'2px 8px', borderRadius:4, cursor:'pointer' }}>Dismiss</button>
          </div>
        )}

        <button className="mobile-nav-toggle" onClick={() => setSidebarOpen(v => !v)}>
          {sidebarOpen ? '✕' : '☰'}
        </button>

        <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
          <div className="sidebar-logo">
            <span className="logo-icon">🏥</span>
            <span className="logo-text">PatientWatch</span>
          </div>
          <div className="sidebar-subtitle">Intelligent Care Ops</div>
          
          <nav className="sidebar-nav">
            <NavLink to="/" end className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'} onClick={() => setSidebarOpen(false)}>📊 Dashboard</NavLink>
            <NavLink to="/patients" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'} onClick={() => setSidebarOpen(false)}>🛏️ Patients</NavLink>
            <NavLink to="/doctors" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'} onClick={() => setSidebarOpen(false)}>👨‍⚕️ Doctors</NavLink>
            <NavLink to="/nurses" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'} onClick={() => setSidebarOpen(false)}>👩‍⚕️ Nurses</NavLink>
            <NavLink to="/vitals" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'} onClick={() => setSidebarOpen(false)}>💓 Vitals Feed</NavLink>
            <NavLink to="/alerts" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'} onClick={() => setSidebarOpen(false)}>🚨 Active Alerts</NavLink>
            {user.role === 'ADMIN' && (
              <>
                <NavLink to="/hospitals" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'} onClick={() => setSidebarOpen(false)}>🏢 Hospitals</NavLink>
                <NavLink to="/whatsapp" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'} onClick={() => setSidebarOpen(false)}>📱 WhatsApp</NavLink>
                <NavLink to="/status" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'} onClick={() => setSidebarOpen(false)}>🖥️ System</NavLink>
                <NavLink to="/audit-logs" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'} onClick={() => setSidebarOpen(false)}>📋 Audit Logs</NavLink>
              </>
            )}
          </nav>

          <div className="sidebar-user">
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12 }}>
               <div>
                  <div className="sidebar-user-name">👤 {user.username}</div>
                  <div className="user-pill" style={{ marginTop:4, fontSize:9, padding:'2px 8px' }}>{user.role}</div>
               </div>
               <button className="logout-btn" onClick={handleLogout} style={{ fontSize:16 }} title="Logout">🚪</button>
            </div>
            <div className="sidebar-insight">
               <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                  <div className="live-dot" />
                  <span style={{ fontWeight:700, fontSize:11 }}>TELEMETRY ACTIVE</span>
               </div>
            </div>
          </div>
          <div className="sidebar-footer">v5.2.0-PRO</div>
        </aside>

        <main className="main-content">
          <div className="content-canvas">
          <Routes>
            <Route path="/"           element={<Dashboard />} />
            <Route path="/patients"   element={<Patients />} />
            <Route path="/doctors"    element={<Doctors />} />
            <Route path="/nurses"     element={<Nurses />} />
            <Route path="/vitals"     element={<Vitals />} />
            <Route path="/alerts"     element={<Alerts />} />
            <Route path="/hospitals"  element={<Hospitals />} />
            <Route path="/whatsapp"   element={<WhatsAppConfig />} />
            <Route path="/status"     element={<SystemStatus />} />
            <Route path="/audit-logs" element={<AuditLogs />} />
          </Routes>
          </div>
        </main>
      </div>
    </Router>
  );
}
