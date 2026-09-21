async function apiCall(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  let data = null;
  const text = await res.text();
  if (text) {
    try { data = JSON.parse(text); } catch (e) { data = text; }
  }
  if (!res.ok) {
    const detail = (data && data.detail) ? data.detail : `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return data;
}

const api = {
  get: (path) => apiCall("GET", path),
  post: (path, body) => apiCall("POST", path, body === undefined ? {} : body),
  put: (path, body) => apiCall("PUT", path, body === undefined ? {} : body),
  del: (path) => apiCall("DELETE", path),
};

function showError(elementId, err) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.textContent = err.message || String(err);
  el.style.display = "block";
}

function clearError(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.style.display = "none";
  el.textContent = "";
}

function statusLabel(status) {
  return status.replace(/_/g, " ");
}

function fmtMinutes(m) {
  if (m === null || m === undefined) return "-";
  if (m < 0) return "overdue";
  return `${m} min`;
}

function fmtTime(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
