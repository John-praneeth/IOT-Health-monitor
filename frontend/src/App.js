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
import './App.css';

export default function App() {
  const [user, setUser] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const role = localStorage.getItem('role');
    const username = localStorage.getItem('username');
    const doctor_id = localStorage.getItem('doctor_id');
    const nurse_id = localStorage.getItem('nurse_id');
    if (token && role && username) {
      setUser({ token, role, username, doctor_id, nurse_id });
    }
  }, []);

  const handleLogin = (data) => {
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('role', data.role);
    localStorage.setItem('username', data.username);
    if (data.doctor_id) localStorage.setItem('doctor_id', data.doctor_id);
    if (data.nurse_id) localStorage.setItem('nurse_id', data.nurse_id);
    setUser({
      token: data.access_token, role: data.role, username: data.username,
      doctor_id: data.doctor_id, nurse_id: data.nurse_id,
    });
  };

  const handleLogout = () => {
    localStorage.clear();
    setUser(null);
  };

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <Router>
      <div className="app-layout">
        <aside className="sidebar">
          <div className="sidebar-logo">
            <span className="logo-icon">🏥</span>
            <span className="logo-text">PatientWatch</span>
          </div>
          <nav className="sidebar-nav">
            <NavLink to="/"         end className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>📊 Dashboard</NavLink>
            <NavLink to="/patients"      className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>🛏️ Patients</NavLink>
            <NavLink to="/doctors"       className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>👨‍⚕️ Doctors</NavLink>
            <NavLink to="/nurses"        className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>👩‍⚕️ Nurses</NavLink>
            <NavLink to="/vitals"        className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>💓 Vitals</NavLink>
            <NavLink to="/alerts"        className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>🚨 Alerts</NavLink>
            {user.role === 'ADMIN' && (
              <>
                <NavLink to="/hospitals"   className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>🏢 Hospitals</NavLink>
                <NavLink to="/whatsapp"    className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>📱 WhatsApp</NavLink>
                <NavLink to="/status"      className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>�️ System Status</NavLink>
                <NavLink to="/audit-logs"  className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>📋 Audit Logs</NavLink>
              </>
            )}
          </nav>
          <div className="sidebar-user">
            <span style={{ color: '#94a3b8', fontSize: 12 }}>👤 {user.username} ({user.role})</span>
            <button onClick={handleLogout} style={{
              marginTop: 6, padding: '4px 12px', borderRadius: 6, border: '1px solid #475569',
              background: 'transparent', color: '#f87171', fontSize: 11, cursor: 'pointer',
            }}>Logout</button>
          </div>
          <div className="sidebar-footer">API: localhost:8000</div>
        </aside>

        <main className="main-content">
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
        </main>
      </div>
    </Router>
  );
}
