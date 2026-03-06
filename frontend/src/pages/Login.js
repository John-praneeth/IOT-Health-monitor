import React, { useState, useEffect } from 'react';
import { login, registerDoctor, registerNurse, getHospitals } from '../api';

const COUNTRY_CODES = [
  { code: '91',  label: '🇮🇳 +91  India' },
  { code: '1',   label: '🇺🇸 +1   USA' },
  { code: '44',  label: '🇬🇧 +44  UK' },
  { code: '971', label: '🇦🇪 +971 UAE' },
  { code: '966', label: '🇸🇦 +966 Saudi' },
  { code: '61',  label: '🇦🇺 +61  Australia' },
  { code: '49',  label: '🇩🇪 +49  Germany' },
  { code: '33',  label: '🇫🇷 +33  France' },
  { code: '81',  label: '🇯🇵 +81  Japan' },
  { code: '86',  label: '🇨🇳 +86  China' },
  { code: '82',  label: '🇰🇷 +82  S. Korea' },
  { code: '55',  label: '🇧🇷 +55  Brazil' },
  { code: '7',   label: '🇷🇺 +7   Russia' },
  { code: '27',  label: '🇿🇦 +27  S. Africa' },
  { code: '65',  label: '🇸🇬 +65  Singapore' },
  { code: '60',  label: '🇲🇾 +60  Malaysia' },
  { code: '63',  label: '🇵🇭 +63  Philippines' },
  { code: '62',  label: '🇮🇩 +62  Indonesia' },
  { code: '234', label: '🇳🇬 +234 Nigeria' },
  { code: '254', label: '🇰🇪 +254 Kenya' },
  { code: '92',  label: '🇵🇰 +92  Pakistan' },
  { code: '880', label: '🇧🇩 +880 Bangladesh' },
  { code: '94',  label: '🇱🇰 +94  Sri Lanka' },
  { code: '977', label: '🇳🇵 +977 Nepal' },
];

const SPECIALIZATIONS = [
  'Cardiology', 'Neurology', 'Pulmonology', 'Orthopedics',
  'Dermatology', 'Pediatrics', 'Oncology', 'General Medicine',
  'Gastroenterology', 'Endocrinology', 'Nephrology', 'Psychiatry',
];

const DEPARTMENTS = [
  'ICU', 'Emergency', 'General', 'Cardiology', 'Neurology',
  'Pediatrics', 'Oncology', 'Surgery', 'Orthopedics',
];

