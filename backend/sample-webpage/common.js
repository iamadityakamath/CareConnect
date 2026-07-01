const SESSION_KEY = "careconnect_session";
const PATIENT_SESSION_DAYS = 30;
const TOKEN_REFRESH_BUFFER_SEC = 120;

const $ = (sel) => document.querySelector(sel);

function getApiBase() {
  const { origin, pathname } = window.location;
  if (origin.startsWith("http") && pathname.includes("/sample-webpage")) {
    return origin;
  }
  return "http://localhost:8000";
}

function isPatientSession(session) {
  return session?.user?.role === "elder";
}

function nowUnix() {
  return Math.floor(Date.now() / 1000);
}

function enrichSession(data) {
  const now = nowUnix();
  const expiresIn = data.expires_in || 3600;
  const enriched = {
    ...data,
    expires_at: data.expires_at || now + expiresIn,
  };
  if (isPatientSession(data) && !data.persistent_until) {
    enriched.persistent_until = now + PATIENT_SESSION_DAYS * 86400;
  }
  return enriched;
}

function isPatientPage() {
  return /patient-home\.html/i.test(window.location.pathname);
}

function getSession() {
  try {
    const fromLocal = localStorage.getItem(SESSION_KEY);
    const fromSession = sessionStorage.getItem(SESSION_KEY);
    const parsedLocal = fromLocal ? JSON.parse(fromLocal) : null;
    const parsedSession = fromSession ? JSON.parse(fromSession) : null;

    // Patient pages prefer long-lived patient storage; caregiver pages prefer session storage.
    if (isPatientPage()) {
      return parsedLocal || parsedSession;
    }
    return parsedSession || parsedLocal;
  } catch {
    return null;
  }
  return null;
}

function setSession(data) {
  const enriched = enrichSession(data);
  if (isPatientSession(enriched)) {
    sessionStorage.removeItem(SESSION_KEY);
    localStorage.setItem(SESSION_KEY, JSON.stringify(enriched));
    return enriched;
  }
  localStorage.removeItem(SESSION_KEY);
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(enriched));
  return enriched;
}

function clearSession() {
  localStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(SESSION_KEY);
}

function patientSessionExpired(session) {
  if (!isPatientSession(session)) {
    return false;
  }
  if (!session?.persistent_until) {
    return false;
  }
  return nowUnix() >= session.persistent_until;
}

function accessTokenNeedsRefresh(session) {
  if (!session?.access_token) {
    return true;
  }
  if (!session.expires_at) {
    return false;
  }
  return session.expires_at - nowUnix() <= TOKEN_REFRESH_BUFFER_SEC;
}

async function refreshSession() {
  const session = getSession();
  if (!session?.refresh_token) {
    clearSession();
    return null;
  }
  if (patientSessionExpired(session)) {
    clearSession();
    return null;
  }

  try {
    const res = await fetch(`${getApiBase()}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: session.refresh_token }),
    });

    if (!res.ok) {
      clearSession();
      return null;
    }

    const data = await res.json();
    return setSession({
      ...data,
      persistent_until: session.persistent_until || data.persistent_until,
    });
  } catch {
    clearSession();
    return null;
  }
}

async function ensureValidSession() {
  let session = getSession();
  if (!session?.access_token) {
    return null;
  }
  if (patientSessionExpired(session)) {
    clearSession();
    return null;
  }
  if (accessTokenNeedsRefresh(session)) {
    session = await refreshSession();
  }
  return session;
}

function clearSessionAndRedirect() {
  clearSession();
  window.location.href = "index.html";
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function formatOverdueDuration(totalMinutes) {
  const minutes = Math.max(0, Number(totalMinutes) || 0);
  if (minutes < 60) {
    return `${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (mins === 0) {
    return `${hours} hr`;
  }
  return `${hours} hr ${mins} min`;
}

async function apiRequest(path, options = {}) {
  let session = await ensureValidSession();
  if (!session?.access_token) {
    clearSessionAndRedirect();
    return null;
  }

  const headers = { ...(options.headers || {}) };
  if (!headers["Content-Type"] && options.body) {
    headers["Content-Type"] = "application/json";
  }
  headers.Authorization = `Bearer ${session.access_token}`;

  let res = await fetch(`${getApiBase()}${path}`, { ...options, headers });

  if (res.status === 401) {
    session = await refreshSession();
    if (session?.access_token) {
      headers.Authorization = `Bearer ${session.access_token}`;
      res = await fetch(`${getApiBase()}${path}`, { ...options, headers });
    }
  }

  if (res.status === 401) {
    clearSessionAndRedirect();
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

async function requireSession() {
  const session = await ensureValidSession();
  if (!session?.access_token || !session.user) {
    clearSessionAndRedirect();
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

const CAREGIVER_MOBILE_TABS = [
  {
    href: "dashboard.html",
    label: "Home",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1v-9.5Z"/></svg>`,
    pages: ["dashboard.html"],
  },
  {
    href: "patients.html",
    label: "Patients",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
    pages: ["patients.html", "patient-detail.html"],
  },
  {
    href: "onboard-patient.html",
    label: "Add",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 8v8M8 12h8"/></svg>`,
    pages: ["onboard-patient.html"],
  },
  {
    href: "apis.html",
    label: "APIs",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M8 9h8M8 15h8M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/></svg>`,
    pages: ["apis.html"],
  },
];

function initCaregiverMobileNav() {
  const shell = document.querySelector(".dashboard, .layout-wide");
  if (!shell || document.querySelector(".mobile-tab-bar")) {
    return;
  }

  const page = window.location.pathname.split("/").pop() || "dashboard.html";
  const nav = document.createElement("nav");
  nav.className = "mobile-tab-bar";
  nav.setAttribute("aria-label", "Caregiver navigation");

  nav.innerHTML = CAREGIVER_MOBILE_TABS.map((tab) => {
    const active = tab.pages.includes(page);
    return `
      <a href="${tab.href}" class="mobile-tab${active ? " active" : ""}"${
        active ? ' aria-current="page"' : ""
      }>
        <span class="mobile-tab-icon">${tab.icon}</span>
        <span class="mobile-tab-label">${tab.label}</span>
      </a>
    `;
  }).join("");

  document.body.appendChild(nav);
  document.body.classList.add("has-mobile-tab-bar");
}

async function initCaregiverShell() {
  const session = await requireSession();
  if (!session) return null;

  if (session.user?.role !== "caregiver") {
    window.location.href = "patient-home.html";
    return null;
  }

  renderCaregiverHeader(session);
  bindLogout();
  initCaregiverMobileNav();
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

async function initPatientShell() {
  const session = await requireSession();
  if (!session) return null;

  if (session.user?.role === "caregiver") {
    window.location.href = "dashboard.html";
    return null;
  }

  document.body.classList.add("patient-shell");
  bindLogout();
  return session;
}
