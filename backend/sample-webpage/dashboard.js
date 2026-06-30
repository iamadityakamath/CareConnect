const PROFILE_FIELDS = [
  { key: "date_of_birth", label: "Date of birth" },
  { key: "address", label: "Address" },
  { key: "phone", label: "Phone" },
  { key: "notes", label: "Care notes" },
];

const STATUS_LABELS = {
  overdue: { label: "Overdue", className: "cg-status-overdue" },
  in_progress: { label: "In progress", className: "cg-status-progress" },
  upcoming: { label: "Upcoming", className: "cg-status-upcoming" },
  complete: { label: "All done today", className: "cg-status-complete" },
  no_meds: { label: "No meds scheduled", className: "cg-status-none" },
};

function setHomeLoading(isLoading) {
  $("#home-loading")?.classList.toggle("hidden", !isLoading);
  $("#home-content")?.classList.toggle("hidden", isLoading);
  $("#home-loading")?.setAttribute("aria-busy", isLoading ? "true" : "false");
}

function patientDetailUrl(patientId, section) {
  const base = `patient-detail.html?id=${encodeURIComponent(patientId)}`;
  return section ? `${base}#${section}` : base;
}

function formatTime(isoString) {
  if (!isoString) return "—";
  try {
    return new Date(isoString).toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}

function formatShortDate(isoString) {
  try {
    return new Date(isoString).toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  } catch {
    return isoString;
  }
}

function getMissingProfileFields(patient) {
  return PROFILE_FIELDS.filter((field) => !patient[field.key]?.toString().trim());
}

function renderOverview(dashboard) {
  const { totals, overall_today_pct, overall_week_pct } = dashboard;

  $("#stat-today-pct").textContent = `${overall_today_pct}%`;
  $("#stat-today-sub").textContent =
    totals.doses_scheduled_today > 0
      ? `${totals.doses_taken_today} of ${totals.doses_scheduled_today} doses`
      : "No doses scheduled today";

  $("#stat-taken").textContent = String(totals.doses_taken_today);
  $("#stat-on-time-sub").textContent =
    totals.doses_late_today > 0
      ? `${totals.doses_on_time_today} on time · ${totals.doses_late_today} late`
      : `${totals.doses_on_time_today} on time`;

  const overdueTotal = totals.doses_overdue_today + totals.doses_missed_today;
  $("#stat-overdue").textContent = String(overdueTotal);
  $("#stat-attention-sub").textContent =
    totals.patients_need_attention > 0
      ? `${totals.patients_need_attention} patient${totals.patients_need_attention === 1 ? "" : "s"} need attention`
      : "All patients on track";

  $("#stat-week-pct").textContent = `${overall_week_pct}%`;

  const dateEl = $("#dash-date");
  if (dateEl) {
    dateEl.textContent = formatShortDate(dashboard.date);
  }
}

function renderChart(breakdown) {
  const chart = $("#adherence-chart");
  const empty = $("#chart-empty");
  if (!chart || !empty) return;

  if (!breakdown.length) {
    chart.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }

  empty.classList.add("hidden");
  const maxTotal = Math.max(...breakdown.map((d) => d.taken + d.missed), 1);

  chart.innerHTML = breakdown
    .map((day) => {
      const total = day.taken + day.missed;
      const takenPct = total ? (day.taken / maxTotal) * 100 : 0;
      const missedPct = total ? (day.missed / maxTotal) * 100 : 0;
      const dayLabel = new Date(day.date).toLocaleDateString(undefined, {
        weekday: "short",
      });

      return `
        <div class="adherence-chart-col">
          <div class="adherence-chart-bars" title="${day.taken} taken, ${day.missed} missed">
            <div class="adherence-bar adherence-bar-taken" style="height: ${takenPct}%"></div>
            <div class="adherence-bar adherence-bar-missed" style="height: ${missedPct}%"></div>
          </div>
          <span class="adherence-chart-label">${escapeHtml(dayLabel)}</span>
          <span class="adherence-chart-meta">${day.taken}/${total || 0}</span>
        </div>
      `;
    })
    .join("");
}

function renderAttentionList(patients) {
  const section = $("#cg-attention-section");
  const list = $("#cg-attention-list");
  if (!section || !list) return;

  const alerts = patients.flatMap((patient) =>
    (patient.overdue_doses || []).map((dose) => ({
      patient,
      dose,
    }))
  );

  if (!alerts.length) {
    section.classList.add("hidden");
    list.innerHTML = "";
    return;
  }

  section.classList.remove("hidden");
  list.innerHTML = alerts
    .map(
      ({ patient, dose }) => `
      <li class="cg-attention-item">
        <div class="cg-attention-main">
          <strong>${escapeHtml(patient.full_name || "Patient")}</strong>
          <span>${escapeHtml(dose.medication_name)} · ${escapeHtml(dose.dosage)}</span>
          <span class="cg-attention-time">Due ${escapeHtml(formatTime(dose.scheduled_for))} · ${escapeHtml(formatOverdueDuration(dose.minutes_overdue))} overdue</span>
        </div>
        <a href="${patientDetailUrl(patient.elder_id, "medications")}" class="btn-secondary btn-sm">View</a>
      </li>
    `
    )
    .join("");
}

function renderPatientAdherenceCards(patients, elderMeta = {}) {
  const container = $("#cg-patient-cards");
  const empty = $("#patients-empty");
  if (!container || !empty) return;

  if (!patients.length) {
    container.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }

  empty.classList.add("hidden");
  container.innerHTML = patients
    .map((patient) => {
      const meta = elderMeta[patient.elder_id] || {};
      const status = STATUS_LABELS[patient.status] || STATUS_LABELS.upcoming;
      const pct = patient.adherence_today_pct ?? 0;
      const detailUrl = patientDetailUrl(patient.elder_id);

      const metrics = [
        { label: "Taken", value: patient.today_taken, tone: "ok" },
        { label: "On time", value: patient.today_on_time, tone: "ok" },
        { label: "Pending", value: patient.today_pending, tone: "pending" },
        { label: "Overdue", value: patient.today_overdue + patient.today_missed, tone: "warn" },
      ];

      return `
        <article class="cg-patient-card ${status.className}">
          <header class="cg-patient-card-header">
            <div class="cg-patient-identity">
              <div class="patient-home-avatar" aria-hidden="true">${escapeHtml((patient.full_name || "P").charAt(0).toUpperCase())}</div>
              <div>
                <h4>${escapeHtml(patient.full_name || "Patient")}</h4>
                <span class="cg-patient-meta">${escapeHtml(patient.last_name || "—")}${meta.login_code ? ` · Code <code class="inline-code">${escapeHtml(meta.login_code)}</code>` : ""}</span>
              </div>
            </div>
            <span class="cg-status-badge ${status.className}">${status.label}</span>
          </header>

          <div class="cg-patient-progress">
            <div class="cg-progress-ring" style="--pct: ${pct}">
              <span class="cg-progress-value">${pct}%</span>
            </div>
            <div class="cg-patient-progress-detail">
              <p class="cg-progress-title">Today: ${patient.today_taken} of ${patient.today_scheduled} doses</p>
              <p class="cg-progress-sub">
                ${patient.next_dose_at ? `Next dose ${escapeHtml(formatTime(patient.next_dose_at))}` : patient.status === "complete" ? "All doses taken today" : "—"}
                ${patient.last_taken_at ? ` · Last taken ${escapeHtml(formatTime(patient.last_taken_at))}` : ""}
              </p>
              <p class="cg-progress-week">7-day: ${patient.week_adherence_pct}% (${patient.week_taken} taken, ${patient.week_missed} missed)</p>
            </div>
          </div>

          <div class="cg-patient-metrics">
            ${metrics
              .map(
                (m) => `
              <div class="cg-metric cg-metric-${m.tone}">
                <span class="cg-metric-value">${m.value}</span>
                <span class="cg-metric-label">${m.label}</span>
              </div>
            `
              )
              .join("")}
          </div>

          <footer class="cg-patient-card-footer">
            <a href="${detailUrl}" class="patient-home-quick-link patient-home-quick-link-primary">Full details</a>
            <a href="${patientDetailUrl(patient.elder_id, "medications")}" class="patient-home-quick-link">Medications</a>
          </footer>
        </article>
      `;
    })
    .join("");
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
    .map(
      ({ patient, missing, noMeds }) => `
      <li class="home-complete-item">
        <div class="home-complete-main">
          <strong>${escapeHtml(patient.full_name || "Patient")}</strong>
          <span class="home-complete-gap">Missing: ${escapeHtml([...missing.map((f) => f.label), ...(noMeds ? ["Medications"] : [])].join(", "))}</span>
        </div>
        <a href="${patientDetailUrl(patient.elder_id, "profile")}" class="btn-secondary btn-sm">Complete</a>
      </li>
    `
    )
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

function elderMetaMap(elders) {
  return Object.fromEntries(
    elders.map((e) => [
      e.elder_id,
      { login_code: e.login_code, active_medication_count: e.active_medication_count },
    ])
  );
}

function renderDashboard(dashboard, elders) {
  renderOverview(dashboard);
  renderChart(dashboard.daily_breakdown || []);
  renderAttentionList(dashboard.patients || []);
  renderPatientAdherenceCards(dashboard.patients || [], elderMetaMap(elders));
  renderCompleteProfilesSection(elders);

  const medsAction = $("#home-action-meds");
  if (medsAction && dashboard.patients?.length) {
    medsAction.href = patientDetailUrl(dashboard.patients[0].elder_id, "medications");
  }
}

async function loadDashboard() {
  const [dashboard, elders] = await Promise.all([
    apiRequest("/relationships/adherence-dashboard"),
    apiRequest("/relationships/my-elders"),
  ]);

  if (!dashboard || !elders) return;

  let enriched = elders;
  if (elders.length) {
    enriched = await enrichPatientDetails(elders);
  }

  renderDashboard(dashboard, enriched);
}

async function init() {
  const session = await initCaregiverShell();
  if (!session) return;

  $("#caregiver-view")?.classList.remove("hidden");
  setHomeLoading(true);

  try {
    await loadDashboard();
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
