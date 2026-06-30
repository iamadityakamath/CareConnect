const SESSION_KEY = "careconnect_session";

const $ = (sel) => document.querySelector(sel);

/** @type {Array<{full_name: string, last_name: string, login_code: string}>} */
let addedThisSession = [];

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

function requireCaregiverSession() {
  const session = getSession();
  if (!session?.access_token || session.user?.role !== "caregiver") {
    window.location.href = "index.html";
    return null;
  }
  return session;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
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
  const session = getSession();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (session?.access_token) {
    headers.Authorization = `Bearer ${session.access_token}`;
  }

  const res = await fetch(`${getApiBase()}${path}`, { ...options, headers });
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

function generateLoginCode() {
  return String(Math.floor(1000 + Math.random() * 9000));
}

function renderPatientsList(elders) {
  const section = $("#patients-added-section");
  const list = $("#patients-added-list");
  const count = $("#patient-count");

  if (!elders.length) {
    section.classList.add("hidden");
    list.innerHTML = "";
    return;
  }

  section.classList.remove("hidden");
  count.textContent = String(elders.length);

  list.innerHTML = elders
    .map(
      (p) => `
    <li class="added-patient-item">
      <div class="added-patient-info">
        <strong>${escapeHtml(p.full_name || "Patient")}</strong>
        <span class="added-patient-meta">Last name: ${escapeHtml(p.last_name)} · Code: <code>${escapeHtml(p.login_code || "—")}</code></span>
      </div>
    </li>
  `
    )
    .join("");

  const title = $("#form-section-title");
  if (title) {
    title.textContent = elders.length ? "Add another patient" : "New patient";
  }
}

async function loadExistingPatients() {
  try {
    const elders = await apiRequest("/relationships/my-elders");
    const mapped = (elders || []).map((e) => ({
      full_name: e.full_name,
      last_name: e.last_name,
      login_code: null,
    }));
    addedThisSession = mapped;
    renderPatientsList(addedThisSession);
  } catch {
    /* list stays empty */
  }
}

function resetForm() {
  const form = $("#form-provision-patient");
  form.reset();
  $("#login-code").value = generateLoginCode();
  form.querySelector('[name="full_name"]')?.focus();
}

const session = requireCaregiverSession();
if (session) {
  const name = session.user?.full_name || session.user?.email || "Caregiver";
  $("#caregiver-name").textContent = name;
  $("#caregiver-banner").classList.remove("hidden");
  $("#login-code").value = generateLoginCode();
  loadExistingPatients();
}

$("#btn-generate-code").addEventListener("click", () => {
  $("#login-code").value = generateLoginCode();
});

$("#form-provision-patient").addEventListener("submit", async (e) => {
  e.preventDefault();
  clearMessage();
  const btn = $("#btn-submit-patient");
  btn.disabled = true;

  try {
    const body = formToObject(e.target);
    const lastName = body.last_name;
    const loginCode = body.login_code;
    const fullName = body.full_name;

    await apiRequest("/patients/provision", {
      method: "POST",
      body: JSON.stringify(body),
    });

    addedThisSession.push({ full_name: fullName, last_name: lastName, login_code: loginCode });
    renderPatientsList(addedThisSession);

    showMessage(
      `${fullName} added. Share last name "${lastName}" and code "${loginCode}" with them. Add another below or continue to dashboard.`,
      "success"
    );
    resetForm();
  } catch (err) {
    showMessage(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

$("#btn-go-dashboard").addEventListener("click", () => {
  window.location.href = "dashboard.html";
});

$("#btn-skip").addEventListener("click", () => {
  window.location.href = "dashboard.html";
});
