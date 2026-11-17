// Cliente de la API (cookie de sesión HttpOnly; el JS nunca toca el token).
export class ApiError extends Error {
  constructor(message, status, data) { super(message); this.status = status; this.data = data; }
}

let csrf = null;
async function call(method, path, body) {
  const opt = { method, headers: {}, credentials: "same-origin" };
  if (body instanceof FormData) opt.body = body;
  else if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers["Content-Type"] = "application/json"; }
  if (!["GET", "HEAD"].includes(method)) {
    if (csrf === null) { const session = await call("GET", "/api/me"); csrf = session.csrf_token || ""; }
    opt.headers["X-CSRF-Token"] = csrf;
  }
  let res;
  try { res = await fetch(path, opt); }
  catch { throw new ApiError("Sin conexión con el servidor.", 0, {}); }
  const data = await res.json().catch(() => ({}));
  if (data.csrf_token !== undefined) csrf = data.csrf_token;
  if (path === "/api/auth/logout") csrf = null;
  if (!res.ok) throw new ApiError(data.message || "Algo salió mal.", res.status, data);
  return data;
}

export const api = {
  get: (p) => call("GET", p),
  post: (p, b = {}) => call("POST", p, b),
  put: (p, b) => call("PUT", p, b),
  del: (p, b) => call("DELETE", p, b),
  form: (method, p, fd) => call(method, p, fd),
};
