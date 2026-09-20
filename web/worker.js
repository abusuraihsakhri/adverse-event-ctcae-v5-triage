"use strict";

importScripts("https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.js");

let pyodide = null;

const initialize = async () => {
  pyodide = await loadPyodide({
    indexURL: "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/"
  });
  const response = await fetch("engine.py", { cache: "no-cache" });
  if (!response.ok) throw new Error(`Engine source could not be loaded (HTTP ${response.status}).`);
  const source = await response.text();
  pyodide.runPython(source);
  self.postMessage({ type: "ready" });
};

const ready = initialize().catch((error) => {
  self.postMessage({ type: "error", message: `Runtime initialization failed: ${error.message || error}` });
  throw error;
});

self.addEventListener("message", async (event) => {
  const message = event.data || {};
  if (message.type !== "analyze") return;

  try {
    await ready;
    pyodide.globals.set("payload_json", JSON.stringify(message.payload));
    const resultJson = pyodide.runPython(`
import json

_payload = json.loads(payload_json)
_event_data = _payload["event"]
_event = AdverseEventInput(
    term=_event_data["term"],
    lab_value=_event_data.get("lab_value"),
    baseline_value=_event_data.get("baseline_value"),
    symptoms=_event_data.get("symptoms", []),
    duration_days=_event_data.get("duration_days", 1),
    temperature_c=_event_data.get("temperature_c"),
    has_bleeding=bool(_event_data.get("has_bleeding", False)),
    is_immune_mediated=bool(_event_data.get("is_immune_mediated", False)),
)
_graded = CTCAETriageEngine.evaluate_single_event(_event)

_hys = None
if _payload.get("screen_hys"):
    _liver = _payload.get("liver") or {}
    _hys = DLTEvaluator.evaluate_hys_law(
        alt=_liver.get("alt"),
        ast=_liver.get("ast"),
        bilirubin=_liver.get("bilirubin"),
        alk_phos=_liver.get("alk_phos"),
    )

json.dumps({
    "event": asdict(_graded),
    "hys_law": asdict(_hys) if _hys is not None else None,
})
`);
    self.postMessage({ type: "result", data: JSON.parse(resultJson) });
  } catch (error) {
    self.postMessage({ type: "error", message: error.message || String(error) });
  } finally {
    if (pyodide) pyodide.globals.delete("payload_json");
  }
});
