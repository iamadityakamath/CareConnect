const params = new URLSearchParams(window.location.search);
const patientId = params.get("id");

let patient = null;
let medicationPresets = window.MEDICATION_PRESETS || [];
let historyPresets = window.MEDICAL_HISTORY_PRESETS || [];
let contactPresets = window.CONTACT_PRESETS || [];

function showPageMessage(text, type) {
  const el = $("#page-message");
  if (!el) return;
  el.textContent = text;
  el.className = `message visible ${type}`;
}

function clearPageMessage() {
  const el = $("#page-message");
  if (!el) return;
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

function formatDate(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return value;
  }
}

function formatDateTime(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

function moodLabel(score) {
  const labels = ["", "Very low", "Low", "Okay", "Good", "Great"];
  return labels[score] || `Mood ${score}`;
}

function renderHeader() {
  $("#patient-name").textContent = patient.full_name || "Patient";
  $("#patient-subtitle").textContent = `Last name for login: ${patient.last_name || "—"}`;

  $("#patient-badges").innerHTML = `
    <span class="stat">Code: <code class="patient-code">${escapeHtml(patient.login_code || "—")}</code></span>
    <span class="stat ${patient.account_status === "active" ? "stat-ok" : ""}">${escapeHtml(patient.account_status || "managed")}</span>
  `;
}

function renderProfileView() {
  const grid = $("#profile-view");
  if (!grid) return;
  const rows = [
    ["Phone", patient.phone],
    ["Date of birth", patient.date_of_birth ? formatDate(patient.date_of_birth) : null],
    ["Address", patient.address],
    ["Timezone", patient.timezone],
    ["Care notes", patient.notes],
  ];
  grid.innerHTML = rows
    .map(
      ([label, value]) => `
    <div class="detail-item">
      <span class="detail-label">${escapeHtml(label)}</span>
      <span class="detail-value">${escapeHtml(value || "—")}</span>
    </div>
  `
    )
    .join("");
}

function fillProfileForm() {
  const form = $("#form-profile");
  if (!form) return;
  form.full_name.value = patient.full_name || "";
  form.last_name.value = patient.last_name || "";
  form.phone.value = patient.phone || "";
  form.date_of_birth.value = patient.date_of_birth ? patient.date_of_birth.slice(0, 10) : "";
  form.address.value = patient.address || "";
  form.timezone.value = patient.timezone || "";
  form.notes.value = patient.notes || "";
}

const DEFAULT_DOSE_TIMES = {
  1: ["08:00"],
  2: ["08:00", "20:00"],
  3: ["08:00", "14:00", "20:00"],
  4: ["08:00", "12:00", "17:00", "21:00"],
  5: ["07:00", "11:00", "15:00", "19:00", "21:00"],
  6: ["07:00", "10:00", "13:00", "16:00", "19:00", "21:00"],
};

const FREQUENCY_BY_COUNT = {
  1: "Once daily",
  2: "Twice daily",
  3: "Three times daily",
  4: "Four times daily",
  5: "Five times daily",
  6: "Six times daily",
};

function getCurrentMedTimes() {
  return Array.from(document.querySelectorAll(".med-time-input"))
    .map((input) => input.value)
    .filter(Boolean);
}

function getCurrentDoseInstructions() {
  return Array.from(document.querySelectorAll(".med-dose-instruction-input")).map((input) =>
    input.value.trim() || null
  );
}

function renderMedTimeInputs(count, values = [], instructionValues = []) {
  const container = $("#med-time-inputs");
  const countSelect = $("#med-times-count");
  if (!container) return;

  const num = Math.min(Math.max(Number(count) || 1, 1), 6);
  if (countSelect) countSelect.value = String(num);

  const defaults = DEFAULT_DOSE_TIMES[num] || DEFAULT_DOSE_TIMES[1];
  const times = Array.from({ length: num }, (_, i) => values[i] || defaults[i] || "08:00");
  const instructions = Array.from({ length: num }, (_, i) => instructionValues[i] || "");

  container.innerHTML = times
    .map(
      (time, index) => `
    <div class="med-dose-row">
      <label class="med-time-label">
        Dose ${index + 1} time
        <input type="time" class="med-time-input" value="${escapeHtml(time)}" required />
      </label>
      <label class="med-instruction-label">
        Instruction
        <input
          type="text"
          class="med-dose-instruction-input"
          value="${escapeHtml(instructions[index])}"
          placeholder="e.g. Take with food"
        />
      </label>
    </div>
  `
    )
    .join("");
}

function setMedTimesCount(count, values = [], instructionValues = [], updateFrequency = false) {
  renderMedTimeInputs(count, values, instructionValues);
  if (updateFrequency) {
    const form = $("#form-medication");
    const num = Math.min(Math.max(Number(count) || 1, 1), 6);
    if (form?.frequency) {
      form.frequency.value = FREQUENCY_BY_COUNT[num] || "Daily";
    }
  }
}

function presetDoseInstructions(preset, count) {
  if (preset.dose_instructions?.length) {
    return preset.dose_instructions;
  }
  if (preset.instructions) {
    return Array.from({ length: count }, () => preset.instructions);
  }
  return [];
}

function fillMedicationForm(preset) {
  const form = $("#form-medication");
  if (!form || !preset) return;
  form.name.value = preset.name || "";
  form.dosage.value = preset.dosage || "";
  form.frequency.value = preset.frequency || "";
  const times = preset.scheduled_times || [];
  const count = times.length || 1;
  setMedTimesCount(count, times, presetDoseInstructions(preset, count), false);
}

function clearMedicationForm() {
  const form = $("#form-medication");
  if (!form) return;
  form.name.value = "";
  form.dosage.value = "";
  form.frequency.value = "";
  setMedTimesCount(1, [], [], true);
}

function initMedicationTimeInputs() {
  const countSelect = $("#med-times-count");
  countSelect?.addEventListener("change", () => {
    const existing = getCurrentMedTimes();
    const existingInstructions = getCurrentDoseInstructions();
    setMedTimesCount(countSelect.value, existing, existingInstructions, true);
  });
  setMedTimesCount(1, [], [], true);
}

function initMedicationPresets() {
  const list = $("#med-preset-list");
  if (!list) return;

  medicationPresets.forEach((preset) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "med-preset-chip";
    btn.dataset.presetId = preset.id;
    btn.innerHTML = `
      <span class="med-preset-chip-name">${escapeHtml(preset.name)}</span>
      <span class="med-preset-chip-meta">${escapeHtml(preset.dosage)} · ${escapeHtml(preset.frequency)}</span>
    `;
    btn.addEventListener("click", () => {
      fillMedicationForm(preset);
      list.querySelectorAll(".med-preset-chip").forEach((el) => el.classList.remove("selected"));
      btn.classList.add("selected");
    });
    list.appendChild(btn);
  });
}

