/**
 * config.js resolves the API/WS base URL at module load from window.location
 * and REACT_APP_* env vars. Each case loads a fresh module instance.
 */
const loadConfigAt = (href, env = {}) => {
  const url = new URL(href);
  delete window.location;
  window.location = {
    href,
    host: url.host,
    hostname: url.hostname,
    port: url.port,
    protocol: url.protocol,
    search: url.search,
  };
  const saved = { ...process.env };
  delete process.env.REACT_APP_API_BASE_URL;
  delete process.env.REACT_APP_WS_BASE_URL;
  Object.assign(process.env, env);
  let mod;
  jest.isolateModules(() => {
    mod = require('./config');
  });
  process.env = saved;
  return mod;
};

const BACKEND = 'https://iot-healthcare-backend.onrender.com';

describe('API base resolution', () => {
  test('Render static-site host defaults to the Render backend', () => {
    const cfg = loadConfigAt('https://iot-healthcare-frontend.onrender.com/');
    expect(cfg.API_BASE_URL).toBe(BACKEND);
    expect(cfg.getWsBaseUrl()).toBe('wss://iot-healthcare-backend.onrender.com/ws');
  });

  test('localhost dev defaults to local backend', () => {
    const cfg = loadConfigAt('http://localhost:3000/');
    expect(cfg.API_BASE_URL).toBe('http://localhost:8000');
    expect(cfg.getWsBaseUrl()).toBe('ws://localhost:8000/ws');
  });

  test('REACT_APP_* env vars take precedence over host detection', () => {
    const cfg = loadConfigAt('https://iot-healthcare-frontend.onrender.com/', {
      REACT_APP_API_BASE_URL: 'https://example.test',
      REACT_APP_WS_BASE_URL: 'wss://example.test/ws',
    });
    expect(cfg.API_BASE_URL).toBe('https://example.test');
    expect(cfg.getWsBaseUrl()).toBe('wss://example.test/ws');
  });

  test('?api= query param overrides everything', () => {
    const cfg = loadConfigAt('https://iot-healthcare-frontend.onrender.com/?api=https://override.test');
    expect(cfg.API_BASE_URL).toBe('https://override.test');
  });
});
