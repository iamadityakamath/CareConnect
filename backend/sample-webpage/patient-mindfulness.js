const BREATHING_CYCLES = 4;
const BREATH_IN_MS = 4000;
const BREATH_OUT_MS = 6000;

let breathingActive = false;
let breathingTimer = null;
let currentCycle = 0;
let isInhale = true;

function openBreathingOverlay() {
  const overlay = $("#breathing-overlay");
  if (!overlay) return;
  overlay.classList.remove("hidden");
  overlay.hidden = false;
  resetBreathingSession();
  $("#btn-begin-breathing")?.focus();
}

function closeBreathingOverlay() {
  stopBreathingSession();
  const overlay = $("#breathing-overlay");
  if (!overlay) return;
  overlay.classList.add("hidden");
  overlay.hidden = true;
  $("#btn-open-breathing")?.focus();
}

function resetBreathingSession() {
  stopBreathingSession(false);
  currentCycle = 0;
  isInhale = true;
  setBreathingPhase("Tap Begin when you're ready");
  setBreathingCounter("");
  setCircleState("idle");
  $("#breathing-subtitle").textContent = "Follow the circle. Breathe slowly and gently.";
  $("#btn-begin-breathing")?.classList.remove("hidden");
  $("#btn-stop-breathing")?.classList.add("hidden");
  $("#btn-done-breathing")?.classList.add("hidden");
}

function setBreathingPhase(text) {
  const el = $("#breathing-phase");
  if (el) el.textContent = text;
}

function setBreathingCounter(text) {
  const el = $("#breathing-counter");
  if (el) el.textContent = text;
}

function setCircleState(state) {
  const circle = $("#breathing-circle");
  if (!circle) return;
  circle.classList.remove("breathing-circle-inhale", "breathing-circle-exhale", "breathing-circle-idle");
  circle.classList.add(`breathing-circle-${state}`);
}

function stopBreathingSession(resetUi = true) {
  breathingActive = false;
  if (breathingTimer) {
    window.clearTimeout(breathingTimer);
    breathingTimer = null;
  }
  if (resetUi) {
    resetBreathingSession();
  }
}

function showSessionComplete() {
  breathingActive = false;
  setCircleState("idle");
  setBreathingPhase("Nice work. Take a moment to notice how you feel.");
  setBreathingCounter("Session complete");
  $("#breathing-subtitle").textContent = "You finished your calming break.";
  $("#btn-stop-breathing")?.classList.add("hidden");
  $("#btn-done-breathing")?.classList.remove("hidden");
}

function runBreathingStep() {
  if (!breathingActive) return;

  if (currentCycle >= BREATHING_CYCLES) {
    showSessionComplete();
    return;
  }

  const cycleNumber = currentCycle + 1;
  setBreathingCounter(`Breath ${cycleNumber} of ${BREATHING_CYCLES}`);

  if (isInhale) {
    setBreathingPhase("Breathe in…");
    setCircleState("inhale");
    breathingTimer = window.setTimeout(() => {
      isInhale = false;
      runBreathingStep();
    }, BREATH_IN_MS);
    return;
  }

  setBreathingPhase("Breathe out…");
  setCircleState("exhale");
  breathingTimer = window.setTimeout(() => {
    isInhale = true;
    currentCycle += 1;
    runBreathingStep();
  }, BREATH_OUT_MS);
}

function startBreathingSession() {
  if (breathingActive) return;
  breathingActive = true;
  currentCycle = 0;
  isInhale = true;

  $("#btn-begin-breathing")?.classList.add("hidden");
  $("#btn-stop-breathing")?.classList.remove("hidden");
  $("#btn-done-breathing")?.classList.add("hidden");
  $("#breathing-subtitle").textContent = "In through your nose, out through your mouth.";

  runBreathingStep();
}

function bindMindfulness() {
  $("#btn-open-breathing")?.addEventListener("click", openBreathingOverlay);
  $("#btn-close-breathing")?.addEventListener("click", closeBreathingOverlay);
  $("#btn-begin-breathing")?.addEventListener("click", startBreathingSession);
  $("#btn-stop-breathing")?.addEventListener("click", () => stopBreathingSession());
  $("#btn-done-breathing")?.addEventListener("click", closeBreathingOverlay);

  $("#breathing-overlay")?.addEventListener("click", (event) => {
    if (event.target.id === "breathing-overlay") {
      closeBreathingOverlay();
    }
  });

  document.addEventListener("keydown", (event) => {
    const overlay = $("#breathing-overlay");
    if (overlay?.hidden) return;
    if (event.key === "Escape") {
      closeBreathingOverlay();
    }
  });
}

bindMindfulness();
