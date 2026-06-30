const SESSION_KEY = "careconnect_session";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let currentPersona = "caregiver";
let currentMode = "login";

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

function setSession(data) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
}

function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
}

function showMessage(text, type) {
  const el = $("#message");
  el.textContent = text;
  el.className = `message visible ${type}`;
}

function clearMessage() {
  const el = $("#message");
  el.textContent = "";
  el.className = "message";
}

function formToObject(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  Object.keys(data).forEach((k) => {
    if (data[k] === "") delete data[k];
  });
  return data;
}

async function apiRequest(path, options = {}) {
  const res = await fetch(`${getApiBase()}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });

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
          : "Something went wrong. Please try again.";
    throw new Error(msg);
  }
  return body;
}

function redirectAfterAuth(data, { isSignup = false } = {}) {
  setSession(data);
  showMessage("Success! Redirecting…", "success");

  const isCaregiver = data.user?.role === "caregiver";
  let target = "dashboard.html";

  if (isCaregiver && isSignup) {
    target = "onboard-patient.html";
  }

  setTimeout(() => {
    window.location.href = target;
  }, 400);
}

function updateHeader() {
  const title = $("#auth-title");
  const subtitle = $("#auth-subtitle");

  if (currentPersona === "patient") {
    title.textContent = "Patient sign in";
    subtitle.textContent = "Enter your last name and login code.";
    return;
  }

  if (currentMode === "signup") {
    title.textContent = "Create caregiver account";
    subtitle.textContent = "Sign up to manage patients and care plans.";
  } else {
    title.textContent = "Caregiver sign in";
    subtitle.textContent = "Manage care for your loved ones.";
  }
}

function setPersona(persona) {
  currentPersona = persona;
  const isPatient = persona === "patient";

  $$(".persona-btn").forEach((btn) => {
    const active = btn.dataset.persona === persona;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active);
  });

  $("#view-patient").classList.toggle("active", isPatient);
  $("#view-patient").hidden = !isPatient;
  $("#view-caregiver").classList.toggle("active", !isPatient);
  $("#view-caregiver").hidden = isPatient;

  if (!isPatient) {
    setMode(currentMode);
  }

  updateHeader();
  clearMessage();
}

function setMode(mode) {
  currentMode = mode;
  const isLogin = mode === "login";

  $$(".mode-btn").forEach((btn) => {
    const active = btn.dataset.mode === mode;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active);
  });

  const loginForm = $("#form-caregiver-login");
  const signupForm = $("#form-caregiver-signup");

  loginForm.classList.toggle("active", isLogin);
  loginForm.hidden = !isLogin;
  signupForm.classList.toggle("active", !isLogin);
  signupForm.hidden = isLogin;

  updateHeader();
  clearMessage();
}

async function submitForm(form, path, label, options = {}) {
  clearMessage();
  const btn = form.querySelector(".submit-btn");
  btn.disabled = true;

  try {
    const body = formToObject(form);
    const data = await apiRequest(path, {
      method: "POST",
      body: JSON.stringify(body),
    });
    redirectAfterAuth(data, options);
  } catch (err) {
    showMessage(err.message || `${label} failed.`, "error");
  } finally {
    btn.disabled = false;
  }
}

$$(".persona-btn").forEach((btn) => {
  btn.addEventListener("click", () => setPersona(btn.dataset.persona));
});

$$(".mode-btn").forEach((btn) => {
  btn.addEventListener("click", () => setMode(btn.dataset.mode));
});

$("#form-caregiver-login").addEventListener("submit", (e) => {
  e.preventDefault();
  submitForm(e.target, "/auth/caregiver/login", "Log in");
});

$("#form-patient-login").addEventListener("submit", (e) => {
  e.preventDefault();
  submitForm(e.target, "/auth/patient-login", "Log in");
});

$("#form-caregiver-signup").addEventListener("submit", (e) => {
  e.preventDefault();
  submitForm(e.target, "/auth/caregiver/signup", "Sign up", { isSignup: true });
});

const existing = getSession();
if (existing?.access_token && existing?.user) {
  window.location.href = "dashboard.html";
} else {
  setPersona("caregiver");
  setMode("login");
}
