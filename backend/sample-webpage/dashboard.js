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

function generateLoginCode() {
  return String(Math.floor(1000 + Math.random() * 9000));
}

function formToObject(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  Object.keys(data).forEach((k) => {
    if (data[k] === "") delete data[k];
  });
  return data;
}

function showFormMessage(text, type) {
  const el = $("#dash-form-message");
  el.textContent = text;
  el.className = `message visible ${type}`;
}

function clearFormMessage() {
  const el = $("#dash-form-message");
  el.textContent = "";
  el.className = "message";
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

function renderPatientDashboard(user) {
  $("#patient-view").classList.remove("hidden");
  $("#user-card").innerHTML = `
    <p class="name">${escapeHtml(user.full_name || "Patient")}</p>
    <p class="meta">Last name: ${escapeHtml(user.last_name || "—")}</p>
    <span class="role-badge">Patient</span>
  `;
}

function renderPatientsList(elders) {
  const list = $("#patients-list");
  const empty = $("#patients-empty");
  const formTitle = $("#dash-form-title");

  if (!elders.length) {
    empty.classList.remove("hidden");
    list.innerHTML = "";
    if (formTitle) formTitle.textContent = "Add a patient";
    return;
  }

  empty.classList.add("hidden");
  if (formTitle) formTitle.textContent = "Add another patient";

  list.innerHTML = elders
    .map(
      (p) => `
    <article class="patient-card">
      <div class="patient-card-main">
        <h3>${escapeHtml(p.full_name || "Patient")}</h3>
        <p class="patient-meta">
          Last name: <strong>${escapeHtml(p.last_name || "—")}</strong>
        </p>
      </div>
      <div class="patient-stats">
        <span class="stat">${p.active_medication_count ?? 0} meds</span>
        <span class="stat ${p.last_checkin_at ? "stat-ok" : "stat-warn"}">
          ${p.last_checkin_at ? "Checked in recently" : "No check-in yet"}
        </span>
      </div>
    </article>
  `
    )
    .join("");
}

async function loadPatients() {
  const elders = await apiRequest("/relationships/my-elders");
  if (!elders) return;
  renderPatientsList(elders);
  return elders;
}

function resetProvisionForm() {
  const form = $("#form-provision-patient");
  form.reset();
  $("#dash-login-code").value = generateLoginCode();
  form.querySelector('[name="full_name"]')?.focus();
}

async function init() {
  const session = getSession();
  if (!session?.access_token || !session.user) {
    window.location.href = "index.html";
    return;
  }

  const user = session.user;
  const isCaregiver = user.role === "caregiver";

  $("#btn-scroll-add").classList.toggle("hidden", !isCaregiver);

  if (!isCaregiver) {
    renderPatientDashboard(user);
    return;
  }

  $("#caregiver-view").classList.remove("hidden");
  $("#dash-login-code").value = generateLoginCode();

  try {
    await loadPatients();
  } catch (err) {
    const msg = $("#dash-message");
    msg.textContent = err.message;
    msg.className = "message visible error";
  }
}

$("#btn-generate-code").addEventListener("click", () => {
  $("#dash-login-code").value = generateLoginCode();
});

$("#form-provision-patient").addEventListener("submit", async (e) => {
  e.preventDefault();
  clearFormMessage();
  const btn = $("#btn-submit-patient");
  btn.disabled = true;

  try {
    const body = formToObject(e.target);
    await apiRequest("/patients/provision", {
      method: "POST",
      body: JSON.stringify(body),
    });

    await loadPatients();
    showFormMessage(
      `${body.full_name} added. Share last name "${body.last_name}" and code "${body.login_code}" with them.`,
      "success"
    );
    resetProvisionForm();
  } catch (err) {
    showFormMessage(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

$("#btn-scroll-add").addEventListener("click", () => {
  $("#add-patient-section").scrollIntoView({ behavior: "smooth" });
  $("#form-provision-patient").querySelector('[name="full_name"]')?.focus();
});

$("#btn-logout").addEventListener("click", () => {
  clearSession();
  window.location.href = "index.html";
});

init();