const HISTORY_CATEGORY_LABELS = {
  condition: "Condition",
  allergy: "Allergy",
  surgery: "Surgery",
  note: "Note",
};

function fillHistoryForm(preset) {
  const form = $("#form-history");
  if (!form || !preset) return;
  form.category.value = preset.category || "condition";
  form.title.value = preset.title || "";
  form.description.value = preset.description || "";
}

function clearHistoryFormSelection() {
  $("#history-preset-list")?.querySelectorAll(".med-preset-chip").forEach((el) => {
    el.classList.remove("selected");
  });
}

function initHistoryPresets() {
  const list = $("#history-preset-list");
  if (!list) return;

  historyPresets.forEach((preset) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "med-preset-chip";
    btn.dataset.presetId = preset.id;
    const categoryLabel = HISTORY_CATEGORY_LABELS[preset.category] || preset.category;
    btn.innerHTML = `
      <span class="med-preset-chip-name">${escapeHtml(preset.title)}</span>
      <span class="med-preset-chip-meta">${escapeHtml(categoryLabel)}</span>
    `;
    btn.addEventListener("click", () => {
      fillHistoryForm(preset);
      list.querySelectorAll(".med-preset-chip").forEach((el) => el.classList.remove("selected"));
      btn.classList.add("selected");
    });
    list.appendChild(btn);
  });
}

const CONTACT_TYPE_LABELS = {
  doctor: "Doctor",
  hospital: "Hospital",
  pharmacy: "Pharmacy",
  emergency: "Emergency",
};

function fillContactForm(preset) {
  const form = $("#form-contact");
  if (!form || !preset) return;
  form.name.value = preset.name || "";
  form.contact_type.value = preset.contact_type || "doctor";
  form.phone.value = preset.phone || "";
  form.specialty.value = preset.specialty || "";
  form.address.value = preset.address || "";
  form.is_primary.checked = Boolean(preset.is_primary);
}

function clearContactFormSelection() {
  $("#contact-preset-list")?.querySelectorAll(".med-preset-chip").forEach((el) => {
    el.classList.remove("selected");
  });
}

