/* Thin fetch wrapper. Every failure becomes an ApiError with a message fit to show a person. */

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'error', details = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request(path, { method = 'GET', json, body, signal } = {}) {
  let response;
  try {
    response = await fetch(path, {
      method,
      headers: json ? { 'Content-Type': 'application/json' } : undefined,
      body: json ? JSON.stringify(json) : body,
      signal,
    });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError('Cannot reach the server. Check that it is still running, then try again.', { code: 'network' });
  }
  let data = null;
  try { data = await response.json(); } catch { /* not JSON */ }
  if (!response.ok) {
    const e = data && data.error;
    throw new ApiError((e && e.message) || `The request failed (${response.status}).`, {
      status: response.status, code: (e && e.code) || 'error', details: (e && e.details) || null,
    });
  }
  return data;
}

export const api = {
  schema: () => request('/api/schema'),
  models: () => request('/api/models'),
  predict: (inputs, { explain = true, signal } = {}) =>
    request('/api/predict', { method: 'POST', json: { inputs, explain }, signal }),
  sensitivity: (inputs, feature, { signal, points = 41 } = {}) =>
    request('/api/sensitivity', { method: 'POST', json: { inputs, feature, points }, signal }),
  batch: (file) => {
    const form = new FormData();
    form.append('file', file);
    return request('/api/predict/batch', { method: 'POST', body: form });
  },
};
