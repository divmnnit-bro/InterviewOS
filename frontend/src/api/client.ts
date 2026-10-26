export class ApiError extends Error {
  status: number;
  code: string;
  details?: any;

  constructor(status: number, code: string, message: string, details?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const TOKEN_KEY = 'interviewos_auth_token';

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // Ignore storage errors in restricted contexts
  }
}

export function clearSession(): void {
  setStoredToken(null);
}

export interface RequestOptions extends RequestInit {
  idempotencyKey?: string;
  isPublic?: boolean;
  params?: Record<string, string | number | boolean | undefined | null>;
}

export async function apiClient<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  
  // Format query params if provided
  let url = `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  if (options.params) {
    const searchParams = new URLSearchParams();
    Object.entries(options.params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString;
    }
  }

  const headers = new Headers(options.headers || {});
  
  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  // Only add bearer token if not a public endpoint (like booking)
  const isPublicBooking = endpoint.startsWith('/booking/') || options.isPublic;
  if (!isPublicBooking) {
    const token = getStoredToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  // Idempotency-Key support
  if (options.idempotencyKey) {
    headers.set('Idempotency-Key', options.idempotencyKey);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // Handle 204 No Content
  if (response.status === 204) {
    return null as unknown as T;
  }

  let body: any = null;
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    try {
      body = await response.json();
    } catch {
      body = null;
    }
  } else if (contentType && (contentType.includes('text/calendar') || contentType.includes('text/plain'))) {
    const text = await response.text();
    return text as unknown as T;
  }

  if (!response.ok) {
    // 401 handling: clear session and redirect if not already on /login
    if (response.status === 401 && !isPublicBooking) {
      clearSession();
      if (typeof window !== 'undefined' && window.location && window.location.pathname !== '/login' && process.env.NODE_ENV !== 'test') {
        window.location.href = '/login';
      }
    }

    let code = `HTTP_${response.status}`;
    let message = response.statusText || 'Request failed';
    let details: any = undefined;

    if (body && typeof body === 'object') {
      // Shape 1: Service-layer error { error, message, details }
      if (body.error) {
        code = body.error;
        message = body.message || code;
        details = body.details;
      }
      // Shape 2: FastAPI HTTPException { detail: string | array | object }
      else if (body.detail !== undefined) {
        if (typeof body.detail === 'string') {
          message = body.detail;
          code = `HTTP_${response.status}`;
        } else if (Array.isArray(body.detail)) {
          // Pydantic 422 validation errors
          message = body.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
          code = 'validation_error';
          details = body.detail;
        } else if (typeof body.detail === 'object') {
          message = body.detail.message || JSON.stringify(body.detail);
          code = body.detail.code || `HTTP_${response.status}`;
          details = body.detail;
        }
      }
    }

    throw new ApiError(response.status, code, message, details);
  }

  return body as T;
}

apiClient.get = <T>(endpoint: string, options?: RequestOptions): Promise<T> =>
  apiClient<T>(endpoint, { ...options, method: 'GET' });

apiClient.post = <T>(endpoint: string, data?: any, options?: RequestOptions): Promise<T> =>
  apiClient<T>(endpoint, {
    ...options,
    method: 'POST',
    body: data !== undefined ? JSON.stringify(data) : undefined,
  });

apiClient.patch = <T>(endpoint: string, data?: any, options?: RequestOptions): Promise<T> =>
  apiClient<T>(endpoint, {
    ...options,
    method: 'PATCH',
    body: data !== undefined ? JSON.stringify(data) : undefined,
  });

apiClient.put = <T>(endpoint: string, data?: any, options?: RequestOptions): Promise<T> =>
  apiClient<T>(endpoint, {
    ...options,
    method: 'PUT',
    body: data !== undefined ? JSON.stringify(data) : undefined,
  });

apiClient.delete = <T>(endpoint: string, options?: RequestOptions): Promise<T> =>
  apiClient<T>(endpoint, { ...options, method: 'DELETE' });

apiClient.getBaseUrl = (): string =>
  import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Generate random UUIDv4 for Idempotency-Key
export function generateIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