function initContactPresets() {
  const list = $("#contact-preset-list");
  if (!list) return;

  contactPresets.forEach((preset) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "med-preset-chip";
    btn.dataset.presetId = preset.id;
    const typeLabel = CONTACT_TYPE_LABELS[preset.contact_type] || preset.contact_type;
    btn.innerHTML = `
      <span class="med-preset-chip-name">${escapeHtml(preset.name)}</span>
      <span class="med-preset-chip-meta">${escapeHtml(typeLabel)}${preset.specialty ? ` · ${escapeHtml(preset.specialty)}` : ""}</span>
    `;
    btn.addEventListener("click", () => {
      fillContactForm(preset);
      list.querySelectorAll(".med-preset-chip").forEach((el) => el.classList.remove("selected"));
      btn.classList.add("selected");
    });
    list.appendChild(btn);
  });
}

function renderMedications(meds) {
  const list = $("#med-list");
  const empty = $("#med-empty");
  if (!meds.length) {
    list.innerHTML = "";
    empty?.classList.remove("hidden");
    return;
  }
  empty?.classList.add("hidden");
  list.innerHTML = meds
    .map(
      (m) => {
        const times = m.scheduled_times || [];
        const doseInstructions = m.dose_instructions || [];
        const scheduleLines = times.map((time, index) => {
          const instruction = doseInstructions[index] || "";
          return instruction ? `${time} — ${instruction}` : time;
        });

        return `
    <li class="detail-list-item">
      <div>
        <strong>${escapeHtml(m.name)}</strong>
        <span class="detail-meta">${escapeHtml(m.dosage || m.dosage_text || "")} · ${escapeHtml(m.frequency || "—")}</span>
        ${scheduleLines.length ? `<span class="detail-meta">${scheduleLines.map((line) => escapeHtml(line)).join(" · ")}</span>` : ""}
      </div>
    </li>
  `;
      }
    )
    .join("");
}

function renderHistory(entries) {
  const list = $("#history-list");
  const empty = $("#history-empty");
  if (!entries.length) {
    list.innerHTML = "";
    empty?.classList.remove("hidden");
    return;
  }
  empty?.classList.add("hidden");
  list.innerHTML = entries
    .map(
      (e) => `
    <li class="detail-list-item">
      <div>
        <strong>${escapeHtml(e.title)}</strong>
        <span class="detail-tag">${escapeHtml(HISTORY_CATEGORY_LABELS[e.category] || e.category)}</span>
        ${e.description ? `<span class="detail-meta">${escapeHtml(e.description)}</span>` : ""}
        ${e.date_occurred ? `<span class="detail-meta">${formatDate(e.date_occurred)}</span>` : ""}
      </div>
    </li>
  `
    )
    .join("");
}

function renderContacts(contacts) {
  const list = $("#contact-list");
  const empty = $("#contact-empty");
  if (!contacts.length) {
    list.innerHTML = "";
    empty?.classList.remove("hidden");
    return;
  }
  empty?.classList.add("hidden");
  list.innerHTML = contacts
    .map(
      (c) => `
    <li class="detail-list-item">
      <div>
        <strong>${escapeHtml(c.name)}</strong>
        <span class="detail-tag">${escapeHtml(CONTACT_TYPE_LABELS[c.contact_type] || c.contact_type)}${c.is_primary ? " · primary" : ""}</span>
        <span class="detail-meta">${escapeHtml(c.phone)}${c.specialty ? ` · ${escapeHtml(c.specialty)}` : ""}</span>
        ${c.address ? `<span class="detail-meta">${escapeHtml(c.address)}</span>` : ""}
      </div>
    </li>
  `
    )
    .join("");
}

function renderCheckins(status, checkins) {
  const statusEl = $("#checkin-status");
  if (statusEl) {
    if (status?.last_checkin_at) {
      statusEl.textContent = `Last check-in: ${formatDateTime(status.last_checkin_at)}${
        status.needs_attention ? " · needs attention" : ""
      }`;
      statusEl.className = `checkin-status-line ${status.needs_attention ? "warn" : "ok"}`;
    } else {
      statusEl.textContent = "No check-ins recorded yet.";
      statusEl.className = "checkin-status-line warn";
    }
  }

  const list = $("#checkin-list");
  const empty = $("#checkin-empty");
  if (!checkins.length) {
    list.innerHTML = "";
    empty?.classList.remove("hidden");
    return;
  }
  empty?.classList.add("hidden");
  list.innerHTML = checkins
    .map(
      (c) => `
    <li class="detail-list-item">
      <div>
        <strong>${escapeHtml(moodLabel(c.mood_score))}</strong>
        <span class="detail-meta">${formatDateTime(c.created_at)}</span>
        ${c.note ? `<span class="detail-meta">${escapeHtml(c.note)}</span>` : ""}
      </div>
    </li>
  `
    )
    .join("");
}

async function loadPatient() {
  patient = await apiRequest(`/patients/${patientId}`);
  renderHeader();
  renderProfileView();
  fillProfileForm();
}

