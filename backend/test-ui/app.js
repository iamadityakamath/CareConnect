const STORAGE_KEY = "careconnect_test_config";
const SESSION_KEY = "careconnect_session";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function getApiBase() {
  return ($("#api-base").value || "http://localhost:8000").replace(/\/$/, "");
}

function saveConfig() {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      apiBase: getApiBase(),
      supabaseUrl: $("#supabase-url").value,
      supabaseAnonKey: $("#supabase-anon-key").value,
    })
  );
}

function loadConfigFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const cfg = JSON.parse(raw);
    if (cfg.apiBase) $("#api-base").value = cfg.apiBase;
    if (cfg.supabaseUrl) $("#supabase-url").value = cfg.supabaseUrl;
    if (cfg.supabaseAnonKey) $("#supabase-anon-key").value = cfg.supabaseAnonKey;
  } catch {
    /* ignore */
  }
}

async function loadConfigFromApi() {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/config/public`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.supabase_url) $("#supabase-url").value = data.supabase_url;
    if (data.supabase_anon_key) $("#supabase-anon-key").value = data.supabase_anon_key;
    showStatus("Loaded Supabase URL and anon key from API.", "success");
  } catch (err) {
    showStatus(`Could not load config from API: ${err.message}`, "error");
  }
}

function showStatus(message, type = "idle") {
  const el = $("#status");
  el.textContent = message;
  el.className = `status ${type}`;
}

function showResponse(data) {
  const pre = $("#response-body");
  pre.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  pre.classList.remove("hidden");
}

function getSession() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY));
  } catch {
    return null;
  }
}

function setSession(data) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
  renderSession();
}

function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
  renderSession();
  $("#me-result").classList.add("hidden");
}

function renderSession() {
  const session = getSession();
  const card = $("#session-card");
  if (!session?.access_token) {
    card.classList.add("hidden");
    return;
  }
  card.classList.remove("hidden");
  const user = session.user || {};
  $("#session-user").innerHTML = `
    <strong>${escapeHtml(user.full_name || "User")}</strong>
    · ${escapeHtml(user.role || "unknown")}
    ${user.email ? `· ${escapeHtml(user.email)}` : ""}
    ${user.last_name ? `· ${escapeHtml(user.last_name)}` : ""}
  `;
  const token = session.access_token;
  $("#session-token").textContent =
    token.length > 48 ? `${token.slice(0, 24)}…${token.slice(-12)}` : token;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function apiRequest(path, options = {}) {
  const url = `${getApiBase()}${path}`;
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const session = getSession();
  if (options.auth && session?.access_token) {
    headers.Authorization = `Bearer ${session.access_token}`;
  }
  const res = await fetch(url, { ...options, headers });
  let body;
  const text = await res.text();
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
          : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return body;
}

function formToObject(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  Object.keys(data).forEach((k) => {
    if (data[k] === "") delete data[k];
  });
  return data;
}

async function handleAuthResponse(data, label) {
  setSession(data);
  showStatus(`${label} successful.`, "success");
  showResponse(data);
}

// Tabs
$$(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$(".tab").forEach((t) => t.classList.remove("active"));
    $$(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $(`#panel-${tab.dataset.tab}`).classList.add("active");
  });
});

$("#save-config").addEventListener("click", () => {
  saveConfig();
  showStatus("Settings saved to browser storage.", "success");
});

$("#load-config").addEventListener("click", loadConfigFromApi);

$("#btn-logout").addEventListener("click", () => {
  clearSession();
  showStatus("Logged out.", "idle");
  $("#response-body").classList.add("hidden");
});

$("#btn-me").addEventListener("click", async () => {
  try {
    const data = await apiRequest("/auth/me", { auth: true });
    const pre = $("#me-result");
    pre.textContent = JSON.stringify(data, null, 2);
    pre.classList.remove("hidden");
    showStatus("GET /auth/me succeeded.", "success");
  } catch (err) {
    showStatus(err.message, "error");
  }
});

$("#form-caregiver-signup").addEventListener("submit", async (e) => {
  e.preventDefault();
  saveConfig();
  try {
    const body = formToObject(e.target);
    const data = await apiRequest("/auth/caregiver/signup", {
      method: "POST",
      body: JSON.stringify(body),
    });
    await handleAuthResponse(data, "Caregiver sign up");
  } catch (err) {
    showStatus(err.message, "error");
    showResponse(err.message);
  }
});

$("#form-caregiver-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  saveConfig();
  try {
    const body = formToObject(e.target);
    const data = await apiRequest("/auth/caregiver/login", {
      method: "POST",
      body: JSON.stringify(body),
    });
    await handleAuthResponse(data, "Caregiver log in");
  } catch (err) {
    showStatus(err.message, "error");
    showResponse(err.message);
  }
});

$("#form-patient-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  saveConfig();
  try {
    const body = formToObject(e.target);
    const data = await apiRequest("/auth/patient-login", {
      method: "POST",
      body: JSON.stringify(body),
    });
    await handleAuthResponse(data, "Patient log in");
  } catch (err) {
    showStatus(err.message, "error");
    showResponse(err.message);
  }
});

$("#form-patient-provision").addEventListener("submit", async (e) => {
  e.preventDefault();
  saveConfig();
  const session = getSession();
  if (!session?.access_token || session.user?.role !== "caregiver") {
    showStatus("Log in as a caregiver first.", "error");
    return;
  }
  try {
    const body = formToObject(e.target);
    const data = await apiRequest("/patients/provision", {
      method: "POST",
      auth: true,
      body: JSON.stringify(body),
    });
    showStatus("Patient account created.", "success");
    showResponse(data);
  } catch (err) {
    showStatus(err.message, "error");
    showResponse(err.message);
  }
});

// Init
loadConfigFromStorage();
renderSession();
loadConfigFromApi();
