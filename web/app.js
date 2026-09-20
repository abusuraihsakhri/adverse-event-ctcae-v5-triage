(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const form = $("eventForm");
  const analyzeButton = $("analyzeButton");
  const status = $("runtimeStatus");
  const formError = $("formError");
  const emptyState = $("emptyState");
  const resultContent = $("resultContent");
  const copyButton = $("copyButton");
  let runtimeReady = false;
  let lastResult = null;
  const smokeMode = new URLSearchParams(window.location.search).has("smoke");

  if (smokeMode) {
    document.documentElement.dataset.smoke = "running";
  }

  const optionalNumber = (id) => {
    const raw = $(id).value.trim();
    if (raw === "") return null;
    const value = Number(raw);
    if (!Number.isFinite(value)) throw new Error("A numeric field contains an invalid value.");
    return value;
  };

  const setTheme = (theme) => {
    document.documentElement.dataset.theme = theme;
    $("themeToggle").setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
    try { localStorage.setItem("ctcae-theme", theme); } catch (_) {}
  };

  try {
    const savedTheme = localStorage.getItem("ctcae-theme");
    if (savedTheme === "dark" || savedTheme === "light") setTheme(savedTheme);
  } catch (_) {}

  $("themeToggle").addEventListener("click", () => {
    setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  });

  $("term").addEventListener("change", () => {
    const custom = $("term").value === "Other";
    $("customTermField").classList.toggle("hidden", !custom);
    if (custom) $("customTerm").focus();
  });

  const showError = (message) => {
    formError.textContent = message;
    formError.classList.remove("hidden");
  };

  const clearError = () => {
    formError.textContent = "";
    formError.classList.add("hidden");
  };

  const setBusy = (busy) => {
    analyzeButton.disabled = busy || !runtimeReady;
    analyzeButton.querySelector("span").textContent = busy ? "Analyzing…" : "Analyze event";
  };

  const collectPayload = () => {
    clearError();
    const selectedTerm = $("term").value;
    const term = selectedTerm === "Other" ? $("customTerm").value.trim() : selectedTerm;
    if (!term) throw new Error("Adverse event term is required.");

    const duration = Number($("duration").value || "1");
    if (!Number.isInteger(duration) || duration < 1) throw new Error("Duration must be a whole number of at least 1 day.");

    const temperature = optionalNumber("temperature");
    if (temperature !== null && (temperature < 30 || temperature > 45)) {
      throw new Error("Temperature must be between 30 and 45 °C.");
    }

    const symptoms = $("symptoms").value.trim();
    const liver = {
      alt: optionalNumber("alt"),
      ast: optionalNumber("ast"),
      bilirubin: optionalNumber("bilirubin"),
      alk_phos: optionalNumber("alkPhos")
    };

    return {
      event: {
        term,
        lab_value: optionalNumber("labValue"),
        baseline_value: optionalNumber("baseline"),
        symptoms: symptoms ? [symptoms] : [],
        duration_days: duration,
        temperature_c: temperature,
        has_bleeding: $("bleeding").checked,
        is_immune_mediated: $("immuneMediated").checked
      },
      liver,
      screen_hys: Object.values(liver).some((value) => value !== null)
    };
  };

  const humanizeAction = (value) => (value || "—")
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());

  const renderResult = (data) => {
    lastResult = data;
    const event = data.event;
    $("resultTerm").textContent = event.term;
    $("gradeBadge").textContent = event.grade_name;
    $("gradeBadge").className = "badge" + (event.grade >= 3 ? " alert" : event.grade === 0 ? " neutral" : "");
    $("dltBadge").textContent = event.is_dlt ? "DLT rule triggered" : "No DLT rule";
    $("dltBadge").className = "badge " + (event.is_dlt ? "alert" : "neutral");
    $("actionText").textContent = humanizeAction(event.action_triage);
    $("rationaleText").textContent = event.rationale;
    $("managementText").textContent = event.management_guidance;

    const reasons = event.dlt_reasons || [];
    $("dltReasonsRow").classList.toggle("hidden", reasons.length === 0);
    $("dltReasonsText").textContent = reasons.join(" • ");

    const hys = data.hys_law;
    $("hysCard").classList.toggle("hidden", !hys);
    if (hys) {
      const incomplete = hys.rationale.toLowerCase().includes("missing");
      $("hysStatus").textContent = hys.meets_hys_law
        ? "Laboratory thresholds met — review required"
        : incomplete
          ? "Incomplete laboratory screen"
          : "Laboratory thresholds not met";
      $("hysRationale").textContent = hys.rationale;
    }

    emptyState.classList.add("hidden");
    resultContent.classList.remove("hidden");
    copyButton.disabled = false;

    if (smokeMode) {
      document.documentElement.dataset.smoke =
        event.term === "Neutropenia" && event.grade === 4 ? "pass" : "fail";
    }
  };

  const worker = new Worker("worker.js", { type: "module" });

  worker.addEventListener("message", (event) => {
    const message = event.data || {};
    if (message.type === "ready") {
      runtimeReady = true;
      status.classList.add("ready");
      status.classList.remove("error");
      status.lastChild.textContent = " Python ready";
      setBusy(false);
      if (smokeMode) {
        $("term").value = "Neutropenia";
        $("labValue").value = "450";
        $("duration").value = "6";
        form.requestSubmit();
      }
      return;
    }
    if (message.type === "result") {
      setBusy(false);
      renderResult(message.data);
      return;
    }
    if (message.type === "error") {
      setBusy(false);
      showError(message.message || "The analysis could not be completed.");
      if (smokeMode) document.documentElement.dataset.smoke = "fail";
    }
  });

  worker.addEventListener("error", () => {
    runtimeReady = false;
    status.classList.remove("ready");
    status.classList.add("error");
    status.lastChild.textContent = " Runtime unavailable";
    showError("Python runtime failed to start. Reload the page or try a current WebAssembly-capable browser.");
    if (smokeMode) document.documentElement.dataset.smoke = "fail";
    setBusy(false);
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!runtimeReady) return;
    try {
      setBusy(true);
      worker.postMessage({ type: "analyze", payload: collectPayload() });
    } catch (error) {
      setBusy(false);
      showError(error.message || String(error));
    }
  });

  $("resetButton").addEventListener("click", () => {
    form.reset();
    $("duration").value = "1";
    $("customTermField").classList.add("hidden");
    clearError();
    emptyState.classList.remove("hidden");
    resultContent.classList.add("hidden");
    copyButton.disabled = true;
    lastResult = null;
  });

  copyButton.addEventListener("click", async () => {
    if (!lastResult) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(lastResult, null, 2));
      copyButton.textContent = "Copied";
      window.setTimeout(() => { copyButton.textContent = "Copy JSON"; }, 1200);
    } catch (_) {
      showError("Clipboard access is unavailable in this browser.");
    }
  });
})();
