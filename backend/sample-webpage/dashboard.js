const PROFILE_FIELDS = [
  { key: "date_of_birth", label: "Date of birth" },
  { key: "address", label: "Address" },
  { key: "phone", label: "Phone" },
  { key: "notes", label: "Care notes" },
];

function setHomeLoading(isLoading) {
  $("#home-loading")?.classList.toggle("hidden", !isLoading);
  $("#home-content")?.classList.toggle("hidden", isLoading);
  const loadingEl = $("#home-loading");
  if (loadingEl) {
    loadingEl.setAttribute("aria-busy", isLoading ? "true" : "false");
  }
}

function formatCheckin(lastCheckinAt) {
  if (!lastCheckinAt) {
    return { label: "No check-in yet", className: "stat-warn" };
  }
  return { label: "Checked in recently", className: "stat-ok" };
}

function getMissingProfileFields(patient) {
  return PROFILE_FIELDS.filter((field) => !patient[field.key]?.toString().trim());
}

function needsAttention(patient) {
  const missing = getMissingProfileFields(patient);
  const noMeds = (patient.active_medication_count ?? 0) === 0;
  const noCheckin = !patient.last_checkin_at;
  return missing.length > 0 || noMeds || noCheckin;
}

function patientDetailUrl(patientId, section) {
  const base = `patient-detail.html?id=${encodeURIComponent(patientId)}`;
  return section ? `${base}#${section}` : base;
}

function renderOverviewStats(elders) {
  const totalMeds = elders.reduce((sum, p) => sum + (p.active_medication_count ?? 0), 0);
  const attention = elders.filter(needsAttention).length;

  const patientsEl = $("#stat-patients");
  const medsEl = $("#stat-meds");
  const attentionEl = $("#stat-attention");

  if (patientsEl) patientsEl.textContent = String(elders.length);
  if (medsEl) medsEl.textContent = String(totalMeds);
  if (attentionEl) attentionEl.textContent = String(attention);
}

function renderCompleteProfilesSection(elders) {
  const section = $("#home-complete-section");
  const list = $("#home-complete-list");
  if (!section || !list) return;

  const incomplete = elders
    .map((patient) => ({
      patient,
      missing: getMissingProfileFields(patient),
      noMeds: (patient.active_medication_count ?? 0) === 0,
    }))
    .filter(({ missing, noMeds }) => missing.length > 0 || noMeds);

  if (!incomplete.length) {
    section.classList.add("hidden");
    list.innerHTML = "";
    return;
  }

  section.classList.remove("hidden");
  list.innerHTML = incomplete
    .map(({ patient, missing, noMeds }) => {
      const gaps = [
        ...missing.map((field) => field.label),
        ...(noMeds ? ["Medications"] : []),
      ];
      const pct = Math.round(
        ((PROFILE_FIELDS.length + 1 - gaps.length) / (PROFILE_FIELDS.length + 1)) * 100
      );

      return `
        <li class="home-complete-item">
          <div class="home-complete-main">
            <strong>${escapeHtml(patient.full_name || "Patient")}</strong>
            <span class="home-complete-gap">Missing: ${escapeHtml(gaps.join(", "))}</span>
            <div class="home-complete-bar" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100">
              <span class="home-complete-bar-fill" style="width: ${pct}%"></span>
            </div>
          </div>
          <div class="home-complete-actions">
            <a href="${patientDetailUrl(patient.elder_id, "profile")}" class="btn-secondary btn-sm">Edit profile</a>
            ${noMeds ? `<a href="${patientDetailUrl(patient.elder_id, "medications")}" class="btn-secondary btn-sm">Add meds</a>` : ""}
          </div>
        </li>
      `;
    })
    .join("");
}

function renderHomePatientList(elders) {
  const list = $("#patients-home-list");
  const empty = $("#patients-empty");

  renderOverviewStats(elders);
  renderCompleteProfilesSection(elders);

  const medsAction = $("#home-action-meds");
  if (medsAction && elders.length) {
    medsAction.href = patientDetailUrl(elders[0].elder_id, "medications");
  }

  if (!elders.length) {
    empty?.classList.remove("hidden");
    if (list) list.innerHTML = "";
    return;
  }

  empty?.classList.add("hidden");
  if (!list) return;

  list.innerHTML = elders
    .map((p) => {
      const checkin = formatCheckin(p.last_checkin_at);
      const missing = getMissingProfileFields(p);
      const detailUrl = patientDetailUrl(p.elder_id);

      return `
    <li class="patient-home-card">
      <a href="${detailUrl}" class="patient-home-link-main">
        <div class="patient-home-avatar" aria-hidden="true">${escapeHtml((p.full_name || "P").charAt(0).toUpperCase())}</div>
        <div class="patient-home-info">
          <strong>${escapeHtml(p.full_name || "Patient")}</strong>
          <span class="patient-home-meta">
            Last name: ${escapeHtml(p.last_name || "—")}
            · Code: <code class="inline-code">${escapeHtml(p.login_code || "—")}</code>
          </span>
          ${
            missing.length
              ? `<span class="patient-home-missing">${escapeHtml(missing.map((f) => f.label).join(" · "))} not set</span>`
              : `<span class="patient-home-complete">Profile complete</span>`
          }
        </div>
      </a>
      <div class="patient-home-side">
        <div class="patient-home-badges">
          <span class="stat">${p.active_medication_count ?? 0} meds</span>
          <span class="stat ${checkin.className}">${checkin.label}</span>
        </div>
        <div class="patient-home-quick">
          <a href="${patientDetailUrl(p.elder_id, "profile")}" class="patient-home-quick-link">Profile</a>
          <a href="${patientDetailUrl(p.elder_id, "medications")}" class="patient-home-quick-link">Meds</a>
          <a href="${detailUrl}" class="patient-home-quick-link patient-home-quick-link-primary">Details</a>
        </div>
      </div>
    </li>
  `;
    })
    .join("");
}

async function enrichPatientDetails(elders) {
  const results = await Promise.allSettled(
    elders.map(async (elder) => {
      const detail = await apiRequest(`/patients/${elder.elder_id}`);
      return detail ? { ...elder, ...detail, elder_id: elder.elder_id } : elder;
    })
  );

  return results.map((result, index) =>
    result.status === "fulfilled" ? result.value : elders[index]
  );
}

async function loadPatients() {
  const elders = await apiRequest("/relationships/my-elders");
  if (!elders) return [];

  if (!elders.length) {
    renderHomePatientList([]);
    return [];
  }

  const enriched = await enrichPatientDetails(elders);
  renderHomePatientList(enriched);
  return enriched;
}

async function init() {
  const session = getSession();
  if (!session?.access_token || !session.user) {
    window.location.href = "index.html";
    return;
  }

  if (session.user.role !== "caregiver") {
    bindLogout();
    renderPatientDashboard(session.user);
    return;
  }

  initCaregiverShell();
  $("#caregiver-view")?.classList.remove("hidden");
  setHomeLoading(true);

  try {
    await loadPatients();
  } catch (err) {
    const msg = $("#dash-message");
    if (msg) {
      msg.textContent = err.message;
      msg.className = "message visible error";
    }
  } finally {
    setHomeLoading(false);
  }
}

init();