export default function Login({ onLogin }) {
  const [tab, setTab] = useState('login'); // 'login' | 'doctor' | 'nurse'
  const [hospitals, setHospitals] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [doctorCountryCode, setDoctorCountryCode] = useState('91');
  const [nurseCountryCode, setNurseCountryCode] = useState('91');

  // Login form
  const [loginForm, setLoginForm] = useState({ username: '', password: '' });

  // Doctor registration form
  const [doctorForm, setDoctorForm] = useState({
    username: '', password: '', name: '', specialization: 'Cardiology',
    hospital_id: '', phone: '', email: '', is_freelancer: true,
  });

  // Nurse registration form
  const [nurseForm, setNurseForm] = useState({
    username: '', password: '', name: '', department: 'General',
    hospital_id: '', phone: '', email: '',
  });

  useEffect(() => {
    getHospitals().then(r => setHospitals(r.data)).catch(() => {});
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const res = await login(loginForm);
      onLogin(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed');
    } finally { setLoading(false); }
  };

  const handleDoctorRegister = async (e) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const cleanPhone = doctorForm.phone.replace(/[^0-9]/g, '').replace(/^0+/, '');
      const payload = {
        ...doctorForm,
        phone: cleanPhone ? doctorCountryCode + cleanPhone : '',
        hospital_id: doctorForm.hospital_id ? parseInt(doctorForm.hospital_id) : null,
      };
      const res = await registerDoctor(payload);
      onLogin(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed');
    } finally { setLoading(false); }
  };

  const handleNurseRegister = async (e) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const cleanPhone = nurseForm.phone.replace(/[^0-9]/g, '').replace(/^0+/, '');
      const payload = {
        ...nurseForm,
        phone: cleanPhone ? nurseCountryCode + cleanPhone : '',
        hospital_id: nurseForm.hospital_id ? parseInt(nurseForm.hospital_id) : null,
      };
      const res = await registerNurse(payload);
      onLogin(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed');
    } finally { setLoading(false); }
  };

  const tabStyle = (t) => ({
    flex: 1, padding: '10px 0', border: 'none', borderBottom: tab === t ? '2px solid #3b82f6' : '2px solid transparent',
    background: 'transparent', color: tab === t ? '#e2e8f0' : '#64748b',
    fontSize: 13, fontWeight: tab === t ? 600 : 400, cursor: 'pointer',
    transition: 'all 0.2s',
  });

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: '100vh', background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
    }}>
      <div style={{
        background: '#1e293b', borderRadius: 16, padding: '32px 36px', width: 420,
        boxShadow: '0 25px 50px rgba(0,0,0,.3)', border: '1px solid #334155',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: 48, marginBottom: 6 }}>🏥</div>
          <h1 style={{ color: '#e2e8f0', fontSize: 22, margin: 0 }}>PatientWatch</h1>
          <p style={{ color: '#64748b', fontSize: 12, marginTop: 4 }}>IoT Healthcare Monitoring</p>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', marginBottom: 20, borderBottom: '1px solid #334155' }}>
          <button style={tabStyle('login')} onClick={() => { setTab('login'); setError(''); }}>🔑 Sign In</button>
          <button style={tabStyle('doctor')} onClick={() => { setTab('doctor'); setError(''); }}>👨‍⚕️ Doctor</button>
          <button style={tabStyle('nurse')} onClick={() => { setTab('nurse'); setError(''); }}>👩‍⚕️ Nurse</button>
        </div>

        {error && (
          <div style={{
            background: '#7f1d1d', color: '#fca5a5', borderRadius: 8,
            padding: '8px 12px', fontSize: 13, marginBottom: 12,
          }}>⚠️ {error}</div>
        )}

        {/* ── Login Tab ── */}
        {tab === 'login' && (
          <form onSubmit={handleLogin}>
            <input placeholder="Username" value={loginForm.username}
              onChange={e => setLoginForm({ ...loginForm, username: e.target.value })}
              required style={inputStyle} />
            <input type="password" placeholder="Password" value={loginForm.password}
              onChange={e => setLoginForm({ ...loginForm, password: e.target.value })}
              required style={inputStyle} />
            <button type="submit" disabled={loading} style={btnStyle}>
              {loading ? '...' : 'Sign In'}
            </button>
          </form>
        )}

        {/* ── Doctor Registration Tab ── */}
        {tab === 'doctor' && (
          <form onSubmit={handleDoctorRegister}>
            <p style={{ color: '#94a3b8', fontSize: 12, marginBottom: 12 }}>
              Register as a doctor (freelancer or hospital-based)
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <input placeholder="Username" value={doctorForm.username}
                onChange={e => setDoctorForm({ ...doctorForm, username: e.target.value })}
                required style={inputStyle} />
              <input type="password" placeholder="Password" value={doctorForm.password}
                onChange={e => setDoctorForm({ ...doctorForm, password: e.target.value })}
                required style={inputStyle} />
            </div>
            <input placeholder="Full Name (e.g. Dr. Jane Smith)" value={doctorForm.name}
              onChange={e => setDoctorForm({ ...doctorForm, name: e.target.value })}
              required style={inputStyle} />
            <select value={doctorForm.specialization}
              onChange={e => setDoctorForm({ ...doctorForm, specialization: e.target.value })}
              style={inputStyle}>
              {SPECIALIZATIONS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <select value={doctorForm.hospital_id}
              onChange={e => setDoctorForm({ ...doctorForm, hospital_id: e.target.value })}
              style={inputStyle}>
              <option value="">— No Hospital (Freelancer) —</option>
              {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
            </select>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', minWidth: 0 }}>
                <select value={doctorCountryCode} onChange={e => setDoctorCountryCode(e.target.value)}
                  style={{ ...inputStyle, width: 'auto', minWidth: 0, flex: '0 0 auto', marginBottom: 0 }}>
                  {COUNTRY_CODES.map(c => <option key={c.code} value={c.code}>{c.label}</option>)}
                </select>
                <input placeholder="Phone number" value={doctorForm.phone}
                  onChange={e => setDoctorForm({ ...doctorForm, phone: e.target.value.replace(/[^0-9]/g, '') })}
                  style={{ ...inputStyle, width: 'auto', flex: 1, minWidth: 0, marginBottom: 0 }} />
              </div>
              <input placeholder="Email" type="email" value={doctorForm.email}
                onChange={e => setDoctorForm({ ...doctorForm, email: e.target.value })}
                style={inputStyle} />
            </div>
            {doctorForm.phone.trim() && (
              <div style={{ color: '#64748b', fontSize: 11, marginBottom: 8, fontFamily: 'monospace' }}>
                → {doctorCountryCode}{doctorForm.phone.trim().replace(/^0+/, '')}
              </div>
            )}
            <label style={{ color: '#94a3b8', fontSize: 12, display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <input type="checkbox" checked={doctorForm.is_freelancer}
                onChange={e => setDoctorForm({ ...doctorForm, is_freelancer: e.target.checked })} />
              Freelancer Doctor
            </label>
            <button type="submit" disabled={loading} style={btnStyle}>
              {loading ? '...' : 'Register as Doctor'}
            </button>
          </form>
        )}

        {/* ── Nurse Registration Tab ── */}
        {tab === 'nurse' && (
          <form onSubmit={handleNurseRegister}>
            <p style={{ color: '#94a3b8', fontSize: 12, marginBottom: 12 }}>
              Register as a nurse at a hospital
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <input placeholder="Username" value={nurseForm.username}
                onChange={e => setNurseForm({ ...nurseForm, username: e.target.value })}
                required style={inputStyle} />
              <input type="password" placeholder="Password" value={nurseForm.password}
                onChange={e => setNurseForm({ ...nurseForm, password: e.target.value })}
                required style={inputStyle} />
            </div>
            <input placeholder="Full Name" value={nurseForm.name}
              onChange={e => setNurseForm({ ...nurseForm, name: e.target.value })}
              required style={inputStyle} />
            <select value={nurseForm.department}
              onChange={e => setNurseForm({ ...nurseForm, department: e.target.value })}
              style={inputStyle}>
              {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
            <select value={nurseForm.hospital_id}
              onChange={e => setNurseForm({ ...nurseForm, hospital_id: e.target.value })}
              style={inputStyle}>
              <option value="">— Select Hospital —</option>
              {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
            </select>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', minWidth: 0 }}>
                <select value={nurseCountryCode} onChange={e => setNurseCountryCode(e.target.value)}
                  style={{ ...inputStyle, width: 'auto', minWidth: 0, flex: '0 0 auto', marginBottom: 0 }}>
                  {COUNTRY_CODES.map(c => <option key={c.code} value={c.code}>{c.label}</option>)}
                </select>
                <input placeholder="Phone number" value={nurseForm.phone}
                  onChange={e => setNurseForm({ ...nurseForm, phone: e.target.value.replace(/[^0-9]/g, '') })}
                  style={{ ...inputStyle, width: 'auto', flex: 1, minWidth: 0, marginBottom: 0 }} />
              </div>
              <input placeholder="Email" type="email" value={nurseForm.email}
                onChange={e => setNurseForm({ ...nurseForm, email: e.target.value })}
                style={inputStyle} />
            </div>
            {nurseForm.phone.trim() && (
              <div style={{ color: '#64748b', fontSize: 11, marginBottom: 8, fontFamily: 'monospace' }}>
                → {nurseCountryCode}{nurseForm.phone.trim().replace(/^0+/, '')}
              </div>
            )}
            <button type="submit" disabled={loading} style={btnStyle}>
              {loading ? '...' : 'Register as Nurse'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

const inputStyle = {
  width: '100%', padding: '10px 14px', borderRadius: 8,
  border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0',
  fontSize: 13, marginBottom: 10, boxSizing: 'border-box', outline: 'none',
};

const btnStyle = {
  width: '100%', padding: '12px 0', borderRadius: 8, border: 'none',
  background: '#3b82f6', color: '#fff', fontWeight: 600, fontSize: 14,
  cursor: 'pointer', marginTop: 4,
};
