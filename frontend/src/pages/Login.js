import React, { useState, useEffect } from 'react';
import { login, registerDoctor, registerNurse, getHospitals, forgotPasswordRequest, forgotPasswordConfirm } from '../api';

const COUNTRY_CODES = [
  { code: '91',  label: '🇮🇳 +91' },
  { code: '1',   label: '🇺🇸 +1' },
  { code: '44',  label: '🇬🇧 +44' },
  { code: '971', label: '🇦🇪 +971' },
  { code: '966', label: '🇸🇦 +966' },
  { code: '61',  label: '🇦🇺 +61' },
  { code: '49',  label: '🇩🇪 +49' },
  { code: '33',  label: '🇫🇷 +33' },
  { code: '81',  label: '🇯🇵 +81' },
  { code: '86',  label: '🇨🇳 +86' },
  { code: '55',  label: '🇧🇷 +55' },
  { code: '65',  label: '🇸🇬 +65' },
  { code: '92',  label: '🇵🇰 +92' },
  { code: '880', label: '🇧🇩 +880' },
  { code: '94',  label: '🇱🇰 +94' },
  { code: '977', label: '🇳🇵 +977' },
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
  const [tab, setTab] = useState('login');
  const [hospitals, setHospitals] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [resetMsg, setResetMsg] = useState('');
  const [doctorCountryCode, setDoctorCountryCode] = useState('91');
  const [nurseCountryCode, setNurseCountryCode] = useState('91');
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [showDoctorPassword, setShowDoctorPassword] = useState(false);
  const [showNursePassword, setShowNursePassword] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [resetStep, setResetStep] = useState('request');

  const [loginForm, setLoginForm] = useState({ username: '', password: '' });
  const [resetForm, setResetForm] = useState({ username: '', verification_code: '', new_password: '', confirm_password: '' });

  const [doctorForm, setDoctorForm] = useState({
    username: '', password: '', name: '', specialization: 'Cardiology',
    hospital_id: '', phone: '', email: '', is_freelancer: true,
  });

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

  const switchTab = (t) => { setTab(t); setError(''); };

  const handleResetRequest = async (e) => {
    e.preventDefault();
    setError('');
    setResetMsg('');
    if (!resetForm.username.trim()) {
      setError('Username is required');
      return;
    }
    setLoading(true);
    try {
      const res = await forgotPasswordRequest({ username: resetForm.username.trim() });
      const codeHint = res?.data?.verification_code ? ` Code: ${res.data.verification_code}` : '';
      setResetMsg((res?.data?.detail || 'Verification code sent if account exists.') + codeHint);
      setResetStep('confirm');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not send verification code');
    } finally {
      setLoading(false);
    }
  };

  const handleResetConfirm = async (e) => {
    e.preventDefault();
    setError('');
    setResetMsg('');
    if (!resetForm.verification_code.trim()) {
      setError('Verification code is required');
      return;
    }
    if (resetForm.new_password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }
    if (resetForm.new_password !== resetForm.confirm_password) {
      setError('Passwords do not match');
      return;
    }
    setLoading(true);
    try {
      const res = await forgotPasswordConfirm({
        username: resetForm.username.trim(),
        verification_code: resetForm.verification_code.trim(),
        new_password: resetForm.new_password,
      });
      setResetMsg(res?.data?.detail || 'Password reset successful. Please sign in.');
      setShowReset(false);
      setResetStep('request');
      setLoginForm((prev) => ({ ...prev, username: resetForm.username, password: '' }));
      setResetForm({ username: '', verification_code: '', new_password: '', confirm_password: '' });
    } catch (err) {
      setError(err.response?.data?.detail || 'Password reset failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: '100vh', background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
    }}>
      <div style={{
        background: '#1e293b', borderRadius: 16, padding: '32px 36px', width: 440,
        boxShadow: '0 25px 50px rgba(0,0,0,.4)', border: '1px solid #334155',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 48, marginBottom: 6 }}>🏥</div>
          <h1 style={{ color: '#e2e8f0', fontSize: 22, margin: 0, fontWeight: 700 }}>PatientWatch</h1>
          <p style={{ color: '#64748b', fontSize: 12, marginTop: 4 }}>IoT Healthcare Monitoring</p>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', marginBottom: 20, borderBottom: '1px solid #334155' }}>
          {[
            { key: 'login',  label: '🔑 Sign In' },
            { key: 'doctor', label: '👨‍⚕️ Doctor' },
            { key: 'nurse',  label: '👩‍⚕️ Nurse'  },
          ].map(({ key, label }) => (
            <button key={key} onClick={() => switchTab(key)} style={{
              flex: 1, padding: '10px 0', border: 'none',
              borderBottom: tab === key ? '2px solid #3b82f6' : '2px solid transparent',
              background: 'transparent',
              color: tab === key ? '#e2e8f0' : '#64748b',
              fontSize: 13, fontWeight: tab === key ? 600 : 400,
              cursor: 'pointer', transition: 'all 0.2s',
            }}>{label}</button>
          ))}
        </div>

        {error && (
          <div style={{
            background: '#7f1d1d', color: '#fca5a5', borderRadius: 8,
            padding: '9px 12px', fontSize: 13, marginBottom: 14,
          }}>⚠️ {error}</div>
        )}

        {resetMsg && (
          <div style={{
            background: '#14532d', color: '#86efac', borderRadius: 8,
            padding: '9px 12px', fontSize: 13, marginBottom: 14,
          }}>✅ {resetMsg}</div>
        )}

        {/* ── Sign In ── */}
        {tab === 'login' && (
          <form onSubmit={showReset ? (resetStep === 'request' ? handleResetRequest : handleResetConfirm) : handleLogin}>
            <label style={labelStyle}>Username</label>
            {showReset ? (
              <>
                <input placeholder="Enter your username" value={resetForm.username}
                  onChange={e => setResetForm({ ...resetForm, username: e.target.value })}
                  required autoFocus style={inputStyle} />
                {resetStep === 'confirm' && (
                  <>
                    <label style={labelStyle}>Verification Code</label>
                    <input placeholder="Enter verification code" value={resetForm.verification_code}
                      onChange={e => setResetForm({ ...resetForm, verification_code: e.target.value })}
                      required style={inputStyle} />
                    <label style={labelStyle}>New Password</label>
                    <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                      <input type={showLoginPassword ? 'text' : 'password'} placeholder="Enter new password" value={resetForm.new_password}
                        onChange={e => setResetForm({ ...resetForm, new_password: e.target.value })}
                        required style={{ ...inputStyle, marginBottom: 0, flex: 1 }} />
                      <button type="button" onClick={() => setShowLoginPassword(v => !v)} style={{ ...inputStyle, marginBottom: 0, width: 86, padding: '10px 8px' }}>
                        {showLoginPassword ? 'Hide' : 'Show'}
                      </button>
                    </div>
                    <label style={labelStyle}>Confirm Password</label>
                    <input type={showLoginPassword ? 'text' : 'password'} placeholder="Confirm password" value={resetForm.confirm_password}
                      onChange={e => setResetForm({ ...resetForm, confirm_password: e.target.value })}
                      required style={inputStyle} />
                  </>
                )}
                <button type="submit" disabled={loading} style={btnStyle}>
                  {loading
                    ? (resetStep === 'request' ? 'Sending…' : 'Resetting…')
                    : (resetStep === 'request' ? '📨 Send Verification Code' : '🔁 Reset Password')}
                </button>
                {resetStep === 'confirm' && (
                  <button type="button" onClick={() => setResetStep('request')} style={{ ...btnStyle, marginTop: 8, background: '#334155' }}>
                    Resend Code
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setShowReset(false);
                    setResetStep('request');
                    setError('');
                    setResetMsg('');
                    setResetForm({ username: '', verification_code: '', new_password: '', confirm_password: '' });
                  }}
                  style={{ ...btnStyle, marginTop: 8, background: '#334155' }}
                >
                  Back to Sign In
                </button>
              </>
            ) : (
              <>
                <input placeholder="Enter your username" value={loginForm.username}
                  onChange={e => setLoginForm({ ...loginForm, username: e.target.value })}
                  required autoFocus style={inputStyle} />
                <label style={labelStyle}>Password</label>
                <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                  <input type={showLoginPassword ? 'text' : 'password'} placeholder="Enter your password" value={loginForm.password}
                    onChange={e => setLoginForm({ ...loginForm, password: e.target.value })}
                    required style={{ ...inputStyle, marginBottom: 0, flex: 1 }} />
                  <button type="button" onClick={() => setShowLoginPassword(v => !v)} style={{ ...inputStyle, marginBottom: 0, width: 86, padding: '10px 8px' }}>
                    {showLoginPassword ? 'Hide' : 'Show'}
                  </button>
                </div>
                <button type="submit" disabled={loading} style={btnStyle}>
                  {loading ? 'Signing in…' : '🔑 Sign In'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowReset(true);
                    setResetStep('request');
                    setError('');
                    setResetMsg('');
                    setResetForm({ username: loginForm.username || '', verification_code: '', new_password: '', confirm_password: '' });
                  }}
                  style={{ ...btnStyle, marginTop: 8, background: '#334155' }}
                >
                  Forgot password? Reset here
                </button>
              </>
            )}
          </form>
        )}

        {/* ── Doctor Registration ── */}
        {tab === 'doctor' && (
          <form onSubmit={handleDoctorRegister}>
            <p style={hintStyle}>Register as a doctor (freelancer or hospital-based)</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div>
                <label style={labelStyle}>Username</label>
                <input placeholder="Username" value={doctorForm.username}
                  onChange={e => setDoctorForm({ ...doctorForm, username: e.target.value })}
                  required style={{ ...inputStyle, marginBottom: 0 }} />
              </div>
              <div>
                <label style={labelStyle}>Password</label>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input type={showDoctorPassword ? 'text' : 'password'} placeholder="Password" value={doctorForm.password}
                    onChange={e => setDoctorForm({ ...doctorForm, password: e.target.value })}
                    required style={{ ...inputStyle, marginBottom: 0, flex: 1 }} />
                  <button type="button" onClick={() => setShowDoctorPassword(v => !v)} style={{ ...inputStyle, marginBottom: 0, width: 78, padding: '10px 8px' }}>
                    {showDoctorPassword ? 'Hide' : 'Show'}
                  </button>
                </div>
              </div>
            </div>
            <div style={{ height: 10 }} />
            <label style={labelStyle}>Full Name</label>
            <input placeholder="e.g. Dr. Jane Smith" value={doctorForm.name}
              onChange={e => setDoctorForm({ ...doctorForm, name: e.target.value })}
              required style={inputStyle} />
            <label style={labelStyle}>Specialization</label>
            <select value={doctorForm.specialization}
              onChange={e => setDoctorForm({ ...doctorForm, specialization: e.target.value })}
              style={inputStyle}>
              {SPECIALIZATIONS.map(s => <option key={s}>{s}</option>)}
            </select>
            <label style={labelStyle}>Hospital <span style={{ color: '#475569' }}>(optional)</span></label>
            <select value={doctorForm.hospital_id}
              onChange={e => setDoctorForm({ ...doctorForm, hospital_id: e.target.value })}
              style={inputStyle}>
              <option value="">— No Hospital (Freelancer) —</option>
              {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
            </select>
            <label style={labelStyle}>Phone <span style={{ color: '#475569' }}>(optional)</span></label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
              <select value={doctorCountryCode} onChange={e => setDoctorCountryCode(e.target.value)}
                style={{ ...inputStyle, width: 90, flex: '0 0 90px', marginBottom: 0 }}>
                {COUNTRY_CODES.map(c => <option key={c.code} value={c.code}>{c.label}</option>)}
              </select>
              <input placeholder="Phone number" value={doctorForm.phone}
                onChange={e => setDoctorForm({ ...doctorForm, phone: e.target.value.replace(/\D/g, '') })}
                style={{ ...inputStyle, flex: 1, minWidth: 0, marginBottom: 0 }} />
            </div>
            <label style={labelStyle}>Email <span style={{ color: '#475569' }}>(optional)</span></label>
            <input placeholder="email@example.com" type="email" value={doctorForm.email}
              onChange={e => setDoctorForm({ ...doctorForm, email: e.target.value })}
              style={inputStyle} />
            <div style={{ height: 10 }} />
            <label style={{ color: '#94a3b8', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, cursor: 'pointer' }}>
              <input type="checkbox" checked={doctorForm.is_freelancer}
                onChange={e => setDoctorForm({ ...doctorForm, is_freelancer: e.target.checked })} />
              Freelancer Doctor
            </label>
            <button type="submit" disabled={loading} style={btnStyle}>
              {loading ? 'Registering…' : '👨‍⚕️ Register as Doctor'}
            </button>
          </form>
        )}

        {/* ── Nurse Registration ── */}
        {tab === 'nurse' && (
          <form onSubmit={handleNurseRegister}>
            <p style={hintStyle}>Register as a nurse at a hospital</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div>
                <label style={labelStyle}>Username</label>
                <input placeholder="Username" value={nurseForm.username}
                  onChange={e => setNurseForm({ ...nurseForm, username: e.target.value })}
                  required style={{ ...inputStyle, marginBottom: 0 }} />
              </div>
              <div>
                <label style={labelStyle}>Password</label>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input type={showNursePassword ? 'text' : 'password'} placeholder="Password" value={nurseForm.password}
                    onChange={e => setNurseForm({ ...nurseForm, password: e.target.value })}
                    required style={{ ...inputStyle, marginBottom: 0, flex: 1 }} />
                  <button type="button" onClick={() => setShowNursePassword(v => !v)} style={{ ...inputStyle, marginBottom: 0, width: 78, padding: '10px 8px' }}>
                    {showNursePassword ? 'Hide' : 'Show'}
                  </button>
                </div>
              </div>
            </div>
            <div style={{ height: 10 }} />
            <label style={labelStyle}>Full Name</label>
            <input placeholder="e.g. Nurse Sarah Connor" value={nurseForm.name}
              onChange={e => setNurseForm({ ...nurseForm, name: e.target.value })}
              required style={inputStyle} />
            <label style={labelStyle}>Department</label>
            <select value={nurseForm.department}
              onChange={e => setNurseForm({ ...nurseForm, department: e.target.value })}
              style={inputStyle}>
              {DEPARTMENTS.map(d => <option key={d}>{d}</option>)}
            </select>
            <label style={labelStyle}>Hospital <span style={{ color: '#475569' }}>(optional)</span></label>
            <select value={nurseForm.hospital_id}
              onChange={e => setNurseForm({ ...nurseForm, hospital_id: e.target.value })}
              style={inputStyle}>
              <option value="">— Select Hospital —</option>
              {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id}>{h.name}</option>)}
            </select>
            <label style={labelStyle}>Phone <span style={{ color: '#475569' }}>(optional)</span></label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
              <select value={nurseCountryCode} onChange={e => setNurseCountryCode(e.target.value)}
                style={{ ...inputStyle, width: 90, flex: '0 0 90px', marginBottom: 0 }}>
                {COUNTRY_CODES.map(c => <option key={c.code} value={c.code}>{c.label}</option>)}
              </select>
              <input placeholder="Phone number" value={nurseForm.phone}
                onChange={e => setNurseForm({ ...nurseForm, phone: e.target.value.replace(/\D/g, '') })}
                style={{ ...inputStyle, flex: 1, minWidth: 0, marginBottom: 0 }} />
            </div>
            <label style={labelStyle}>Email <span style={{ color: '#475569' }}>(optional)</span></label>
            <input placeholder="email@example.com" type="email" value={nurseForm.email}
              onChange={e => setNurseForm({ ...nurseForm, email: e.target.value })}
              style={inputStyle} />
            <div style={{ height: 14 }} />
            <button type="submit" disabled={loading} style={btnStyle}>
              {loading ? 'Registering…' : '👩‍⚕️ Register as Nurse'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

const labelStyle = {
  display: 'block', color: '#94a3b8', fontSize: 11,
  fontWeight: 600, marginBottom: 5, letterSpacing: '0.05em', textTransform: 'uppercase',
};

const hintStyle = {
  color: '#64748b', fontSize: 12, marginBottom: 14, marginTop: 0,
};

const inputStyle = {
  width: '100%', padding: '10px 12px', borderRadius: 8,
  border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0',
  fontSize: 13, marginBottom: 10, boxSizing: 'border-box', outline: 'none',
};

const btnStyle = {
  width: '100%', padding: '12px 0', borderRadius: 8, border: 'none',
  background: '#3b82f6', color: '#fff', fontWeight: 700, fontSize: 14,
  cursor: 'pointer', marginTop: 2, letterSpacing: '0.02em',
};
