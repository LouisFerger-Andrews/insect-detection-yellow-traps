const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

async function apiErrorMessage(response: Response): Promise<string> {
  if (response.status >= 500) {
    return 'Server error. Try again later.';
  }
  const contentType = response.headers.get('Content-Type') ?? '';
  const text = await response.text();
  if (contentType.includes('application/json')) {
    try {
      const payload = JSON.parse(text) as { detail?: unknown };
      if (typeof payload.detail === 'string') return payload.detail;
    } catch {
      return text || 'Request failed';
    }
  }
  return text || 'Request failed';
}

async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(init.headers || {});
  headers.set('Accept', 'application/json');
  if (!(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      referrerPolicy: 'same-origin',
    });
  } catch {
    throw new Error(`Cannot reach API at ${API_BASE}. Ensure backend is running on port 8000.`);
  }

  if (!response.ok) {
    throw new Error(await apiErrorMessage(response));
  }

  return response.json() as Promise<T>;
}

async function requestText(path: string, init: RequestInit = {}, token?: string): Promise<string> {
  const headers = new Headers(init.headers || {});
  headers.set('Accept', 'text/csv, text/plain');
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      referrerPolicy: 'same-origin',
    });
  } catch {
    throw new Error(`Cannot reach API at ${API_BASE}. Ensure backend is running on port 8000.`);
  }

  if (!response.ok) {
    throw new Error(await apiErrorMessage(response));
  }

  return response.text();
}

export const apiClient = {
  get: <T>(path: string, token?: string) => request<T>(path, { method: 'GET' }, token),
  post: <T>(path: string, body: unknown, token?: string) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }, token),
  patch: <T>(path: string, body: unknown, token?: string) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }, token),
  postForm: <T>(path: string, body: FormData, token?: string) =>
    request<T>(path, { method: 'POST', body }, token),
  getText: (path: string, token?: string) => requestText(path, { method: 'GET' }, token),
};
