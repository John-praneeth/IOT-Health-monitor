import axios from 'axios';

const API = axios.create({ baseURL: 'http://localhost:8000' });

// ── Token interceptor: attach JWT to every request if available ──
API.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Auth ──────────────────────────────────────────────────
export const register         = (data) => API.post('/auth/register', data);
export const registerDoctor   = (data) => API.post('/auth/register/doctor', data);
export const registerNurse    = (data) => API.post('/auth/register/nurse', data);
export const login            = (data) => API.post('/auth/login', data);
export const getMe            = ()     => API.get('/auth/me');

// ── Patients ──────────────────────────────────────────────
export const getPatients   = (params={})     => API.get('/patients', { params });
export const createPatient = (data)          => API.post('/patients', data);
export const deletePatient = (id)            => API.delete(`/patients/${id}`);
export const assignDoctor  = (id, doctorId)  => API.patch(`/patients/${id}/assign_doctor`, { doctor_id: doctorId });
export const assignNurse   = (id, nurseId)   => API.patch(`/patients/${id}/assign_nurse`,  { nurse_id: nurseId });

// ── Vitals ────────────────────────────────────────────────
export const getVitals      = (params={})    => API.get('/vitals', { params });
export const getLatestVital = (patientId)    => API.get(`/vitals/latest/${patientId}`);

// ── Alerts ────────────────────────────────────────────────
export const getAlerts         = (params={}) => API.get('/alerts', { params });
export const acknowledgeAlert  = (id, by)    => API.patch(`/alerts/${id}/acknowledge`, { acknowledged_by: by });

// ── Doctors ───────────────────────────────────────────────
export const getDoctors    = (params={})     => API.get('/doctors', { params });
export const createDoctor  = (data)          => API.post('/doctors', data);
export const deleteDoctor  = (id)            => API.delete(`/doctors/${id}`);
export const getDoctorPatients = (id)        => API.get(`/doctors/${id}/patients`);

// ── Nurses ────────────────────────────────────────────────
export const getNurses     = (params={})     => API.get('/nurses', { params });
export const createNurse   = (data)          => API.post('/nurses', data);
export const deleteNurse   = (id)            => API.delete(`/nurses/${id}`);
export const getNursePatients  = (id)        => API.get(`/nurses/${id}/patients`);

// ── Hospitals ─────────────────────────────────────────────
export const getHospitals  = ()              => API.get('/hospitals');
export const createHospital= (data)          => API.post('/hospitals', data);

// ── Notifications ─────────────────────────────────────────
export const getMyNotifications = (params={}) => API.get('/notifications/my', { params });
export const markNotificationRead = (id)      => API.patch(`/notifications/${id}/read`);
export const markAllNotificationsRead = ()    => API.post('/notifications/read-all');

// ── Dashboard Stats ───────────────────────────────────────
export const getDashboardStats = ()          => API.get('/dashboard/stats');

// ── Chat (per-patient) ───────────────────────────────────
export const getPatientChat  = (patientId, params={}) => API.get(`/patients/${patientId}/chat`, { params });
export const sendPatientChat = (patientId, message)   => API.post(`/patients/${patientId}/chat`, { message });

// ── Escalations ───────────────────────────────────────────
export const getEscalations = (params={})    => API.get('/escalations', { params });

// ── Audit Logs ────────────────────────────────────────────
export const getAuditLogs  = (params={})     => API.get('/audit-logs', { params });

export default API;