async function loadSections() {
  const [meds, history, contacts, checkinStatus, checkins] = await Promise.all([
    apiRequest(`/medications/${patientId}`).catch(() => []),
    apiRequest(`/medical-history/${patientId}`).catch(() => []),
    apiRequest(`/contacts/${patientId}`).catch(() => []),
    apiRequest(`/checkins/${patientId}/status`).catch(() => null),
    apiRequest(`/checkins/${patientId}`).catch(() => []),
  ]);

  renderMedications(Array.isArray(meds) ? meds : []);
  renderHistory(Array.isArray(history) ? history : []);
  renderContacts(Array.isArray(contacts) ? contacts : []);
  renderCheckins(checkinStatus, Array.isArray(checkins) ? checkins : []);
}

async function init() {
  if (!(await initCaregiverShell())) return;

  if (!patientId) {
    showPageMessage("Missing patient id.", "error");
    return;
  }

  try {
    await loadPatient();
    initMedicationTimeInputs();
    initMedicationPresets();
    initHistoryPresets();
    initContactPresets();
    await loadSections();
    scrollToSectionHash();
  } catch (err) {
    showPageMessage(err.message, "error");
  }
}

function scrollToSectionHash() {
  const hash = window.location.hash?.replace("#", "");
  if (!hash) return;
  const section = document.getElementById(`section-${hash}`);
  if (section) {
    section.scrollIntoView({ behavior: "smooth", block: "start" });
    section.classList.add("detail-section-highlight");
    window.setTimeout(() => section.classList.remove("detail-section-highlight"), 1800);
  }
}

$("#btn-edit-profile")?.addEventListener("click", () => {
  $("#profile-view")?.classList.add("hidden");
  $("#form-profile")?.classList.remove("hidden");
});

$("#btn-cancel-profile")?.addEventListener("click", () => {
  fillProfileForm();
  $("#form-profile")?.classList.add("hidden");
  $("#profile-view")?.classList.remove("hidden");
});

$("#form-profile")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearPageMessage();
  try {
    const body = formToObject(e.target);
    patient = await apiRequest(`/users/${patientId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    const codeRow = await apiRequest("/relationships/my-elders");
    const match = (codeRow || []).find((p) => p.elder_id === patientId);
    if (match?.login_code) patient.login_code = match.login_code;

    renderHeader();
    renderProfileView();
    $("#form-profile")?.classList.add("hidden");
    $("#profile-view")?.classList.remove("hidden");
    showPageMessage("Profile updated.", "success");
  } catch (err) {
    showPageMessage(err.message, "error");
  }
});

$("#form-medication")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearPageMessage();
  try {
    const body = formToObject(e.target);
    const times = getCurrentMedTimes();
    const doseInstructions = getCurrentDoseInstructions();
    if (!times.length) {
      showPageMessage("Add at least one dose time.", "error");
      return;
    }
    await apiRequest("/medications", {
      method: "POST",
      body: JSON.stringify({
        elder_id: patientId,
        name: body.name,
        dosage: body.dosage,
        frequency: body.frequency,
        dose_instructions: doseInstructions,
        scheduled_times: times,
      }),
    });
    e.target.reset();
    $("#med-preset-list")?.querySelectorAll(".med-preset-chip").forEach((el) => {
      el.classList.remove("selected");
    });
    setMedTimesCount(1, [], [], true);
    const meds = await apiRequest(`/medications/${patientId}`);
    renderMedications(meds || []);
    showPageMessage("Medication added.", "success");
  } catch (err) {
    showPageMessage(err.message, "error");
  }
});

$("#form-history")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearPageMessage();
  try {
    const body = formToObject(e.target);
    await apiRequest("/medical-history", {
      method: "POST",
      body: JSON.stringify({ elder_id: patientId, ...body, is_active: true }),
    });
    e.target.reset();
    clearHistoryFormSelection();
    const history = await apiRequest(`/medical-history/${patientId}`);
    renderHistory(history || []);
    showPageMessage("Medical history entry added.", "success");
  } catch (err) {
    showPageMessage(err.message, "error");
  }
});

$("#form-contact")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearPageMessage();
  try {
    const raw = formToObject(e.target);
    raw.is_primary = e.target.is_primary.checked;
    await apiRequest("/contacts", {
      method: "POST",
      body: JSON.stringify({ elder_id: patientId, ...raw }),
    });
    e.target.reset();
    clearContactFormSelection();
    const contacts = await apiRequest(`/contacts/${patientId}`);
    renderContacts(contacts || []);
    showPageMessage("Contact added.", "success");
  } catch (err) {
    showPageMessage(err.message, "error");
  }
});

init();
