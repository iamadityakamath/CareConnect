const SESSION_KEY = "careconnect_session";

const $ = (sel) => document.querySelector(sel);

function getApiBase() {
  const { origin, pathname } = window.location;
  if (origin.startsWith("http") && pathname.includes("/sample-webpage")) {
    return origin;
  }
  return "http://localhost:8000";
}

function getSession() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY));
  } catch {
    return null;
  }
}

function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

async function apiRequest(path, options = {}) {
  const session = getSession();
  if (!session?.access_token) {
    window.location.href = "index.html";
    return null;
  }

  const headers = { ...(options.headers || {}) };
  if (!headers["Content-Type"] && options.body) {
    headers["Content-Type"] = "application/json";
  }
  headers.Authorization = `Bearer ${session.access_token}`;

  const res = await fetch(`${getApiBase()}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearSession();
    window.location.href = "index.html";
    return null;
  }

  const text = await res.text();
  let body;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }

  if (!res.ok) {
    const detail = body?.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg).join("; ")
          : "Something went wrong.";
    throw new Error(msg);
  }
  return body;
}

function requireSession() {
  const session = getSession();
  if (!session?.access_token || !session.user) {
    window.location.href = "index.html";
    return null;
  }
  return session;
}

function renderCaregiverHeader(session) {
  const name = session.user?.full_name || session.user?.email || "Caregiver";
  const el = $("#caregiver-greeting");
  if (el) {
    el.textContent = name;
  }
}

function bindLogout() {
  const btn = $("#btn-logout");
  if (!btn) return;
  btn.addEventListener("click", () => {
    clearSession();
    window.location.href = "index.html";
  });
}

function initCaregiverShell() {
  const session = requireSession();
  if (!session) return null;

  if (session.user?.role !== "caregiver") {
    window.location.href = "dashboard.html";
    return null;
  }

  renderCaregiverHeader(session);
  bindLogout();
  return session;
}

function renderPatientDashboard(user) {
  $("#patient-view")?.classList.remove("hidden");
  const card = $("#user-card");
  if (!card) return;
  card.innerHTML = `
    <p class="name">${escapeHtml(user.full_name || "Patient")}</p>
    <p class="meta">Last name: ${escapeHtml(user.last_name || "—")}</p>
    <span class="role-badge">Patient</span>
  `;
}

function initPatientShell() {
  const session = requireSession();
  if (!session) return null;

  if (session.user?.role === "caregiver") {
    window.location.href = "dashboard.html";
    return null;
  }

  bindLogout();
  renderPatientDashboard(session.user);
  return session;
}
