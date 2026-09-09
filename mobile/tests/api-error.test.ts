import { describe, expect, it, vi } from 'vitest';

vi.mock('expo-secure-store', () => ({
  getItemAsync: vi.fn(),
  setItemAsync: vi.fn(),
  deleteItemAsync: vi.fn(),
}));

vi.mock('@react-native-async-storage/async-storage', () => ({
  default: {
    getItem: vi.fn(),
    setItem: vi.fn(),
  },
}));

import { api, apiError } from '../src/api/client';

describe('apiError', () => {
  it('explains a transport error when no HTTP response exists', () => {
    expect(apiError({ code: 'ERR_NETWORK', message: 'Network Error' })).toBe(
      'No se pudo conectar con Monetra. Revisa tu conexión e inténtalo nuevamente.'
    );
  });

  it('explains a request timeout when no HTTP response exists', () => {
    expect(apiError({ code: 'ECONNABORTED', message: 'timeout of 15000ms exceeded' })).toBe(
      'La conexión con Monetra tardó demasiado. Inténtalo nuevamente.'
    );
  });

  it('configures JSON headers for API POST requests', () => {
    expect(api.defaults.headers.common.Accept).toBe('application/json');
    expect(api.defaults.headers.post['Content-Type']).toBe('application/json');
  });

  it('uses the public Monetra API when no build-time URL is supplied', () => {
    expect(api.defaults.baseURL).toBe('https://monetra.hgrey.net/api/v1');
  });
});
