const rawApiBase = (process.env.REACT_APP_API_BASE_URL || '').trim();
const rawWsBase = (process.env.REACT_APP_WS_BASE_URL || '').trim();

export const API_BASE_URL = rawApiBase || '/api';

export const API_BASE_LABEL =
  API_BASE_URL.startsWith('http://') || API_BASE_URL.startsWith('https://')
    ? API_BASE_URL
    : 'same-origin (/api)';

const normalizeBase = (base) => (base || '').replace(/\/+$/, '');

export const getDocsUrl = () => `${normalizeBase(API_BASE_URL)}/docs`;
export const getRedocUrl = () => `${normalizeBase(API_BASE_URL)}/redoc`;

export const getWsBaseUrl = () => {
  if (rawWsBase) return normalizeBase(rawWsBase);
  if (typeof window === 'undefined') return 'ws://localhost:8000/ws';

  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  if (window.location.port === '3000') {
    return `${proto}://${window.location.hostname}:8000/ws`;
  }
  return `${proto}://${window.location.host}/ws`;
};

export const buildVitalsWsUrl = (token) =>
  `${normalizeBase(getWsBaseUrl())}/vitals?token=${encodeURIComponent(token)}`;
