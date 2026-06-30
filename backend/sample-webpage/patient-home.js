const PERIODS = [
  { id: "morning", label: "Morning", hint: "Before noon", icon: "🌅" },
  { id: "afternoon", label: "Afternoon", hint: "Noon – 5 PM", icon: "☀️" },
  { id: "night", label: "Night", hint: "After 5 PM", icon: "🌙" },
];

let todayDoses = [];
let confirmingId = null;
let shouldScrollOnRender = false;

function setPatientLoading(isLoading) {
  $("#patient-loading")?.classList.toggle("hidden", !isLoading);
  $("#patient-content")?.classList.toggle("hidden", isLoading);
  $("#patient-loading")?.setAttribute("aria-busy", isLoading ? "true" : "false");
}

function formatTime(isoString) {
  try {
    return new Date(isoString).toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
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

function formatTodayDate() {
  return new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function showPatientMessage(text, type) {
  const el = $("#patient-message");
  if (!el) return;
  el.textContent = text;
  el.className = `message patient-toast visible ${type}`;
  window.clearTimeout(showPatientMessage._timer);
  showPatientMessage._timer = window.setTimeout(() => {
    el.className = "message patient-toast";
  }, 3200);
}

function updateSummary(doses) {
  const taken = doses.filter((d) => d.status === "taken").length;
  const left = doses.filter((d) => d.status === "pending").length;
  const takenEl = $("#summary-taken");
  const leftEl = $("#summary-left");
  if (takenEl) takenEl.textContent = String(taken);
  if (leftEl) leftEl.textContent = String(left);
}

function doseKey(dose) {
  return `${dose.medication_id}:${dose.scheduled_for}`;
}

function getPeriodFromHour(hour) {
  if (hour < 12) return "morning";
  if (hour < 17) return "afternoon";
  return "night";
}

function getPeriodFromDose(dose) {
  return getPeriodFromHour(new Date(dose.scheduled_for).getHours());
}

function getCurrentPeriod() {
  return getPeriodFromHour(new Date().getHours());
}

function groupDosesByPeriod(doses) {
  const grouped = { morning: [], afternoon: [], night: [] };
  for (const dose of doses) {
    grouped[getPeriodFromDose(dose)].push(dose);
  }
  for (const period of PERIODS) {
    grouped[period.id].sort((a, b) => a.scheduled_for.localeCompare(b.scheduled_for));
  }
  return grouped;
}

function isPeriodComplete(doses) {
  return doses.length > 0 && doses.every((d) => d.status === "taken");
}

function periodProgress(doses) {
  const taken = doses.filter((d) => d.status === "taken").length;
  return { taken, total: doses.length };
}

function getScrollTargetPeriod(grouped) {
  const current = getCurrentPeriod();
  const currentIndex = PERIODS.findIndex((p) => p.id === current);

  for (let offset = 0; offset < PERIODS.length; offset += 1) {
    const period = PERIODS[(currentIndex + offset) % PERIODS.length];
    const doses = grouped[period.id];
    if (doses.length && doses.some((d) => d.status === "pending")) {
      return period.id;
    }
  }

  for (const period of PERIODS) {
    if (grouped[period.id].length) {
      return period.id;
    }
  }

  return current;
}

function scrollToPeriod(periodId, { smooth = true } = {}) {
  const section = document.getElementById(`period-${periodId}`);
  if (!section) return;

  section.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
  updatePeriodNav(periodId);
}

function updatePeriodNav(activePeriod) {
  const nav = $("#period-nav");
  if (!nav) return;

  nav.querySelectorAll(".period-nav-btn").forEach((btn) => {
    const isActive = btn.dataset.period === activePeriod;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-current", isActive ? "true" : "false");
  });
}

function renderDoseCard(dose) {
  const isTaken = dose.status === "taken";
  const isConfirming = confirmingId === doseKey(dose);
  const timeLabel = formatTime(dose.scheduled_for);
  const overdue =
    !isTaken && dose.minutes_overdue > 0
      ? `<p class="dose-overdue">Overdue by ${escapeHtml(formatOverdueDuration(dose.minutes_overdue))}</p>`
      : "";

  return `
    <li class="dose-card ${isTaken ? "dose-card-taken" : "dose-card-pending"}" data-key="${escapeHtml(doseKey(dose))}">
      <div class="dose-card-main">
        <p class="dose-time">${escapeHtml(timeLabel)}</p>
        <h3 class="dose-name">${escapeHtml(dose.medication_name)}</h3>
        <p class="dose-dosage">${escapeHtml(dose.dosage)}</p>
        ${
          dose.instructions
            ? `<p class="dose-instructions">${escapeHtml(dose.instructions)}</p>`
            : ""
        }
        ${overdue}
      </div>
      ${
        isTaken
          ? `<div class="dose-taken-badge" aria-label="Taken">
               <span class="dose-check" aria-hidden="true">✓</span>
               <span>Taken${dose.taken_at ? ` at ${escapeHtml(formatTime(dose.taken_at))}` : ""}</span>
             </div>`
          : `<button
               type="button"
               class="dose-take-btn"
               data-medication-id="${escapeHtml(dose.medication_id)}"
               data-scheduled-for="${escapeHtml(dose.scheduled_for)}"
               ${isConfirming ? "disabled" : ""}
             >
               ${isConfirming ? "Saving…" : "I took this"}
             </button>`
      }
    </li>
  `;
}

function renderPeriodSection(period, doses, activePeriod) {
  if (!doses.length) {
    return "";
  }

  const { taken, total } = periodProgress(doses);
  const complete = isPeriodComplete(doses);
  const isActive = period.id === activePeriod;

  return `
    <section
      id="period-${period.id}"
      class="dose-period ${isActive ? "dose-period-active" : ""} ${complete ? "dose-period-complete" : ""}"
      aria-label="${escapeHtml(period.label)} medications"
    >
      <header class="dose-period-header">
        <div class="dose-period-title-row">
          <span class="dose-period-icon" aria-hidden="true">${period.icon}</span>
          <div>
            <h2 class="dose-period-title">${escapeHtml(period.label)}</h2>
            <p class="dose-period-hint">${escapeHtml(period.hint)}</p>
          </div>
        </div>
        <span class="dose-period-badge ${complete ? "dose-period-badge-done" : ""}">
          ${complete ? "All done" : `${taken} of ${total}`}
        </span>
      </header>
      <ul class="dose-list">
        ${doses.map(renderDoseCard).join("")}
      </ul>
    </section>
  `;
}

function renderDoses(doses) {
  todayDoses = doses;
  updateSummary(doses);

  const container = $("#dose-periods");
  const empty = $("#dose-empty");
  const nav = $("#period-nav");
  if (!container || !empty) return;

  if (!doses.length) {
    container.innerHTML = "";
    empty.classList.remove("hidden");
    nav?.classList.add("hidden");
    return;
  }

  empty.classList.add("hidden");
  nav?.classList.remove("hidden");

  const grouped = groupDosesByPeriod(doses);
  const scrollTarget = getScrollTargetPeriod(grouped);

  container.innerHTML = PERIODS.map((period) =>
    renderPeriodSection(period, grouped[period.id], scrollTarget)
  ).join("");

  container.querySelectorAll(".dose-take-btn").forEach((btn) => {
    btn.addEventListener("click", () => confirmDose(btn));
  });

  updatePeriodNav(scrollTarget);

  if (shouldScrollOnRender) {
    shouldScrollOnRender = false;
    window.requestAnimationFrame(() => {
      scrollToPeriod(scrollTarget, { smooth: true });
    });
  }
}

async function loadTodayDoses(patientId, { scroll = false } = {}) {
  shouldScrollOnRender = scroll;
  const doses = await apiRequest(`/medications/${patientId}/today`);
  renderDoses(Array.isArray(doses) ? doses : []);
}

async function confirmDose(button) {
  const medicationId = button.dataset.medicationId;
  const scheduledFor = button.dataset.scheduledFor;
  if (!medicationId || !scheduledFor) return;

  const confirmedPeriod = getPeriodFromDose(
    todayDoses.find((d) => doseKey(d) === `${medicationId}:${scheduledFor}`) || {
      scheduled_for: scheduledFor,
    }
  );

  confirmingId = `${medicationId}:${scheduledFor}`;
  renderDoses(todayDoses);

  try {
    await apiRequest(`/medications/${medicationId}/confirm`, {
      method: "POST",
      body: JSON.stringify({ scheduled_for: scheduledFor }),
    });
    showPatientMessage("Great job — marked as taken.", "success");

    const session = requireSession();
    if (!session) return;

    confirmingId = null;
    await loadTodayDoses(session.user.id);

    const afterGrouped = groupDosesByPeriod(todayDoses);
    let nextPeriod = null;

    if (confirmedPeriod === "morning" && isPeriodComplete(afterGrouped.morning)) {
      if (afterGrouped.afternoon.some((d) => d.status === "pending")) {
        nextPeriod = "afternoon";
      } else if (afterGrouped.night.some((d) => d.status === "pending")) {
        nextPeriod = "night";
      }
    } else if (confirmedPeriod === "afternoon" && isPeriodComplete(afterGrouped.afternoon)) {
      if (afterGrouped.night.some((d) => d.status === "pending")) {
        nextPeriod = "night";
      }
    }

    if (!nextPeriod) {
      nextPeriod = getScrollTargetPeriod(afterGrouped);
    }

    window.requestAnimationFrame(() => {
      scrollToPeriod(nextPeriod, { smooth: true });
    });
  } catch (err) {
    showPatientMessage(err.message || "Could not save. Try again.", "error");
    confirmingId = null;
    renderDoses(todayDoses);
  }
}

function bindPeriodNav() {
  $("#period-nav")?.querySelectorAll(".period-nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      scrollToPeriod(btn.dataset.period, { smooth: true });
    });
  });
}

async function init() {
  const session = requireSession();
  if (!session) return;

  if (session.user?.role === "caregiver") {
    window.location.href = "dashboard.html";
    return;
  }

  bindLogout();
  bindPeriodNav();

  const firstName = (session.user.full_name || "there").split(" ")[0];
  $("#patient-greeting").textContent = `Hello, ${firstName}`;
  $("#patient-date").textContent = formatTodayDate();

  setPatientLoading(true);
  try {
    await loadTodayDoses(session.user.id, { scroll: true });
  } catch (err) {
    showPatientMessage(err.message || "Could not load medications.", "error");
  } finally {
    setPatientLoading(false);
  }
}

init();
