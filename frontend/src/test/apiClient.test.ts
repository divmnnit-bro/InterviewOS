import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import {
  apiClient,
  ApiError,
  setStoredToken,
  getStoredToken,
  generateIdempotencyKey,
} from '../api/client';

describe('API Client', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('generates a valid UUIDv4 idempotency key', () => {
    const key = generateIdempotencyKey();
    expect(key).toBeDefined();
    expect(typeof key).toBe('string');
    expect(key.length).toBeGreaterThanOrEqual(16);
  });

  it('attaches bearer token from storage on authenticated requests', async () => {
    setStoredToken('mock-jwt-token');

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ id: '123', name: 'Test' }),
    });
    global.fetch = fetchMock;

    await apiClient('/auth/me');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get('Authorization')).toBe('Bearer mock-jwt-token');
  });

  it('does NOT attach bearer token on public booking requests', async () => {
    setStoredToken('mock-jwt-token');

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ stage_name: 'Tech', slots: [] }),
    });
    global.fetch = fetchMock;

    await apiClient('/booking/public-token-123');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get('Authorization')).toBeNull();
  });

  it('attaches Idempotency-Key header when provided', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ id: 'iv-1' }),
    });
    global.fetch = fetchMock;

    await apiClient('/booking/token-123/confirm', {
      method: 'POST',
      body: JSON.stringify({ start: '2026-11-02T10:00:00Z' }),
      idempotencyKey: 'idemp-key-xyz-1234',
    });

    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get('Idempotency-Key')).toBe('idemp-key-xyz-1234');
  });

  it('parses service-layer error shape { error, message, details }', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      statusText: 'Conflict',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({
        error: 'stale_schedule_version',
        message: 'The schedule has been modified by another process',
        details: { current_version: 3, expected_version: 2 },
      }),
    });
    global.fetch = fetchMock;

    await expect(apiClient('/drives/d1/schedule/publish', { method: 'POST' })).rejects.toThrowError(
      'The schedule has been modified by another process'
    );

    try {
      await apiClient('/drives/d1/schedule/publish', { method: 'POST' });
    } catch (e: any) {
      expect(e).toBeInstanceOf(ApiError);
      expect(e.status).toBe(409);
      expect(e.code).toBe('stale_schedule_version');
      expect(e.details).toEqual({ current_version: 3, expected_version: 2 });
    }
  });

  it('parses FastAPI HTTPException string detail', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ detail: 'incorrect email or password' }),
    });
    global.fetch = fetchMock;

    try {
      await apiClient('/auth/login', { method: 'POST' });
    } catch (e: any) {
      expect(e).toBeInstanceOf(ApiError);
      expect(e.status).toBe(401);
      expect(e.message).toBe('incorrect email or password');
    }
  });

  it('parses FastAPI 422 validation error detail array', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({
        detail: [
          { loc: ['body', 'email'], msg: 'value is not a valid email address' },
          { loc: ['body', 'password'], msg: 'field required' },
        ],
      }),
    });
    global.fetch = fetchMock;

    try {
      await apiClient('/auth/register', { method: 'POST' });
    } catch (e: any) {
      expect(e).toBeInstanceOf(ApiError);
      expect(e.status).toBe(422);
      expect(e.code).toBe('validation_error');
      expect(e.message).toContain('value is not a valid email address');
      expect(Array.isArray(e.details)).toBe(true);
    }
  });

  it('clears session on 401 response and redirects to /login', async () => {
    setStoredToken('expired-token');

    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ detail: 'Token expired' }),
    });
    global.fetch = fetchMock;

    try {
      await apiClient('/auth/me');
    } catch {
      // expected error
    }

    expect(getStoredToken()).toBeNull();
  });
});
