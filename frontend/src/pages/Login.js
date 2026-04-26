import React, { useState, useEffect } from 'react';
import { login, registerDoctor, registerNurse, getHospitals, forgotPasswordRequest, forgotPasswordConfirm } from '../api';
import { API_BASE_URL } from '../config';

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
    getHospitals().then(r => setHospitals(r.data)).catch(err => console.error("Failed to load hospitals:", err));
  }, []);

  const humanizeApiError = (err, fallback) => {
    if (err?.code === 'ECONNABORTED') {
      return 'Clinical terminal timed out. Please verify your connection to the hospital intranet.';
    }
    if (!err?.response) {
      const target = API_BASE_URL.includes('localhost') ? 'your local development server' : `the medical gateway at ${API_BASE_URL}`;
      return `Network Connectivity Failure: Unable to reach ${target}. Ensure the backend service is deployed and active.`;
    }
    return err.response?.data?.detail || fallback;
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const res = await login(loginForm);
      onLogin(res.data);
    } catch (err) {
      setError(humanizeApiError(err, 'Login failed'));
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
      setError(humanizeApiError(err, 'Registration failed'));
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
      setError(humanizeApiError(err, 'Registration failed'));
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
      setError(humanizeApiError(err, 'Could not send verification code'));
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
      setError(humanizeApiError(err, 'Password reset failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container" style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: '100vh', width: '100vw',
      position: 'relative', overflow: 'hidden', padding: '20px',
    }}>
      {/* Background orbs reused from App.css via class but let's ensure they show if App.css is loaded */}
      <div className="bg-orb orb-a" />
      <div className="bg-orb orb-b" />
      <div className="bg-orb orb-c" />

      <div style={{
        background: 'rgba(15, 23, 42, 0.75)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        borderRadius: 32, padding: '40px', width: '100%', maxWidth: 480,
        boxShadow: '0 25px 80px rgba(0,0,0,0.5)', 
        border: '1px solid rgba(255, 255, 255, 0.1)',
        position: 'relative', zIndex: 10,
        animation: 'reveal 0.6s ease-out',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontSize: 64, marginBottom: 12, filter: 'drop-shadow(0 0 20px rgba(34, 211, 238, 0.4))' }}>🏥</div>
          <h1 style={{ color: '#fff', fontSize: 32, margin: 0, fontWeight: 800, fontFamily: 'Space Grotesk, sans-serif', letterSpacing: '-0.03em' }}>PatientWatch</h1>
          <p style={{ color: '#94a3b8', fontSize: 13, marginTop: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Medical Command Center</p>
        </div>

        {/* Dynamic Badges */}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24,
        }}>
          <div style={{ background: 'rgba(34, 211, 238, 0.1)', border: '1px solid rgba(34, 211, 238, 0.2)', borderRadius: 12, padding: '10px 4px', textAlign: 'center', color: '#22d3ee', fontSize: 10, fontWeight: 800, textTransform: 'uppercase' }}>Live Telemetry</div>
          <div style={{ background: 'rgba(52, 211, 153, 0.1)', border: '1px solid rgba(52, 211, 153, 0.2)', borderRadius: 12, padding: '10px 4px', textAlign: 'center', color: '#34d399', fontSize: 10, fontWeight: 800, textTransform: 'uppercase' }}>Alert Ready</div>
          <div style={{ background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.2)', borderRadius: 12, padding: '10px 4px', textAlign: 'center', color: '#f43f5e', fontSize: 10, fontWeight: 800, textTransform: 'uppercase' }}>Secure Pro</div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', marginBottom: 28, background: 'rgba(0,0,0,0.2)', borderRadius: 16, padding: 4 }}>
          {[
            { key: 'login',  label: 'Sign In' },
            { key: 'doctor', label: 'Doctor' },
            { key: 'nurse',  label: 'Nurse'  },
          ].map(({ key, label }) => (
            <button key={key} onClick={() => switchTab(key)} style={{
              flex: 1, padding: '10px 0', border: 'none',
              background: tab === key ? 'rgba(255,255,255,0.08)' : 'transparent',
              borderRadius: 12,
              color: tab === key ? '#fff' : '#64748b',
              fontSize: 13, fontWeight: 800,
              cursor: 'pointer', transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
            }}>{label}</button>
          ))}
        </div>

        {error && (
          <>
            <div style={{
              background: 'rgba(244, 63, 94, 0.15)', color: '#fda4af', borderRadius: 14,
              border: '1px solid rgba(244, 63, 94, 0.3)',
              padding: '12px 16px', fontSize: 13, marginBottom: 20, fontWeight: 600,
              animation: 'shake 0.4s ease-in-out'
            }}>⚠️ {error}</div>
            
            {error.includes('Connectivity Failure') && (
              <div style={{
                background: 'rgba(34, 211, 238, 0.05)', color: '#22d3ee', borderRadius: 12,
                border: '1px solid rgba(34, 211, 238, 0.2)',
                padding: '10px 14px', fontSize: 11, marginBottom: 20, lineHeight: 1.4
              }}>
                <strong>Diagnostic Tip:</strong> If your medical gateway is deployed at a different address, you can override it by adding <code>?api=YOUR_API_URL</code> to the address bar.
              </div>
            )}
          </>
        )}

        {resetMsg && (
          <div style={{
            background: 'rgba(52, 211, 153, 0.15)', color: '#6ee7b7', borderRadius: 14,
            border: '1px solid rgba(52, 211, 153, 0.3)',
            padding: '12px 16px', fontSize: 13, marginBottom: 20, fontWeight: 600,
          }}>✅ {resetMsg}</div>
        )}

        {/* ── Sign In ── */}
        {tab === 'login' && (
          <form onSubmit={showReset ? (resetStep === 'request' ? handleResetRequest : handleResetConfirm) : handleLogin}>
            <label style={labelStyle}>Staff ID / Username</label>
            {showReset ? (
              <>
                <input placeholder="Enter your username" value={resetForm.username}
                  onChange={e => setResetForm({ ...resetForm, username: e.target.value })}
                  required autoFocus style={inputStyle} />
                {resetStep === 'confirm' && (
                  <>
                    <label style={labelStyle}>Verification Code</label>
                    <input placeholder="Enter 6-digit code" value={resetForm.verification_code}
                      onChange={e => setResetForm({ ...resetForm, verification_code: e.target.value })}
                      required style={inputStyle} />
                    <label style={labelStyle}>New Password</label>
                    <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                      <input type={showLoginPassword ? 'text' : 'password'} placeholder="New password" value={resetForm.new_password}
                        onChange={e => setResetForm({ ...resetForm, new_password: e.target.value })}
                        required style={{ ...inputStyle, marginBottom: 0, flex: 1 }} />
                      <button type="button" onClick={() => setShowLoginPassword(v => !v)} style={{ ...inputStyle, marginBottom: 0, width: 80, padding: 0, fontSize: 11, fontWeight: 800 }}>
                        {showLoginPassword ? 'HIDE' : 'SHOW'}
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
                    ? (resetStep === 'request' ? 'AUTHORIZING…' : 'UPDATING…')
                    : (resetStep === 'request' ? 'SEND RESET CODE' : 'CONFIRM NEW PASSWORD')}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowReset(false);
                    setResetStep('request');
                    setError('');
                    setResetMsg('');
                    setResetForm({ username: '', verification_code: '', new_password: '', confirm_password: '' });
                  }}
                  style={{ ...btnStyle, marginTop: 12, background: 'rgba(255,255,255,0.05)', color: '#94a3b8', boxShadow: 'none', border: '1px solid rgba(255,255,255,0.1)' }}
                >
                  RETURN TO SIGN IN
                </button>
              </>
            ) : (
              <>
                <input placeholder="Enter staff identifier" value={loginForm.username}
                  onChange={e => setLoginForm({ ...loginForm, username: e.target.value })}
                  required autoFocus style={inputStyle} />
                <label style={labelStyle}>Access Key / Password</label>
                <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                  <input type={showLoginPassword ? 'text' : 'password'} placeholder="Enter credentials" value={loginForm.password}
                    onChange={e => setLoginForm({ ...loginForm, password: e.target.value })}
                    required style={{ ...inputStyle, marginBottom: 0, flex: 1 }} />
                  <button type="button" onClick={() => setShowLoginPassword(v => !v)} style={{ ...inputStyle, marginBottom: 0, width: 80, padding: 0, fontSize: 11, fontWeight: 800 }}>
                    {showLoginPassword ? 'HIDE' : 'SHOW'}
                  </button>
                </div>
                <button type="submit" disabled={loading} style={btnStyle}>
                  {loading ? 'AUTHENTICATING…' : 'INITIALIZE SESSION'}
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
                  style={{ 
                    marginTop: 20, background: 'none', border: 'none', color: '#64748b', 
                    fontSize: 12, fontWeight: 700, cursor: 'pointer', width: '100%',
                    textDecoration: 'underline', textUnderlineOffset: '4px'
                  }}
                >
                  Forgot credentials? Reset here
                </button>
              </>
            )}
          </form>
        )}

        {/* ── Doctor Registration ── */}
        {tab === 'doctor' && (
          <form onSubmit={handleDoctorRegister}>
            <p style={hintStyle}>Initialize new Doctor terminal (Freelance or Hospital)</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
              <div>
                <label style={labelStyle}>Username</label>
                <input placeholder="ID" value={doctorForm.username}
                  onChange={e => setDoctorForm({ ...doctorForm, username: e.target.value })}
                  required style={{ ...inputStyle, marginBottom: 0 }} />
              </div>
              <div>
                <label style={labelStyle}>Password</label>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input type={showDoctorPassword ? 'text' : 'password'} placeholder="Key" value={doctorForm.password}
                    onChange={e => setDoctorForm({ ...doctorForm, password: e.target.value })}
                    required style={{ ...inputStyle, marginBottom: 0, flex: 1 }} />
                </div>
              </div>
            </div>
            
            <label style={labelStyle}>Full Name</label>
            <input placeholder="e.g. Dr. Jane Smith" value={doctorForm.name}
              onChange={e => setDoctorForm({ ...doctorForm, name: e.target.value })}
              required style={inputStyle} />
            <label style={labelStyle}>Specialization</label>
            <select value={doctorForm.specialization}
              onChange={e => setDoctorForm({ ...doctorForm, specialization: e.target.value })}
              style={inputStyle}>
              {SPECIALIZATIONS.map(s => <option key={s} style={{background: '#020617'}}>{s}</option>)}
            </select>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
               <div>
                  <label style={labelStyle}>Hospital</label>
                  <select value={doctorForm.hospital_id}
                    onChange={e => setDoctorForm({ ...doctorForm, hospital_id: e.target.value })}
                    style={inputStyle}>
                    <option value="" style={{background: '#020617'}}>— Freelance —</option>
                    {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id} style={{background: '#020617'}}>{h.name}</option>)}
                  </select>
               </div>
               <div>
                  <label style={labelStyle}>Region Code</label>
                  <select value={doctorCountryCode} onChange={e => setDoctorCountryCode(e.target.value)}
                    style={inputStyle}>
                    {COUNTRY_CODES.map(c => <option key={c.code} value={c.code} style={{background: '#020617'}}>{c.label}</option>)}
                  </select>
               </div>
            </div>

            <label style={labelStyle}>Emergency Contact (Phone)</label>
            <input placeholder="Phone number" value={doctorForm.phone}
              onChange={e => setDoctorForm({ ...doctorForm, phone: e.target.value.replace(/\D/g, '') })}
              style={inputStyle} />

            <div style={{ height: 8 }} />
            <label style={{ color: '#94a3b8', fontSize: 12, display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20, cursor: 'pointer', fontWeight: 700 }}>
              <input type="checkbox" checked={doctorForm.is_freelancer}
                onChange={e => setDoctorForm({ ...doctorForm, is_freelancer: e.target.checked })} 
                style={{ width: 16, height: 16, accentColor: '#22d3ee' }} />
              ENABLE FREELANCE OVERRIDE
            </label>
            <button type="submit" disabled={loading} style={btnStyle}>
              {loading ? 'REGISTERING…' : 'AUTHORIZE DOCTOR TERMINAL'}
            </button>
          </form>
        )}

        {/* ── Nurse Registration ── */}
        {tab === 'nurse' && (
          <form onSubmit={handleNurseRegister}>
            <p style={hintStyle}>Initialize new Nurse terminal for local care ward</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
              <div>
                <label style={labelStyle}>Username</label>
                <input placeholder="ID" value={nurseForm.username}
                  onChange={e => setNurseForm({ ...nurseForm, username: e.target.value })}
                  required style={{ ...inputStyle, marginBottom: 0 }} />
              </div>
              <div>
                <label style={labelStyle}>Password</label>
                <input type={showNursePassword ? 'text' : 'password'} placeholder="Key" value={nurseForm.password}
                  onChange={e => setNurseForm({ ...nurseForm, password: e.target.value })}
                  required style={{ ...inputStyle, marginBottom: 0 }} />
              </div>
            </div>
            
            <label style={labelStyle}>Full Name</label>
            <input placeholder="e.g. Nurse Sarah Connor" value={nurseForm.name}
              onChange={e => setNurseForm({ ...nurseForm, name: e.target.value })}
              required style={inputStyle} />
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
               <div>
                  <label style={labelStyle}>Ward / Dept</label>
                  <select value={nurseForm.department}
                    onChange={e => setNurseForm({ ...nurseForm, department: e.target.value })}
                    style={inputStyle}>
                    {DEPARTMENTS.map(d => <option key={d} style={{background: '#020617'}}>{d}</option>)}
                  </select>
               </div>
               <div>
                  <label style={labelStyle}>Region Code</label>
                  <select value={nurseCountryCode} onChange={e => setNurseCountryCode(e.target.value)}
                    style={inputStyle}>
                    {COUNTRY_CODES.map(c => <option key={c.code} value={c.code} style={{background: '#020617'}}>{c.label}</option>)}
                  </select>
               </div>
            </div>

            <label style={labelStyle}>Assigned Hospital</label>
            <select value={nurseForm.hospital_id}
              onChange={e => setNurseForm({ ...nurseForm, hospital_id: e.target.value })}
              style={inputStyle}>
              <option value="" style={{background: '#020617'}}>— Select Hospital —</option>
              {hospitals.map(h => <option key={h.hospital_id} value={h.hospital_id} style={{background: '#020617'}}>{h.name}</option>)}
            </select>

            <label style={labelStyle}>Emergency Contact (Phone)</label>
            <input placeholder="Phone number" value={nurseForm.phone}
              onChange={e => setNurseForm({ ...nurseForm, phone: e.target.value.replace(/\D/g, '') })}
              style={inputStyle} />

            <div style={{ height: 12 }} />
            <button type="submit" disabled={loading} style={btnStyle}>
              {loading ? 'REGISTERING…' : 'AUTHORIZE NURSE TERMINAL'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

const labelStyle = {
  display: 'block', color: '#94a3b8', fontSize: 10,
  fontWeight: 800, marginBottom: 6, letterSpacing: '0.1em', textTransform: 'uppercase',
};

const hintStyle = {
  color: '#64748b', fontSize: 11, marginBottom: 20, marginTop: 0, fontWeight: 600,
};

const inputStyle = {
  width: '100%', padding: '14px 16px', borderRadius: 14,
  border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.2)', color: '#fff',
  fontSize: 14, marginBottom: 16, boxSizing: 'border-box', outline: 'none',
  transition: 'all 0.3s ease',
};

const btnStyle = {
  width: '100%', padding: '14px 0', borderRadius: 14, border: 'none',
  background: '#22d3ee', color: '#020617', fontWeight: 800, fontSize: 14,
  cursor: 'pointer', marginTop: 4, letterSpacing: '0.05em', textTransform: 'uppercase',
  boxShadow: '0 4px 20px rgba(34, 211, 238, 0.3)',
  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
};

