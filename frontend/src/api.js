import axios from 'axios';
import { API_BASE_URL } from './config';

const API = axios.create({ baseURL: API_BASE_URL });
const AUTH_TIMEOUT_MS = 15000;

// ── Token interceptor: attach JWT to every request if available ──
API.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Error interceptor: normalize backend error format ──
// Backend returns { success: false, error: { message: "..." } }
// but frontend expects err.response.data.detail — bridge both.
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

API.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (originalRequest.url === '/auth/refresh' || originalRequest.url === '/auth/login') {
        localStorage.clear();
        if (window.location.pathname !== '/') {
          window.location.href = '/';
        }
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise(function(resolve, reject) {
          failedQueue.push({ resolve, reject });
        }).then(token => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return API(originalRequest);
        }).catch(err => {
          return Promise.reject(err);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const { data } = await API.post('/auth/refresh', {}, { withCredentials: true });
        const newToken = data.access_token;
        localStorage.setItem('token', newToken);
        if (data.role) localStorage.setItem('role', data.role);
        if (data.username) localStorage.setItem('username', data.username);
        
        API.defaults.headers.common.Authorization = `Bearer ${newToken}`;
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        
        processQueue(null, newToken);
        return API(originalRequest);
      } catch (err) {
        processQueue(err, null);
        localStorage.clear();
        if (window.location.pathname !== '/') {
          window.location.href = '/';
        }
        return Promise.reject(err);
      } finally {
        isRefreshing = false;
      }
    }
    
    if (error.response?.data?.error?.message && !error.response.data.detail) {
      error.response.data.detail = error.response.data.error.message;
    }

    // Handle Network Error (Server Offline)
    if (!error.response && (error.code === 'ECONNABORTED' || error.message === 'Network Error')) {
      window.dispatchEvent(new CustomEvent('server-offline', { 
        detail: { message: 'Server is currently unreachable. Please check your connection.' } 
      }));
    }

    return Promise.reject(error);
  }
);

// ── Auth ──────────────────────────────────────────────────
export const registerDoctor   = (data) => API.post('/auth/register/doctor', data);
export const registerNurse    = (data) => API.post('/auth/register/nurse', data);
export const login            = (data) => API.post('/auth/login', data, { timeout: AUTH_TIMEOUT_MS });
export const logout           = ()     => API.post('/auth/logout');
export const getMe            = ()     => API.get('/auth/me');
export const resetPassword    = (data) => API.post('/auth/reset-password', data);
export const forgotPasswordRequest = (data) => API.post('/auth/forgot-password/request', data, { timeout: AUTH_TIMEOUT_MS });
export const forgotPasswordConfirm = (data) => API.post('/auth/forgot-password/confirm', data);

// ── Patients ──────────────────────────────────────────────
export const getPatients   = (params={})     => API.get('/patients', { params });
export const createPatient = (data)          => API.post('/patients', data);
export const deletePatient = (id)            => API.delete(`/patients/${id}`);
export const updatePatient = (id, data)      => API.put(`/patients/${id}`, data);
export const assignDoctor  = (id, doctorId)  => API.patch(`/patients/${id}/assign_doctor`, { doctor_id: doctorId });
export const assignNurse   = (id, nurseId)   => API.patch(`/patients/${id}/assign_nurse`,  { nurse_id: nurseId });

// ── Vitals ────────────────────────────────────────────────
export const getVitals      = (params={})    => API.get('/vitals', { params });
export const getLatestVital = (patientId)    => API.get(`/vitals/latest/${patientId}`);
export const getVitalsSourceConfig = ()      => API.get('/vitals/source');
export const updateVitalsSourceConfig = (data) => API.put('/vitals/source', data);
export const getFakeVitalsStatus = ()        => API.get('/admin/fake-vitals/status');
export const forceStartFakeVitals = ()       => API.post('/admin/fake-vitals/force-start');
export const forceStopFakeVitals = ()        => API.post('/admin/fake-vitals/force-stop');
export const cleanupVitalsByTime = (data)    => API.post('/admin/vitals/cleanup', data);
export const freshResetDomainData = ()       => API.post('/admin/reset/fresh');

// ── Alerts ────────────────────────────────────────────────
export const getAlerts         = (params={}) => API.get('/alerts', { params });
export const acknowledgeAlert  = (id, by)    => API.patch(`/alerts/${id}/acknowledge`, { acknowledged_by: by });

// ── Doctors ───────────────────────────────────────────────
export const getDoctors    = (params={})     => API.get('/doctors', { params });
export const createDoctor  = (data)          => API.post('/doctors', data);
export const updateDoctor  = (id, data)      => API.put(`/doctors/${id}`, data);
export const deleteDoctor  = (id)            => API.delete(`/doctors/${id}`);
export const getDoctorPatients = (id)        => API.get(`/doctors/${id}/patients`);

// ── Nurses ────────────────────────────────────────────────
export const getNurses     = (params={})     => API.get('/nurses', { params });
export const createNurse   = (data)          => API.post('/nurses', data);
export const updateNurse   = (id, data)      => API.put(`/nurses/${id}`, data);
export const deleteNurse   = (id)            => API.delete(`/nurses/${id}`);
export const getNursePatients  = (id)        => API.get(`/nurses/${id}/patients`);

// ── Hospitals ─────────────────────────────────────────────
export const getHospitals  = ()              => API.get('/hospitals');
export const createHospital= (data)          => API.post('/hospitals', data);
export const updateHospital = (id, data) => API.put(`/hospitals/${id}`, data);
export const deleteHospital = (id)       => API.delete(`/hospitals/${id}`);

// ── Doctors ────────────────────────────────────────────────

export const getMyNotifications = (params={}) => API.get('/notifications/my', { params });
export const markNotificationRead = (id)      => API.patch(`/notifications/${id}/read`);
export const markAllNotificationsRead = ()    => API.post('/notifications/read-all');

// ── Dashboard Stats ───────────────────────────────────────
export const getDashboardStats = ()          => API.get('/dashboard/stats');

// ── Chat (per-patient) ───────────────────────────────────
export const getPatientChat  = (patientId, params={}) => API.get(`/patients/${patientId}/chat`, { params });
export const sendPatientChat = (patientId, message)   => API.post(`/patients/${patientId}/chat`, { message });

// ── Audit Logs ────────────────────────────────────────────
export const getAuditLogs  = (params={})     => API.get('/audit-logs', { params });

// ── WhatsApp Notifications (GREEN-API) ───────────────────────────────────────
export const getWhatsAppConfig   = ()       => API.get('/whatsapp/config');
export const pauseWhatsAppAlerts = ()       => API.post('/whatsapp/alerts/pause');
export const resumeWhatsAppAlerts= ()       => API.post('/whatsapp/alerts/resume');
export const addWhatsAppRecipient = (phone) => API.post('/whatsapp/recipients/add', { phone });
export const removeWhatsAppRecipient = (phone) => API.post('/whatsapp/recipients/remove', { phone });
export const getWhatsAppLogs     = (p={})   => API.get('/whatsapp/logs', { params: p });

// ── Health Checks ─────────────────────────────────────────────────────────────
export const getHealthFull = () => API.get('/health/full');

export default API;
