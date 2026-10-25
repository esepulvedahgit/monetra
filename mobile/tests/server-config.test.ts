import { describe, expect, it } from 'vitest';

import { normalizeServerUrl, serverInputValue, serverLabel, serverProbeProblem } from '../src/config/serverUrl';

describe('server URL normalization', () => {
  it('builds the API base URL from what a person types', () => {
    expect(normalizeServerUrl('monetra.example.com')).toBe('https://monetra.example.com/api/v1');
    expect(normalizeServerUrl('  https://Monetra.Example.com/  ')).toBe('https://monetra.example.com/api/v1');
    expect(normalizeServerUrl('https://example.com/monetra')).toBe('https://example.com/monetra/api/v1');
    expect(normalizeServerUrl('https://example.com:8443/api/v1/')).toBe('https://example.com:8443/api/v1');
  });

  it('rejects insecure, empty or unsafe addresses', () => {
    expect(() => normalizeServerUrl('')).toThrow();
    expect(() => normalizeServerUrl('http://example.com')).toThrow(/https/);
    expect(() => normalizeServerUrl('ftp://example.com')).toThrow();
    expect(() => normalizeServerUrl('https://user:secret@example.com')).toThrow();
    expect(() => normalizeServerUrl('javascript:alert(1)')).toThrow();
    expect(() => normalizeServerUrl('https://example.com/?next=evil')).toThrow();
    expect(() => normalizeServerUrl('https://example.com:70000')).toThrow();
  });

  it('allows plain HTTP only when explicitly enabled for development', () => {
    expect(normalizeServerUrl('http://10.0.2.2:5000', { allowHttp: true })).toBe('http://10.0.2.2:5000/api/v1');
  });

  it('shows a readable label and editable value', () => {
    expect(serverLabel('https://monetra.example.com/api/v1')).toBe('monetra.example.com');
    expect(serverLabel('https://example.com/monetra/api/v1')).toBe('example.com/monetra');
    expect(serverInputValue('https://example.com/monetra/api/v1')).toBe('https://example.com/monetra');
  });
});

describe('server probe', () => {
  it('accepts the JSON 401 a Monetra API returns without credentials', () => {
    expect(serverProbeProblem({ status: 401, contentType: 'application/json; charset=utf-8' })).toBeNull();
  });

  it('rejects addresses that are not a Monetra API', () => {
    expect(serverProbeProblem({ status: 200, contentType: 'text/html' })).not.toBeNull();
    expect(serverProbeProblem({ status: 404, contentType: 'application/json' })).not.toBeNull();
    expect(serverProbeProblem({ status: 401, contentType: 'text/html' })).not.toBeNull();
  });

  it('explains connectivity and timeout failures', () => {
    expect(serverProbeProblem({ error: { code: 'ERR_NETWORK' } })).toMatch(/certificado/);
    expect(serverProbeProblem({ error: { code: 'ECONNABORTED' } })).toMatch(/tardó/);
  });
});
