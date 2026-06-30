function formatCheckin(status, timestamp) {
  if (!timestamp) {
    return { label: "No check-in yet", className: "stat-warn" };
  }
  return { label: "Checked in recently", className: "stat-ok" };
}

function renderPatientsList(elders) {
  const list = $("#patients-list");
  const empty = $("#patients-empty");

  if (!elders.length) {
    empty?.classList.remove("hidden");
    if (list) list.innerHTML = "";
    return;
  }

  empty?.classList.add("hidden");
  if (!list) return;

  list.innerHTML = elders
    .map((p) => {
      const checkin = formatCheckin(p.last_checkin_at, p.last_checkin_at);
      return `
    <article class="patient-card">
      <div class="patient-card-main">
        <h3>${escapeHtml(p.full_name || "Patient")}</h3>
        <p class="patient-meta">
          Last name: <strong>${escapeHtml(p.last_name || "—")}</strong>
        </p>
        <p class="patient-code-row">
          Login code: <code class="patient-code">${escapeHtml(p.login_code || "Not saved")}</code>
        </p>
        <a href="patient-detail.html?id=${encodeURIComponent(p.elder_id)}" class="patient-detail-link">View full details →</a>
      </div>
      <div class="patient-stats">
        <span class="stat">${p.active_medication_count ?? 0} meds</span>
        <span class="stat ${checkin.className}">${checkin.label}</span>
      </div>
    </article>
  `;
    })
    .join("");
}

async function loadPatients() {
  const elders = await apiRequest("/relationships/my-elders");
  if (!elders) return;
  renderPatientsList(elders);
  return elders;
}

async function init() {
  if (!(await initCaregiverShell())) return;

  try {
    await loadPatients();
  } catch (err) {
    const msg = $("#page-message");
    if (msg) {
      msg.textContent = err.message;
      msg.className = "message visible error";
    }
  }
}

init();
